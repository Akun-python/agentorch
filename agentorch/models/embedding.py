from __future__ import annotations

from abc import ABC, abstractmethod

from .base import BaseModelAdapter


class EmbeddingCapableModelAdapter(BaseModelAdapter, ABC):
    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        *,
        embedding_model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        raise NotImplementedError

    async def embed_text(
        self,
        text: str,
        *,
        embedding_model: str | None = None,
        dimensions: int | None = None,
    ) -> list[float]:
        vectors = await self.embed([text], embedding_model=embedding_model, dimensions=dimensions)
        if not vectors:
            raise RuntimeError("Embedding response was empty.")
        return vectors[0]
