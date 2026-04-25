from __future__ import annotations

import pytest

from experiments.long_term_memory_graph import GraphMemoryConfig
from experiments.long_term_memory_graph.api.models import ClaimSlot


def test_claim_slot_and_scene_hash_normalization(make_candidate, sample_now):
    candidate = make_candidate(
        "caps-1",
        created_at=sample_now,
        thread_id="thread-1:planner",
        task_id="task-1:planner",
        goal=" Ship Feature ",
        knowledge_scope=[" Ops ", "ops"],
        tags=["Deploy", "deploy"],
        entities=["Service-A", "service-a"],
        claims=[
            {
                "slot": "Status",
                "value": "Enabled",
                "polarity": "POSITIVE",
                "scope": "PROD",
                "evidence_ids": [{"doc": "A"}, {"doc": "A"}],
            }
        ],
    )
    normalized = make_candidate(
        "caps-2",
        created_at=sample_now,
        thread_id="thread-1:planner",
        task_id="task-1:planner",
        goal="ship feature",
        knowledge_scope=["ops"],
        tags=["deploy"],
        entities=["service-a"],
        claims=[
            {
                "slot": "status",
                "value": "enabled",
                "polarity": "positive",
                "scope": "prod",
                "evidence_ids": [{"doc": "A"}],
            }
        ],
    )

    assert candidate.agent_id == "planner"
    assert candidate.thread_family == "thread-1"
    assert candidate.task_family == "task-1"
    assert candidate.claims[0] == ClaimSlot(slot="status", value="enabled", polarity="positive", scope="prod", evidence_ids=["doc=a"])
    assert candidate.computed_scene_hash() == normalized.computed_scene_hash()


def test_graph_memory_config_validates_ranges(embedding_provider):
    GraphMemoryConfig(embedding_provider=embedding_provider, top_candidates=6, top_seeds=3, max_nodes=12, max_edges=24)

    with pytest.raises(ValueError, match="top_candidates must be >= top_seeds"):
        GraphMemoryConfig(embedding_provider=embedding_provider, top_candidates=2, top_seeds=3)

    with pytest.raises(ValueError, match="embedding_dimensions must be > 0"):
        GraphMemoryConfig(embedding_provider=embedding_provider, embedding_dimensions=0)
