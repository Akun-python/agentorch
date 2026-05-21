from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from agentorch.core import Message, ModelRequest
from agentorch.models import create_model_adapter
from agentorch.parsing import JSONParser, ParseError

from .agentorch_runtime import estimate_tokens
from .env_config import build_live_model_config


STRUCTURED_MEMORY_PROMPT = """\
你是长期记忆胶囊的结构化抽取器。请只基于给定会话内容抽取可进入候选记忆的结构化字段。

要求：
1. 不要使用问题标准答案、目标胶囊标签或外部知识。
2. summary 用一句话概括该会话中最值得保留的事实或偏好。
3. entities 只保留会话中明确出现的人、地点、项目、产品、组织、任务或主题。
4. claims 用 slot/value/scope 表示稳定事实、偏好、计划、时间事件或更新后的状态。
5. 每个 claim 必须能被 evidence_text 直接支持；没有证据就不要编造 claim。
6. 如果信息不足，claims 可以为空，但仍需输出 JSON 对象。

只输出 JSON 对象，字段为：
{
  "summary": "string",
  "entities": ["string"],
  "claims": [
    {
      "slot": "string",
      "value": "string",
      "scope": "string",
      "polarity": "positive",
      "evidence_text": "string",
      "confidence": 0.0
    }
  ],
  "confidence": 0.0
}
"""


@dataclass(frozen=True)
class StructuredExtractionMetrics:
    """记录 LLM 抽取成本，便于后续写入实验日志。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0.0
    output_token_estimate: int = 0


@dataclass(frozen=True)
class StructuredMemoryExtraction:
    """LLM 抽取后的候选结构。"""

    summary: str
    entities: list[str]
    claims: list[dict[str, Any]]
    confidence: float
    metrics: StructuredExtractionMetrics
    raw_output: str = ""
    parse_error: str = ""


class LLMStructuredMemoryExtractor:
    """把原始会话整理为胶囊候选结构，准入决策仍由 promotion 规则完成。"""

    def __init__(
        self,
        *,
        model_backend: str,
        model_name: str | None,
        env_file: str | None,
        load_env: bool = True,
        overwrite_env: bool = False,
        max_tokens: int = 768,
    ) -> None:
        self.model_backend = model_backend
        self.model_name = model_name
        self.max_tokens = max_tokens
        self._model_config, self.env_report = build_live_model_config(
            model_backend=model_backend,
            model_name=model_name,
            env_file=env_file,
            load_env=load_env,
            overwrite_env=overwrite_env,
        )
        self.model_name = self._model_config.model
        self._parser = JSONParser()

    def extract(
        self,
        *,
        session_text: str,
        session_id: str,
        question_type: str,
        created_at: str,
    ) -> StructuredMemoryExtraction:
        """调用轻量模型抽取 summary/entities/claims，并返回 token 与耗时。"""

        payload = {
            "session_id": session_id,
            "question_type": question_type,
            "created_at": created_at,
            "session_text": session_text,
        }
        prompt = STRUCTURED_MEMORY_PROMPT + "\n\nSESSION_JSON=" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        request = ModelRequest(
            messages=[
                Message(role="system", content="你只输出可解析 JSON，不添加 Markdown。"),
                Message(role="user", content=prompt),
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=self.max_tokens,
        )
        start = perf_counter()
        adapter = create_model_adapter(self._model_config)
        try:
            response = _run_model(adapter, request)
        finally:
            _close_model_adapter(adapter)
        duration_ms = (perf_counter() - start) * 1000
        metrics = StructuredExtractionMetrics(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            duration_ms=duration_ms,
            output_token_estimate=estimate_tokens(response.content),
        )
        return self._parse_response(response.content, metrics=metrics)

    def _parse_response(self, text: str, *, metrics: StructuredExtractionMetrics) -> StructuredMemoryExtraction:
        """解析模型 JSON；失败时返回空结构并记录错误。"""

        try:
            parsed = self._parser.parse_sync(text)
        except (ParseError, RuntimeError) as exc:
            return StructuredMemoryExtraction(
                summary="",
                entities=[],
                claims=[],
                confidence=0.0,
                metrics=metrics,
                raw_output=text,
                parse_error=str(exc),
            )
        if not isinstance(parsed, dict):
            return StructuredMemoryExtraction(
                summary="",
                entities=[],
                claims=[],
                confidence=0.0,
                metrics=metrics,
                raw_output=text,
                parse_error="structured_output_not_object",
            )
        return StructuredMemoryExtraction(
            summary=_clean_text(parsed.get("summary")),
            entities=_clean_list(parsed.get("entities")),
            claims=_clean_claims(parsed.get("claims")),
            confidence=_clamp_float(parsed.get("confidence"), default=0.7),
            metrics=metrics,
            raw_output=text,
        )


def _run_model(adapter, request: ModelRequest):
    """同步运行异步模型接口，保持转换脚本调用简单。"""

    from ..domain.utils import run_async

    return run_async(adapter.generate(request))


def _close_model_adapter(adapter) -> None:
    """优先关闭真实后端的异步 HTTP 客户端。"""

    from ..domain.utils import run_async

    async_close = getattr(adapter, "aclose", None)
    if callable(async_close):
        run_async(async_close())
        return
    close_fn = getattr(adapter, "close", None)
    if callable(close_fn):
        close_fn()


def _clean_text(value: Any) -> str:
    """清理模型返回的单个文本字段。"""

    if value is None:
        return ""
    return " ".join(str(value).split())


def _clean_list(value: Any, *, limit: int = 12) -> list[str]:
    """清理模型返回的字符串列表。"""

    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_text(item).lower()
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _clean_claims(value: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    """只保留有证据和 slot/value 的 claim，避免把猜测写入胶囊。"""

    if not isinstance(value, list):
        return []
    claims: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        slot = _clean_text(item.get("slot")).lower()
        claim_value = _clean_text(item.get("value")).lower()
        scope = _clean_text(item.get("scope")).lower()
        evidence_text = _clean_text(item.get("evidence_text"))
        if not slot or not claim_value or not evidence_text:
            continue
        claims.append(
            {
                "slot": slot,
                "value": claim_value,
                "scope": scope,
                "polarity": _clean_text(item.get("polarity") or "positive").lower() or "positive",
                "evidence_ids": [evidence_text],
                "confidence": _clamp_float(item.get("confidence"), default=0.7),
            }
        )
        if len(claims) >= limit:
            break
    return claims


def _clamp_float(value: Any, *, default: float) -> float:
    """把模型返回的数值压到 0-1。"""

    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


__all__ = [
    "LLMStructuredMemoryExtractor",
    "STRUCTURED_MEMORY_PROMPT",
    "StructuredExtractionMetrics",
    "StructuredMemoryExtraction",
]
