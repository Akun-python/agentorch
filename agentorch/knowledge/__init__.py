"""Knowledge retrieval abstractions and a minimal local implementation.

This package separates external knowledge access from runtime memory so RAG
capabilities can evolve independently from thread state management.
"""

from .base import (
    BaseRetriever,
    Citation,
    ClassicRagConfig,
    ChunkingStrategy,
    DeliberativeRagConfig,
    Document,
    DocumentChunk,
    DocumentSection,
    EmbeddingProvider,
    HybridRagConfig,
    IngestionPipeline,
    IngestionJob,
    KnowledgeBase,
    KnowledgeAsset,
    KnowledgeRoute,
    KnowledgeScope,
    ParsedDocument,
    ParsedDocumentAdapter,
    RAGContextBuilder,
    RagStrategyConfig,
    RetrievalCoverage,
    RetrievalIntent,
    RetrievalMode,
    RetrievalPlan,
    RetrievalQuery,
    RetrievalReport,
    RetrievalSession,
    RetrievalStep,
    RetrievedChunk,
    RetrievedEvidence,
    Reranker,
)
from .classic import CodeSymbolChunkingStrategy, FixedTokenChunkingStrategy, HeadingAwareChunkingStrategy, ParagraphChunkingStrategy
from .adapters import (
    CodeAdapter,
    DocxAdapter,
    MarkdownAdapter,
    MemoryRecordAdapter,
    PdfAdapter,
    TextAdapter,
    WorkspaceArtifactAdapter,
    infer_asset_from_path,
)
from .factory import create_chunking_strategy, create_document_adapter, create_embedding_provider, create_reranker, create_retriever
from .indexed import (
    ClassicRagContextBuilder,
    ClassicRetriever,
    DeliberativeRetriever,
    HybridRetriever,
    IndexedKnowledgeBase,
    KnowledgeIngestionManager,
    create_rag_retriever,
)
from .in_memory import InMemoryKnowledgeBase, KeywordRetriever
from .registry import (
    list_chunking_strategies,
    list_document_adapters,
    list_embedding_providers,
    list_rerankers,
    list_retrievers,
    register_chunking_strategy,
    register_document_adapter,
    register_embedding_provider,
    register_reranker,
    register_retriever,
)

register_retriever("keyword", KeywordRetriever)
register_retriever("classic", ClassicRetriever)
register_retriever("deliberative", DeliberativeRetriever)
register_retriever("hybrid", HybridRetriever)
register_chunking_strategy("fixed_token_chunk", FixedTokenChunkingStrategy)
register_chunking_strategy("paragraph_chunk", ParagraphChunkingStrategy)
register_chunking_strategy("heading_aware_chunk", HeadingAwareChunkingStrategy)
register_chunking_strategy("code_symbol_chunk", CodeSymbolChunkingStrategy)
register_document_adapter("markdown", MarkdownAdapter)
register_document_adapter("text", TextAdapter)
register_document_adapter("code", CodeAdapter)
register_document_adapter("pdf", PdfAdapter)
register_document_adapter("docx", DocxAdapter)
register_document_adapter("memory_record", MemoryRecordAdapter)
register_document_adapter("workspace_artifact", WorkspaceArtifactAdapter)

__all__ = [
    "BaseRetriever",
    "Citation",
    "ClassicRagConfig",
    "ClassicRagContextBuilder",
    "ClassicRetriever",
    "ChunkingStrategy",
    "CodeAdapter",
    "CodeSymbolChunkingStrategy",
    "FixedTokenChunkingStrategy",
    "Document",
    "DocumentChunk",
    "DocumentSection",
    "DeliberativeRetriever",
    "DeliberativeRagConfig",
    "DocxAdapter",
    "EmbeddingProvider",
    "HeadingAwareChunkingStrategy",
    "HybridRagConfig",
    "HybridRetriever",
    "IndexedKnowledgeBase",
    "InMemoryKnowledgeBase",
    "IngestionPipeline",
    "IngestionJob",
    "KnowledgeAsset",
    "KeywordRetriever",
    "KnowledgeBase",
    "KnowledgeIngestionManager",
    "KnowledgeRoute",
    "KnowledgeScope",
    "MarkdownAdapter",
    "MemoryRecordAdapter",
    "ParsedDocument",
    "ParsedDocumentAdapter",
    "PdfAdapter",
    "ParagraphChunkingStrategy",
    "RAGContextBuilder",
    "RagStrategyConfig",
    "RetrievalCoverage",
    "RetrievalIntent",
    "RetrievalMode",
    "RetrievalPlan",
    "RetrievalQuery",
    "RetrievalReport",
    "RetrievalSession",
    "RetrievalStep",
    "RetrievedChunk",
    "RetrievedEvidence",
    "Reranker",
    "TextAdapter",
    "WorkspaceArtifactAdapter",
    "create_rag_retriever",
    "create_chunking_strategy",
    "create_document_adapter",
    "create_embedding_provider",
    "create_reranker",
    "create_retriever",
    "infer_asset_from_path",
    "list_chunking_strategies",
    "list_document_adapters",
    "list_embedding_providers",
    "list_rerankers",
    "list_retrievers",
    "register_chunking_strategy",
    "register_document_adapter",
    "register_embedding_provider",
    "register_reranker",
    "register_retriever",
]
