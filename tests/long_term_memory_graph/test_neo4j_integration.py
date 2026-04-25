from __future__ import annotations

import os
from datetime import timedelta

import pytest

from experiments.long_term_memory_graph import GraphMemoryConfig, LongTermMemoryGraphPlugin, RecallRequest


def test_live_neo4j_roundtrip_if_env_configured(make_candidate, embedding_provider, sample_now):
    neo4j = pytest.importorskip("neo4j")
    _ = neo4j
    uri = os.getenv("NEO4J_URI")
    if not uri:
        pytest.skip("Neo4j integration test requires NEO4J_URI.")
    username = os.getenv("NEO4J_USERNAME", "")
    password = os.getenv("NEO4J_PASSWORD", "")

    config = GraphMemoryConfig(
        neo4j_uri=uri,
        neo4j_username=username,
        neo4j_password=password,
        embedding_provider=embedding_provider,
        embedding_dimensions=3,
    )
    plugin = LongTermMemoryGraphPlugin(config=config)
    prefix = "neo4j-test-"

    try:
        with plugin.store._session() as session:
            session.run("MATCH (n:MemoryCapsule) WHERE n.capsule_id STARTS WITH $prefix DETACH DELETE n", prefix=prefix).consume()

        candidates = [
            make_candidate(
                f"{prefix}1",
                created_at=sample_now - timedelta(minutes=5),
                summary="Owner approval recorded for alpha deployment.",
                claims=[{"slot": "status", "value": "approved", "polarity": "positive", "scope": "prod", "evidence_ids": ["approval-doc"]}],
                evidence_refs=["approval-doc"],
            ),
            make_candidate(
                f"{prefix}2",
                created_at=sample_now - timedelta(minutes=1),
                summary="Reviewer linked approval evidence to the alpha deployment runbook.",
                claims=[{"slot": "owner", "value": "alice", "polarity": "positive", "scope": "prod", "evidence_ids": ["approval-doc"]}],
                evidence_refs=["approval-doc"],
                source_memory_refs=[f"{prefix}1"],
            ),
        ]
        plugin.store_capsules(candidates)
        response = plugin.recall(RecallRequest(query="alpha deployment approval"))
        assert response.node_index
        details = plugin.fetch_capsule_details([entry.capsule_id for entry in response.node_index])
        assert details.details
    finally:
        with plugin.store._session() as session:
            session.run("MATCH (n:MemoryCapsule) WHERE n.capsule_id STARTS WITH $prefix DETACH DELETE n", prefix=prefix).consume()
        plugin.close()
