from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentorch.config import MemoryConfig
from agentorch.core import Message

from .stores import InMemoryStateStore, SQLiteCheckpointStore, SQLiteRecordStore


class MemoryRecord(BaseModel):
    thread_id: str
    kind: str
    content: str
    tags: list[str] = Field(default_factory=list)


class MemoryManager:
    def __init__(
        self,
        *,
        state_store: InMemoryStateStore | None = None,
        checkpoint_store: SQLiteCheckpointStore | None = None,
        record_store: SQLiteRecordStore | None = None,
        config: MemoryConfig | None = None,
    ) -> None:
        self.config = config or MemoryConfig()
        self.state_store = state_store or InMemoryStateStore()
        self.checkpoint_store = checkpoint_store or SQLiteCheckpointStore(self.config.checkpoint_path)
        self.record_store = record_store or SQLiteRecordStore(self.config.record_path)
        self._thread_messages: dict[str, list[Message]] = {}

    async def append_message(self, thread_id: str, message: Message) -> None:
        self._thread_messages.setdefault(thread_id, []).append(message)

    async def get_thread_messages(self, thread_id: str) -> list[Message]:
        return list(self._thread_messages.get(thread_id, []))

    async def clear_thread(self, thread_id: str) -> None:
        self._thread_messages.pop(thread_id, None)

    async def get_context_window(self, thread_id: str) -> list[Message]:
        messages = self._thread_messages.get(thread_id, [])
        return list(messages[-self.config.message_window :])

    async def summarize_thread(self, thread_id: str) -> str:
        messages = self._thread_messages.get(thread_id, [])
        if not messages:
            return ""
        if len(messages) <= self.config.message_window:
            return "\n".join(f"{message.role}: {message.content}" for message in messages)
        recent = messages[-self.config.message_window :]
        return "Recent thread summary:\n" + "\n".join(f"{message.role}: {message.content}" for message in recent)

    async def remember(self, record: MemoryRecord) -> int:
        return await self.record_store.add_record(record.thread_id, record.kind, record.content, record.tags)

    async def search(self, *, thread_id: str | None = None, query: str | None = None, tags: list[str] | None = None) -> list[dict[str, Any]]:
        return await self.record_store.search(thread_id=thread_id, query=query, tags=tags)

    async def checkpoint(self, thread_id: str, checkpoint_id: str, payload: dict[str, Any]) -> None:
        await self.checkpoint_store.save(thread_id, checkpoint_id, payload)

    async def load_checkpoint(self, thread_id: str, checkpoint_id: str) -> dict[str, Any] | None:
        return await self.checkpoint_store.load(thread_id, checkpoint_id)
