from __future__ import annotations

from dataclasses import dataclass
import asyncio
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, Field

import agentorch

from .config import resolve_model_name, resolve_model_names
from .metrics import RewriteMetrics, RewriteResult
from .prompts import SYSTEM_PROMPT, build_rewrite_prompt


class SentenceGenerator(Protocol):
    model_name: str
    model_names: list[str]

    def rewrite_text(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int = 0) -> str:
        ...

    def rewrite_record(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int = 0) -> RewriteResult:
        ...

    def close(self) -> None:
        ...


class GeneratedSentencePayload(BaseModel):
    ai_text: str = Field(description="保持原意、但表达更像 AI 生成的中文单句。")


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
        self._parser = agentorch.PydanticParser(GeneratedSentencePayload)
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
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._rewrite_record_async(prompt=prompt, thread_id=thread_id))
        raise RuntimeError(
            "rewrite_record() 不能在运行中的事件循环里直接调用。"
            "若在 notebook/async 场景使用，请补一个 async 入口。"
        )

    async def _rewrite_record_async(self, *, prompt: str, thread_id: str) -> RewriteResult:
        start_time = perf_counter()
        formatted_prompt = self._parser.with_prompt(prompt)
        first_token_latency_seconds: float | None = None
        final_result = None

        try:
            async for event in self._agent.run(formatted_prompt, thread_id=thread_id, stream=True):
                if event.event_type == "model_delta" and first_token_latency_seconds is None and event.delta_text:
                    first_token_latency_seconds = perf_counter() - start_time
                if event.event_type == "final_result":
                    final_result = event.result
        except Exception:
            return await self._rewrite_record_async_fallback(prompt=formatted_prompt, thread_id=thread_id, start_time=start_time)

        if final_result is None:
            raise RuntimeError("流式生成未返回 final_result，无法完成统计。")

        parsed = await self._parser.parse(final_result.output_text)
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
            text=normalize_generated_text(parsed.ai_text),
            model_name=self.model_name,
            metrics=metrics,
        )

    async def _rewrite_record_async_fallback(self, *, prompt: str, thread_id: str, start_time: float) -> RewriteResult:
        run_result = await self._agent.run(prompt, thread_id=thread_id, stream=False)
        parsed = await self._parser.parse(run_result.output_text)
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
            text=normalize_generated_text(parsed.ai_text),
            model_name=self.model_name,
            metrics=metrics,
        )

    def close(self) -> None:
        self._agent.close()


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
