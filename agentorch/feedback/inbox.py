from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from .base import BaseHumanInbox
from .types import FeedbackStatus, HumanFeedbackEvent, HumanResponse, PendingHumanFeedback


class InMemoryHumanInbox(BaseHumanInbox):
    def __init__(self) -> None:
        self._items: dict[str, PendingHumanFeedback] = {}
        self._events: dict[str, asyncio.Event] = {}

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def create_pending(self, event: HumanFeedbackEvent) -> PendingHumanFeedback:
        now = self._utc_now()
        pending = PendingHumanFeedback(
            feedback_id=event.event_id,
            event=event,
            created_at=now,
            updated_at=now,
        )
        self._items[event.event_id] = pending
        self._events[event.event_id] = asyncio.Event()
        return pending

    async def get(self, feedback_id: str) -> PendingHumanFeedback | None:
        return self._items.get(feedback_id)

    async def list_pending(self, *, thread_id: str | None = None) -> list[PendingHumanFeedback]:
        items = [item for item in self._items.values() if item.status == FeedbackStatus.PENDING]
        if thread_id is not None:
            items = [item for item in items if item.event.thread_id == thread_id]
        return list(items)

    async def submit_response(self, response: HumanResponse) -> PendingHumanFeedback:
        pending = self._items[response.feedback_id]
        updated = pending.model_copy(update={"status": FeedbackStatus.RESPONDED, "response": response, "updated_at": self._utc_now()})
        self._items[response.feedback_id] = updated
        self._events[response.feedback_id].set()
        return updated

    async def wait_for_response(self, feedback_id: str, *, timeout: float | None = None) -> HumanResponse | None:
        pending = self._items.get(feedback_id)
        if pending is None:
            return None
        if pending.response is not None:
            return pending.response
        event = self._events.setdefault(feedback_id, asyncio.Event())
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        updated = self._items.get(feedback_id)
        return updated.response if updated else None

