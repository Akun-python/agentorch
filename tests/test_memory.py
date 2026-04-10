import asyncio
from pathlib import Path

from agentorch.agents import SharedNote, TaskArtifact
from agentorch.config import MemoryConfig, MemoryMechanismConfig
from agentorch.core import Message
from agentorch.memory import MemoryManager, MemoryRecord


def test_memory_thread_isolation():
    asyncio.run(_test_memory_thread_isolation())


async def _test_memory_thread_isolation():
    memory = MemoryManager()
    await memory.append_message("thread-a", Message(role="user", content="hello"))
    await memory.append_message("thread-b", Message(role="user", content="world"))
    assert len(await memory.get_thread_messages("thread-a")) == 1
    assert (await memory.get_thread_messages("thread-a"))[0].content == "hello"
    assert (await memory.get_thread_messages("thread-b"))[0].content == "world"


def test_checkpoint_roundtrip():
    asyncio.run(_test_checkpoint_roundtrip())


async def _test_checkpoint_roundtrip():
    memory = MemoryManager()
    await memory.checkpoint("thread-a", "cp1", {"step": 1})
    payload = await memory.load_checkpoint("thread-a", "cp1")
    assert payload == {"step": 1}


def test_memory_agent_and_workspace_layers():
    asyncio.run(_test_memory_agent_and_workspace_layers())


async def _test_memory_agent_and_workspace_layers():
    memory = MemoryManager()
    await memory.append_agent_memory("thread-c", "planner", {"goal": "plan"})
    assert (await memory.get_agent_memory("thread-c", "planner"))[0]["goal"] == "plan"
    record = await memory.write_workspace_record(
        "thread-c",
        task_id="task-1",
        owner_agent="planner",
        artifact=TaskArtifact(name="outline", content={"steps": 3}),
    )
    assert record.name == "outline"
    await memory.add_shared_note("thread-c", SharedNote(note_id="note-1", task_id="task-1", content="review this"))
    assert (await memory.get_shared_notes("thread-c"))[0].content == "review this"


def test_collective_memory_governance_roundtrip():
    asyncio.run(_test_collective_memory_governance_roundtrip())


async def _test_collective_memory_governance_roundtrip():
    memory = MemoryManager()
    await memory.append_agent_memory("thread-d", "researcher", {"lesson": "private observation"})
    assert await memory.search_collective_memory(query="private observation", thread_id="thread-d") == []

    record_id = await memory.promote_collective_memory(
        thread_id="thread-d",
        kind="route",
        content="use the northern river crossing during dry season",
        tags=["migration"],
        source_agents=["planner", "reviewer"],
        confidence=0.9,
        scope="planning",
    )
    promoted = await memory.search_collective_memory(query="northern river", thread_id="thread-d")
    assert len(promoted) == 1
    assert promoted[0]["id"] == record_id
    assert promoted[0]["memory_role"] == "matriarch"
    assert promoted[0]["status"] == "validated"

    validated = await memory.validate_collective_memory(record_id)
    assert validated is not None
    assert validated["reuse_count"] == 1
    assert validated["last_validated_at"] is not None

    deprecated = await memory.deprecate_collective_memory(record_id)
    assert deprecated is not None
    assert deprecated["status"] == "deprecated"


def test_memory_manager_supports_multiple_configured_mechanisms():
    asyncio.run(_test_memory_manager_supports_multiple_configured_mechanisms())


async def _test_memory_manager_supports_multiple_configured_mechanisms():
    memory = MemoryManager(
        config=MemoryConfig(
            allow_partial_mechanisms=True,
            required_operations=["append_message", "summarize_thread", "remember", "search"],
            mechanisms=[
                MemoryMechanismConfig(kind="session_memory"),
                MemoryMechanismConfig(kind="thread_summary_memory"),
                MemoryMechanismConfig(kind="record_memory"),
            ]
        )
    )
    await memory.append_message("thread-e", Message(role="user", content="hello"))
    memory_record = MemoryRecord(thread_id="thread-e", kind="fact", content="alpha")
    await memory.remember(memory_record)
    assert "session_memory" in memory.list_mechanisms()
    assert "thread_summary_memory" in memory.list_mechanisms()
    assert "record_memory" in memory.list_mechanisms()
    assert await memory.summarize_thread("thread-e") == "user: hello"
    records = await memory.search(thread_id="thread-e", query="alpha")
    assert records[0]["content"] == memory_record.content


def test_memory_manager_rejects_incomplete_composition_by_default():
    try:
        MemoryManager(
            config=MemoryConfig(
                mechanisms=[
                    MemoryMechanismConfig(kind="session_memory"),
                    MemoryMechanismConfig(kind="record_memory"),
                ]
            )
        )
    except ValueError as exc:
        assert "required operations" in str(exc)
    else:
        raise AssertionError("Expected invalid composition to fail fast.")


def test_memory_manager_rejects_missing_dependencies():
    try:
        MemoryManager(
            config=MemoryConfig(
                allow_partial_mechanisms=True,
                mechanisms=[
                    MemoryMechanismConfig(kind="record_memory"),
                    MemoryMechanismConfig(kind="collective_memory"),
                ],
            )
        )
    except ValueError as exc:
        assert "missing dependencies" in str(exc)
    else:
        raise AssertionError("Expected dependency validation to fail fast.")


def test_memory_manager_allows_advanced_partial_composition_when_requested():
    memory = MemoryManager(
        config=MemoryConfig(
            allow_partial_mechanisms=True,
            required_operations=["append_message", "summarize_thread"],
            mechanisms=[
                MemoryMechanismConfig(kind="session_memory"),
                MemoryMechanismConfig(kind="thread_summary_memory"),
            ],
        )
    )
    assert memory.list_mechanisms() == ["session_memory", "thread_summary_memory"]
    assert memory.describe_mechanisms()[0]["kind"] == "session_memory"


def test_thread_messages_are_persisted_and_reloaded_from_record_store(tmp_path: Path):
    asyncio.run(_test_thread_messages_are_persisted_and_reloaded_from_record_store(tmp_path))


async def _test_thread_messages_are_persisted_and_reloaded_from_record_store(tmp_path: Path):
    config = MemoryConfig(
        checkpoint_path=tmp_path / "checkpoints.db",
        record_path=tmp_path / "records.db",
    )
    first = MemoryManager(config=config)
    await first.append_message("thread-persist", Message(role="user", content="owner approval required before release"))
    await first.append_message("thread-persist", Message(role="assistant", content="noted for the release checklist"))

    second = MemoryManager(config=config)
    restored = await second.get_thread_messages("thread-persist")
    assert [item.role for item in restored] == ["user", "assistant"]
    assert restored[0].content == "owner approval required before release"
    assert restored[1].content == "noted for the release checklist"

    matches = await second.search_thread_history(thread_id="thread-persist", query="approval required", limit=2)
    assert matches
    assert matches[0]["metadata"]["role"] == "user"
