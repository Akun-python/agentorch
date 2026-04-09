from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalQuery(BaseModel):
    query: str
    top_k: int = 5
    filters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    chunk: DocumentChunk
    score: float = 0.0
    source: str = "unknown"


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        raise NotImplementedError


class KnowledgeBase(ABC):
    @abstractmethod
    def get_retriever(self) -> BaseRetriever:
        raise NotImplementedError


class IngestionPipeline(ABC):
    @abstractmethod
    async def ingest(self, documents: list[Document]) -> None:
        raise NotImplementedError


class RAGContextBuilder:
    def build(self, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return ""
        lines = []
        for index, item in enumerate(chunks, start=1):
            lines.append(
                f"[{index}] score={item.score:.3f} doc={item.chunk.document_id} text={item.chunk.text}"
            )
        return "\n".join(lines)
