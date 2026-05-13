from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

import agentorch

from .config import resolve_model_name
from .prompts import SYSTEM_PROMPT, build_rewrite_prompt


class SentenceGenerator(Protocol):
    model_name: str

    def rewrite_text(self, *, source_text: str, domain_label: str | None, thread_id: str) -> str:
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
        )

    def rewrite_text(self, *, source_text: str, domain_label: str | None, thread_id: str) -> str:
        prompt = build_rewrite_prompt(source_text=source_text, domain_label=domain_label)
        result = self._agent.run_parsed_sync(
            prompt,
            parser=self._parser,
            thread_id=thread_id,
        )
        return normalize_generated_text(result.parsed.ai_text)

    def close(self) -> None:
        self._agent.close()
