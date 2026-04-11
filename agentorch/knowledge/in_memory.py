from __future__ import annotations

import re
from collections import Counter

from .factory import create_retriever
from .base import BaseRetriever, Document, DocumentChunk, IngestionPipeline, KnowledgeBase, RetrievalQuery, RetrievedChunk


class KeywordRetriever(BaseRetriever):
    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks

    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        allowed_scopes = set(query.scopes)
        terms = [term for term in re.findall(r"\w+", query.query.lower()) if term]
        results: list[RetrievedChunk] = []
        for chunk in self.chunks:
            chunk_scopes = set(chunk.metadata.get("scopes", []))
            if allowed_scopes and chunk_scopes and not chunk_scopes.intersection(allowed_scopes):
                continue
            text = chunk.text.lower()
            counts = Counter(term for term in terms if term in text)
            if not counts:
                continue
            score = float(sum(counts.values()))
            results.append(RetrievedChunk(chunk=chunk, score=score, source="keyword"))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[: query.top_k]


class InMemoryKnowledgeBase(KnowledgeBase, IngestionPipeline):
    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}
        self.chunks: list[DocumentChunk] = []

    async def ingest(self, documents: list[Document]) -> None:
        for document in documents:
            self.documents[document.id] = document
            self.chunks.append(
                DocumentChunk(
                    id=f"{document.id}-chunk-1",
                    document_id=document.id,
                    text=document.text,
                    metadata=document.metadata,
                )
            )

    def get_retriever(self) -> BaseRetriever:
        return create_retriever("keyword", chunks=self.chunks)
