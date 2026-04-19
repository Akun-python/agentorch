from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus(str, Enum):
    PENDING = "pending"
    PREPARED = "prepared"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    NEEDS_FOLLOWUP = "needs_followup"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    ABORTED = "aborted"


class SessionStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    FINISHED = "finished"
    ERRORED = "errored"
    LOST = "lost"
    STOPPED = "stopped"


class ReviewDecisionKind(str, Enum):
    COMPLETED = "completed"
    NEEDS_FOLLOWUP = "needs_followup"
    REDO = "redo"
    BLOCKED = "blocked"
    ASK_HUMAN = "ask_human"


class WorkspaceMode(str, Enum):
    SHARED = "shared"
    GIT_WORKTREE = "git-worktree"
    COPY = "copy"


class HarnessTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task-{uuid4().hex[:10]}")
    goal: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    expected_output: str | None = None
    write_scope: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    phase: str = "execute"
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    workspace_path: str | None = None
    assigned_session_id: str | None = None
    latest_prompt: str | None = None
    followup_prompt: str | None = None
    review_summary: str | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceAllocation(BaseModel):
    task_id: str
    workspace_path: str
    workspace_kind: WorkspaceMode
    ready: bool = True
    branch_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StartCodexTaskRequest(BaseModel):
    task_id: str
    cwd: str
    prompt: str
    sandbox_mode: str = "workspace-write"
    approval_policy: str = "never"
    skip_git_repo_check: bool = False


class CodexSessionEvent(BaseModel):
    session_id: str
    event_index: int
    stream: Literal["stdout", "stderr", "system"]
    raw_text: str = ""
    parsed: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class CodexSessionState(BaseModel):
    session_id: str
    task_id: str
    backend: str = "exec_json"
    cwd: str
    codex_thread_id: str | None = None
    resumed_from_session_id: str | None = None
    status: SessionStatus = SessionStatus.STARTING
    pid: int | None = None
    started_at: str = Field(default_factory=utc_now)
    finished_at: str | None = None
    last_activity_at: str | None = None
    log_path: str
    event_count: int = 0
    last_message: str | None = None
    exit_code: int | None = None
    error_message: str | None = None


class PollSessionResult(BaseModel):
    session: CodexSessionState
    events: list[CodexSessionEvent] = Field(default_factory=list)
    next_offset: int = 0


class TaskArtifactBundle(BaseModel):
    task_id: str
    workspace_path: str
    changed_files: list[str] = Field(default_factory=list)
    git_diff_summary: str = ""
    last_agent_message: str = ""
    log_excerpt: str = ""
    output_files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewDecision(BaseModel):
    task_id: str
    decision: ReviewDecisionKind = ReviewDecisionKind.NEEDS_FOLLOWUP
    score: float = 0.0
    gap_list: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    next_prompt: str | None = None
    needs_human: bool = False
    summary: str = ""


class IntegrationSummary(BaseModel):
    all_done: bool = False
    summary: str = ""
    next_actions: list[str] = Field(default_factory=list)


class HarnessRunState(BaseModel):
    run_id: str = Field(default_factory=lambda: f"run-{uuid4().hex[:12]}")
    thread_id: str = Field(default_factory=lambda: f"thread-{uuid4().hex[:12]}")
    user_request: str
    project_root: str
    round_index: int = 0
    overall_status: str = "running"
    tasks: list[HarnessTask] = Field(default_factory=list)
    sessions: dict[str, CodexSessionState] = Field(default_factory=dict)
    summary: str = ""
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()
