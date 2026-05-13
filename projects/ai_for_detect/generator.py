from __future__ import annotations

from dataclasses import dataclass
import json
import re
from time import perf_counter
from typing import Protocol

import agentorch
from agentorch._facade_support import BackgroundRuntimeBridge

from .config import resolve_model_name, resolve_model_names
from .metrics import RewriteMetrics, RewriteResult
from .prompts import SYSTEM_PROMPT, build_rewrite_prompt

_GENERATOR_BACKGROUND_BRIDGE = BackgroundRuntimeBridge()


class SentenceGenerator(Protocol):
    model_name: str
    model_names: list[str]

    def rewrite_text(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int = 0) -> str:
        ...

    def rewrite_record(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int = 0) -> RewriteResult:
        ...

    def close(self) -> None:
        ...


def normalize_generated_text(text: str) -> str:
    cleaned = (text or "").strip()
    pairs = {
        '"': '"',
        "'": "'",
        "“": "”",
        "‘": "’",
    }
    if len(cleaned) >= 2 and cleaned[0] in pairs and cleaned[-1] == pairs[cleaned[0]]:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def extract_ai_text(payload: str) -> str:
    cleaned = (payload or "").strip()
    if not cleaned:
        raise ValueError("模型返回空文本。")

    for candidate in _candidate_payloads(cleaned):
        text = _extract_from_json_like(candidate)
        if text:
            return normalize_generated_text(text)
        text = _extract_plain_sentence(candidate)
        if text:
            return normalize_generated_text(text)

    raise ValueError(f"无法从模型输出中提取有效改写文本：{cleaned[:200]}")


def _candidate_payloads(text: str) -> list[str]:
    candidates: list[str] = [text]
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        inner = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
        inner = re.sub(r"\s*```$", "", inner).strip()
        if inner:
            candidates.append(inner)
    return candidates


def _extract_from_json_like(text: str) -> str | None:
    for candidate in _json_variants(text):
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            for key in ("ai_text", "text", "content", "rewritten_text", "rewrite", "value"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    for pattern in (
        r'"ai_text"\s*:\s*"(?P<value>(?:[^"\\]|\\.)*)"',
        r'"text"\s*:\s*"(?P<value>(?:[^"\\]|\\.)*)"',
        r'"value"\s*:\s*"(?P<value>(?:[^"\\]|\\.)*)"',
    ):
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            raw_value = match.group("value")
            try:
                return json.loads(f'"{raw_value}"').strip()
            except Exception:
                return raw_value.strip()
    return None


def _json_variants(text: str) -> list[str]:
    variants = [text]
    if '""' in text:
        variants.append(text.replace('""', '"'))
    return variants


def _extract_plain_sentence(text: str) -> str | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    if cleaned.startswith("<") and ">" in cleaned:
        without_tags = re.sub(r"<[^>]+>", " ", cleaned).strip()
        if not without_tags:
            return None
        cleaned = without_tags
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return None
    if cleaned.lower().startswith("json"):
        return None
    return cleaned


class AgentTorchSentenceGenerator:
    """基于 AgentTorch 的单句改写器。"""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 256,
        min_request_interval: float = 0.0,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.model_name = resolve_model_name(model_name)
        self.model_names = [self.model_name]
        self._agent = agentorch.create_agent(
            model={
                "provider": "openai",
                "model": self.model_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "min_request_interval": min_request_interval,
                "timeout": timeout,
                "max_retries": max_retries,
            },
            name="ai-for-detect-rewriter",
            system_prompt=SYSTEM_PROMPT,
            enable_tools=False,
            enable_rag=False,
            enable_memory=False,
            enable_streaming=True,
        )

    def rewrite_text(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int = 0) -> str:
        return self.rewrite_record(
            source_text=source_text,
            domain_label=domain_label,
            thread_id=thread_id,
            row_index=row_index,
        ).text

    def rewrite_record(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int = 0) -> RewriteResult:
        prompt = build_rewrite_prompt(source_text=source_text, domain_label=domain_label)
        return _GENERATOR_BACKGROUND_BRIDGE.run(
            self._rewrite_record_async(prompt=prompt, thread_id=thread_id)
        )

    async def _rewrite_record_async(self, *, prompt: str, thread_id: str) -> RewriteResult:
        start_time = perf_counter()
        first_token_latency_seconds: float | None = None
        final_result = None

        try:
            async for event in self._agent.run(prompt, thread_id=thread_id, stream=True):
                if event.event_type == "model_delta" and first_token_latency_seconds is None and event.delta_text:
                    first_token_latency_seconds = perf_counter() - start_time
                if event.event_type == "final_result":
                    final_result = event.result
        except Exception:
            return await self._rewrite_record_async_fallback(prompt=prompt, thread_id=thread_id, start_time=start_time)

        if final_result is None:
            raise RuntimeError("流式生成未返回 final_result，无法完成统计。")

        extracted_text = extract_ai_text(final_result.output_text)
        total_latency_seconds = perf_counter() - start_time
        metrics = RewriteMetrics(
            prompt_tokens=int(final_result.usage.prompt_tokens or 0),
            completion_tokens=int(final_result.usage.completion_tokens or 0),
            total_tokens=int(final_result.usage.total_tokens or 0),
            first_token_latency_seconds=first_token_latency_seconds or total_latency_seconds,
            total_latency_seconds=total_latency_seconds,
            finish_reason=final_result.finish_reason or "",
        )
        return RewriteResult(
            text=extracted_text,
            model_name=self.model_name,
            metrics=metrics,
        )

    async def _rewrite_record_async_fallback(self, *, prompt: str, thread_id: str, start_time: float) -> RewriteResult:
        run_result = await self._agent.run(prompt, thread_id=thread_id, stream=False)
        extracted_text = extract_ai_text(run_result.output_text)
        total_latency_seconds = perf_counter() - start_time
        metrics = RewriteMetrics(
            prompt_tokens=int(run_result.usage.prompt_tokens or 0),
            completion_tokens=int(run_result.usage.completion_tokens or 0),
            total_tokens=int(run_result.usage.total_tokens or 0),
            first_token_latency_seconds=total_latency_seconds,
            total_latency_seconds=total_latency_seconds,
            finish_reason=run_result.finish_reason or "",
        )
        return RewriteResult(
            text=extracted_text,
            model_name=self.model_name,
            metrics=metrics,
        )

    def close(self) -> None:
        _GENERATOR_BACKGROUND_BRIDGE.run(self._agent.aclose())


@dataclass(slots=True)
class ModelSelection:
    model_name: str
    slot_index: int


class MultiModelSentenceGenerator:
    """在多个模型之间按行轮转分配请求。"""

    def __init__(
        self,
        *,
        model_names: str | list[str] | None = None,
        temperature: float = 0.8,
        max_tokens: int = 256,
        min_request_interval: float = 0.0,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.model_names = resolve_model_names(model_names)
        self.model_name = ",".join(self.model_names)
        self._generators = {
            name: AgentTorchSentenceGenerator(
                model_name=name,
                temperature=temperature,
                max_tokens=max_tokens,
                min_request_interval=min_request_interval,
                timeout=timeout,
                max_retries=max_retries,
            )
            for name in self.model_names
        }

    def select_model(self, *, row_index: int) -> ModelSelection:
        slot_index = row_index % len(self.model_names)
        return ModelSelection(
            model_name=self.model_names[slot_index],
            slot_index=slot_index,
        )

    def resolve_model_for_row(self, *, row_index: int) -> str:
        return self.select_model(row_index=row_index).model_name

    def rewrite_text(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int = 0) -> str:
        return self.rewrite_record(
            source_text=source_text,
            domain_label=domain_label,
            thread_id=thread_id,
            row_index=row_index,
        ).text

    def rewrite_record(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int = 0) -> RewriteResult:
        model_name = self.resolve_model_for_row(row_index=row_index)
        generator = self._generators[model_name]
        result = generator.rewrite_record(
            source_text=source_text,
            domain_label=domain_label,
            thread_id=thread_id,
            row_index=row_index,
        )
        result.model_name = model_name
        return result

    def close(self) -> None:
        for generator in self._generators.values():
            generator.close()
