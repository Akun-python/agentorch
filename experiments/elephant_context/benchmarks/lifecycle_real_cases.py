from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..core.models import BenchmarkCollectiveMemory
from .lifecycle_cases import LifecycleBenchmarkCase, LifecycleSharedNoteSeed


def _days_ago_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def list_real_lifecycle_cases() -> list[LifecycleBenchmarkCase]:
    return [
        LifecycleBenchmarkCase(
            case_id="succession_real_01",
            family="succession",
            description="Successor should recover validated protocol fact from persistent collective memory.",
            query="validated protocol rfc number",
            source_thread_id="succession-real-source-01",
            target_thread_id="succession-real-target-01",
            collective_memories=[
                BenchmarkCollectiveMemory(
                    record_key="primary",
                    kind="protocol_fact",
                    content="Validated protocol fact: IPv4 is defined in RFC 791.",
                    tags=["protocol", "ipv4", "validated"],
                    source_agents=["matriarch"],
                    confidence=0.92,
                    scope="planning",
                )
            ],
            expected_present_markers=["RFC 791"],
        ),
        LifecycleBenchmarkCase(
            case_id="cross_thread_real_01",
            family="cross_thread",
            description="Cross-thread recall should recover validated public fact from prior episode.",
            query="first crewed moon landing",
            source_goal="first crewed moon landing",
            source_output="validated historical marker 1969 for first crewed moon landing.",
            source_thread_id="cross-real-source-01",
            target_thread_id="cross-real-target-01",
            expected_present_markers=["1969"],
        ),
        LifecycleBenchmarkCase(
            case_id="promotion_validation_real_01",
            family="promotion_validation",
            description="Consensus public-science note should be promoted into validated collective memory.",
            query="penicillin discoverer",
            source_thread_id="promotion-real-thread-01",
            candidate_notes=[
                LifecycleSharedNoteSeed(
                    task_id="promotion-real-task-01",
                    author_agent="planner",
                    content="Consensus marker: penicillin discoverer is Alexander Fleming.",
                    metadata={
                        "collective_candidate": True,
                        "memory_kind": "public_fact",
                        "tags": ["history_of_science"],
                        "source_agents": ["planner", "reviewer"],
                        "scope": "planning",
                    },
                )
            ],
            expected_present_markers=["Alexander Fleming"],
        ),
        LifecycleBenchmarkCase(
            case_id="conflict_real_01",
            family="conflict",
            description="Conflict resolution should keep newer validated paper venue fact.",
            query="transformer paper venue",
            source_thread_id="conflict-real-thread-01",
            collective_memories=[
                BenchmarkCollectiveMemory(
                    record_key="left",
                    kind="paper_fact",
                    content="Conflicting claim marker VENUE_WRONG: Transformer paper venue was ICLR 2017.",
                    tags=["conflict", "left"],
                    source_agents=["planner"],
                    confidence=0.7,
                    scope="planning",
                ),
                BenchmarkCollectiveMemory(
                    record_key="right",
                    kind="paper_fact",
                    content="Validated claim marker VENUE_RIGHT: Transformer paper venue was NeurIPS 2017.",
                    tags=["conflict", "right"],
                    source_agents=["reviewer"],
                    confidence=0.9,
                    scope="planning",
                ),
            ],
            expected_present_markers=["VENUE_RIGHT"],
            conflict_record_keys=["left", "right"],
            conflict_resolution="supersede",
        ),
        LifecycleBenchmarkCase(
            case_id="temporal_decay_real_01",
            family="temporal_decay",
            description="Recency-weighted ranking should prioritize recently validated safety protocol.",
            query="recent emergency protocol revision",
            source_thread_id="temporal-real-thread-01",
            collective_memories=[
                BenchmarkCollectiveMemory(
                    record_key="recent",
                    kind="safety_protocol",
                    content="recent emergency protocol revision marker RECENT_PROTOCOL_v3",
                    tags=["temporal", "recent"],
                    source_agents=["planner", "reviewer"],
                    confidence=0.9,
                    scope="planning",
                    reuse_count=1,
                    last_validated_at=_days_ago_iso(1),
                ),
                BenchmarkCollectiveMemory(
                    record_key="stale",
                    kind="safety_protocol",
                    content="recent emergency protocol revision marker STALE_PROTOCOL_v1",
                    tags=["temporal", "stale"],
                    source_agents=["planner", "reviewer"],
                    confidence=0.9,
                    scope="planning",
                    reuse_count=1,
                    last_validated_at=_days_ago_iso(120),
                ),
            ],
            expected_present_markers=["RECENT_PROTOCOL_v3"],
            temporal_rank_markers=["RECENT_PROTOCOL_v3", "STALE_PROTOCOL_v1"],
        ),
    ]


def get_real_lifecycle_case(case_id: str) -> LifecycleBenchmarkCase:
    for case in list_real_lifecycle_cases():
        if case.case_id == case_id:
            return case
    available = ", ".join(case.case_id for case in list_real_lifecycle_cases())
    raise KeyError(f"Unknown real-task lifecycle case '{case_id}'. Available cases: {available}")


__all__ = ["get_real_lifecycle_case", "list_real_lifecycle_cases"]
