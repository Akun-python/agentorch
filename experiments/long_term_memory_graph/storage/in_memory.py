from __future__ import annotations

from collections import Counter

from ..domain.entities import GraphEdgeCandidate, MemoryCapsuleDetail, SearchHit, SubgraphEdge
from ..domain.utils import now_utc


class InMemoryGraphStore:
    """内存图存储，供实验、测试和无 Neo4j 场景使用。"""

    def __init__(self) -> None:
        self.nodes: dict[str, MemoryCapsuleDetail] = {}
        self.edges: dict[tuple[str, str, str], GraphEdgeCandidate] = {}
        self.schema_created = False

    def ensure_schema(self) -> None:
        """内存实现不建真实索引，只记录 schema 已初始化。"""

        self.schema_created = True

    def close(self) -> None:
        """保持和 Neo4j 存储一致的关闭接口。"""

        return None

    def upsert_capsule(
        self,
        capsule: MemoryCapsuleDetail,
        *,
        summary_embedding: list[float] | None,
        scene_hash: str,
    ) -> MemoryCapsuleDetail:
        """插入或更新记忆胶囊。"""

        existing = self.nodes.get(capsule.capsule_id)
        payload = capsule.model_copy(deep=True)
        payload.scene_hash = scene_hash
        payload.summary_embedding = summary_embedding
        if existing is not None:
            payload.reuse_count = existing.reuse_count
            payload.last_validated_at = existing.last_validated_at
        self.nodes[payload.capsule_id] = payload
        return payload

    def fetch_temporal_neighbors(self, capsule: MemoryCapsuleDetail) -> tuple[MemoryCapsuleDetail | None, MemoryCapsuleDetail | None]:
        """查同一线程族里时间上最近的前后节点。"""

        family_nodes = sorted(
            [item for item in self.nodes.values() if item.thread_family == capsule.thread_family and item.capsule_id != capsule.capsule_id],
            key=lambda item: item.created_at,
        )
        previous = None
        following = None
        for node in family_nodes:
            if node.created_at < capsule.created_at:
                previous = node
            elif node.created_at > capsule.created_at and following is None:
                following = node
        return previous, following

    def fetch_rule_neighbors(self, capsule: MemoryCapsuleDetail, *, limit: int) -> list[MemoryCapsuleDetail]:
        """按任务、标签、实体和证据引用找规则邻居。"""

        neighbors: list[MemoryCapsuleDetail] = []
        for node in self.nodes.values():
            if node.capsule_id == capsule.capsule_id:
                continue
            if (
                (capsule.thread_family and node.thread_family == capsule.thread_family)
                or (capsule.task_id and node.task_id == capsule.task_id)
                or (capsule.task_family and node.task_family == capsule.task_family)
                or set(capsule.tags).intersection(node.tags)
                or set(capsule.entities).intersection(node.entities)
                or set(capsule.evidence_refs).intersection(node.evidence_refs)
                or set(capsule.source_memory_refs).intersection(node.source_memory_refs)
            ):
                neighbors.append(node)
        neighbors.sort(key=lambda item: item.created_at, reverse=True)
        return neighbors[:limit]

    def upsert_edges(self, edges: list[GraphEdgeCandidate]) -> None:
        """写入或覆盖边。"""

        for edge in edges:
            self.edges[(edge.source_capsule_id, edge.relation_type, edge.target_capsule_id)] = edge

    def query_vector(self, embedding: list[float], *, limit: int) -> list[SearchHit]:
        """用简化向量重叠模拟语义检索。"""

        def score(node: MemoryCapsuleDetail) -> float:
            if not node.summary_embedding:
                return 0.0
            return sum(min(left, right) for left, right in zip(embedding, node.summary_embedding))

        ranked = sorted(self.nodes.values(), key=score, reverse=True)[:limit]
        return [SearchHit(node=node, score=score(node)) for node in ranked if score(node) > 0]

    def query_fulltext(self, query_text: str, *, limit: int) -> list[SearchHit]:
        """用词面包含关系模拟全文检索。"""

        tokens = {item for item in query_text.lower().split() if item}

        def score(node: MemoryCapsuleDetail) -> float:
            haystack = " ".join([node.goal, node.summary, " ".join(node.tags), " ".join(node.entities)]).lower()
            return float(sum(1 for token in tokens if token in haystack))

        ranked = sorted(self.nodes.values(), key=score, reverse=True)[:limit]
        return [SearchHit(node=node, score=score(node)) for node in ranked if score(node) > 0]

    def fetch_conflict_counts(self, capsule_ids: list[str]) -> dict[str, int]:
        """统计每个节点关联的冲突边数量。"""

        counts: Counter[str] = Counter()
        for edge in self.edges.values():
            if edge.relation_type != "CONFLICTS_WITH":
                continue
            if edge.source_capsule_id in capsule_ids:
                counts[edge.source_capsule_id] += 1
            if edge.target_capsule_id in capsule_ids:
                counts[edge.target_capsule_id] += 1
        return {capsule_id: counts[capsule_id] for capsule_id in capsule_ids}

    def fetch_capsules(self, capsule_ids: list[str]) -> list[MemoryCapsuleDetail]:
        """按 ID 批量取节点。"""

        return [self.nodes[capsule_id] for capsule_id in capsule_ids if capsule_id in self.nodes]

    def fetch_one_hop_subgraph(self, seed_ids: list[str], *, edge_limit: int) -> tuple[list[MemoryCapsuleDetail], list[SubgraphEdge]]:
        """围绕种子节点取一跳子图。"""

        node_ids = set(seed_ids)
        edges: list[SubgraphEdge] = []
        for edge in sorted(self.edges.values(), key=lambda item: item.score, reverse=True):
            if edge.source_capsule_id in seed_ids or edge.target_capsule_id in seed_ids:
                edges.append(
                    SubgraphEdge(
                        source_capsule_id=edge.source_capsule_id,
                        target_capsule_id=edge.target_capsule_id,
                        relation_type=edge.relation_type,
                        score=edge.score,
                        source_rule=edge.source_rule,
                        support_count=edge.support_count,
                    )
                )
                node_ids.add(edge.source_capsule_id)
                node_ids.add(edge.target_capsule_id)
            if len(edges) >= edge_limit:
                break
        return self.fetch_capsules(sorted(node_ids)), edges

    def mark_recalled(self, capsule_ids: list[str]) -> None:
        """记录节点被召回，更新复用次数和验证时间。"""

        for capsule_id in capsule_ids:
            if capsule_id not in self.nodes:
                continue
            node = self.nodes[capsule_id]
            node.reuse_count += 1
            node.last_validated_at = now_utc()
