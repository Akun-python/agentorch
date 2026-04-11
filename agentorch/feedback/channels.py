from __future__ import annotations

import json

from .base import BaseFeedbackDispatcher
from .types import FeedbackDecision, HumanFeedbackEvent


class ConsoleFeedbackDispatcher(BaseFeedbackDispatcher):
    def __init__(self) -> None:
        self.dispatched_events: list[HumanFeedbackEvent] = []

    async def dispatch(self, event: HumanFeedbackEvent, decision: FeedbackDecision) -> None:
        self.dispatched_events.append(event)
        payload = {
            "feedback_id": event.event_id,
            "thread_id": event.thread_id,
            "kind": event.kind.value,
            "title": event.title,
            "message": event.message,
            "severity": event.severity.value,
            "blocking": decision.block_run,
        }
        print(json.dumps(payload, ensure_ascii=False))

