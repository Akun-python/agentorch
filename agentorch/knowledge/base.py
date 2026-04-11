from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Document(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeAsset(BaseModel):
    asset_id: str
    source_type: str
    uri: str | None = None
    path: str | None = None
    mime_type: str | None = None
    scope_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        asset_id: str | None = None,
        source_type: str = "filesystem",
        scope_tags: list[str] | None = None,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "KnowledgeAsset":
        file_path = Path(path)
        return cls(
            asset_id=asset_id or file_path.stem or file_path.name,
            source_type=source_type,
            path=str(file_path),
            mime_type=mime_type,
            scope_tags=list(scope_tags or []),
            metadata={"suffix": file_path.suffix.lower(), **(metadata or {})},
        )


class DocumentSection(BaseModel):
    section_id: str
    heading: str | None = None
    text: str
    locator: dict[str, Any] = Field(default_factory=dict)
    section_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    document_id: str
    asset_id: str | None = None
    title: str | None = None
    content_type: str = "text/plain"
    plain_text: str = ""
    sections: list[DocumentSection] = Field(default_factory=list)
    structural_map: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalQuery(BaseModel):
    query: str
    top_k: int = 5
    filters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    scopes: list[str] = Field(default_factory=list)


class ClassicRagConfig(BaseModel):
    strategy: Literal["keyword", "lexical", "bm25"] = "lexical"
    chunking_strategy: str = "paragraph_chunk"
    chunk_size: int = 600
    chunk_overlap: int = 80
    top_k: int = 5
    rerank_enabled: bool = False
    context_compression: bool = False


class DeliberativeRagConfig(BaseModel):
    max_steps: int = 3
    max_documents: int = 8
    structure_aware: bool = True
    coverage_check: bool = True
    source_routing: bool = True


class HybridRagConfig(BaseModel):
    classic: ClassicRagConfig = Field(default_factory=ClassicRagConfig)
    deliberative: DeliberativeRagConfig = Field(default_factory=DeliberativeRagConfig)
    merge_policy: Literal["classic_then_deliberative"] = "classic_then_deliberative"


class RagStrategyConfig(BaseModel):
    mode: Literal["off", "classic", "deliberative", "hybrid"] = "deliberative"
    mount: Literal["inline", "tool_only", "workflow_only", "agent_only"] = "inline"
    injection_policy: Literal["disabled", "summary_only", "evidence_only", "full_report"] = "full_report"
    knowledge_scope: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    file_types: list[str] = Field(default_factory=list)
    top_k: int = 5
    must_cover: list[str] = Field(default_factory=list)
    max_steps: int = 3
    rerank_enabled: bool = False
    fallback_mode: Literal["off", "classic", "deliberative"] = "off"
    classic: ClassicRagConfig = Field(default_factory=ClassicRagConfig)
    deliberative: DeliberativeRagConfig = Field(default_factory=DeliberativeRagConfig)
    hybrid: HybridRagConfig = Field(default_factory=HybridRagConfig)

    @model_validator(mode="before")
    @classmethod
    def _normalize_shortcuts(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"mode": data}
        return data

    @classmethod
    def from_any(cls, value: "RagStrategyConfig | str | dict[str, Any] | None", **overrides: Any) -> "RagStrategyConfig":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        elif isinstance(value, str):
            base = cls(mode=value)
        else:
            base = cls.model_validate(value)
        if overrides:
            return base.model_copy(update=overrides)
        return base

    @classmethod
    def off(cls, **kwargs: Any) -> "RagStrategyConfig":
        return cls(mode="off", **kwargs)

    @classmethod
    def for_classic(cls, **kwargs: Any) -> "RagStrategyConfig":
        return cls(mode="classic", **kwargs)

    @classmethod
    def for_deliberative(cls, **kwargs: Any) -> "RagStrategyConfig":
        return cls(mode="deliberative", **kwargs)

    @classmethod
    def for_hybrid(cls, **kwargs: Any) -> "RagStrategyConfig":
        return cls(mode="hybrid", **kwargs)

    def mounted(self, mount: Literal["inline", "tool_only", "workflow_only", "agent_only"]) -> "RagStrategyConfig":
        return self.model_copy(update={"mount": mount})

    def with_scope(self, *scope_tags: str) -> "RagStrategyConfig":
        return self.model_copy(update={"knowledge_scope": [*self.knowledge_scope, *scope_tags]})


class RetrievalIntent(BaseModel):
    question: str
    goal: str | None = None
    must_cover: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    preferred_sources: list[str] = Field(default_factory=list)
    knowledge_scope: list[str] = Field(default_factory=list)
    file_types: list[str] = Field(default_factory=list)
    max_steps: int = 3
    max_documents: int = 8
    metadata: dict[str, Any] = Field(default_factory=dict)
    rag_mode: str = "deliberative"

    @classmethod
    def from_question(
        cls,
        question: str,
        *,
        goal: str | None = None,
        must_cover: list[str] | None = None,
        knowledge_scope: list[str] | None = None,
        file_types: list[str] | None = None,
        sources: list[str] | None = None,
        max_steps: int = 3,
        max_documents: int = 8,
        rag_mode: str = "deliberative",
        metadata: dict[str, Any] | None = None,
    ) -> "RetrievalIntent":
        return cls(
            question=question,
            goal=goal,
            must_cover=list(must_cover or []),
            preferred_sources=list(sources or []),
            knowledge_scope=list(knowledge_scope or []),
            file_types=list(file_types or []),
            max_steps=max_steps,
            max_documents=max_documents,
            rag_mode=rag_mode,
            metadata=dict(metadata or {}),
        )


class RetrievedChunk(BaseModel):
    chunk: DocumentChunk
    score: float = 0.0
    source: str = "unknown"


class RetrievalMode(str, Enum):
    OFF = "off"
    INLINE = "inline"
    EXPLICIT_STEP = "explicit_step"
    POLICY_DRIVEN = "policy_driven"


class KnowledgeScope(BaseModel):
    name: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    source: str
    document_id: str
    chunk_id: str
    quote: str | None = None
    locator: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedEvidence(BaseModel):
    chunk: RetrievedChunk
    citation: Citation
    summary: str | None = None
    source_type: str = "document"
    locator: dict[str, Any] = Field(default_factory=dict)
    claim: str | None = None
    snippet: str | None = None
    relevance_score: float = 0.0
    support_score: float = 0.0
    scope_tags: list[str] = Field(default_factory=list)


class RetrievalPlan(BaseModel):
    query: str
    top_k: int = 5
    scopes: list[str] = Field(default_factory=list)
    strategy: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalStep(BaseModel):
    step_type: str
    query: str | None = None
    source: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalCoverage(BaseModel):
    covered: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class RetrievalReport(BaseModel):
    summary: str = ""
    retrieval_context: str = ""
    evidence: list[RetrievedEvidence] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    coverage: RetrievalCoverage = Field(default_factory=RetrievalCoverage)
    plan: list[RetrievalStep] = Field(default_factory=list)
    visited_documents: list[str] = Field(default_factory=list)
    visited_sources: list[str] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalSession(BaseModel):
    intent: RetrievalIntent
    plan: list[RetrievalStep] = Field(default_factory=list)
    visited_documents: list[str] = Field(default_factory=list)
    evidence: list[RetrievedEvidence] = Field(default_factory=list)
    coverage: RetrievalCoverage = Field(default_factory=RetrievalCoverage)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeRoute(BaseModel):
    route_name: str
    scopes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionJob(BaseModel):
    job_id: str
    document_ids: list[str] = Field(default_factory=list)
    status: str = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkingStrategy(ABC):
    @abstractmethod
    async def chunk(self, documents: list[Document]) -> list[DocumentChunk]:
        raise NotImplementedError


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: RetrievalQuery, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        raise NotImplementedError


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        raise NotImplementedError

    async def retrieve_report(self, intent: RetrievalIntent | RetrievalQuery) -> RetrievalReport:
        query = intent.query if isinstance(intent, RetrievalQuery) else intent.question
        top_k = intent.top_k if isinstance(intent, RetrievalQuery) else intent.max_documents
        scopes = intent.scopes if isinstance(intent, RetrievalQuery) else intent.knowledge_scope
        chunks = await self.retrieve(RetrievalQuery(query=query, top_k=top_k, scopes=scopes))
        builder = RAGContextBuilder()
        evidence = builder.build_evidence(chunks)
        return RetrievalReport(
            summary=builder.build(chunks),
            retrieval_context=builder.build(chunks),
            evidence=evidence,
            citations=[item.citation for item in evidence],
            visited_documents=[item.chunk.chunk.document_id for item in evidence],
            visited_sources=sorted({item.source_type for item in evidence}),
            plan=[RetrievalStep(step_type="retrieve", query=query)],
        )


class KnowledgeBase(ABC):
    @abstractmethod
    def get_retriever(self) -> BaseRetriever:
        raise NotImplementedError


class IngestionPipeline(ABC):
    @abstractmethod
    async def ingest(self, documents: list[Document]) -> None:
        raise NotImplementedError

    async def ingest_assets(self, assets: list[KnowledgeAsset]) -> None:
        raise NotImplementedError

    async def ingest_paths(self, paths: list[str | Path], scopes: list[str] | None = None) -> None:
        raise NotImplementedError


class ParsedDocumentAdapter(ABC):
    kind: str = "base"
    supported_suffixes: tuple[str, ...] = ()

    @abstractmethod
    async def parse(self, asset: KnowledgeAsset) -> ParsedDocument:
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

    def build_evidence(self, chunks: list[RetrievedChunk]) -> list[RetrievedEvidence]:
        evidence: list[RetrievedEvidence] = []
        for item in chunks:
            locator = dict(item.chunk.metadata.get("locator") or {})
            evidence.append(
                RetrievedEvidence(
                    chunk=item,
                    citation=Citation(
                        source=item.source,
                        document_id=item.chunk.document_id,
                        chunk_id=item.chunk.id,
                        quote=item.chunk.text,
                        locator=locator,
                        metadata=dict(item.chunk.metadata),
                    ),
                    summary=item.chunk.text,
                    source_type=str(item.chunk.metadata.get("source_type", item.source)),
                    locator=locator,
                    claim=item.chunk.text,
                    snippet=item.chunk.text,
                    relevance_score=item.score,
                    support_score=item.score,
                    scope_tags=list(item.chunk.metadata.get("scopes", [])),
                )
            )
        return evidence

    def build_report(self, report: RetrievalReport) -> str:
        if report.retrieval_context:
            return report.retrieval_context
        if not report.evidence:
            return ""
        lines: list[str] = []
        for index, item in enumerate(report.evidence, start=1):
            locator = item.locator or item.citation.locator
            locator_text = ""
            if locator:
                locator_text = f" locator={locator}"
            lines.append(
                f"[{index}] source={item.source_type} doc={item.citation.document_id} score={item.relevance_score:.3f}{locator_text} text={item.snippet or item.summary or ''}"
            )
        return "\n".join(lines)
