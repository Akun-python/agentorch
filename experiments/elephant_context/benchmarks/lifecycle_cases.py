from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..core.models import BenchmarkCollectiveMemory


def _days_ago_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


class LifecycleSharedNoteSeed(BaseModel):
    task_id: str
    content: str
    author_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LifecycleBenchmarkCase(BaseModel):
    case_id: str
    family: Literal["succession", "cross_thread", "promotion_validation", "conflict", "temporal_decay"]
    description: str
    query: str
    knowledge_scope: list[str] = Field(default_factory=lambda: ["planning"])
    source_thread_id: str = "mgcm-source"
    target_thread_id: str = "mgcm-target"
    agent_role: str = "planner"
    collective_memories: list[BenchmarkCollectiveMemory] = Field(default_factory=list)
    candidate_notes: list[LifecycleSharedNoteSeed] = Field(default_factory=list)
    source_goal: str | None = None
    source_output: str | None = None
    expected_present_markers: list[str] = Field(default_factory=list)
    expected_absent_markers: list[str] = Field(default_factory=list)
    validate_record_key: str | None = None
    validate_rounds: int = 0
    deprecate_record_key: str | None = None
    conflict_record_keys: list[str] = Field(default_factory=list)
    conflict_resolution: Literal["supersede", "merge", "keep_both"] | None = None
    temporal_rank_markers: list[str] = Field(default_factory=list)


class LifecycleVariantSpec(BaseModel):
    name: str
    description: str
    category: Literal["baseline", "ablation"] = "ablation"
    persistent_inheritance_enabled: bool = True
    allow_cross_thread_recall: bool = True
    collective_governance_enabled: bool = True
    conflict_resolution_enabled: bool = True
    recency_weight: float = 0.9


def list_lifecycle_variants() -> list[LifecycleVariantSpec]:
    return [
        LifecycleVariantSpec(
            name="mgcm_full",
            description="Full MGCM lifecycle suite with persistence, cross-thread recall, governance, conflict resolution, and temporal decay.",
            category="baseline",
            persistent_inheritance_enabled=True,
            allow_cross_thread_recall=True,
            collective_governance_enabled=True,
            conflict_resolution_enabled=True,
            recency_weight=0.9,
        ),
        LifecycleVariantSpec(
            name="mgcm_thread_local_memory",
            description="Thread-local memory baseline without persistent inheritance, cross-thread recall, governance, conflict resolution, or temporal decay.",
            category="baseline",
            persistent_inheritance_enabled=False,
            allow_cross_thread_recall=False,
            collective_governance_enabled=False,
            conflict_resolution_enabled=False,
            recency_weight=0.0,
        ),
        LifecycleVariantSpec(
            name="mgcm_no_persistent_inheritance",
            description="Ablate persistent inheritance while keeping the rest of MGCM enabled.",
            category="ablation",
            persistent_inheritance_enabled=False,
            allow_cross_thread_recall=True,
            collective_governance_enabled=True,
            conflict_resolution_enabled=True,
            recency_weight=0.9,
        ),
        LifecycleVariantSpec(
            name="mgcm_no_cross_thread",
            description="Disable cross-thread recall while keeping MGCM persistence and governance.",
            category="ablation",
            persistent_inheritance_enabled=True,
            allow_cross_thread_recall=False,
            collective_governance_enabled=True,
            conflict_resolution_enabled=True,
            recency_weight=0.9,
        ),
        LifecycleVariantSpec(
            name="mgcm_no_collective_governance",
            description="Disable collective promotion and validation governance.",
            category="ablation",
            persistent_inheritance_enabled=True,
            allow_cross_thread_recall=True,
            collective_governance_enabled=False,
            conflict_resolution_enabled=True,
            recency_weight=0.9,
        ),
        LifecycleVariantSpec(
            name="mgcm_no_conflict_resolution",
            description="Leave conflicting collective memories unresolved.",
            category="ablation",
            persistent_inheritance_enabled=True,
            allow_cross_thread_recall=True,
            collective_governance_enabled=True,
            conflict_resolution_enabled=False,
            recency_weight=0.9,
        ),
        LifecycleVariantSpec(
            name="mgcm_no_temporal_decay",
            description="Disable recency weighting during long-term memory ranking.",
            category="ablation",
            persistent_inheritance_enabled=True,
            allow_cross_thread_recall=True,
            collective_governance_enabled=True,
            conflict_resolution_enabled=True,
            recency_weight=0.0,
        ),
    ]


def get_lifecycle_variant(name: str) -> LifecycleVariantSpec:
    for variant in list_lifecycle_variants():
        if variant.name == name:
            return variant
    available = ", ".join(variant.name for variant in list_lifecycle_variants())
    raise KeyError(f"Unknown lifecycle variant '{name}'. Available variants: {available}")


def _succession_case(index: int) -> LifecycleBenchmarkCase:
    marker = f"SUCCESSION_ALPHA_{index:02d}"
    deprecated = f"SUCCESSION_OLD_{index:02d}"
    records = [
        BenchmarkCollectiveMemory(
            record_key="primary",
            kind="route",
            content=f"validated succession route marker {marker} safe checkpoint {index:02d}",
            tags=["succession", "route"],
            source_agents=["matriarch"],
            confidence=0.92,
            scope="planning",
        ),
    ]
    if index == 3:
        records.append(
            BenchmarkCollectiveMemory(
                record_key="deprecated",
                kind="route",
                content=f"deprecated succession route marker {deprecated} old checkpoint {index:02d}",
                tags=["succession", "deprecated"],
                source_agents=["matriarch"],
                confidence=0.8,
                scope="planning",
                status="deprecated",
            )
        )
    return LifecycleBenchmarkCase(
        case_id=f"succession_{index:02d}",
        family="succession",
        description="A successor supervisor should recover validated collective memory from persistent storage.",
        query=f"route safe checkpoint {index:02d}",
        source_thread_id=f"succession-thread-{index:02d}",
        target_thread_id=f"succession-successor-{index:02d}",
        collective_memories=records,
        expected_present_markers=[marker],
        expected_absent_markers=[deprecated] if index == 3 else [],
    )


def _cross_thread_case(index: int) -> LifecycleBenchmarkCase:
    marker = f"CROSS_THREAD_SIGMA_{index:02d}"
    goal = f"planning relay {index:02d}"
    output = (
        f"validated cross thread relay marker {marker} for planning relay {index:02d}. "
        f"validated cross thread relay marker {marker} for planning relay {index:02d}. "
        f"validated cross thread relay marker {marker} for planning relay {index:02d}."
    )
    return LifecycleBenchmarkCase(
        case_id=f"cross_thread_{index:02d}",
        family="cross_thread",
        description="Scene-first recall should recover relevant long-term memory across different threads when enabled.",
        query=goal,
        source_goal=goal,
        source_output=output,
        source_thread_id=f"cross-thread-source-{index:02d}",
        target_thread_id=f"cross-thread-target-{index:02d}",
        expected_present_markers=[marker],
    )


def _promotion_case(index: int) -> LifecycleBenchmarkCase:
    promoted = f"PROMOTION_DELTA_{index:02d}"
    validated = f"VALIDATION_DELTA_{index:02d}"
    deprecated = f"DEPRECATION_DELTA_{index:02d}"
    if index == 1:
        return LifecycleBenchmarkCase(
            case_id="promotion_validation_01",
            family="promotion_validation",
            description="Consensus candidate notes should be promoted into validated collective memory.",
            query="caching consensus lesson",
            source_thread_id="promotion-thread-01",
            candidate_notes=[
                LifecycleSharedNoteSeed(
                    task_id="promotion-task-01",
                    author_agent="planner",
                    content=f"consensus caching lesson marker {promoted}",
                    metadata={
                        "collective_candidate": True,
                        "memory_kind": "lesson_learned",
                        "tags": ["caching", "consensus"],
                        "source_agents": ["planner", "reviewer"],
                        "scope": "planning",
                    },
                )
            ],
            expected_present_markers=[promoted],
        )
    if index == 2:
        return LifecycleBenchmarkCase(
            case_id="promotion_validation_02",
            family="promotion_validation",
            description="Validated collective memory should increment reuse_count when revalidated.",
            query="checkpoint validation pattern",
            source_thread_id="promotion-thread-02",
            collective_memories=[
                BenchmarkCollectiveMemory(
                    record_key="validated",
                    kind="lesson_learned",
                    content=f"validated checkpoint pattern marker {validated}",
                    tags=["validation"],
                    source_agents=["planner", "reviewer"],
                    confidence=0.9,
                    scope="planning",
                )
            ],
            expected_present_markers=[validated],
            validate_record_key="validated",
            validate_rounds=2,
        )
    return LifecycleBenchmarkCase(
        case_id="promotion_validation_03",
        family="promotion_validation",
        description="Deprecated collective memory should disappear from default validated retrieval.",
        query="unsafe route deprecation",
        source_thread_id="promotion-thread-03",
        collective_memories=[
            BenchmarkCollectiveMemory(
                record_key="deprecated",
                kind="route",
                content=f"unsafe deprecated route marker {deprecated}",
                tags=["deprecation", "route"],
                source_agents=["planner", "reviewer"],
                confidence=0.82,
                scope="planning",
            )
        ],
        expected_absent_markers=[deprecated],
        deprecate_record_key="deprecated",
    )


def _conflict_case(index: int) -> LifecycleBenchmarkCase:
    resolution = ["supersede", "merge", "keep_both"][index - 1]
    marker_a = f"CONFLICT_LEFT_{index:02d}"
    marker_b = f"CONFLICT_RIGHT_{index:02d}"
    merged = f"CONFLICT_MERGED_{index:02d}"
    return LifecycleBenchmarkCase(
        case_id=f"conflict_{index:02d}",
        family="conflict",
        description="MGCM should resolve conflicting collective memories with explicit governance metadata.",
        query=f"conflict review {index:02d}",
        source_thread_id=f"conflict-thread-{index:02d}",
        collective_memories=[
            BenchmarkCollectiveMemory(
                record_key="left",
                kind="route_rule",
                content=f"left conflict marker {marker_a}",
                tags=["conflict", "left"],
                source_agents=["planner"],
                confidence=0.76,
                scope="planning",
            ),
            BenchmarkCollectiveMemory(
                record_key="right",
                kind="route_rule",
                content=f"right conflict marker {marker_b}",
                tags=["conflict", "right"],
                source_agents=["reviewer"],
                confidence=0.88,
                scope="planning",
            ),
        ],
        expected_present_markers=[marker_a, marker_b] if resolution == "merge" else [marker_b],
        expected_absent_markers=[],
        conflict_record_keys=["left", "right"],
        conflict_resolution=resolution,
        source_output=merged,
    )


def _temporal_decay_case(index: int) -> LifecycleBenchmarkCase:
    recent = f"RECENT_PRIORITY_{index:02d}"
    stale = f"STALE_PRIORITY_{index:02d}"
    return LifecycleBenchmarkCase(
        case_id=f"temporal_decay_{index:02d}",
        family="temporal_decay",
        description="Recency-aware ranking should prioritize recently validated collective memory when relevance is otherwise similar.",
        query=f"temporal priority audit {index:02d}",
        source_thread_id=f"temporal-thread-{index:02d}",
        collective_memories=[
            BenchmarkCollectiveMemory(
                record_key="recent",
                kind="lesson_learned",
                content=f"temporal priority audit {index:02d} marker {recent}",
                tags=["temporal", "recent"],
                source_agents=["planner", "reviewer"],
                confidence=0.9,
                scope="planning",
                reuse_count=1,
                last_validated_at=_days_ago_iso(2),
            ),
            BenchmarkCollectiveMemory(
                record_key="stale",
                kind="lesson_learned",
                content=f"temporal priority audit {index:02d} marker {stale}",
                tags=["temporal", "stale"],
                source_agents=["planner", "reviewer"],
                confidence=0.9,
                scope="planning",
                reuse_count=1,
                last_validated_at=_days_ago_iso(90 + (index * 15)),
            ),
        ],
        expected_present_markers=[recent],
        temporal_rank_markers=[recent, stale],
    )


def list_lifecycle_cases() -> list[LifecycleBenchmarkCase]:
    cases: list[LifecycleBenchmarkCase] = []
    for index in range(1, 4):
        cases.append(_succession_case(index))
        cases.append(_cross_thread_case(index))
        cases.append(_promotion_case(index))
        cases.append(_conflict_case(index))
        cases.append(_temporal_decay_case(index))
    return cases


def get_lifecycle_case(case_id: str) -> LifecycleBenchmarkCase:
    for case in list_lifecycle_cases():
        if case.case_id == case_id:
            return case
    available = ", ".join(case.case_id for case in list_lifecycle_cases())
    raise KeyError(f"Unknown lifecycle case '{case_id}'. Available cases: {available}")


def quick_lifecycle_case_ids() -> list[str]:
    seen: set[str] = set()
    selected: list[str] = []
    for case in list_lifecycle_cases():
        if case.family in seen:
            continue
        seen.add(case.family)
        selected.append(case.case_id)
    return selected


__all__ = [
    "LifecycleBenchmarkCase",
    "LifecycleSharedNoteSeed",
    "LifecycleVariantSpec",
    "get_lifecycle_case",
    "get_lifecycle_variant",
    "list_lifecycle_cases",
    "list_lifecycle_variants",
    "quick_lifecycle_case_ids",
]
