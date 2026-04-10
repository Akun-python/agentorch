from __future__ import annotations

import asyncio
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .adapters import DEFAULT_ADAPTERS, infer_asset_from_path
from .base import (
    BaseRetriever,
    Citation,
    ClassicRagConfig,
    Document,
    DocumentChunk,
    DocumentSection,
    DeliberativeRagConfig,
    IngestionPipeline,
    KnowledgeAsset,
    KnowledgeBase,
    ParsedDocument,
    ParsedDocumentAdapter,
    RagStrategyConfig,
    RetrievalCoverage,
    RetrievalIntent,
    RetrievalQuery,
    RetrievalReport,
    RetrievalSession,
    RetrievalStep,
    RetrievedChunk,
    RetrievedEvidence,
)
from .classic import (
    CodeSymbolChunkingStrategy,
    FixedTokenChunkingStrategy,
    HeadingAwareChunkingStrategy,
    ParagraphChunkingStrategy,
)


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", text.lower()) if token]


class KnowledgeIngestionManager:
    def __init__(self, adapters: Iterable[ParsedDocumentAdapter] | None = None) -> None:
        adapter_items = list(adapters or [adapter_cls() for adapter_cls in DEFAULT_ADAPTERS])
        self._adapters_by_kind = {adapter.kind: adapter for adapter in adapter_items}
        self._adapters_by_suffix: dict[str, ParsedDocumentAdapter] = {}
        for adapter in adapter_items:
            for suffix in adapter.supported_suffixes:
                self._adapters_by_suffix[suffix.lower()] = adapter

    def register_adapter(self, adapter: ParsedDocumentAdapter) -> None:
        self._adapters_by_kind[adapter.kind] = adapter
        for suffix in adapter.supported_suffixes:
            self._adapters_by_suffix[suffix.lower()] = adapter

    def list_adapters(self) -> list[str]:
        return sorted(self._adapters_by_kind.keys())

    def resolve_adapter(self, asset: KnowledgeAsset) -> ParsedDocumentAdapter:
        if asset.source_type in self._adapters_by_kind:
            return self._adapters_by_kind[asset.source_type]
        suffix = Path(asset.path or "").suffix.lower()
        if suffix in self._adapters_by_suffix:
            return self._adapters_by_suffix[suffix]
        if asset.mime_type == "text/markdown":
            return self._adapters_by_kind["markdown"]
        return self._adapters_by_kind["text"]

    async def parse_asset(self, asset: KnowledgeAsset) -> ParsedDocument:
        adapter = self.resolve_adapter(asset)
        return await adapter.parse(asset)


class LexicalIndex:
    def __init__(self) -> None:
        self.section_terms: dict[str, Counter[str]] = {}
        self.section_documents: dict[str, str] = {}
        self.section_lengths: dict[str, int] = {}
        self.document_frequency: Counter[str] = Counter()
        self.doc_count = 0

    def add_document(self, document: ParsedDocument) -> None:
        for section in document.sections:
            tokens = _tokenize(f"{section.heading or ''}\n{section.text}")
            counts = Counter(tokens)
            self.section_terms[section.section_id] = counts
            self.section_documents[section.section_id] = document.document_id
            self.section_lengths[section.section_id] = max(sum(counts.values()), 1)
            for token in counts.keys():
                self.document_frequency[token] += 1
            self.doc_count += 1

    def score(self, section: DocumentSection, document: ParsedDocument, terms: list[str]) -> float:
        counts = self.section_terms.get(section.section_id) or Counter(_tokenize(section.text))
        if not terms:
            return 0.0
        avg_len = max(sum(self.section_lengths.values()) / max(len(self.section_lengths), 1), 1.0)
        k1 = 1.2
        b = 0.75
        score = 0.0
        for term in terms:
            if term not in counts:
                continue
            tf = counts[term]
            df = self.document_frequency.get(term, 0)
            idf = math.log(1 + ((self.doc_count - df + 0.5) / (df + 0.5 if df else 0.5)))
            denom = tf + k1 * (1 - b + b * self.section_lengths.get(section.section_id, 1) / avg_len)
            score += idf * ((tf * (k1 + 1)) / max(denom, 1e-6))
        title_terms = _tokenize(document.title or "")
        scope_terms = _tokenize(" ".join(document.metadata.get("scopes", [])))
        for term in terms:
            if term in title_terms:
                score += 0.8
            if term in scope_terms:
                score += 0.4
        return score


class IndexedKnowledgeBase(KnowledgeBase, IngestionPipeline):
    def __init__(self, *, ingestion_manager: KnowledgeIngestionManager | None = None) -> None:
        self.documents: dict[str, ParsedDocument] = {}
        self.assets: dict[str, KnowledgeAsset] = {}
        self.sections: dict[str, DocumentSection] = {}
        self.ingestion_manager = ingestion_manager or KnowledgeIngestionManager()
        self.lexical_index = LexicalIndex()

    @classmethod
    async def acreate(
        cls,
        *,
        paths: list[str | Path] | None = None,
        assets: list[KnowledgeAsset] | None = None,
        documents: list[Document] | None = None,
        scopes: list[str] | None = None,
        ingestion_manager: KnowledgeIngestionManager | None = None,
    ) -> "IndexedKnowledgeBase":
        kb = cls(ingestion_manager=ingestion_manager)
        if documents:
            await kb.ingest(list(documents))
        if assets:
            await kb.ingest_assets(list(assets))
        if paths:
            await kb.ingest_paths(list(paths), scopes=scopes)
        return kb

    @classmethod
    def create(
        cls,
        *,
        paths: list[str | Path] | None = None,
        assets: list[KnowledgeAsset] | None = None,
        documents: list[Document] | None = None,
        scopes: list[str] | None = None,
        ingestion_manager: KnowledgeIngestionManager | None = None,
    ) -> "IndexedKnowledgeBase":
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                cls.acreate(
                    paths=paths,
                    assets=assets,
                    documents=documents,
                    scopes=scopes,
                    ingestion_manager=ingestion_manager,
                )
            )
        raise RuntimeError(
            "IndexedKnowledgeBase.create() cannot be used inside a running event loop. "
            "Use 'await IndexedKnowledgeBase.acreate(...)' in async applications and notebooks."
        )

    async def ingest(self, documents: list[Document]) -> None:
        for document in documents:
            parsed = ParsedDocument(
                document_id=document.id,
                asset_id=document.id,
                title=document.metadata.get("title", document.id),
                plain_text=document.text,
                sections=[
                    DocumentSection(
                        section_id=f"{document.id}:section:1",
                        heading=document.metadata.get("title", document.id),
                        text=document.text,
                        locator={"document_id": document.id},
                        section_type="text",
                        metadata=dict(document.metadata),
                    )
                ],
                metadata={**document.metadata, "source_type": document.metadata.get("source_type", "document")},
            )
            self._store_document(parsed, KnowledgeAsset(asset_id=document.id, source_type="document", metadata=document.metadata))

    async def ingest_assets(self, assets: list[KnowledgeAsset]) -> None:
        for asset in assets:
            parsed = await self.ingestion_manager.parse_asset(asset)
            self._store_document(parsed, asset)

    async def ingest_paths(self, paths: list[str | Path], scopes: list[str] | None = None) -> None:
        assets = [infer_asset_from_path(path, scopes=scopes) for path in paths]
        await self.ingest_assets(assets)

    def register_adapter(self, adapter: ParsedDocumentAdapter) -> None:
        self.ingestion_manager.register_adapter(adapter)

    def list_assets(self, *, source_types: list[str] | None = None, file_types: list[str] | None = None) -> list[KnowledgeAsset]:
        results = list(self.assets.values())
        if source_types:
            allowed_sources = {value.lower() for value in source_types}
            results = [asset for asset in results if asset.source_type.lower() in allowed_sources]
        if file_types:
            allowed_types = {value.lower() for value in file_types}
            results = [
                asset
                for asset in results
                if Path(asset.path or "").suffix.lower() in allowed_types
                or (asset.metadata.get("suffix") or "").lower() in allowed_types
            ]
        return results

    def get_document(self, document_id: str) -> ParsedDocument:
        return self.documents[document_id]

    def get_retriever(self) -> BaseRetriever:
        return DeliberativeRetriever(self)

    def _store_document(self, document: ParsedDocument, asset: KnowledgeAsset) -> None:
        merged_metadata = {**document.metadata}
        merged_metadata.setdefault("source_type", asset.source_type)
        merged_metadata.setdefault("scopes", list(asset.scope_tags))
        if asset.path and "path" not in merged_metadata:
            merged_metadata["path"] = asset.path
        document = document.model_copy(update={"metadata": merged_metadata})
        self.documents[document.document_id] = document
        self.assets[asset.asset_id] = asset
        for section in document.sections:
            merged_section_metadata = {**section.metadata, "source_type": merged_metadata.get("source_type"), "scopes": merged_metadata.get("scopes", [])}
            self.sections[section.section_id] = section.model_copy(update={"metadata": merged_section_metadata})
        self.lexical_index.add_document(document)


class DeliberativeRetriever(BaseRetriever):
    def __init__(self, knowledge_base: IndexedKnowledgeBase) -> None:
        self.knowledge_base = knowledge_base

    def _matches_filters(self, document: ParsedDocument, intent: RetrievalIntent | RetrievalQuery) -> bool:
        scopes = intent.scopes if isinstance(intent, RetrievalQuery) else intent.knowledge_scope
        if scopes:
            doc_scopes = set(document.metadata.get("scopes", []))
            if doc_scopes and not doc_scopes.intersection(scopes):
                return False
        filters = intent.filters if isinstance(intent, RetrievalQuery) else intent.constraints
        allowed_sources = set(filters.get("source_types", []) or filters.get("sources", []) or [])
        if allowed_sources and document.metadata.get("source_type") not in allowed_sources:
            return False
        allowed_file_types = set(filters.get("file_types", []) or [])
        suffix = Path(str(document.metadata.get("path", ""))).suffix.lower()
        if allowed_file_types and suffix not in allowed_file_types:
            return False
        path_filters = filters.get("path_filters", []) or []
        if path_filters:
            path_value = str(document.metadata.get("path", ""))
            if not any(filter_value in path_value for filter_value in path_filters):
                return False
        mime_filters = set(filters.get("mime_filters", []) or [])
        if mime_filters and document.content_type not in mime_filters:
            return False
        return True

    def _make_chunks(self, query: str, top_k: int, filters: dict[str, Any] | None = None, scopes: list[str] | None = None) -> list[RetrievedChunk]:
        terms = _tokenize(query)
        scored: list[RetrievedChunk] = []
        query_wrapper = RetrievalQuery(query=query, top_k=top_k, filters=filters or {}, scopes=scopes or [])
        for document in self.knowledge_base.documents.values():
            if not self._matches_filters(document, query_wrapper):
                continue
            for index, section in enumerate(document.sections):
                score = self.knowledge_base.lexical_index.score(section, document, terms)
                if score <= 0:
                    continue
                extra_window = []
                if index > 0:
                    extra_window.append(document.sections[index - 1].text)
                extra_window.append(section.text)
                if index + 1 < len(document.sections):
                    extra_window.append(document.sections[index + 1].text)
                chunk_text = "\n".join(text for text in extra_window if text).strip()
                metadata = {
                    **section.metadata,
                    "locator": section.locator,
                    "section_id": section.section_id,
                    "heading": section.heading,
                    "source_type": document.metadata.get("source_type", "document"),
                    "scopes": document.metadata.get("scopes", []),
                    "content_type": document.content_type,
                    "path": document.metadata.get("path"),
                    "title": document.title,
                }
                scored.append(
                    RetrievedChunk(
                        chunk=DocumentChunk(
                            id=section.section_id,
                            document_id=document.document_id,
                            text=chunk_text,
                            metadata=metadata,
                        ),
                        score=score,
                        source=str(document.metadata.get("source_type", "document")),
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def _compute_coverage(self, intent: RetrievalIntent, evidence: list[RetrievedEvidence]) -> RetrievalCoverage:
        if not intent.must_cover:
            return RetrievalCoverage(covered=[], missing=[])
        haystack = "\n".join((item.snippet or item.summary or "").lower() for item in evidence)
        covered = [item for item in intent.must_cover if item.lower() in haystack]
        missing = [item for item in intent.must_cover if item not in covered]
        return RetrievalCoverage(covered=covered, missing=missing)

    def _evidence_from_chunks(self, chunks: list[RetrievedChunk]) -> list[RetrievedEvidence]:
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
                    claim=item.chunk.metadata.get("heading") or item.chunk.text[:120],
                    snippet=item.chunk.text,
                    relevance_score=item.score,
                    support_score=item.score,
                    scope_tags=list(item.chunk.metadata.get("scopes", [])),
                )
            )
        return evidence

    def _summarize(self, evidence: list[RetrievedEvidence], coverage: RetrievalCoverage) -> str:
        if not evidence:
            return "No matching evidence found."
        lines = []
        for item in evidence[:5]:
            locator = item.locator or item.citation.locator
            lines.append(
                f"- {item.source_type}::{item.citation.document_id} {locator} -> {(item.snippet or item.summary or '').strip()[:220]}"
            )
        if coverage.missing:
            lines.append(f"Uncovered targets: {', '.join(coverage.missing)}")
        return "\n".join(lines)

    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        return self._make_chunks(query.query, query.top_k, filters=query.filters, scopes=query.scopes)

    async def retrieve_report(self, intent: RetrievalIntent | RetrievalQuery) -> RetrievalReport:
        if isinstance(intent, RetrievalQuery):
            intent = RetrievalIntent(
                question=intent.query,
                knowledge_scope=intent.scopes,
                max_documents=intent.top_k,
                constraints=intent.filters,
                metadata=intent.metadata,
            )
        session = RetrievalSession(intent=intent)
        session.plan.append(RetrievalStep(step_type="route_sources", query=intent.question, metadata={"sources": intent.preferred_sources}))
        filters = dict(intent.constraints)
        if intent.preferred_sources:
            filters.setdefault("source_types", intent.preferred_sources)
        if intent.file_types:
            filters.setdefault("file_types", intent.file_types)
        initial_chunks = self._make_chunks(intent.question, max(intent.max_documents, 1), filters=filters, scopes=intent.knowledge_scope)
        session.plan.append(RetrievalStep(step_type="search_index", query=intent.question, metadata={"candidate_count": len(initial_chunks)}))
        evidence = self._evidence_from_chunks(initial_chunks)
        coverage = self._compute_coverage(intent, evidence)
        if coverage.missing and session.intent.max_steps > 1:
            follow_up_query = " ".join([intent.question, *coverage.missing]).strip()
            session.plan.append(RetrievalStep(step_type="refine_search", query=follow_up_query, notes="Expanded query to cover missing targets."))
            follow_up_chunks = self._make_chunks(
                follow_up_query,
                max(1, intent.max_documents),
                filters=filters,
                scopes=intent.knowledge_scope,
            )
            existing_ids = {item.chunk.chunk.id for item in evidence}
            for item in self._evidence_from_chunks(follow_up_chunks):
                if item.chunk.chunk.id not in existing_ids:
                    evidence.append(item)
            evidence.sort(key=lambda item: item.relevance_score, reverse=True)
            evidence = evidence[: max(1, intent.max_documents)]
            coverage = self._compute_coverage(intent, evidence)
        session.evidence = evidence
        session.coverage = coverage
        session.visited_documents = [item.citation.document_id for item in evidence]
        retrieval_context = self._summarize(evidence, coverage)
        summary = retrieval_context
        residual_risks: list[str] = []
        for document_id in session.visited_documents:
            metadata = self.knowledge_base.documents[document_id].metadata
            if metadata.get("extraction_status") == "needs_ocr":
                residual_risks.append(f"{document_id} requires OCR for full coverage.")
        if coverage.missing:
            residual_risks.append(f"Coverage incomplete for: {', '.join(coverage.missing)}")
        return RetrievalReport(
            summary=summary,
            retrieval_context=retrieval_context,
            evidence=evidence,
            citations=[item.citation for item in evidence],
            coverage=coverage,
            plan=session.plan,
            visited_documents=session.visited_documents,
            visited_sources=sorted({item.source_type for item in evidence}),
            residual_risks=residual_risks,
            metadata={"question": intent.question},
        )


class ClassicRagContextBuilder:
    def build(self, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return ""
        return "\n".join(f"[{index}] score={chunk.score:.3f} {chunk.chunk.text}" for index, chunk in enumerate(chunks, start=1))


class ClassicRetriever(BaseRetriever):
    def __init__(self, knowledge_base: IndexedKnowledgeBase, *, config: ClassicRagConfig | None = None) -> None:
        self.knowledge_base = knowledge_base
        self.config = config or ClassicRagConfig()
        self.context_builder = ClassicRagContextBuilder()

    def _select_chunker(self):
        mapping = {
            "fixed_token_chunk": FixedTokenChunkingStrategy(chunk_size=self.config.chunk_size, chunk_overlap=self.config.chunk_overlap),
            "paragraph_chunk": ParagraphChunkingStrategy(),
            "heading_aware_chunk": HeadingAwareChunkingStrategy(),
            "code_symbol_chunk": CodeSymbolChunkingStrategy(),
        }
        return mapping.get(self.config.chunking_strategy, ParagraphChunkingStrategy())

    async def _chunk_documents(self, query: RetrievalQuery) -> list[DocumentChunk]:
        documents: list[Document] = []
        for parsed in self.knowledge_base.documents.values():
            scopes = set(parsed.metadata.get("scopes", []))
            if query.scopes and scopes and not scopes.intersection(query.scopes):
                continue
            source_types = set(query.filters.get("source_types", []) or [])
            if source_types and parsed.metadata.get("source_type") not in source_types:
                continue
            file_types = set(query.filters.get("file_types", []) or [])
            suffix = Path(str(parsed.metadata.get("path", ""))).suffix.lower()
            if file_types and suffix not in file_types:
                continue
            documents.append(
                Document(
                    id=parsed.document_id,
                    text=parsed.plain_text or "\n\n".join(section.text for section in parsed.sections),
                    metadata=parsed.metadata,
                )
            )
        return await self._select_chunker().chunk(documents)

    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        chunks = await self._chunk_documents(query)
        terms = _tokenize(query.query)
        scored: list[RetrievedChunk] = []
        for chunk in chunks:
            haystack = f"{chunk.metadata.get('heading', '')}\n{chunk.text}"
            score = sum(1.0 for term in terms if term in haystack.lower())
            if score <= 0:
                continue
            metadata = dict(chunk.metadata)
            metadata.setdefault("source_type", metadata.get("source_type", "document"))
            scored.append(
                RetrievedChunk(
                    chunk=chunk.model_copy(update={"metadata": metadata}),
                    score=float(score),
                    source=str(metadata.get("source_type", "classic")),
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: query.top_k]

    async def retrieve_report(self, intent: RetrievalIntent | RetrievalQuery) -> RetrievalReport:
        if isinstance(intent, RetrievalIntent):
            query = RetrievalQuery(
                query=intent.question,
                top_k=intent.max_documents or self.config.top_k,
                scopes=intent.knowledge_scope,
                filters={
                    **intent.constraints,
                    "source_types": intent.preferred_sources or intent.constraints.get("source_types", []),
                    "file_types": intent.file_types or intent.constraints.get("file_types", []),
                },
            )
        else:
            query = intent
        chunks = await self.retrieve(query)
        evidence = DeliberativeRetriever(self.knowledge_base)._evidence_from_chunks(chunks)
        context = self.context_builder.build(chunks)
        return RetrievalReport(
            summary=context or "No matching evidence found.",
            retrieval_context=context,
            evidence=evidence,
            citations=[item.citation for item in evidence],
            coverage=RetrievalCoverage(covered=[], missing=[]),
            plan=[RetrievalStep(step_type="classic_retrieve", query=query.query)],
            visited_documents=[item.chunk.document_id for item in chunks],
            visited_sources=sorted({item.source for item in chunks}),
            metadata={"rag_mode": "classic"},
        )


class HybridRetriever(BaseRetriever):
    def __init__(
        self,
        knowledge_base: IndexedKnowledgeBase,
        *,
        classic_config: ClassicRagConfig | None = None,
        deliberative_config: DeliberativeRagConfig | None = None,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.classic = ClassicRetriever(knowledge_base, config=classic_config)
        self.deliberative = DeliberativeRetriever(knowledge_base)
        self.deliberative_config = deliberative_config or DeliberativeRagConfig()

    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        return await self.classic.retrieve(query)

    async def retrieve_report(self, intent: RetrievalIntent | RetrievalQuery) -> RetrievalReport:
        if isinstance(intent, RetrievalQuery):
            intent = RetrievalIntent(
                question=intent.query,
                knowledge_scope=intent.scopes,
                constraints=intent.filters,
                max_documents=intent.top_k,
                rag_mode="hybrid",
            )
        classic_report = await self.classic.retrieve_report(intent)
        seeded_terms = []
        for evidence in classic_report.evidence[: max(1, min(len(classic_report.evidence), 3))]:
            seeded_terms.extend(_tokenize(evidence.claim or evidence.summary or ""))
        follow_up_question = " ".join([intent.question, *seeded_terms[:6]]).strip()
        refined_intent = intent.model_copy(
            update={
                "question": follow_up_question or intent.question,
                "max_steps": self.deliberative_config.max_steps,
                "max_documents": max(intent.max_documents, self.deliberative_config.max_documents),
                "rag_mode": "hybrid",
            }
        )
        deliberative_report = await self.deliberative.retrieve_report(refined_intent)
        merged: dict[str, RetrievedEvidence] = {}
        for item in [*classic_report.evidence, *deliberative_report.evidence]:
            merged[item.citation.chunk_id] = item
        evidence = sorted(merged.values(), key=lambda item: item.relevance_score, reverse=True)[: max(1, intent.max_documents)]
        coverage = deliberative_report.coverage if deliberative_report.coverage.covered or deliberative_report.coverage.missing else classic_report.coverage
        summary = "\n".join(
            filter(
                None,
                [
                    classic_report.summary,
                    deliberative_report.summary if deliberative_report.summary != classic_report.summary else "",
                ],
            )
        ).strip()
        return RetrievalReport(
            summary=summary or "No matching evidence found.",
            retrieval_context=summary or deliberative_report.retrieval_context or classic_report.retrieval_context,
            evidence=evidence,
            citations=[item.citation for item in evidence],
            coverage=coverage,
            plan=[
                RetrievalStep(step_type="classic_retrieve", query=intent.question),
                RetrievalStep(step_type="deliberative_refine", query=follow_up_question or intent.question),
            ],
            visited_documents=sorted({item.citation.document_id for item in evidence}),
            visited_sources=sorted({item.source_type for item in evidence}),
            residual_risks=deliberative_report.residual_risks,
            metadata={"rag_mode": "hybrid"},
        )


def create_rag_retriever(
    knowledge_base: IndexedKnowledgeBase,
    rag_strategy: RagStrategyConfig | None = None,
) -> BaseRetriever:
    strategy = rag_strategy or RagStrategyConfig()
    if strategy.mode == "classic":
        return ClassicRetriever(knowledge_base, config=strategy.classic.model_copy(update={"top_k": strategy.top_k}))
    if strategy.mode == "hybrid":
        return HybridRetriever(knowledge_base, classic_config=strategy.hybrid.classic, deliberative_config=strategy.hybrid.deliberative)
    return DeliberativeRetriever(knowledge_base)
