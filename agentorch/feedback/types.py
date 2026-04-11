from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FeedbackKind(str, Enum):
    PROGRESS_UPDATE = "progress_update"
    RISK_ALERT = "risk_alert"
    MILESTONE = "milestone"
    NEEDS_INPUT = "needs_input"
    NEEDS_APPROVAL = "needs_approval"
    BLOCKED = "blocked"
    COMPLETION = "completion"
    HANDOFF = "handoff"


class FeedbackSeverity(str, Enum):
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"


class FeedbackStatus(str, Enum):
    PENDING = "pending"
    RESPONDED = "responded"
    ACKNOWLEDGED = "acknowledged"
    CANCELLED = "cancelled"


class HumanFeedbackEvent(BaseModel):
    event_id: str
    thread_id: str
    run_id: str
    task_id: str | None = None
    source_agent: str | None = None
    kind: FeedbackKind
    title: str
    message: str
    severity: FeedbackSeverity = FeedbackSeverity.INFO
    requires_response: bool = False
    requires_ack: bool = False
    blocking: bool = False
    response_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackDecision(BaseModel):
    should_dispatch: bool = True
    should_store: bool = True
    channel: str | None = None
    block_run: bool = False
    reason: str | None = None


class HumanResponse(BaseModel):
    feedback_id: str
    responder: str | None = None
    content: Any
    received_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PendingHumanFeedback(BaseModel):
    feedback_id: str
    event: HumanFeedbackEvent
    status: FeedbackStatus = FeedbackStatus.PENDING
    response: HumanResponse | None = None
    created_at: str
    updated_at: str


class FeedbackHandle(BaseModel):
    feedback_id: str
    status: str
    blocking: bool = False
    requires_response: bool = False
    event: HumanFeedbackEvent
