from __future__ import annotations

from agentorch.knowledge.base import EmbeddingProvider
from agentorch.models import create_model_adapter


class LiveOpenAIEmbeddingProvider(EmbeddingProvider):
    """真实 OpenAI-compatible embedding provider。"""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        embedding_model: str | None = None,
        embedding_dimensions: int | None = None,
        provider: str = "openai_http",
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.embedding_model = embedding_model or model
        self.embedding_dimensions = embedding_dimensions
        self.dimensions = embedding_dimensions or 1536
        self.provider = provider

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """调用 AgentTorch 模型适配器的 embedding 能力。"""

        if not texts:
            return []
        adapter = create_model_adapter(
            {
                "provider": self.provider,
                "model": self.model,
                "api_key": self.api_key,
                "base_url": self.base_url,
                "embedding_model": self.embedding_model,
                "embedding_dimensions": self.dimensions,
            }
        )
        try:
            return await adapter.embed(
                texts,
                embedding_model=self.embedding_model,
                dimensions=self.dimensions,
            )
        finally:
            close_fn = getattr(adapter, "aclose", None)
            if callable(close_fn):
                await close_fn()


__all__ = ["LiveOpenAIEmbeddingProvider"]
