"""Knowledge retrieval abstractions and a minimal local implementation.

This package separates external knowledge access from runtime memory so RAG
capabilities can evolve independently from thread state management.
"""

from .base import (
    BaseRetriever,
    Document,
    DocumentChunk,
    IngestionPipeline,
    KnowledgeBase,
    RAGContextBuilder,
    RetrievalQuery,
    RetrievedChunk,
)
from .in_memory import InMemoryKnowledgeBase, KeywordRetriever

__all__ = [
    "BaseRetriever",
    "Document",
    "DocumentChunk",
    "InMemoryKnowledgeBase",
    "IngestionPipeline",
    "KeywordRetriever",
    "KnowledgeBase",
    "RAGContextBuilder",
    "RetrievalQuery",
    "RetrievedChunk",
]
