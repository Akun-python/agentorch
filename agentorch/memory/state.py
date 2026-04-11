from __future__ import annotations

from typing import Any

from agentorch.agents import SharedNote, WorkspaceRecord
from agentorch.core import Message


class MemorySessionState:
    def __init__(self) -> None:
        self.thread_messages: dict[str, list[Message]] = {}
        self.agent_local_memory: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.workspace_records: dict[str, list[WorkspaceRecord]] = {}
        self.workspace_notes: dict[str, list[SharedNote]] = {}
