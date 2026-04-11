from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    thread_id: str
    kind: str
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    memory_role: str = "individual"
    confidence: float = 0.5
    source_agents: list[str] = Field(default_factory=list)
    status: str = "candidate"
    last_validated_at: str | None = None
    reuse_count: int = 0
    scope: str | None = None


class CollectiveMemoryRecord(MemoryRecord):
    memory_role: str = "matriarch"
    status: str = "validated"


class EpisodicCapsule(BaseModel):
    thread_id: str
    task_id: str | None = None
    agent_role: str | None = None
    goal: str = ""
    summary: str = ""
    outcome: str = ""
    knowledge_scope: list[str] = Field(default_factory=list)
    scene_index: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    salience_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
