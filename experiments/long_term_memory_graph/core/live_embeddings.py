from __future__ import annotations

from agentorch.knowledge.base import EmbeddingProvider
from agentorch.models import create_model_adapter


class LiveOpenAIEmbeddingProvider(EmbeddingProvider):
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
        self.provider = provider
        self._adapter = create_model_adapter(
            {
                "provider": provider,
                "model": model,
                "api_key": api_key,
                "base_url": base_url,
                "embedding_model": self.embedding_model,
                "embedding_dimensions": embedding_dimensions,
            }
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._adapter.embed(
            texts,
            embedding_model=self.embedding_model,
            dimensions=self.embedding_dimensions,
        )


__all__ = ["LiveOpenAIEmbeddingProvider"]
