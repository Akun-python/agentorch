from __future__ import annotations

import json
import sqlite3

from experiments.long_term_memory_graph import AgentOrchBridge, GraphMemoryConfig, LongTermMemoryGraphPlugin
from experiments.long_term_memory_graph.api.models import RecallResponse
from experiments.long_term_memory_graph.domain.entities import MemoryCapsuleDetail
from experiments.long_term_memory_graph.domain.utils import now_utc
from experiments.long_term_memory_graph.integrations.backfill import load_sqlite_backfill_candidates


def test_backfill_loader_imports_supported_records(tmp_path):
    db_path = tmp_path / "records.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        rows = [
            (
                "thread-a:planner",
                "episodic_capsule",
                "Deployment review capsule",
                json.dumps(["episodic"]),
                json.dumps({"goal": "Deploy alpha", "task_id": "task-a", "agent_role": "planner", "confidence": 0.8}),
            ),
            (
                "thread-a:reviewer",
                "semantic_memory",
                "Alpha deployment needs approval",
                json.dumps(["semantic"]),
                json.dumps({"goal": "Deploy alpha", "task_id": "task-a", "agent_role": "reviewer", "evidence_refs": [{"doc": "approval"}]}),
            ),
            (
                "thread-b",
                "lesson_learned",
                "Escalate approval checks early",
                json.dumps(["lesson"]),
                json.dumps({"source_agents": ["planner", "reviewer"], "status": "validated"}),
            ),
        ]
        conn.executemany(
            "INSERT INTO records(thread_id, kind, content, tags, metadata) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()

    candidates, report = load_sqlite_backfill_candidates(str(db_path))

    assert report.imported_capsules == 3
    assert report.imported_by_kind == {
        "episodic_capsule": 1,
        "semantic_memory": 1,
        "lesson_learned": 1,
    }
    assert all(candidate.capsule_id.startswith("legacy-") for candidate in candidates)
    assert any("legacy_sqlite_backfill" in candidate.tags for candidate in candidates)
    assert all(not candidate.claims for candidate in candidates)


def test_backfill_plugin_skips_non_deterministic_revision_edges(tmp_path, embedding_provider, fake_store):
    db_path = tmp_path / "records.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.executemany(
            "INSERT INTO records(thread_id, kind, content, tags, metadata) VALUES (?, ?, ?, ?, ?)",
            [
                ("thread-a:planner", "episodic_capsule", "Deployment review capsule", json.dumps(["episodic"]), json.dumps({"goal": "Deploy alpha"})),
                ("thread-a:reviewer", "semantic_memory", "Alpha deployment needs approval", json.dumps(["semantic"]), json.dumps({"goal": "Deploy alpha"})),
            ],
        )
        conn.commit()

    plugin = LongTermMemoryGraphPlugin(
        config=GraphMemoryConfig(embedding_provider=embedding_provider),
        store=fake_store,
    )
    plugin.backfill_from_sqlite(str(db_path))
    relation_types = {edge.relation_type for edge in plugin.store.edges.values()}
    assert "REVISES" not in relation_types
    assert "CONFLICTS_WITH" not in relation_types


def test_agentorch_bridge_builds_retrieval_report(make_candidate, embedding_provider, fake_store):
    response = RecallResponse.model_validate(
        {
            "prompt_summary": "Subgraph theme: deploy, approval.",
            "node_index": [
                {
                    "index": "N1",
                    "capsule_id": "caps-1",
                    "title": "Deploy alpha",
                    "score": 2.4,
                    "why_selected": "vector match, scene alignment",
                }
            ],
            "edges": [],
            "retrieval_report": {
                "candidate_count": 4,
                "expansion_hops": 1,
                "suppressed_stale_nodes": [],
                "suppressed_conflict_nodes": [],
            },
        }
    )
    details = LongTermMemoryGraphPlugin(
        config=GraphMemoryConfig(embedding_provider=embedding_provider),
        store=fake_store,
    ).fetch_capsule_details([])
    details.details = [
        MemoryCapsuleDetail.model_validate(
            make_candidate(
                "caps-1",
                created_at=now_utc(),
                summary="Deployment capsule for alpha.",
            ).model_dump()
        )
    ]

    bridge = AgentOrchBridge()
    report = bridge.to_retrieval_report(response, details=details)

    assert report.evidence
    assert report.evidence[0].citation.document_id == "caps-1"
    assert report.metadata["detail_available"] is True
