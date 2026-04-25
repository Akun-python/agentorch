from __future__ import annotations

from collections.abc import Callable

from ...api.config import GraphMemoryConfig
from ...api.models import GraphEdgeView, NodeIndexEntry, RecallRequest, RecallResponse, RecallRetrievalReport
from ...storage.base import GraphStore
from ..entities import MemoryCapsuleDetail, SearchHit, SubgraphEdge
from ..scoring import (
    build_fulltext_query,
    build_selection_reason,
    is_stale,
    resolve_conflict,
    reuse_component,
    scene_match,
    stale_penalty,
)
from ..summary import TemplateSubgraphSummarizer
from ..utils import truncate_text


class RecallService:
    def __init__(
        self,
        *,
        config: GraphMemoryConfig,
        store: GraphStore,
        embed_texts: Callable[[list[str]], list[list[float]]],
        summarizer: TemplateSubgraphSummarizer | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.embed_texts = embed_texts
        self.summarizer = summarizer or TemplateSubgraphSummarizer()

    def recall(self, request: RecallRequest) -> RecallResponse:
        if self.config.embedding_provider is None:
            raise RuntimeError("Long-term memory graph recall requires an embedding provider.")
        top_candidates = request.top_candidates or self.config.top_candidates
        top_seeds = request.top_seeds or self.config.top_seeds
        max_nodes = request.max_nodes or self.config.max_nodes
        max_edges = request.max_edges or self.config.max_edges
        query_embedding = self.embed_texts([request.query])[0]
        semantic_results = self.store.query_vector(query_embedding, limit=top_candidates)
        lexical_query = build_fulltext_query(request)
        lexical_results = self.store.query_fulltext(lexical_query, limit=top_candidates) if lexical_query else []

        candidates = self._merge_candidates(semantic_results, lexical_results)
        if not candidates:
            return RecallResponse(
                prompt_summary="No long-term memory capsules were returned.",
                node_index=[],
                edges=[],
                retrieval_report=RecallRetrievalReport(candidate_count=0, expansion_hops=self.config.expansion_hops),
            )

        conflict_counts = self.store.fetch_conflict_counts(list(candidates.keys()))
        score_map: dict[str, float] = {}
        why_map: dict[str, str] = {}
        lexical_ids: list[str] = []
        semantic_ids: list[str] = []
        for capsule_id, bucket in candidates.items():
            node = bucket["node"]
            semantic_score = float(bucket["semantic_score"])
            lexical_score = float(bucket["lexical_score"])
            if semantic_score > 0:
                semantic_ids.append(capsule_id)
            if lexical_score > 0:
                lexical_ids.append(capsule_id)
            scene_score = scene_match(request, node, weight=self.config.scene_match_weight)
            confidence_component = float(node.confidence) * self.config.confidence_weight
            recall_reuse = reuse_component(node.reuse_count, weight=self.config.reuse_weight)
            recall_stale_penalty = stale_penalty(
                node,
                blocked_statuses=self.config.blocked_statuses,
                stale_after_days=self.config.stale_after_days,
                stale_low_confidence_threshold=self.config.stale_low_confidence_threshold,
                penalty_weight=self.config.stale_penalty_weight,
            )
            conflict_penalty = float(conflict_counts.get(capsule_id, 0)) * self.config.conflict_penalty_weight
            final_score = (
                semantic_score
                + lexical_score
                + scene_score
                + confidence_component
                + recall_reuse
                - recall_stale_penalty
                - conflict_penalty
            )
            score_map[capsule_id] = final_score
            why_map[capsule_id] = build_selection_reason(
                semantic_score=semantic_score,
                lexical_score=lexical_score,
                scene_score=scene_score,
                confidence=node.confidence,
                reuse_count=node.reuse_count,
            )

        reranked = sorted(candidates.values(), key=lambda item: score_map[item["node"].capsule_id], reverse=True)[:top_candidates]
        seed_ids = [item["node"].capsule_id for item in reranked[:top_seeds]]
        expanded_nodes, expanded_edges = self.store.fetch_one_hop_subgraph(seed_ids, edge_limit=max_edges * 3)
        node_lookup = {item.capsule_id: item for item in expanded_nodes}
        for item in reranked:
            node_lookup[item["node"].capsule_id] = item["node"]

        self._propagate_expansion_scores(node_lookup=node_lookup, expanded_edges=expanded_edges, score_map=score_map, why_map=why_map)
        active_nodes, suppressed_stale = self._filter_stale(node_lookup)
        active_nodes, suppressed_conflicts = self._filter_conflicts(active_nodes=active_nodes, edges=expanded_edges, why_map=why_map)

        final_nodes = sorted(active_nodes.values(), key=lambda item: score_map.get(item.capsule_id, item.confidence), reverse=True)[:max_nodes]
        final_ids = {item.capsule_id for item in final_nodes}
        indexed_edges_raw = self._select_edges(active_nodes=active_nodes, edges=expanded_edges, final_ids=final_ids, max_edges=max_edges)

        node_index: list[NodeIndexEntry] = []
        id_to_index: dict[str, str] = {}
        for ordinal, node in enumerate(final_nodes, start=1):
            index = f"N{ordinal}"
            id_to_index[node.capsule_id] = index
            node_index.append(
                NodeIndexEntry(
                    index=index,
                    capsule_id=node.capsule_id,
                    title=truncate_text(node.title, max_chars=96),
                    score=round(score_map.get(node.capsule_id, node.confidence), 4),
                    why_selected=why_map.get(node.capsule_id, "Reached the returned subgraph."),
                )
            )

        edge_views = [
            GraphEdgeView(
                source_index=id_to_index[edge.source_capsule_id],
                relation_type=edge.relation_type,
                target_index=id_to_index[edge.target_capsule_id],
                score=round(float(edge.score), 4),
            )
            for edge in indexed_edges_raw
            if edge.source_capsule_id in id_to_index and edge.target_capsule_id in id_to_index
        ]

        prompt_summary = self.summarizer.summarize(
            query=request.query,
            nodes=final_nodes,
            edges=indexed_edges_raw,
            scores=score_map,
            suppressed_stale_nodes=suppressed_stale,
            suppressed_conflict_nodes=suppressed_conflicts,
        )
        self.store.mark_recalled([entry.capsule_id for entry in final_nodes])
        return RecallResponse(
            prompt_summary=prompt_summary,
            node_index=node_index,
            edges=edge_views,
            retrieval_report=RecallRetrievalReport(
                candidate_count=len(candidates),
                expansion_hops=self.config.expansion_hops,
                suppressed_stale_nodes=suppressed_stale,
                suppressed_conflict_nodes=suppressed_conflicts,
                lexical_candidate_ids=lexical_ids,
                semantic_candidate_ids=semantic_ids,
            ),
        )

    def _merge_candidates(
        self,
        semantic_results: list[SearchHit],
        lexical_results: list[SearchHit],
    ) -> dict[str, dict[str, float | MemoryCapsuleDetail]]:
        candidates: dict[str, dict[str, float | MemoryCapsuleDetail]] = {}
        for item in semantic_results:
            bucket = candidates.setdefault(item.node.capsule_id, {"node": item.node, "semantic_score": 0.0, "lexical_score": 0.0})
            bucket["semantic_score"] = max(float(bucket["semantic_score"]), float(item.score))
        for item in lexical_results:
            bucket = candidates.setdefault(item.node.capsule_id, {"node": item.node, "semantic_score": 0.0, "lexical_score": 0.0})
            bucket["lexical_score"] = max(float(bucket["lexical_score"]), float(item.score))
        return candidates

    def _propagate_expansion_scores(
        self,
        *,
        node_lookup: dict[str, MemoryCapsuleDetail],
        expanded_edges: list[SubgraphEdge],
        score_map: dict[str, float],
        why_map: dict[str, str],
    ) -> None:
        for edge in expanded_edges:
            source_id = edge.source_capsule_id
            target_id = edge.target_capsule_id
            propagation_weight = self._edge_propagation_weight(edge.relation_type)
            if source_id in score_map:
                propagated = score_map[source_id] * propagation_weight + edge.score * propagation_weight
                if propagated > score_map.get(target_id, float("-inf")):
                    score_map[target_id] = propagated
                    if target_id in node_lookup:
                        why_map.setdefault(
                            target_id,
                            f"Expanded via {edge.relation_type} from {truncate_text(node_lookup[source_id].title, max_chars=48)}",
                        )
            if target_id in score_map:
                propagated = score_map[target_id] * propagation_weight + edge.score * propagation_weight
                if propagated > score_map.get(source_id, float("-inf")):
                    score_map[source_id] = propagated
                    if source_id in node_lookup:
                        why_map.setdefault(
                            source_id,
                            f"Expanded via {edge.relation_type} from {truncate_text(node_lookup[target_id].title, max_chars=48)}",
                        )

    def _edge_propagation_weight(self, relation_type: str) -> float:
        relation_weights = {
            "TEMPORAL_NEXT": 0.95,
            "REVISES": 0.9,
            "EVIDENCE_SUPPORTS": 0.82,
            "SCOPE_OVERLAP": 0.6,
            "SAME_TASK": 0.22,
            "CONFLICTS_WITH": 0.1,
        }
        return relation_weights.get(relation_type, 0.5)

    def _filter_stale(self, node_lookup: dict[str, MemoryCapsuleDetail]) -> tuple[dict[str, MemoryCapsuleDetail], list[str]]:
        suppressed_stale: list[str] = []
        active_nodes: dict[str, MemoryCapsuleDetail] = {}
        for capsule_id, node in node_lookup.items():
            if node.status in self.config.blocked_statuses:
                suppressed_stale.append(capsule_id)
                continue
            if is_stale(
                node,
                stale_after_days=self.config.stale_after_days,
                stale_low_confidence_threshold=self.config.stale_low_confidence_threshold,
            ):
                suppressed_stale.append(capsule_id)
                continue
            active_nodes[capsule_id] = node
        return active_nodes, suppressed_stale

    def _filter_conflicts(
        self,
        *,
        active_nodes: dict[str, MemoryCapsuleDetail],
        edges: list[SubgraphEdge],
        why_map: dict[str, str],
    ) -> tuple[dict[str, MemoryCapsuleDetail], list[str]]:
        suppressed_conflicts: list[str] = []
        for edge in edges:
            if edge.relation_type != "CONFLICTS_WITH":
                continue
            source_id = edge.source_capsule_id
            target_id = edge.target_capsule_id
            if source_id not in active_nodes or target_id not in active_nodes:
                continue
            winner, loser = resolve_conflict(
                active_nodes[source_id],
                active_nodes[target_id],
                status_priority=self.config.status_priority,
            )
            if loser.capsule_id in active_nodes:
                active_nodes.pop(loser.capsule_id)
                suppressed_conflicts.append(loser.capsule_id)
                why_map.setdefault(winner.capsule_id, "Preferred over a conflicting older or lower-confidence capsule.")
        return active_nodes, suppressed_conflicts

    def _select_edges(
        self,
        *,
        active_nodes: dict[str, MemoryCapsuleDetail],
        edges: list[SubgraphEdge],
        final_ids: set[str],
        max_edges: int,
    ) -> list[SubgraphEdge]:
        indexed_edges_raw: list[SubgraphEdge] = []
        for edge in sorted(edges, key=lambda item: float(item.score), reverse=True):
            if edge.source_capsule_id not in final_ids or edge.target_capsule_id not in final_ids:
                continue
            source_node = active_nodes[edge.source_capsule_id]
            target_node = active_nodes[edge.target_capsule_id]
            indexed_edges_raw.append(
                SubgraphEdge(
                    source_capsule_id=edge.source_capsule_id,
                    target_capsule_id=edge.target_capsule_id,
                    relation_type=edge.relation_type,
                    score=edge.score,
                    source_rule=edge.source_rule,
                    support_count=edge.support_count,
                    source_title=source_node.title,
                    target_title=target_node.title,
                )
            )
            if len(indexed_edges_raw) >= max_edges:
                break
        return indexed_edges_raw
