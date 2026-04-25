from __future__ import annotations

from datetime import timedelta

from experiments.long_term_memory_graph import GraphMemoryConfig, LongTermMemoryGraphPlugin, RecallRequest


def test_plugin_recall_progressive_disclosure_and_suppression(fake_store, embedding_provider, make_candidate, sample_now):
    config = GraphMemoryConfig(
        embedding_provider=embedding_provider,
        stale_after_days=10,
        stale_low_confidence_threshold=0.7,
    )
    plugin = LongTermMemoryGraphPlugin(config=config, store=fake_store)

    current = make_candidate(
        "caps-current",
        created_at=sample_now - timedelta(days=1),
        summary="Service alpha deployment requires owner approval and a validated evidence pack.",
        outcome="Deployment checklist prepared with owner approval evidence.",
        claims=[{"slot": "status", "value": "approved", "polarity": "positive", "scope": "prod", "evidence_ids": ["approval-doc"]}],
        evidence_refs=["approval-doc"],
        confidence=0.95,
    )
    support = make_candidate(
        "caps-support",
        created_at=sample_now - timedelta(hours=8),
        summary="Reviewer confirmed the owner approval evidence pack for service alpha deployment.",
        outcome="Evidence pack reviewed and linked to the deployment runbook.",
        claims=[{"slot": "owner", "value": "alice", "polarity": "positive", "scope": "prod", "evidence_ids": ["approval-doc"]}],
        evidence_refs=["approval-doc"],
        source_memory_refs=["caps-current"],
        confidence=0.88,
    )
    stale = make_candidate(
        "caps-stale",
        created_at=sample_now - timedelta(days=90),
        summary="Old deployment note mentioning owner approval for service alpha.",
        outcome="Historic note only.",
        claims=[{"slot": "status", "value": "draft", "polarity": "positive", "scope": "prod", "evidence_ids": ["legacy-doc"]}],
        evidence_refs=["legacy-doc"],
        confidence=0.35,
    )
    conflict_old = make_candidate(
        "caps-conflict",
        created_at=sample_now - timedelta(days=2),
        summary="Earlier note claimed service alpha deployment was blocked.",
        outcome="Older blocker note.",
        claims=[{"slot": "status", "value": "blocked", "polarity": "negative", "scope": "prod", "evidence_ids": ["approval-doc"]}],
        evidence_refs=["approval-doc"],
        confidence=0.55,
    )

    stored_ids = plugin.store_capsules([stale, conflict_old, current, support])
    assert stored_ids == ["caps-stale", "caps-conflict", "caps-current", "caps-support"]
    assert fake_store.schema_created is True

    response = plugin.recall(RecallRequest(query="service alpha deployment owner approval"))
    returned_ids = [entry.capsule_id for entry in response.node_index]

    assert returned_ids
    assert "caps-stale" not in returned_ids
    assert "caps-conflict" not in returned_ids
    assert "caps-support" in returned_ids
    assert "caps-current" in returned_ids
    assert response.retrieval_report.suppressed_stale_nodes == ["caps-stale"]
    assert response.retrieval_report.suppressed_conflict_nodes == ["caps-conflict"]
    assert response.prompt_summary.startswith("Subgraph theme:")
    assert all(entry.index.startswith("N") for entry in response.node_index)
    assert response.edges

    details = plugin.fetch_capsule_details(returned_ids[:2])
    assert len(details.details) == min(2, len(returned_ids))
    assert details.missing_capsule_ids == []
