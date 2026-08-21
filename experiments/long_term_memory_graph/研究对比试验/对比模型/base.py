from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ...api.models import MemoryCapsuleCandidate
from ...core.schemas import ExperimentCase, RetrievalResult


OFFICIAL_SDK_BOUNDARY = "official_sdk"


@dataclass(frozen=True)
class OfficialBaselineProbe:
    """官方 baseline 的可用性探测结果。"""

    enabled: bool
    ready: bool
    reason: str = ""


def build_scope_id(*, case: ExperimentCase, method: str, seed: int, prefix: str) -> str:
    """为第三方 SDK 构造隔离命名空间，避免不同 case 污染。"""

    payload = f"{prefix}:{method}:{case.case_id}:{seed}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def format_capsule_text(capsule: MemoryCapsuleCandidate) -> str:
    """把记忆胶囊格式化成第三方 SDK 可写入的文本。"""

    lines = [
        f"capsule_id: {capsule.capsule_id}",
        f"goal: {capsule.goal}",
        f"summary: {capsule.summary}",
        f"outcome: {capsule.outcome}",
        f"created_at: {capsule.created_at.isoformat()}",
    ]
    if capsule.task_id:
        lines.append(f"task_id: {capsule.task_id}")
    if capsule.thread_id:
        lines.append(f"thread_id: {capsule.thread_id}")
    if capsule.knowledge_scope:
        lines.append(f"knowledge_scope: {', '.join(capsule.knowledge_scope)}")
    if capsule.tags:
        lines.append(f"tags: {', '.join(capsule.tags)}")
    if capsule.entities:
        lines.append(f"entities: {', '.join(capsule.entities)}")
    if capsule.claims:
        claim_text = "; ".join(f"{claim.slot}={claim.value}" for claim in capsule.claims)
        lines.append(f"claims: {claim_text}")
    return "\n".join(lines)


def build_capsule_metadata(capsule: MemoryCapsuleCandidate) -> dict[str, object]:
    """把胶囊关键字段保存在第三方 SDK metadata 中。"""

    return {
        "capsule_id": capsule.capsule_id,
        "summary": capsule.summary,
        "goal": capsule.goal,
        "outcome": capsule.outcome,
        "task_id": capsule.task_id,
        "thread_id": capsule.thread_id,
        "thread_family": capsule.thread_family,
        "task_family": capsule.task_family,
        "knowledge_scope": list(capsule.knowledge_scope),
        "tags": list(capsule.tags),
        "entities": list(capsule.entities),
        "status": capsule.status,
        "confidence": capsule.confidence,
        "created_at": capsule.created_at.isoformat(),
    }


def build_official_result(
    *,
    method: str,
    variant: str,
    summary_prefix: str,
    hits: list[dict[str, object]],
    latency_ms: float,
) -> RetrievalResult:
    """把官方 SDK 检索结果转换成统一 RetrievalResult。"""

    lines = [summary_prefix]
    returned_capsule_ids: list[str] = []
    for hit in hits[:6]:
        capsule_id = str(hit.get("capsule_id", "")).strip()
        text = str(hit.get("text", "")).strip()
        if not capsule_id:
            continue
        returned_capsule_ids.append(capsule_id)
        lines.append(f"[{capsule_id}] {text}")
    return RetrievalResult(
        method=method,
        variant=variant,
        prompt_summary="\n".join(lines),
        returned_capsule_ids=returned_capsule_ids,
        returned_relation_types=[],
        returned_edge_keys=[],
        suppressed_stale_nodes=[],
        suppressed_conflict_nodes=[],
        detail_lookup_capsule_ids=[],
        detail_lookup_hit_count=0,
        detail_lookup_missing_count=0,
        detail_lookup_latency_ms=0.0,
        latency_breakdown={"total_ms": round(latency_ms, 4)},
        latency_ms=latency_ms,
        source_boundary=OFFICIAL_SDK_BOUNDARY,
        is_proxy=False,
    )
