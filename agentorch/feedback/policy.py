from __future__ import annotations

from .base import BaseFeedbackPolicy
from .types import FeedbackDecision, FeedbackKind, HumanFeedbackEvent


class DefaultFeedbackPolicy(BaseFeedbackPolicy):
    async def evaluate(self, event: HumanFeedbackEvent) -> FeedbackDecision:
        block_run = event.blocking or event.kind in {FeedbackKind.NEEDS_INPUT, FeedbackKind.NEEDS_APPROVAL}
        should_dispatch = event.kind != FeedbackKind.PROGRESS_UPDATE or event.metadata.get("force_dispatch", False)
        return FeedbackDecision(
            should_dispatch=should_dispatch,
            should_store=block_run or event.requires_ack or event.requires_response,
            block_run=block_run,
            reason="default_policy",
        )

