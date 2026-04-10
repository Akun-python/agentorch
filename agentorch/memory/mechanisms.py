from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentorch.agents import SharedNote, TaskArtifact, WorkspaceRecord
from agentorch.core import Message

from .base import MemoryMechanism


class SessionMemoryMechanism(MemoryMechanism):
    kind = "session_memory"
    supported_operations = {
        "append_message",
        "get_thread_messages",
        "clear_thread",
        "get_context_window",
    }
    depends_on: tuple[str, ...] = ()

    def supports(self, operation: str) -> bool:
        return operation in self.supported_operations

    async def invoke(self, manager: Any, operation: str, **kwargs: Any) -> Any:
        thread_id = kwargs["thread_id"]
        if operation == "append_message":
            message: Message = kwargs["message"]
            manager.session_state.thread_messages.setdefault(thread_id, []).append(message)
            if manager.config.persist_thread_messages:
                await manager.record_store.add_record(
                    thread_id,
                    "thread_message",
                    message.content,
                    ["conversation", message.role],
                    metadata={
                        "role": message.role,
                        "name": message.name,
                        "tool_call_id": message.tool_call_id,
                        "tool_calls": [item.model_dump() for item in message.tool_calls],
                    },
                )
            return None
        if operation == "get_thread_messages":
            messages = manager.session_state.thread_messages.get(thread_id)
            if messages is None and manager.config.persist_thread_messages:
                messages = await manager.load_persisted_thread_messages(thread_id)
                if messages:
                    manager.session_state.thread_messages[thread_id] = list(messages)
            return list(messages or [])
        if operation == "clear_thread":
            manager.session_state.thread_messages.pop(thread_id, None)
            return None
        if operation == "get_context_window":
            messages = await self.invoke(manager, "get_thread_messages", thread_id=thread_id)
            return list(messages[-manager.config.message_window :])
        raise ValueError(f"Unsupported operation '{operation}' for {self.kind}.")


class ThreadSummaryMemoryMechanism(MemoryMechanism):
    kind = "thread_summary_memory"
    supported_operations = {"summarize_thread"}
    depends_on: tuple[str, ...] = ("session_memory",)

    def supports(self, operation: str) -> bool:
        return operation in self.supported_operations

    async def invoke(self, manager: Any, operation: str, **kwargs: Any) -> str:
        thread_id = kwargs["thread_id"]
        messages = await manager.get_thread_messages(thread_id)
        if not messages:
            return ""
        if len(messages) <= manager.config.message_window:
            return "\n".join(f"{message.role}: {message.content}" for message in messages)
        recent = messages[-manager.config.message_window :]
        return "Recent thread summary:\n" + "\n".join(f"{message.role}: {message.content}" for message in recent)


class AgentLocalMemoryMechanism(MemoryMechanism):
    kind = "agent_local_memory"
    supported_operations = {"append_agent_memory", "get_agent_memory"}
    depends_on: tuple[str, ...] = ()

    def supports(self, operation: str) -> bool:
        return operation in self.supported_operations

    async def invoke(self, manager: Any, operation: str, **kwargs: Any) -> Any:
        key = (kwargs["thread_id"], kwargs["agent_name"])
        if operation == "append_agent_memory":
            manager.session_state.agent_local_memory.setdefault(key, []).append(kwargs["payload"])
            return None
        if operation == "get_agent_memory":
            return list(manager.session_state.agent_local_memory.get(key, []))
        raise ValueError(f"Unsupported operation '{operation}' for {self.kind}.")


class WorkspaceMemoryMechanism(MemoryMechanism):
    kind = "workspace_memory"
    supported_operations = {"write_workspace_record", "read_workspace_records"}
    depends_on: tuple[str, ...] = ()

    def supports(self, operation: str) -> bool:
        return operation in self.supported_operations

    async def invoke(self, manager: Any, operation: str, **kwargs: Any) -> Any:
        thread_id = kwargs["thread_id"]
        if operation == "write_workspace_record":
            artifact: TaskArtifact = kwargs["artifact"]
            task_id = kwargs["task_id"]
            owner_agent = kwargs.get("owner_agent")
            artifact_id = artifact.metadata.get("artifact_id") or f"{task_id}:{artifact.name}"
            record = WorkspaceRecord(
                artifact_id=artifact_id,
                task_id=task_id,
                owner_agent=owner_agent,
                name=artifact.name,
                kind=artifact.kind,
                content=artifact.content,
                metadata=artifact.metadata,
            )
            manager.session_state.workspace_records.setdefault(thread_id, []).append(record)
            return record
        if operation == "read_workspace_records":
            return list(manager.session_state.workspace_records.get(thread_id, []))
        raise ValueError(f"Unsupported operation '{operation}' for {self.kind}.")


class SharedNoteMemoryMechanism(MemoryMechanism):
    kind = "shared_note_memory"
    supported_operations = {"add_shared_note", "get_shared_notes"}
    depends_on: tuple[str, ...] = ()

    def supports(self, operation: str) -> bool:
        return operation in self.supported_operations

    async def invoke(self, manager: Any, operation: str, **kwargs: Any) -> Any:
        thread_id = kwargs["thread_id"]
        if operation == "add_shared_note":
            note: SharedNote = kwargs["note"]
            manager.session_state.workspace_notes.setdefault(thread_id, []).append(note)
            return None
        if operation == "get_shared_notes":
            return list(manager.session_state.workspace_notes.get(thread_id, []))
        raise ValueError(f"Unsupported operation '{operation}' for {self.kind}.")


class RecordMemoryMechanism(MemoryMechanism):
    kind = "record_memory"
    supported_operations = {"remember", "search"}
    depends_on: tuple[str, ...] = ()

    def supports(self, operation: str) -> bool:
        return operation in self.supported_operations

    async def invoke(self, manager: Any, operation: str, **kwargs: Any) -> Any:
        if operation == "remember":
            record = kwargs["record"]
            return await manager.record_store.add_record(
                record.thread_id,
                record.kind,
                record.content,
                record.tags,
                metadata={
                    **dict(getattr(record, "metadata", {}) or {}),
                    "memory_role": record.memory_role,
                    "confidence": record.confidence,
                    "source_agents": record.source_agents,
                    "status": record.status,
                    "last_validated_at": record.last_validated_at,
                    "reuse_count": record.reuse_count,
                    "scope": record.scope,
                },
            )
        if operation == "search":
            return await manager.record_store.search(
                thread_id=kwargs.get("thread_id"),
                query=kwargs.get("query"),
                tags=kwargs.get("tags"),
            )
        raise ValueError(f"Unsupported operation '{operation}' for {self.kind}.")


class CollectiveMemoryMechanism(MemoryMechanism):
    kind = "collective_memory"
    supported_operations = {
        "search_collective_memory",
        "promote_collective_memory",
        "validate_collective_memory",
        "deprecate_collective_memory",
        "collect_candidate_notes",
    }
    depends_on: tuple[str, ...] = ("record_memory", "shared_note_memory")

    def supports(self, operation: str) -> bool:
        return operation in self.supported_operations

    async def invoke(self, manager: Any, operation: str, **kwargs: Any) -> Any:
        if operation == "search_collective_memory":
            return await manager.governance.search_collective_memory(manager, **kwargs)
        if operation == "promote_collective_memory":
            return await manager.governance.promote_collective_memory(manager, **kwargs)
        if operation == "validate_collective_memory":
            return await manager.governance.validate_collective_memory(manager, kwargs["record_id"])
        if operation == "deprecate_collective_memory":
            return await manager.governance.deprecate_collective_memory(manager, kwargs["record_id"])
        if operation == "collect_candidate_notes":
            return await manager.governance.collect_candidate_notes(
                manager,
                kwargs["thread_id"],
                task_id=kwargs.get("task_id"),
            )
        raise ValueError(f"Unsupported operation '{operation}' for {self.kind}.")


class TemporalDecayMemoryMechanism(MemoryMechanism):
    """Optional ranking layer for future time-aware long-term memory retrieval."""

    kind = "temporal_decay_memory"
    supported_operations = {"score_record"}
    depends_on: tuple[str, ...] = ("record_memory",)

    def supports(self, operation: str) -> bool:
        return operation in self.supported_operations

    async def invoke(self, manager: Any, operation: str, **kwargs: Any) -> float:
        timestamp = kwargs.get("last_validated_at")
        if not timestamp:
            return 0.0
        try:
            validated_at = datetime.fromisoformat(timestamp)
        except ValueError:
            return 0.0
        age_seconds = max((datetime.now(timezone.utc) - validated_at).total_seconds(), 0.0)
        return 1.0 / (1.0 + age_seconds / 86400.0)
