from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agentorch.knowledge import RagStrategyConfig
from agentorch.strategies import ContextStrategyConfig, CooperationStrategyConfig, LongHorizonStrategyConfig


class AgentCapability(str, Enum):
    PLAN = "plan"
    RETRIEVE = "retrieve"
    CODE = "code"
    REVIEW = "review"
    AGGREGATE = "aggregate"
    TOOL_USE = "tool_use"
    MEMORY_WRITE = "memory_write"
    DELEGATE = "delegate"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    WAITING_HUMAN = "waiting_human"


class ReturnMode(str, Enum):
    SUMMARY = "summary"
    STRUCTURED = "structured"
    BOTH = "both"


class AgentPolicyProfile(BaseModel):
    retrieval_mode: str = "inline"
    reasoning_mode: str = "react"
    allow_tool_calls: bool = True
    allow_delegation: bool = False
    default_rag_strategy: RagStrategyConfig | None = None
    allowed_rag_modes: list[str] = Field(default_factory=lambda: ["classic", "deliberative", "hybrid"])
    allow_inline_rag_mount: bool = True
    allow_explicit_retrieval_tool: bool = True
    preferred_reasoning_kind: str | None = None
    default_context_strategy: ContextStrategyConfig | None = None
    default_long_horizon_strategy: LongHorizonStrategyConfig | None = None
    default_cooperation_strategy: CooperationStrategyConfig | None = None
    notes: dict[str, Any] = Field(default_factory=dict)


class TaskBudget(BaseModel):
    max_steps: int | None = None
    max_tokens: int | None = None
    max_duration_seconds: float | None = None
    max_tool_calls: int | None = None


class TaskConstraint(BaseModel):
    name: str
    value: Any
    description: str | None = None


class TaskArtifact(BaseModel):
    name: str
    kind: str = "text"
    content: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRef(BaseModel):
    artifact_id: str
    name: str
    kind: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceRecord(BaseModel):
    artifact_id: str
    task_id: str
    owner_agent: str | None = None
    name: str
    kind: str = "text"
    content: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class SharedNote(BaseModel):
    note_id: str
    task_id: str
    author_agent: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SharedWorkspace(BaseModel):
    artifacts: list[WorkspaceRecord] = Field(default_factory=list)
    notes: list[SharedNote] = Field(default_factory=list)


class TaskPacket(BaseModel):
    task_id: str
    goal: str
    input: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: list[TaskConstraint] = Field(default_factory=list)
    expected_output: str | None = None
    artifacts: list[TaskArtifact] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    parent_task_id: str | None = None
    origin_agent: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    budget: TaskBudget | None = None
    knowledge_scope: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    return_mode: ReturnMode = ReturnMode.BOTH
    metadata: dict[str, Any] = Field(default_factory=dict)


class Handoff(BaseModel):
    from_agent: str
    to_agent: str
    task: TaskPacket
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentInvocation(BaseModel):
    agent_name: str
    task: TaskPacket
    parent_run_id: str | None = None
    delegation_depth: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskStep(BaseModel):
    step_id: str
    description: str
    assigned_agent: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskPlan(BaseModel):
    task_id: str
    summary: str | None = None
    steps: list[TaskStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskAssignment(BaseModel):
    agent_name: str
    task: TaskPacket
    step_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DelegationRule(BaseModel):
    max_depth: int = 1
    allow_parallel: bool = False
    require_explicit_capability: bool = True


class AggregationResult(BaseModel):
    summary: str
    combined_output: dict[str, Any] = Field(default_factory=dict)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    agent_name: str
    output_text: str
    status: TaskStatus = TaskStatus.COMPLETED
    summary: str | None = None
    structured_output: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[TaskArtifact] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    budget_used: dict[str, Any] = Field(default_factory=dict)
    handoff_suggestions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
