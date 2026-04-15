from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Iterable

from agentorch.agents import SharedNote, TaskArtifact, WorkspaceRecord
from agentorch.config import MemoryConfig, MemoryMechanismConfig
from agentorch.core import Message

from .bootstrap import bootstrap_memory_defaults
from .base import MemoryGovernance, MemoryMechanism
from .backends import InMemoryStateStore, SQLiteCheckpointStore, SQLiteRecordStore
from .factory import create_memory_backend, create_memory_governance, create_memory_mechanism
from .state import MemorySessionState
from .types import CollectiveMemoryRecord, MemoryRecord


class MemoryManager:
    _STANDARD_OPERATIONS = (
        "append_message",
        "get_thread_messages",
        "clear_thread",
        "get_context_window",
        "summarize_thread",
        "remember",
        "search",
        "search_collective_memory",
        "promote_collective_memory",
        "validate_collective_memory",
        "deprecate_collective_memory",
        "append_agent_memory",
        "get_agent_memory",
        "write_workspace_record",
        "read_workspace_records",
        "add_shared_note",
        "get_shared_notes",
        "collect_candidate_notes",
    )

    def __init__(
        self,
        *,
        state_store: InMemoryStateStore | None = None,
        checkpoint_store: SQLiteCheckpointStore | None = None,
        record_store: SQLiteRecordStore | None = None,
        governance: MemoryGovernance | None = None,
        session_state: MemorySessionState | None = None,
        config: MemoryConfig | None = None,
        mechanisms: Iterable[str | MemoryMechanismConfig | MemoryMechanism] | None = None,
    ) -> None:
        self.config = config or MemoryConfig()
        bootstrap_memory_defaults()
        self.state_store = state_store or create_memory_backend("in_memory_state_store")
        self.checkpoint_store = checkpoint_store or create_memory_backend(
            "sqlite_checkpoint_store",
            path=self.config.checkpoint_path,
            redaction=self.config.redaction,
        )
        self.record_store = record_store or create_memory_backend(
            "sqlite_record_store",
            path=self.config.record_path,
            redaction=self.config.redaction,
            summary_only_content=self.config.summary_only_persistence,
            max_content_chars=self.config.max_record_content_chars,
            max_metadata_chars=self.config.max_record_metadata_chars,
            truncate_thread_messages=self.config.truncate_thread_messages_before_persist,
            persist_full_prompt_text=self.config.persist_full_prompt_text,
        )
        self.governance = governance or create_memory_governance("mgcm_governance")
        self.collective_record_type = CollectiveMemoryRecord
        self.session_state = session_state or MemorySessionState()
        self.mechanisms = self._build_mechanisms(mechanisms)
        self._mechanism_index = {mechanism.kind: mechanism for mechanism in self.mechanisms}
        self._validate_mechanism_composition()

    @classmethod
    def compose(
        cls,
        *mechanisms: str | MemoryMechanismConfig | MemoryMechanism,
        config: MemoryConfig | None = None,
        **kwargs: Any,
    ) -> "MemoryManager":
        return cls(config=config, mechanisms=mechanisms, **kwargs)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _build_mechanisms(
        self,
        mechanisms: Iterable[str | MemoryMechanismConfig | MemoryMechanism] | None,
    ) -> list[MemoryMechanism]:
        items = list(mechanisms or self.config.mechanisms)
        built: list[MemoryMechanism] = []
        for item in items:
            if isinstance(item, MemoryMechanism):
                built.append(item)
                continue
            if isinstance(item, str):
                built.append(create_memory_mechanism(item))
                continue
            if not item.enabled:
                continue
            built.append(create_memory_mechanism(item.kind, **item.config))
        return built

    def _validate_mechanism_composition(self) -> None:
        if not self.config.validate_composition:
            return
        mechanism_kinds = [mechanism.kind for mechanism in self.mechanisms]
        duplicates = sorted({kind for kind in mechanism_kinds if mechanism_kinds.count(kind) > 1})
        if duplicates:
            raise ValueError(f"Duplicate memory mechanisms are not allowed: {', '.join(duplicates)}")

        available = set(mechanism_kinds)
        missing_dependencies: dict[str, list[str]] = {}
        for mechanism in self.mechanisms:
            dependencies = [kind for kind in getattr(mechanism, "depends_on", ()) if kind not in available]
            if dependencies:
                missing_dependencies[mechanism.kind] = dependencies
        if missing_dependencies:
            details = "; ".join(f"{kind} -> {', '.join(deps)}" for kind, deps in sorted(missing_dependencies.items()))
            raise ValueError(f"Invalid memory mechanism composition, missing dependencies: {details}")

        if self.config.allow_partial_mechanisms:
            return
        supported_operations = {
            operation
            for mechanism in self.mechanisms
            for operation in getattr(mechanism, "supported_operations", set())
        }
        required_operations = tuple(self.config.required_operations or self._STANDARD_OPERATIONS)
        missing_operations = [operation for operation in required_operations if operation not in supported_operations]
        if missing_operations:
            raise ValueError(
                "Memory mechanism composition does not cover required operations: "
                + ", ".join(missing_operations)
            )

    async def _invoke_first(self, operation: str, **kwargs: Any) -> Any:
        for mechanism in self.mechanisms:
            if mechanism.supports(operation):
                return await mechanism.invoke(self, operation, **kwargs)
        raise ValueError(f"No memory mechanism registered for operation '{operation}'.")

    async def _invoke_all(self, operation: str, **kwargs: Any) -> list[Any]:
        results: list[Any] = []
        for mechanism in self.mechanisms:
            if mechanism.supports(operation):
                results.append(await mechanism.invoke(self, operation, **kwargs))
        return results

    def list_mechanisms(self) -> list[str]:
        return [mechanism.kind for mechanism in self.mechanisms]

    def describe_mechanisms(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": mechanism.kind,
                "depends_on": list(getattr(mechanism, "depends_on", ())),
                "supported_operations": sorted(getattr(mechanism, "supported_operations", set())),
            }
            for mechanism in self.mechanisms
        ]

    def get_mechanism(self, kind: str) -> MemoryMechanism:
        try:
            return self._mechanism_index[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported memory mechanism kind: {kind}") from exc

    def _normalize_collective_result(self, result: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(result.get("metadata") or {})
        return {
            "id": result["id"],
            "thread_id": result["thread_id"],
            "kind": result["kind"],
            "content": result["content"],
            "tags": result.get("tags", []),
            "memory_role": metadata.get("memory_role", "individual"),
            "confidence": metadata.get("confidence", 0.5),
            "source_agents": metadata.get("source_agents", []),
            "status": metadata.get("status", "candidate"),
            "last_validated_at": metadata.get("last_validated_at"),
            "reuse_count": metadata.get("reuse_count", 0),
            "scope": metadata.get("scope"),
            "metadata": metadata,
        }

    async def append_message(self, thread_id: str, message: Message) -> None:
        await self._invoke_first("append_message", thread_id=thread_id, message=message)

    async def get_thread_messages(self, thread_id: str) -> list[Message]:
        return await self._invoke_first("get_thread_messages", thread_id=thread_id)

    async def clear_thread(self, thread_id: str) -> None:
        await self._invoke_first("clear_thread", thread_id=thread_id)

    async def get_context_window(self, thread_id: str) -> list[Message]:
        return await self._invoke_first("get_context_window", thread_id=thread_id)

    async def summarize_thread(self, thread_id: str) -> str:
        return await self._invoke_first("summarize_thread", thread_id=thread_id)

    async def remember(self, record: MemoryRecord) -> int:
        return await self._invoke_first("remember", record=record)

    async def search(self, *, thread_id: str | None = None, query: str | None = None, tags: list[str] | None = None) -> list[dict[str, Any]]:
        return await self._invoke_first("search", thread_id=thread_id, query=query, tags=tags)

    def deserialize_persisted_message(self, record: dict[str, Any]) -> Message:
        metadata = dict(record.get("metadata") or {})
        tool_calls = metadata.get("tool_calls") or []
        if isinstance(tool_calls, str):
            try:
                tool_calls = json.loads(tool_calls)
            except json.JSONDecodeError:
                tool_calls = []
        return Message(
            role=metadata.get("role", "assistant"),
            content=record.get("content", ""),
            name=metadata.get("name"),
            tool_call_id=metadata.get("tool_call_id"),
            tool_calls=tool_calls,
            metadata={key: value for key, value in metadata.items() if key not in {"role", "name", "tool_call_id", "tool_calls"}},
        )

    async def load_persisted_thread_messages(self, thread_id: str, *, limit: int | None = None) -> list[Message]:
        if not self.config.persist_thread_messages:
            return []
        records = await self.record_store.search(
            thread_id=thread_id,
            tags=["conversation"],
            limit=limit,
            order_desc=False,
        )
        return [self.deserialize_persisted_message(record) for record in records]

    async def search_thread_history(
        self,
        *,
        thread_id: str,
        query: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self.config.persist_thread_messages or not query:
            return []
        return await self.record_store.search(
            thread_id=thread_id,
            query=query,
            tags=["conversation"],
            limit=limit or self.config.thread_history_recall_limit,
            order_desc=True,
        )

    async def aclose(self) -> None:
        return None

    async def search_collective_memory(
        self,
        *,
        query: str | None = None,
        thread_id: str | None = None,
        memory_role: str = "matriarch",
        status: str | None = "validated",
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        return await self._invoke_first(
            "search_collective_memory",
            query=query,
            thread_id=thread_id,
            memory_role=memory_role,
            status=status,
            limit=limit,
        )

    async def promote_collective_memory(
        self,
        *,
        thread_id: str,
        kind: str,
        content: str,
        tags: list[str] | None = None,
        source_agents: list[str] | None = None,
        confidence: float = 0.7,
        scope: str | None = None,
        status: str = "validated",
    ) -> int:
        return await self._invoke_first(
            "promote_collective_memory",
            thread_id=thread_id,
            kind=kind,
            content=content,
            tags=tags,
            source_agents=source_agents,
            confidence=confidence,
            scope=scope,
            status=status,
        )

    async def validate_collective_memory(self, record_id: int) -> dict[str, Any] | None:
        return await self._invoke_first("validate_collective_memory", record_id=record_id)

    async def deprecate_collective_memory(self, record_id: int) -> dict[str, Any] | None:
        return await self._invoke_first("deprecate_collective_memory", record_id=record_id)

    async def append_agent_memory(self, thread_id: str, agent_name: str, payload: dict[str, Any]) -> None:
        await self._invoke_first("append_agent_memory", thread_id=thread_id, agent_name=agent_name, payload=payload)

    async def get_agent_memory(self, thread_id: str, agent_name: str) -> list[dict[str, Any]]:
        return await self._invoke_first("get_agent_memory", thread_id=thread_id, agent_name=agent_name)

    async def write_workspace_record(
        self,
        thread_id: str,
        *,
        task_id: str,
        owner_agent: str | None,
        artifact: TaskArtifact,
    ) -> WorkspaceRecord:
        return await self._invoke_first(
            "write_workspace_record",
            thread_id=thread_id,
            task_id=task_id,
            owner_agent=owner_agent,
            artifact=artifact,
        )

    async def read_workspace_records(self, thread_id: str) -> list[WorkspaceRecord]:
        return await self._invoke_first("read_workspace_records", thread_id=thread_id)

    async def add_shared_note(self, thread_id: str, note: SharedNote) -> None:
        await self._invoke_first("add_shared_note", thread_id=thread_id, note=note)

    async def get_shared_notes(self, thread_id: str) -> list[SharedNote]:
        return await self._invoke_first("get_shared_notes", thread_id=thread_id)

    async def collect_candidate_notes(self, thread_id: str, *, task_id: str | None = None) -> list[SharedNote]:
        return await self._invoke_first("collect_candidate_notes", thread_id=thread_id, task_id=task_id)

    async def checkpoint(self, thread_id: str, checkpoint_id: str, payload: dict[str, Any]) -> None:
        await self.checkpoint_store.save(thread_id, checkpoint_id, payload)

    async def load_checkpoint(self, thread_id: str, checkpoint_id: str) -> dict[str, Any] | None:
        return await self.checkpoint_store.load(thread_id, checkpoint_id)
