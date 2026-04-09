from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaskConstraint(BaseModel):
    name: str
    value: Any
    description: str | None = None


class TaskArtifact(BaseModel):
    name: str
    kind: str = "text"
    content: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskPacket(BaseModel):
    task_id: str
    goal: str
    input: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: list[TaskConstraint] = Field(default_factory=list)
    expected_output: str | None = None
    artifacts: list[TaskArtifact] = Field(default_factory=list)
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


class AgentResult(BaseModel):
    agent_name: str
    output_text: str
    structured_output: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[TaskArtifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
