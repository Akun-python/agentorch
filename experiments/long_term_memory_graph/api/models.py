from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ..domain.utils import (
    derive_task_family,
    derive_thread_family,
    ensure_utc_datetime,
    infer_agent_id,
    normalize_refs,
    normalize_string_list,
    normalize_text,
    stable_hash,
)


class ClaimSlot(BaseModel):
    slot: str
    value: str
    polarity: str = "positive"
    scope: str = ""
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("slot", "value", "polarity", "scope", mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: Any) -> str:
        return normalize_text(value).lower()

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def _normalize_evidence_ids(cls, value: Any) -> list[str]:
        return normalize_refs(value)


class MemoryCapsuleCandidate(BaseModel):
    capsule_id: str
    agent_id: str | None = None
    run_id: str | None = None
    thread_id: str | None = None
    thread_family: str | None = None
    task_id: str | None = None
    task_family: str | None = None
    created_at: datetime
    goal: str = ""
    summary: str = ""
    outcome: str = ""
    knowledge_scope: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    claims: list[ClaimSlot] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_memory_refs: list[str] = Field(default_factory=list)
    salience_score: float = 0.0
    confidence: float = 0.5
    status: str = "validated"

    @field_validator(
        "capsule_id",
        "agent_id",
        "run_id",
        "thread_id",
        "thread_family",
        "task_id",
        "task_family",
        "goal",
        "summary",
        "outcome",
        "status",
        mode="before",
    )
    @classmethod
    def _normalize_textual_fields(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_text(value)

    @field_validator("knowledge_scope", "tags", "entities", mode="before")
    @classmethod
    def _normalize_lists(cls, value: Any) -> list[str]:
        return normalize_string_list(value)

    @field_validator("evidence_refs", "source_memory_refs", mode="before")
    @classmethod
    def _normalize_refs(cls, value: Any) -> list[str]:
        return normalize_refs(value)

    @field_validator("created_at", mode="before")
    @classmethod
    def _normalize_created_at(cls, value: Any) -> datetime:
        return ensure_utc_datetime(value)

    @model_validator(mode="after")
    def _fill_derived_fields(self) -> "MemoryCapsuleCandidate":
        self.agent_id = infer_agent_id(self.thread_id, self.agent_id)
        self.thread_family = self.thread_family or derive_thread_family(self.thread_id)
        self.task_family = self.task_family or derive_task_family(self.task_id)
        return self

    @property
    def title(self) -> str:
        return self.goal or self.summary or self.capsule_id

    def scene_payload(self) -> dict[str, Any]:
        return {
            "goal": self.goal.lower(),
            "knowledge_scope": self.knowledge_scope,
            "tags": self.tags,
            "entities": self.entities,
            "thread_family": self.thread_family,
            "task_family": self.task_family,
        }

    def computed_scene_hash(self) -> str:
        return stable_hash(self.scene_payload(), length=16)


class RecallRequest(BaseModel):
    query: str
    agent_id: str | None = None
    thread_id: str | None = None
    thread_family: str | None = None
    task_id: str | None = None
    task_family: str | None = None
    knowledge_scope: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    top_candidates: int | None = None
    top_seeds: int | None = None
    max_nodes: int | None = None
    max_edges: int | None = None

    @field_validator("query", "agent_id", "thread_id", "thread_family", "task_id", "task_family", mode="before")
    @classmethod
    def _normalize_textual_fields(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_text(value)

    @field_validator("knowledge_scope", "tags", "entities", mode="before")
    @classmethod
    def _normalize_lists(cls, value: Any) -> list[str]:
        return normalize_string_list(value)

    @model_validator(mode="after")
    def _fill_derived_fields(self) -> "RecallRequest":
        self.thread_family = self.thread_family or derive_thread_family(self.thread_id)
        self.task_family = self.task_family or derive_task_family(self.task_id)
        self.agent_id = infer_agent_id(self.thread_id, self.agent_id)
        return self

    def scene_payload(self) -> dict[str, Any]:
        return {
            "thread_family": self.thread_family,
            "task_family": self.task_family,
            "knowledge_scope": self.knowledge_scope,
            "tags": self.tags,
            "entities": self.entities,
        }


class NodeIndexEntry(BaseModel):
    index: str
    capsule_id: str
    title: str
    score: float
    why_selected: str


class GraphEdgeView(BaseModel):
    source_index: str
    relation_type: str
    target_index: str
    score: float


class RecallRetrievalReport(BaseModel):
    candidate_count: int = 0
    expansion_hops: int = 1
    suppressed_stale_nodes: list[str] = Field(default_factory=list)
    suppressed_conflict_nodes: list[str] = Field(default_factory=list)
    lexical_candidate_ids: list[str] = Field(default_factory=list)
    semantic_candidate_ids: list[str] = Field(default_factory=list)


class RecallResponse(BaseModel):
    prompt_summary: str
    node_index: list[NodeIndexEntry] = Field(default_factory=list)
    edges: list[GraphEdgeView] = Field(default_factory=list)
    retrieval_report: RecallRetrievalReport = Field(default_factory=RecallRetrievalReport)


class CapsuleDetailResponse(BaseModel):
    details: list["MemoryCapsuleDetail"] = Field(default_factory=list)
    missing_capsule_ids: list[str] = Field(default_factory=list)


class BackfillReport(BaseModel):
    source_path: str
    total_records: int = 0
    imported_capsules: int = 0
    skipped_records: int = 0
    imported_by_kind: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


from ..domain.entities import MemoryCapsuleDetail  # noqa: E402

CapsuleDetailResponse.model_rebuild()
