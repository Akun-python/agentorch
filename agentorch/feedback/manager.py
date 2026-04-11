from __future__ import annotations

import contextvars
import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from .base import BaseFeedbackDispatcher, BaseFeedbackPolicy, BaseHumanInbox
from .channels import ConsoleFeedbackDispatcher
from .inbox import InMemoryHumanInbox
from .policy import DefaultFeedbackPolicy
from .types import FeedbackHandle, FeedbackKind, FeedbackSeverity, HumanFeedbackEvent, HumanResponse

if TYPE_CHECKING:
    from agentorch.runtime.runtime import Runtime


class HumanFeedbackManager:
    def __init__(
        self,
        *,
        policy: BaseFeedbackPolicy | None = None,
        dispatcher: BaseFeedbackDispatcher | None = None,
        inbox: BaseHumanInbox | None = None,
    ) -> None:
        self.policy = policy or DefaultFeedbackPolicy()
        self.dispatcher = dispatcher or ConsoleFeedbackDispatcher()
        self.inbox = inbox or InMemoryHumanInbox()
        self.runtime: Runtime | None = None
        self._context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("agentorch_feedback_context", default=None)

    @classmethod
    def console(cls) -> "HumanFeedbackManager":
        return cls(dispatcher=ConsoleFeedbackDispatcher(), inbox=InMemoryHumanInbox(), policy=DefaultFeedbackPolicy())

    @classmethod
    def enabled(cls) -> "HumanFeedbackManager":
        return cls.console()

    def bind_runtime(self, runtime: "Runtime") -> None:
        self.runtime = runtime

    def set_context(self, **context: Any):
        return self._context.set(context)

    def reset_context(self, token) -> None:
        self._context.reset(token)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _require_context_value(self, name: str, explicit: Any | None) -> Any:
        if explicit is not None:
            return explicit
        context = self._context.get() or {}
        value = context.get(name)
        if value is None:
            raise ValueError(f"Missing required feedback context field '{name}'.")
        return value

    async def emit(self, event: HumanFeedbackEvent) -> FeedbackHandle:
        decision = await self.policy.evaluate(event)
        if decision.should_dispatch:
            await self.dispatcher.dispatch(event, decision)
        if decision.should_store:
            await self.inbox.create_pending(event)
        if self.runtime is not None:
            self.runtime.tracer.emit(
                "human_feedback_emitted",
                {
                    "thread_id": event.thread_id,
                    "run_id": event.run_id,
                    "task_id": event.task_id,
                    "feedback_id": event.event_id,
                    "kind": event.kind.value,
                    "severity": event.severity.value,
                    "blocking": decision.block_run,
                    "title": event.title,
                    "message": event.message,
                    "metadata": event.metadata,
                },
            )
        return FeedbackHandle(
            feedback_id=event.event_id,
            status="waiting_human" if decision.block_run else "dispatched",
            blocking=decision.block_run,
            requires_response=event.requires_response,
            event=event,
        )

    async def notify(
        self,
        *,
        kind: FeedbackKind | str,
        title: str,
        message: str,
        severity: FeedbackSeverity = FeedbackSeverity.INFO,
        thread_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        source_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FeedbackHandle:
        context = self._context.get() or {}
        event = HumanFeedbackEvent(
            event_id=str(uuid.uuid4()),
            thread_id=self._require_context_value("thread_id", thread_id),
            run_id=self._require_context_value("run_id", run_id),
            task_id=task_id if task_id is not None else context.get("task_id"),
            source_agent=source_agent or context.get("source_agent"),
            kind=FeedbackKind(kind),
            title=title,
            message=message,
            severity=severity,
            metadata=metadata or {},
        )
        return await self.emit(event)

    async def request_input(
        self,
        *,
        title: str,
        message: str,
        response_schema: dict[str, Any] | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        source_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        blocking: bool = True,
    ) -> FeedbackHandle:
        context = self._context.get() or {}
        event = HumanFeedbackEvent(
            event_id=str(uuid.uuid4()),
            thread_id=self._require_context_value("thread_id", thread_id),
            run_id=self._require_context_value("run_id", run_id),
            task_id=task_id if task_id is not None else context.get("task_id"),
            source_agent=source_agent or context.get("source_agent"),
            kind=FeedbackKind.NEEDS_INPUT,
            title=title,
            message=message,
            requires_response=True,
            blocking=blocking,
            response_schema=response_schema,
            metadata=metadata or {},
        )
        return await self.emit(event)

    async def request_approval(
        self,
        *,
        title: str,
        message: str,
        response_schema: dict[str, Any] | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        source_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        blocking: bool = True,
    ) -> FeedbackHandle:
        context = self._context.get() or {}
        event = HumanFeedbackEvent(
            event_id=str(uuid.uuid4()),
            thread_id=self._require_context_value("thread_id", thread_id),
            run_id=self._require_context_value("run_id", run_id),
            task_id=task_id if task_id is not None else context.get("task_id"),
            source_agent=source_agent or context.get("source_agent"),
            kind=FeedbackKind.NEEDS_APPROVAL,
            title=title,
            message=message,
            severity=FeedbackSeverity.NOTICE,
            requires_response=True,
            requires_ack=True,
            blocking=blocking,
            response_schema=response_schema,
            metadata=metadata or {},
        )
        return await self.emit(event)

    async def submit_response(
        self,
        feedback_id: str,
        *,
        response: Any,
        responder: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        submission = HumanResponse(
            feedback_id=feedback_id,
            responder=responder,
            content=response,
            received_at=self._utc_now(),
            metadata=metadata or {},
        )
        pending = await self.inbox.submit_response(submission)
        if self.runtime is not None:
            self.runtime.tracer.emit(
                "human_feedback_responded",
                {
                    "thread_id": pending.event.thread_id,
                    "run_id": pending.event.run_id,
                    "task_id": pending.event.task_id,
                    "feedback_id": feedback_id,
                },
            )
        return pending

    async def wait_for_response(self, feedback_id: str, *, timeout: float | None = None):
        return await self.inbox.wait_for_response(feedback_id, timeout=timeout)

    async def list_pending(self, *, thread_id: str | None = None):
        return await self.inbox.list_pending(thread_id=thread_id)

    async def get(self, feedback_id: str):
        return await self.inbox.get(feedback_id)
