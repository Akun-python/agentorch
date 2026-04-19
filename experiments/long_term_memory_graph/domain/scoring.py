from __future__ import annotations

import math

from ..api.models import RecallRequest
from .entities import MemoryCapsuleDetail
from .utils import ensure_utc_datetime, jaccard_similarity, now_utc, stable_hash, to_iso8601, truncate_text


def build_fulltext_query(request: RecallRequest) -> str:
    terms = [request.query, *request.tags, *request.entities, *request.knowledge_scope]
    text = " ".join(item for item in terms if item)
    return truncate_text(text, max_chars=240)


def scene_match(request: RecallRequest, node: MemoryCapsuleDetail, *, weight: float) -> float:
    score = 0.0
    if request.thread_family and node.thread_family == request.thread_family:
        score += 0.5
    if request.task_family and node.task_family == request.task_family:
        score += 0.5
    overlap = jaccard_similarity(
        request.knowledge_scope + request.tags + request.entities,
        node.knowledge_scope + node.tags + node.entities,
    )
    score += overlap
    return score * weight


def build_selection_reason(
    *,
    semantic_score: float,
    lexical_score: float,
    scene_score: float,
    confidence: float,
    reuse_count: int,
) -> str:
    reasons: list[str] = []
    if semantic_score > 0:
        reasons.append("vector match")
    if lexical_score > 0:
        reasons.append("fulltext match")
    if scene_score > 0:
        reasons.append("scene alignment")
    if confidence >= 0.8:
        reasons.append("high confidence")
    if reuse_count > 0:
        reasons.append("previously reused")
    return ", ".join(reasons) if reasons else "recalled through graph expansion"


def is_stale(
    node: MemoryCapsuleDetail,
    *,
    stale_after_days: int,
    stale_low_confidence_threshold: float,
) -> bool:
    reference_time = ensure_utc_datetime(node.last_validated_at or node.created_at)
    age_days = (now_utc() - reference_time).days
    return age_days >= stale_after_days and float(node.confidence) < stale_low_confidence_threshold


def stale_penalty(
    node: MemoryCapsuleDetail,
    *,
    blocked_statuses: tuple[str, ...],
    stale_after_days: int,
    stale_low_confidence_threshold: float,
    penalty_weight: float,
) -> float:
    if node.status in blocked_statuses:
        return 100.0
    if not is_stale(
        node,
        stale_after_days=stale_after_days,
        stale_low_confidence_threshold=stale_low_confidence_threshold,
    ):
        return 0.0
    age_days = (now_utc() - ensure_utc_datetime(node.last_validated_at or node.created_at)).days
    return max(0.0, age_days / max(1, stale_after_days)) * penalty_weight


def resolve_conflict(
    left: MemoryCapsuleDetail,
    right: MemoryCapsuleDetail,
    *,
    status_priority: dict[str, int],
) -> tuple[MemoryCapsuleDetail, MemoryCapsuleDetail]:
    left_status = status_priority.get(left.status, 1)
    right_status = status_priority.get(right.status, 1)
    if left_status != right_status:
        return (left, right) if left_status > right_status else (right, left)
    left_time = ensure_utc_datetime(left.last_validated_at or left.created_at)
    right_time = ensure_utc_datetime(right.last_validated_at or right.created_at)
    if left_time != right_time:
        return (left, right) if left_time > right_time else (right, left)
    if float(left.confidence) != float(right.confidence):
        return (left, right) if float(left.confidence) > float(right.confidence) else (right, left)
    left_hash = stable_hash({"capsule_id": left.capsule_id, "time": to_iso8601(left_time)})
    right_hash = stable_hash({"capsule_id": right.capsule_id, "time": to_iso8601(right_time)})
    return (left, right) if left_hash >= right_hash else (right, left)


def reuse_component(reuse_count: int, *, weight: float) -> float:
    return math.log1p(max(0, int(reuse_count))) * weight
