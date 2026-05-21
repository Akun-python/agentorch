from __future__ import annotations

from agentorch.knowledge.base import Citation, DocumentChunk, RetrievalCoverage, RetrievalReport, RetrievalStep, RetrievedChunk, RetrievedEvidence

from ..api.models import CapsuleDetailResponse, RecallResponse


class AgentOrchBridge:
    """把图谱召回结果转换为 AgentTorch 证据对象。"""

    def to_retrieved_evidence(
        self,
        response: RecallResponse,
        *,
        details: CapsuleDetailResponse | None = None,
    ) -> list[RetrievedEvidence]:
        """转换成 RetrievedEvidence 列表，供 AgentTorch 证据链使用。"""

        detail_map = {item.capsule_id: item for item in (details.details if details is not None else [])}
        evidence: list[RetrievedEvidence] = []
        for entry in response.node_index:
            detail = detail_map.get(entry.capsule_id)
            text = ""
            if detail is not None:
                text = detail.summary or detail.outcome or detail.goal
            if not text:
                text = entry.title
            chunk = RetrievedChunk(
                chunk=DocumentChunk(
                    id=f"{entry.capsule_id}:summary",
                    document_id=entry.capsule_id,
                    text=text,
                    metadata={
                        "capsule_id": entry.capsule_id,
                        "node_index": entry.index,
                        "why_selected": entry.why_selected,
                    },
                ),
                score=entry.score,
                source="long_term_memory_graph",
            )
            citation = Citation(
                source="long_term_memory_graph",
                document_id=entry.capsule_id,
                chunk_id=chunk.chunk.id,
                quote=text[:200] if text else None,
                locator={"capsule_id": entry.capsule_id, "node_index": entry.index},
                metadata={"score": entry.score},
            )
            evidence.append(
                RetrievedEvidence(
                    chunk=chunk,
                    citation=citation,
                    summary=detail.summary if detail is not None else entry.title,
                    source_type="long_term_memory_graph",
                    locator={"capsule_id": entry.capsule_id, "node_index": entry.index},
                    claim=detail.goal if detail is not None else entry.title,
                    snippet=text[:240] if text else entry.title,
                    relevance_score=entry.score,
                    support_score=entry.score,
                    scope_tags=list(detail.knowledge_scope if detail is not None else []),
                )
            )
        return evidence

    def to_citations(
        self,
        response: RecallResponse,
        *,
        details: CapsuleDetailResponse | None = None,
    ) -> list[Citation]:
        """只取 citation，供需要轻量引用的调用方使用。"""

        return [item.citation for item in self.to_retrieved_evidence(response, details=details)]

    def to_retrieval_report(
        self,
        response: RecallResponse,
        *,
        details: CapsuleDetailResponse | None = None,
    ) -> RetrievalReport:
        """转换成完整 RetrievalReport，保留边、风险和访问来源。"""

        evidence = self.to_retrieved_evidence(response, details=details)
        return RetrievalReport(
            summary=response.prompt_summary,
            retrieval_context=response.prompt_summary,
            evidence=evidence,
            citations=[item.citation for item in evidence],
            coverage=RetrievalCoverage(covered=[entry.capsule_id for entry in response.node_index], missing=[]),
            plan=[
                RetrievalStep(
                    step_type="long_term_memory_graph_recall",
                    notes=f"Returned {len(response.node_index)} capsules with progressive disclosure.",
                    metadata=response.retrieval_report.model_dump(),
                )
            ],
            visited_documents=[entry.capsule_id for entry in response.node_index],
            visited_sources=["long_term_memory_graph"],
            residual_risks=[
                *[f"Suppressed stale node: {capsule_id}" for capsule_id in response.retrieval_report.suppressed_stale_nodes],
                *[f"Suppressed conflicting node: {capsule_id}" for capsule_id in response.retrieval_report.suppressed_conflict_nodes],
            ],
            metadata={
                "edges": [edge.model_dump() for edge in response.edges],
                "detail_available": details is not None,
            },
        )
