"""Tests for MGCM persistence, governance, conflict resolution, and temporal decay."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentorch import AgentRegistry, MemoryManager, Supervisor
from agentorch.agents.types import SharedNote, TaskPacket
from agentorch.memory import RelevanceOnlyDecayPolicy


def _memory_config(tmp_path: Path, name: str):
    from agentorch.config import MemoryConfig

    return MemoryConfig(
        checkpoint_path=tmp_path / f"{name}_checkpoints.db",
        record_path=tmp_path / f"{name}_records.db",
    )


@pytest.fixture
def agent_registry() -> AgentRegistry:
    return AgentRegistry()


def test_matriarch_succession_uses_thread_metadata_for_retrieval(tmp_path: Path, agent_registry: AgentRegistry):
    asyncio.run(_test_matriarch_succession_uses_thread_metadata_for_retrieval(tmp_path, agent_registry))


async def _test_matriarch_succession_uses_thread_metadata_for_retrieval(tmp_path: Path, agent_registry: AgentRegistry):
    memory = MemoryManager(config=_memory_config(tmp_path, "succession"))
    thread_id = "mgcm-herd-thread"
    record_id = await memory.promote_collective_memory(
        thread_id=thread_id,
        kind="route",
        content="follow the dry riverbed to reach the safe checkpoint",
        tags=["route", "hazard"],
        source_agents=["elder"],
        confidence=0.85,
        scope="planning",
    )

    successor = Supervisor(registry=agent_registry)
    task = TaskPacket(
        task_id="successor-task",
        goal="plan route to checkpoint",
        knowledge_scope=["planning"],
        metadata={"thread_id": thread_id},
    )
    recovered = await successor.retrieve_collective_knowledge(task, memory, limit=10)

    assert any(item["id"] == record_id for item in recovered)
    assert any("dry riverbed" in item["content"] for item in recovered)


def test_supervisor_cross_thread_collective_lookup_can_be_enabled(tmp_path: Path, agent_registry: AgentRegistry):
    asyncio.run(_test_supervisor_cross_thread_collective_lookup_can_be_enabled(tmp_path, agent_registry))


async def _test_supervisor_cross_thread_collective_lookup_can_be_enabled(tmp_path: Path, agent_registry: AgentRegistry):
    memory = MemoryManager(config=_memory_config(tmp_path, "cross_thread"))
    record_id = await memory.promote_collective_memory(
        thread_id="original-thread",
        kind="lesson_learned",
        content="always validate input before processing",
        tags=["validation"],
        source_agents=["reviewer", "planner"],
        confidence=0.9,
        scope="planning",
    )

    supervisor = Supervisor(registry=agent_registry)
    task = TaskPacket(
        task_id="new-thread-task",
        goal="validate and process input",
        knowledge_scope=["planning"],
        metadata={"thread_id": "other-thread", "allow_cross_thread_recall": True},
    )
    recovered = await supervisor.retrieve_collective_knowledge(task, memory, limit=10)

    assert any(item["id"] == record_id for item in recovered)


def test_supervisor_governs_candidate_notes_and_promotes_consensus(tmp_path: Path, agent_registry: AgentRegistry):
    asyncio.run(_test_supervisor_governs_candidate_notes_and_promotes_consensus(tmp_path, agent_registry))


async def _test_supervisor_governs_candidate_notes_and_promotes_consensus(tmp_path: Path, agent_registry: AgentRegistry):
    memory = MemoryManager(config=_memory_config(tmp_path, "promotion"))
    supervisor = Supervisor(registry=agent_registry)
    thread_id = "promotion-thread"
    candidates = [
        SharedNote(
            note_id="promotion-note-1",
            task_id="task-1",
            author_agent="planner",
            content="use caching to improve performance",
            metadata={
                "collective_candidate": True,
                "memory_kind": "optimization",
                "tags": ["performance", "caching"],
                "source_agents": ["planner", "reviewer"],
                "scope": "planning",
            },
        ),
        SharedNote(
            note_id="promotion-note-2",
            task_id="task-2",
            author_agent="planner",
            content="low confidence note",
            metadata={
                "collective_candidate": True,
                "memory_kind": "note",
                "source_agents": ["planner"],
            },
        ),
    ]

    promoted_ids = await supervisor.govern_collective_memory(
        thread_id=thread_id,
        candidates=candidates,
        memory=memory,
        promotion_threshold=0.7,
    )

    assert promoted_ids
    records = await memory.search_collective_memory(
        query="caching",
        thread_id=thread_id,
        status="validated",
        limit=10,
    )
    assert any("caching" in item["content"].lower() for item in records)


def test_memory_reuse_count_and_deprecation_flow(tmp_path: Path, agent_registry: AgentRegistry):
    asyncio.run(_test_memory_reuse_count_and_deprecation_flow(tmp_path, agent_registry))


async def _test_memory_reuse_count_and_deprecation_flow(tmp_path: Path, agent_registry: AgentRegistry):
    memory = MemoryManager(config=_memory_config(tmp_path, "validation"))
    supervisor = Supervisor(registry=agent_registry)
    thread_id = "validation-thread"
    record_id = await memory.promote_collective_memory(
        thread_id=thread_id,
        kind="route",
        content="checkpoint route knowledge",
        source_agents=["elder"],
        confidence=0.8,
    )

    validated = await memory.validate_collective_memory(record_id)
    validated_again = await memory.validate_collective_memory(record_id)
    assert validated is not None and validated["reuse_count"] == 1
    assert validated_again is not None and validated_again["reuse_count"] == 2

    deprecated = await memory.deprecate_collective_memory(record_id)
    assert deprecated is not None
    assert deprecated["status"] == "deprecated"

    recovered = await supervisor.retrieve_collective_knowledge(
        TaskPacket(
            task_id="validation-task",
            goal="find safe route",
            knowledge_scope=["planning"],
            metadata={"thread_id": thread_id},
        ),
        memory,
        limit=10,
    )
    assert not any(item["id"] == record_id for item in recovered)


@pytest.mark.parametrize("resolution", ["supersede", "merge", "keep_both"])
def test_conflict_resolution_records_relationship_metadata(tmp_path: Path, resolution: str):
    asyncio.run(_test_conflict_resolution_records_relationship_metadata(tmp_path, resolution))


async def _test_conflict_resolution_records_relationship_metadata(tmp_path: Path, resolution: str):
    memory = MemoryManager(config=_memory_config(tmp_path, f"conflict_{resolution}"))
    thread_id = "conflict-thread"
    left_id = await memory.promote_collective_memory(
        thread_id=thread_id,
        kind="route_rule",
        content=f"left conflict content {resolution}",
        source_agents=["planner"],
        confidence=0.76,
    )
    right_id = await memory.promote_collective_memory(
        thread_id=thread_id,
        kind="route_rule",
        content=f"right conflict content {resolution}",
        source_agents=["reviewer"],
        confidence=0.88,
    )

    result = await memory.resolve_conflict(left_id, right_id, resolution, reason="pytest")
    assert result["status"] == "resolved"

    rows = await memory.search_collective_memory(query=None, thread_id=thread_id, status=None, limit=20)
    row_by_id = {row["id"]: row for row in rows}
    left = row_by_id[left_id]
    right = row_by_id[right_id]

    if resolution == "supersede":
        assert left["metadata"]["status"] == "deprecated"
        assert left["metadata"]["superseded_by"] == right_id
        assert left_id in list(right["metadata"].get("supersedes") or [])
    elif resolution == "merge":
        merged_id = result["merged_id"]
        merged = row_by_id[merged_id]
        assert left["metadata"]["merged_into"] == merged_id
        assert right["metadata"]["merged_into"] == merged_id
        assert "left conflict content" in merged["content"]
        assert "right conflict content" in merged["content"]
    else:
        assert left["metadata"]["conflict_reviewed"] is True
        assert right["metadata"]["conflict_reviewed"] is True
        assert left["metadata"]["conflict_with"] == right_id


def test_relevance_only_decay_prioritizes_recent_memories_when_weighted():
    policy = RelevanceOnlyDecayPolicy()
    now = datetime.now(timezone.utc)
    recent_record = {
        "content": "temporal priority route",
        "metadata": {
            "confidence": 0.8,
            "reuse_count": 1,
            "evidence_count": 1,
            "outcome_strength": 0.6,
            "last_validated_at": (now - timedelta(days=2)).isoformat(),
        },
    }
    stale_record = {
        "content": "temporal priority route",
        "metadata": {
            "confidence": 0.8,
            "reuse_count": 1,
            "evidence_count": 1,
            "outcome_strength": 0.6,
            "last_validated_at": (now - timedelta(days=120)).isoformat(),
        },
    }

    recent_score, _ = policy.score(recent_record, query="temporal priority route", config={"recency_weight": 1.0})
    stale_score, _ = policy.score(stale_record, query="temporal priority route", config={"recency_weight": 1.0})

    assert recent_score > stale_score
