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
    """记忆中的一个结构化主张槽位。"""

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


class ExperienceCandidate(BaseModel):
    """待晋升的短期经验。

    该模型贴近运行日志或短期记忆输入，后续可转换成 MemoryCapsuleCandidate。
    """

    experience_id: str
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
    status: str = "candidate"
    reuse_count: int = 0

    @field_validator(
        "experience_id",
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
    def _fill_derived_fields(self) -> "ExperienceCandidate":
        """补齐可由线程或任务推导出的归属字段。"""

        self.agent_id = infer_agent_id(self.thread_id, self.agent_id)
        self.thread_family = self.thread_family or derive_thread_family(self.thread_id)
        self.task_family = self.task_family or derive_task_family(self.task_id)
        return self

    @property
    def title(self) -> str:
        return self.goal or self.summary or self.experience_id

    def to_memory_capsule(self, *, capsule_id: str | None = None) -> "MemoryCapsuleCandidate":
        """将短期经验转换为可入图的长期记忆胶囊。"""

        return MemoryCapsuleCandidate(
            capsule_id=capsule_id or self.experience_id,
            agent_id=self.agent_id,
            run_id=self.run_id,
            thread_id=self.thread_id,
            thread_family=self.thread_family,
            task_id=self.task_id,
            task_family=self.task_family,
            created_at=self.created_at,
            goal=self.goal,
            summary=self.summary,
            outcome=self.outcome,
            knowledge_scope=list(self.knowledge_scope),
            tags=list(self.tags),
            entities=list(self.entities),
            claims=list(self.claims),
            evidence_refs=list(self.evidence_refs),
            source_memory_refs=list(self.source_memory_refs),
            salience_score=self.salience_score,
            confidence=self.confidence,
            status=self.status,
        )


class MemoryCapsuleCandidate(BaseModel):
    """可写入长期记忆图谱的记忆胶囊。"""

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
        """提取用于场景哈希和场景匹配的稳定字段。"""

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


class PromotionComponentScores(BaseModel):
    """经验晋升评分的分项结果。"""

    val_score: float = 0.0
    reuse_score: float = 0.0
    out_score: float = 0.0
    gen_score: float = 0.0
    noise_score: float = 0.0


class PromotionDecision(BaseModel):
    """单条经验是否晋升为长期记忆的决策记录。"""

    experience_id: str
    promoted: bool
    total_score: float
    threshold: float
    scores: PromotionComponentScores
    capsule_id: str | None = None
    reasons: list[str] = Field(default_factory=list)


class PromotionReport(BaseModel):
    """一批经验晋升后的统计报告。"""

    total_candidates: int = 0
    promoted_count: int = 0
    skipped_count: int = 0
    stored_capsule_ids: list[str] = Field(default_factory=list)
    decisions: list[PromotionDecision] = Field(default_factory=list)


class RecallRequest(BaseModel):
    """长期记忆召回请求。"""

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
        """召回请求侧的场景描述，用于和记忆胶囊做匹配。"""

        return {
            "thread_family": self.thread_family,
            "task_family": self.task_family,
            "knowledge_scope": self.knowledge_scope,
            "tags": self.tags,
            "entities": self.entities,
        }


class NodeIndexEntry(BaseModel):
    """给生成提示词使用的节点索引项。"""

    index: str
    capsule_id: str
    title: str
    score: float
    why_selected: str


class GraphEdgeView(BaseModel):
    """给生成提示词使用的图关系视图。"""

    source_index: str
    relation_type: str
    target_index: str
    score: float


class RecallRetrievalReport(BaseModel):
    """召回过程的可审计信息。"""

    candidate_count: int = 0
    expansion_hops: int = 1
    suppressed_stale_nodes: list[str] = Field(default_factory=list)
    suppressed_conflict_nodes: list[str] = Field(default_factory=list)
    lexical_candidate_ids: list[str] = Field(default_factory=list)
    semantic_candidate_ids: list[str] = Field(default_factory=list)
    timing_breakdown_ms: dict[str, float] = Field(default_factory=dict)
    total_latency_ms: float = 0.0


class RecallResponse(BaseModel):
    """召回服务返回给 Agent 的提示词摘要和图证据。"""

    prompt_summary: str
    node_index: list[NodeIndexEntry] = Field(default_factory=list)
    edges: list[GraphEdgeView] = Field(default_factory=list)
    retrieval_report: RecallRetrievalReport = Field(default_factory=RecallRetrievalReport)


class CapsuleDetailResponse(BaseModel):
    """按胶囊 ID 查询详情的返回结果。"""

    details: list["MemoryCapsuleDetail"] = Field(default_factory=list)
    missing_capsule_ids: list[str] = Field(default_factory=list)


class BackfillReport(BaseModel):
    """从历史 SQLite 记忆库回填后的导入报告。"""

    source_path: str
    total_records: int = 0
    imported_capsules: int = 0
    skipped_records: int = 0
    imported_by_kind: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


from ..domain.entities import MemoryCapsuleDetail  # noqa: E402

CapsuleDetailResponse.model_rebuild()
