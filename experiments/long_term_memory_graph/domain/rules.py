from __future__ import annotations

from collections.abc import Iterable

from ..api.models import ClaimSlot
from .entities import GraphEdgeCandidate, MemoryCapsuleDetail
from .utils import jaccard_similarity, now_utc


def _canonical_pair(left_id: str, right_id: str) -> tuple[str, str]:
    """无向语义关系使用稳定 ID 顺序，避免重复边。"""

    return (left_id, right_id) if left_id <= right_id else (right_id, left_id)


def _claim_index(claims: Iterable[ClaimSlot]) -> dict[tuple[str, str], list[ClaimSlot]]:
    """按 slot/scope 聚合主张，便于识别修订和冲突。"""

    index: dict[tuple[str, str], list[ClaimSlot]] = {}
    for claim in claims:
        key = (claim.slot, claim.scope)
        index.setdefault(key, []).append(claim)
    return index


def _share_task(left: MemoryCapsuleDetail, right: MemoryCapsuleDetail) -> tuple[bool, float]:
    """判断两条记忆是否属于同一任务或任务族。"""

    if left.task_id and right.task_id and left.task_id == right.task_id:
        return True, 1.0
    if left.task_family and right.task_family and left.task_family == right.task_family:
        return True, 0.8
    return False, 0.0


def _share_evidence(left: MemoryCapsuleDetail, right: MemoryCapsuleDetail) -> tuple[bool, float, int]:
    """判断两条记忆是否共享证据来源。"""

    overlap = set(left.evidence_refs).intersection(right.evidence_refs)
    overlap.update(set(left.source_memory_refs).intersection(right.source_memory_refs))
    if not overlap:
        return False, 0.0, 0
    denominator = max(1, len(set(left.evidence_refs + left.source_memory_refs + right.evidence_refs + right.source_memory_refs)))
    score = len(overlap) / float(denominator)
    return True, score, len(overlap)


def _scope_overlap(left: MemoryCapsuleDetail, right: MemoryCapsuleDetail, *, threshold: float) -> tuple[bool, float]:
    """用 scope/tag/entity 的 Jaccard 重叠判断场景接近度。"""

    overlap_score = jaccard_similarity(
        left.knowledge_scope + left.tags + left.entities,
        right.knowledge_scope + right.tags + right.entities,
    )
    return overlap_score >= threshold, overlap_score


def _claim_revision_pairs(left: MemoryCapsuleDetail, right: MemoryCapsuleDetail) -> list[tuple[ClaimSlot, ClaimSlot]]:
    """同任务同 slot 但 value 不同时，视作可能的版本修订。"""

    if not (left.claims and right.claims):
        return []
    shared_task, _ = _share_task(left, right)
    same_goal = bool(left.goal and right.goal and left.goal.lower() == right.goal.lower())
    if not shared_task and not same_goal:
        return []
    left_index = _claim_index(left.claims)
    right_index = _claim_index(right.claims)
    revisions: list[tuple[ClaimSlot, ClaimSlot]] = []
    for key in set(left_index).intersection(right_index):
        for left_claim in left_index[key]:
            for right_claim in right_index[key]:
                if left_claim.value and right_claim.value and left_claim.value != right_claim.value:
                    revisions.append((left_claim, right_claim))
    return revisions


def _claims_conflict(left: ClaimSlot, right: ClaimSlot) -> bool:
    """判断两个主张是否构成直接冲突。"""

    if left.slot != right.slot or left.scope != right.scope:
        return False
    if left.polarity and right.polarity and left.polarity != right.polarity:
        return True
    return bool(left.value and right.value and left.value != right.value)


def build_temporal_edges(
    current: MemoryCapsuleDetail,
    *,
    previous_capsule: MemoryCapsuleDetail | None,
    next_capsule: MemoryCapsuleDetail | None,
) -> list[GraphEdgeCandidate]:
    """给同一线程族中的相邻记忆建立时间顺序边。"""

    edges: list[GraphEdgeCandidate] = []
    timestamp = now_utc()
    if previous_capsule is not None:
        edges.append(
            GraphEdgeCandidate(
                source_capsule_id=previous_capsule.capsule_id,
                relation_type="TEMPORAL_NEXT",
                target_capsule_id=current.capsule_id,
                score=1.0,
                created_at=timestamp,
                source_rule="temporal_nearest_previous",
                support_count=1,
            )
        )
    if next_capsule is not None:
        edges.append(
            GraphEdgeCandidate(
                source_capsule_id=current.capsule_id,
                relation_type="TEMPORAL_NEXT",
                target_capsule_id=next_capsule.capsule_id,
                score=1.0,
                created_at=timestamp,
                source_rule="temporal_nearest_next",
                support_count=1,
            )
        )
    return edges


def build_pairwise_edges(
    current: MemoryCapsuleDetail,
    other: MemoryCapsuleDetail,
    *,
    scope_overlap_threshold: float,
) -> list[GraphEdgeCandidate]:
    """根据任务、证据、范围和主张关系生成成对边。"""

    if current.capsule_id == other.capsule_id:
        return []
    edges: list[GraphEdgeCandidate] = []
    timestamp = now_utc()

    shares_task, same_task_score = _share_task(current, other)
    if shares_task:
        source_id, target_id = _canonical_pair(current.capsule_id, other.capsule_id)
        edges.append(
            GraphEdgeCandidate(
                source_capsule_id=source_id,
                relation_type="SAME_TASK",
                target_capsule_id=target_id,
                score=same_task_score,
                created_at=timestamp,
                source_rule="same_task_identity",
                support_count=1,
            )
        )

    shares_evidence, evidence_score, support_count = _share_evidence(current, other)
    if shares_evidence:
        source_id, target_id = _canonical_pair(current.capsule_id, other.capsule_id)
        edges.append(
            GraphEdgeCandidate(
                source_capsule_id=source_id,
                relation_type="EVIDENCE_SUPPORTS",
                target_capsule_id=target_id,
                score=evidence_score,
                created_at=timestamp,
                source_rule="evidence_overlap",
                support_count=support_count,
            )
        )

    overlaps_scope, scope_score = _scope_overlap(current, other, threshold=scope_overlap_threshold)
    if overlaps_scope:
        source_id, target_id = _canonical_pair(current.capsule_id, other.capsule_id)
        edges.append(
            GraphEdgeCandidate(
                source_capsule_id=source_id,
                relation_type="SCOPE_OVERLAP",
                target_capsule_id=target_id,
                score=scope_score,
                created_at=timestamp,
                source_rule="scope_jaccard",
                support_count=max(1, int(scope_score * 10)),
            )
        )

    revisions = _claim_revision_pairs(current, other)
    if revisions:
        newer, older = (current, other) if current.created_at >= other.created_at else (other, current)
        edges.append(
            GraphEdgeCandidate(
                source_capsule_id=newer.capsule_id,
                relation_type="REVISES",
                target_capsule_id=older.capsule_id,
                score=min(1.0, 0.6 + 0.1 * len(revisions)),
                created_at=timestamp,
                source_rule="claim_slot_revision",
                support_count=len(revisions),
            )
        )

    current_claims = _claim_index(current.claims)
    other_claims = _claim_index(other.claims)
    conflict_count = 0
    for key in set(current_claims).intersection(other_claims):
        for left_claim in current_claims[key]:
            for right_claim in other_claims[key]:
                if _claims_conflict(left_claim, right_claim):
                    conflict_count += 1
    if conflict_count:
        source_id, target_id = _canonical_pair(current.capsule_id, other.capsule_id)
        edges.append(
            GraphEdgeCandidate(
                source_capsule_id=source_id,
                relation_type="CONFLICTS_WITH",
                target_capsule_id=target_id,
                score=min(1.0, 0.6 + 0.1 * conflict_count),
                created_at=timestamp,
                source_rule="claim_slot_conflict",
                support_count=conflict_count,
            )
        )

    return edges


def deduplicate_edges(edges: Iterable[GraphEdgeCandidate]) -> list[GraphEdgeCandidate]:
    """合并重复边，保留更高分并累计支持数。"""

    merged: dict[tuple[str, str, str], GraphEdgeCandidate] = {}
    for edge in edges:
        key = (edge.source_capsule_id, edge.relation_type, edge.target_capsule_id)
        existing = merged.get(key)
        if existing is None:
            merged[key] = edge
            continue
        if edge.score > existing.score:
            merged[key] = edge
        else:
            existing.support_count += edge.support_count
    return list(merged.values())
