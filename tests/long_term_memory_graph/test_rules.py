from __future__ import annotations

from datetime import timedelta

from experiments.long_term_memory_graph.domain.entities import MemoryCapsuleDetail
from experiments.long_term_memory_graph.domain.rules import build_pairwise_edges, build_temporal_edges, deduplicate_edges


def test_rule_builder_emits_expected_edge_types(make_candidate, sample_now):
    older = MemoryCapsuleDetail.model_validate(
        make_candidate(
            "caps-old",
            created_at=sample_now - timedelta(hours=2),
            claims=[{"slot": "status", "value": "enabled", "polarity": "positive", "scope": "prod", "evidence_ids": ["doc-1"]}],
            evidence_refs=["doc-1"],
            source_memory_refs=["caps-seed"],
        ).model_dump()
    )
    current = MemoryCapsuleDetail.model_validate(
        make_candidate(
            "caps-current",
            created_at=sample_now - timedelta(hours=1),
            claims=[{"slot": "status", "value": "disabled", "polarity": "negative", "scope": "prod", "evidence_ids": ["doc-1"]}],
            evidence_refs=["doc-1"],
            source_memory_refs=["caps-seed"],
        ).model_dump()
    )
    newer = MemoryCapsuleDetail.model_validate(
        make_candidate(
            "caps-new",
            created_at=sample_now,
            claims=[{"slot": "status", "value": "approved", "polarity": "positive", "scope": "prod", "evidence_ids": ["doc-2"]}],
            evidence_refs=["doc-2"],
        ).model_dump()
    )

    temporal_edges = build_temporal_edges(current, previous_capsule=older, next_capsule=newer)
    pairwise_edges = build_pairwise_edges(current, older, scope_overlap_threshold=0.4)
    relation_types = {edge.relation_type for edge in [*temporal_edges, *pairwise_edges]}

    assert relation_types == {
        "TEMPORAL_NEXT",
        "SAME_TASK",
        "EVIDENCE_SUPPORTS",
        "SCOPE_OVERLAP",
        "REVISES",
        "CONFLICTS_WITH",
    }


def test_deduplicate_edges_merges_support_count(sample_now):
    edge_a, edge_b = build_temporal_edges(
        MemoryCapsuleDetail.model_validate(
            {
                "capsule_id": "caps-b",
                "thread_id": "thread-1:planner",
                "task_id": "task-1",
                "created_at": sample_now,
                "goal": "goal",
            }
        ),
        previous_capsule=MemoryCapsuleDetail.model_validate(
            {
                "capsule_id": "caps-a",
                "thread_id": "thread-1:planner",
                "task_id": "task-1",
                "created_at": sample_now - timedelta(minutes=1),
                "goal": "goal",
            }
        ),
        next_capsule=MemoryCapsuleDetail.model_validate(
            {
                "capsule_id": "caps-c",
                "thread_id": "thread-1:planner",
                "task_id": "task-1",
                "created_at": sample_now + timedelta(minutes=1),
                "goal": "goal",
            }
        ),
    )
    merged = deduplicate_edges([edge_a, edge_a.model_copy(update={"support_count": 2}), edge_b])

    by_key = {(edge.source_capsule_id, edge.relation_type, edge.target_capsule_id): edge for edge in merged}
    assert by_key[("caps-a", "TEMPORAL_NEXT", "caps-b")].support_count == 3
