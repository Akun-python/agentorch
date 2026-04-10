from __future__ import annotations

from typing import Any


class InMemoryStateStore:
    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    async def get_state(self, thread_id: str) -> dict[str, Any]:
        return self._state.setdefault(thread_id, {})

    async def set_state(self, thread_id: str, state: dict[str, Any]) -> None:
        self._state[thread_id] = state
