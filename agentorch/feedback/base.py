from __future__ import annotations

from abc import ABC, abstractmethod

from .types import FeedbackDecision, HumanFeedbackEvent, HumanResponse, PendingHumanFeedback


class BaseFeedbackPolicy(ABC):
    @abstractmethod
    async def evaluate(self, event: HumanFeedbackEvent) -> FeedbackDecision:
        raise NotImplementedError


class BaseFeedbackDispatcher(ABC):
    @abstractmethod
    async def dispatch(self, event: HumanFeedbackEvent, decision: FeedbackDecision) -> None:
        raise NotImplementedError


class BaseHumanInbox(ABC):
    @abstractmethod
    async def create_pending(self, event: HumanFeedbackEvent) -> PendingHumanFeedback:
        raise NotImplementedError

    @abstractmethod
    async def get(self, feedback_id: str) -> PendingHumanFeedback | None:
        raise NotImplementedError

    @abstractmethod
    async def list_pending(self, *, thread_id: str | None = None) -> list[PendingHumanFeedback]:
        raise NotImplementedError

    @abstractmethod
    async def submit_response(self, response: HumanResponse) -> PendingHumanFeedback:
        raise NotImplementedError

    @abstractmethod
    async def wait_for_response(self, feedback_id: str, *, timeout: float | None = None) -> HumanResponse | None:
        raise NotImplementedError

