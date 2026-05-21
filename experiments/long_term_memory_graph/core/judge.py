from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any

from agentorch import Agent, Runtime
from agentorch.config import ModelConfig
from agentorch.models import create_model_adapter

from .agentorch_runtime import ExperimentAnswerModel, estimate_tokens
from .env_config import build_live_model_config
from .schemas import AgentAnswer, ExperimentCase, JudgeResult, RetrievalResult

JUDGE_PROMPT = """\
你是长期记忆问答实验的评分器。请根据标准答案、模型答案、目标胶囊命中、目标关系命中、陈旧节点注入和冲突节点注入进行评分。

评分规则：
1. 答案必须覆盖标准答案中的核心事实。
2. 目标胶囊未命中时，原则上不能给满分。
3. 多跳、时序或开放问题需要目标关系或等价证据链。
4. 返回陈旧节点或冲突失败节点并影响答案时，应判为失败。
5. 如果答案明确表示无法可靠回答，请标记 refusal=true。
6. 只输出一个 JSON 对象，字段为 score、reason、capsule_hit、relation_hit、pollution、refusal。
7. score 只能是 0 或 1。
"""


class ExperimentJudgeRunner:
    """实验裁判运行器，支持确定性裁判和真实模型裁判。"""

    def __init__(
        self,
        *,
        judge_backend: str,
        judge_model_backend: str | None,
        judge_model_name: str | None,
        env_file: str | None,
        load_env: bool,
        overwrite_env: bool,
    ) -> None:
        self.judge_backend = judge_backend
        self.model_backend = judge_model_backend
        self.model_name = judge_model_name
        self.env_report = None
        self._model_config: ModelConfig | None = None
        if judge_backend != "model_judge":
            return
        if not judge_model_backend:
            raise ValueError("model_judge requires judge_model_backend.")
        model_config, env_report = build_live_model_config(
            model_backend=judge_model_backend,
            model_name=judge_model_name,
            env_file=env_file,
            load_env=load_env,
            role_prefix="JUDGE",
            overwrite_env=overwrite_env,
        )
        self.env_report = env_report
        self._model_config = model_config
        self.model_name = model_config.model

    def _make_agent(self) -> Agent:
        """构造裁判模型使用的 AgentTorch Agent。"""

        if self._model_config is None:
            raise ValueError("model_judge requires a resolved judge model config.")
        runtime = Runtime.create(model=create_model_adapter(self._model_config), skills=[])
        return Agent(runtime=runtime)

    def evaluate(
        self,
        *,
        case: ExperimentCase,
        retrieval: RetrievalResult,
        answer: AgentAnswer,
    ) -> JudgeResult:
        """按配置选择模型裁判或确定性裁判。"""

        if self.judge_backend == "model_judge":
            return self._evaluate_with_model(case=case, retrieval=retrieval, answer=answer)
        return _deterministic_judge(case=case, retrieval=retrieval, answer=answer, judge_backend=self.judge_backend)

    def _evaluate_with_model(
        self,
        *,
        case: ExperimentCase,
        retrieval: RetrievalResult,
        answer: AgentAnswer,
    ) -> JudgeResult:
        """调用真实裁判模型，并把 token/耗时写入原始输出。"""

        payload = {
            "query": case.query,
            "question_type": case.question_type,
            "standard_answer": case.standard_answer,
            "model_answer": answer.answer,
            "target_capsule_ids": list(case.target_capsule_ids),
            "target_relation_types": list(case.target_relation_types),
            "returned_capsule_ids": retrieval.returned_capsule_ids,
            "returned_relation_types": retrieval.returned_relation_types,
            "stale_capsule_ids": list(case.stale_capsule_ids),
            "conflict_loser_ids": list(case.conflict_loser_ids),
            "suppressed_stale_nodes": retrieval.suppressed_stale_nodes,
            "suppressed_conflict_nodes": retrieval.suppressed_conflict_nodes,
        }
        prompt = JUDGE_PROMPT + "\n\nJUDGE_PAYLOAD_JSON=" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        start = perf_counter()
        result = self._make_agent().run_sync(
            prompt,
            thread_id=f"judge-{case.case_id}-{retrieval.method}",
            metadata={"suite": "long_term_memory_graph", "role": "judge", "case_id": case.case_id},
        )
        duration_ms = (perf_counter() - start) * 1000
        raw = _parse_judge_json(result.output_text)
        score = 1.0 if float(raw.get("score", 0.0)) >= 0.5 else 0.0
        raw["judge_backend"] = self.judge_backend
        raw["judge_model_backend"] = self.model_backend
        raw["judge_model_name"] = self.model_name
        raw["judge_output_text"] = result.output_text
        raw["judge_token_estimate"] = estimate_tokens(result.output_text)
        raw["judge_prompt_tokens"] = result.usage.prompt_tokens
        raw["judge_completion_tokens"] = result.usage.completion_tokens
        raw["judge_total_tokens"] = result.usage.total_tokens
        raw["judge_duration_ms"] = duration_ms
        return JudgeResult(
            score=score,
            raw_output=raw,
            model_backend=self.model_backend,
            model_name=self.model_name,
            duration_ms=duration_ms,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
        )


def judge_answer(
    *,
    case: ExperimentCase,
    retrieval: RetrievalResult,
    answer: AgentAnswer,
    judge_backend: str,
    judge_runner: ExperimentJudgeRunner | None = None,
) -> JudgeResult:
    """统一裁判入口，供 pipeline 调用。"""

    if judge_backend == "model_judge":
        if judge_runner is None:
            raise ValueError("model_judge requires a configured judge_runner.")
        return judge_runner.evaluate(case=case, retrieval=retrieval, answer=answer)
    return _deterministic_judge(case=case, retrieval=retrieval, answer=answer, judge_backend=judge_backend)


def _deterministic_judge(
    *,
    case: ExperimentCase,
    retrieval: RetrievalResult,
    answer: AgentAnswer,
    judge_backend: str,
) -> JudgeResult:
    """确定性评分器：用于 smoke test 和字段验证，不替代正式人工/模型评测。"""

    returned_capsules = set(retrieval.returned_capsule_ids)
    returned_relations = set(retrieval.returned_relation_types)
    target_capsules = set(case.target_capsule_ids)
    target_relations = set(case.target_relation_types)
    capsule_hit = bool(target_capsules) and target_capsules.issubset(returned_capsules)
    relation_hit = not target_relations or bool(target_relations.intersection(returned_relations))
    pollution = bool(returned_capsules.intersection(set(case.stale_capsule_ids) | set(case.conflict_loser_ids)))
    answer_text = answer.answer.lower()
    standard_tokens = [token for token in case.standard_answer.lower().replace(";", " ").replace(",", " ").split() if len(token) > 2]
    overlap = sum(1 for token in standard_tokens if token in answer_text)
    lexical_ok = overlap >= max(1, min(5, len(standard_tokens) // 3))
    score = 1.0 if capsule_hit and relation_hit and lexical_ok and not pollution else 0.0
    raw = {
        "judge_backend": judge_backend,
        "score": score,
        "reason": "deterministic rubric over target capsule, relation, answer overlap and pollution controls",
        "capsule_hit": capsule_hit,
        "relation_hit": relation_hit,
        "pollution": pollution,
        "refusal": "不能可靠回答" in answer.answer,
        "answer_token_estimate": estimate_tokens(answer.answer),
    }
    return JudgeResult(score=score, raw_output=raw, model_backend=None, model_name=None)


def _parse_judge_json(text: str) -> dict[str, Any]:
    """从裁判输出中尽量解析 JSON，失败时返回零分结构。"""

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {
        "score": 0,
        "reason": "judge_output_parse_failed",
        "capsule_hit": False,
        "relation_hit": False,
        "pollution": False,
        "refusal": False,
    }


def serialize_judge_raw(result: JudgeResult) -> str:
    """把裁判原始信息稳定序列化进 CSV/JSONL。"""

    return json.dumps(result.raw_output, ensure_ascii=False, sort_keys=True)
