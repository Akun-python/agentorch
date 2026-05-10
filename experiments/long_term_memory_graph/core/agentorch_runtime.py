from __future__ import annotations

import json
from typing import Any

from agentorch import Agent, Runtime
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models import create_model_adapter
from agentorch.models.base import BaseModelAdapter

from .env_config import EnvLoadReport, build_live_model_config, is_probe_backend
from .schemas import AgentAnswer, ExperimentCase, RetrievalResult


def estimate_tokens(text: str) -> int:
    ascii_words = len([item for item in text.replace("\n", " ").split(" ") if item])
    cjk_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return max(1, ascii_words + cjk_chars // 2)


class ExperimentAnswerModel(BaseModelAdapter):
    """AgentTorch 离线回答模型：只用于实验管线 smoke test，不充当正式论文结果。"""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        prompt = "\n".join(message.content for message in request.messages if message.content)
        payload = _extract_payload(prompt)
        answer = _build_probe_answer(payload)
        prompt_tokens = estimate_tokens(prompt)
        completion_tokens = estimate_tokens(answer)
        return ModelResponse(
            message=Message(role="assistant", content=answer),
            content=answer,
            finish_reason="stop",
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            raw={"backend": "agentorch_probe"},
        )


def _extract_payload(prompt: str) -> dict[str, Any]:
    marker = "EXPERIMENT_PAYLOAD_JSON="
    if marker not in prompt:
        return {}
    text = prompt.split(marker, 1)[1].strip()
    start = text.find("{")
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        for offset, char in enumerate(text[start:], start=start):
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    text = text[start : offset + 1]
                    break
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _build_probe_answer(payload: dict[str, Any]) -> str:
    method = str(payload.get("method", ""))
    standard_answer = str(payload.get("standard_answer", ""))
    target_capsules = set(payload.get("target_capsule_ids", []))
    returned_capsules = set(payload.get("returned_capsule_ids", []))
    target_relations = set(payload.get("target_relation_types", []))
    returned_relations = set(payload.get("returned_relation_types", []))
    stale_ids = set(payload.get("stale_capsule_ids", []))
    conflict_losers = set(payload.get("conflict_loser_ids", []))

    if method == "no_long_term_memory":
        return "无法从长期记忆中确认答案。"

    capsule_ok = bool(target_capsules) and target_capsules.issubset(returned_capsules)
    relation_ok = not target_relations or bool(target_relations.intersection(returned_relations))
    polluted = bool(returned_capsules.intersection(stale_ids | conflict_losers))
    if capsule_ok and relation_ok and not polluted:
        return f"依据长期记忆子图：{standard_answer}"
    if capsule_ok and not polluted:
        return f"依据部分长期记忆：{standard_answer}"
    if returned_capsules:
        return "召回到相关长期记忆，但证据链不完整，不能可靠回答。"
    return "没有召回可用长期记忆，不能可靠回答。"


class AgentTorchExperimentRunner:
    def __init__(
        self,
        *,
        model_backend: str = "agentorch_probe",
        model_name: str | None = None,
        env_file: str | None = None,
        load_env: bool = True,
        overwrite_env: bool = False,
    ) -> None:
        self.model_backend = model_backend
        self.env_report: EnvLoadReport | None = None
        self._probe_model: BaseModelAdapter | None = None
        self._live_model_config = None
        if is_probe_backend(model_backend):
            self._probe_model = ExperimentAnswerModel()
        else:
            model_config, env_report = build_live_model_config(
                model_backend=model_backend,
                model_name=model_name,
                env_file=env_file,
                load_env=load_env,
                overwrite_env=overwrite_env,
            )
            self.env_report = env_report
            self._live_model_config = model_config

    def _make_agent(self) -> Agent:
        # 真实后端每次请求都重建一次运行时，避免异步 HTTP 客户端跨事件循环复用。
        if self._live_model_config is not None:
            model = create_model_adapter(self._live_model_config)
        else:
            model = self._probe_model or ExperimentAnswerModel()
        runtime = Runtime.create(model=model, skills=[])
        return Agent(runtime=runtime)

    def answer(
        self,
        *,
        case: ExperimentCase,
        retrieval: RetrievalResult,
        run_round: int,
    ) -> AgentAnswer:
        thread_id = f"ltmg-{case.case_id}-{retrieval.method}-{retrieval.variant}-r{run_round}"
        payload = {
            "case_id": case.case_id,
            "question_type": case.question_type,
            "query": case.query,
            "standard_answer": case.standard_answer,
            "method": retrieval.method,
            "variant": retrieval.variant,
            "target_capsule_ids": list(case.target_capsule_ids),
            "target_relation_types": list(case.target_relation_types),
            "stale_capsule_ids": list(case.stale_capsule_ids),
            "conflict_loser_ids": list(case.conflict_loser_ids),
            "returned_capsule_ids": retrieval.returned_capsule_ids,
            "returned_relation_types": retrieval.returned_relation_types,
            "suppressed_stale_nodes": retrieval.suppressed_stale_nodes,
            "suppressed_conflict_nodes": retrieval.suppressed_conflict_nodes,
        }
        prompt = (
            "你是长期记忆问答实验中的 AgentTorch 被试智能体。"
            "只能依据给定的长期记忆召回结果回答；证据不足时必须说明不能可靠回答。\n"
            f"查询：{case.query}\n"
            f"召回摘要：{retrieval.prompt_summary}\n"
            "EXPERIMENT_PAYLOAD_JSON="
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        )
        result = self._make_agent().run_sync(
            prompt,
            thread_id=thread_id,
            metadata={"suite": "long_term_memory_graph", "case_id": case.case_id},
        )
        return AgentAnswer(
            answer=result.output_text,
            input_tokens=result.usage.prompt_tokens,
            output_tokens=result.usage.completion_tokens,
            agentorch_run_id=result.run_id,
            thread_id=result.thread_id,
            finish_reason=result.finish_reason,
        )
