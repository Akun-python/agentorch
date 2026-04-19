from __future__ import annotations

from .backends import ExecJsonBackend
from .config import HarnessConfig
from .schemas import CodexSessionState, PollSessionResult, StartCodexTaskRequest
from .state_store import StateStore


class SessionManager:
    def __init__(self, config: HarnessConfig, state_store: StateStore) -> None:
        self.config = config
        self.state_store = state_store
        self.backend = ExecJsonBackend(config, state_store)

    async def start_task(self, request: StartCodexTaskRequest) -> CodexSessionState:
        return await self.backend.start(request)

    async def poll_session(self, session_id: str, *, after_event_index: int = 0) -> PollSessionResult:
        return await self.backend.poll(session_id, after_event_index=after_event_index)

    async def wait_for_completion(self, session_id: str, *, timeout: float | None = None) -> CodexSessionState:
        return await self.backend.wait(session_id, timeout=timeout)

    async def stop_session(self, session_id: str) -> CodexSessionState:
        return await self.backend.stop(session_id)

    async def restore_session(self, session_id: str) -> CodexSessionState:
        return await self.backend.restore(session_id)

    async def start_followup(self, *, previous_session_id: str, prompt: str) -> CodexSessionState:
        previous = await self.restore_session(previous_session_id)
        return await self.backend.resume(previous_session=previous, prompt=prompt)
