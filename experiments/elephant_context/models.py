from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


_DEFAULT_STAGE_ATTENTION_PROFILES: dict[str, dict[str, float]] = {
    "default": {
        "collective_memory": 1.18,
        "retrieval_evidence": 1.12,
        "delegation_context": 1.05,
        "task_packet": 1.00,
        "tool_observation": 0.88,
        "conversation": 0.78,
    },
    "plan": {
        "task_packet": 1.30,
        "delegation_context": 1.22,
        "collective_memory": 1.20,
        "retrieval_evidence": 1.05,
        "tool_observation": 0.65,
        "conversation": 0.70,
    },
    "execute*": {
        "tool_observation": 1.22,
        "retrieval_evidence": 1.18,
        "collective_memory": 1.10,
        "delegation_context": 1.02,
        "conversation": 0.82,
    },
    "review": {
        "citation": 1.18,
        "retrieval_report": 1.12,
        "collective_memory": 1.08,
        "conversation": 0.80,
        "tool_observation": 0.86,
    },
    "aggregate": {
        "citation": 1.18,
        "retrieval_report": 1.12,
        "collective_memory": 1.08,
        "conversation": 0.80,
        "tool_observation": 0.86,
    },
}


def default_stage_attention_profiles() -> dict[str, dict[str, float]]:
    return deepcopy(_DEFAULT_STAGE_ATTENTION_PROFILES)


def flatten_stage_attention_profiles() -> dict[str, dict[str, float]]:
    return {"default": deepcopy(_DEFAULT_STAGE_ATTENTION_PROFILES["default"])}


class ElephantChapterConfig(BaseModel):
    char_budget: int = 18000
    selection_mode: Literal["rule", "hybrid"] = "hybrid"
    overflow_action: Literal["compress", "drop_low_priority", "disable_heavy_blocks", "fail_closed"] = "compress"
    conversation_window: int = 6
    tool_observation_mode: Literal["full", "summary", "truncate", "off"] = "summary"
    stage_attention_profiles: dict[str, dict[str, float]] = Field(default_factory=default_stage_attention_profiles)
    use_builtin_stage_profiles: bool = False
    redundancy_inhibition_enabled: bool = True
    salience_rerank_top_k: int = 8
    segment_min_keep: int = 6
    route_mode: Literal["guided", "distributed"] = "guided"
    validation_threshold: float = 0.65
    collective_promotion_threshold: float = 2.4
    retrieval_evidence_max_items: int = 5
    retrieval_citation_max_items: int = 6
    shared_memory_max_items: int = 6
    default_knowledge_scope: list[str] = Field(default_factory=lambda: ["planning"])

    @model_validator(mode="after")
    def _normalize_bounds(self) -> "ElephantChapterConfig":
        self.char_budget = max(2000, int(self.char_budget))
        self.salience_rerank_top_k = max(1, int(self.salience_rerank_top_k))
        self.segment_min_keep = max(1, int(self.segment_min_keep))
        self.retrieval_evidence_max_items = max(1, int(self.retrieval_evidence_max_items))
        self.retrieval_citation_max_items = max(1, int(self.retrieval_citation_max_items))
        self.shared_memory_max_items = max(1, int(self.shared_memory_max_items))
        self.validation_threshold = min(max(float(self.validation_threshold), 0.0), 1.0)
        self.collective_promotion_threshold = max(float(self.collective_promotion_threshold), 0.0)
        return self

    def merged(self, **updates: Any) -> "ElephantChapterConfig":
        return self.model_copy(update=updates, deep=True)


class ElephantVariantSpec(BaseModel):
    name: str
    description: str
    category: Literal["baseline", "ablation"] = "baseline"
    aliases: list[str] = Field(default_factory=list)
    multi_agent: bool = True
    use_elephant_selector: bool = True
    use_elephant_route_planner: bool = True
    use_elephant_memory_evaluator: bool = True
    chapter_config: ElephantChapterConfig = Field(default_factory=ElephantChapterConfig)
    default_knowledge_scope: list[str] = Field(default_factory=lambda: ["planning"])


class BenchmarkMessageSeed(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkKnowledgeDocument(BaseModel):
    document_id: str
    text: str
    scopes: list[str] = Field(default_factory=list)
    source_type: str = "benchmark"
    locator: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkCollectiveMemory(BaseModel):
    kind: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source_agents: list[str] = Field(default_factory=lambda: ["elder"])
    confidence: float = 0.85
    scope: str | None = None


class ElephantBenchmarkCase(BaseModel):
    case_id: str
    family: str
    description: str
    user_input: str
    stage_tags: list[str] = Field(default_factory=list)
    knowledge_scope: list[str] = Field(default_factory=lambda: ["elephant-benchmark"])
    thread_messages: list[BenchmarkMessageSeed] = Field(default_factory=list)
    knowledge_documents: list[BenchmarkKnowledgeDocument] = Field(default_factory=list)
    collective_memories: list[BenchmarkCollectiveMemory] = Field(default_factory=list)
    task_context: dict[str, Any] = Field(default_factory=dict)
    gold_key_segment_ids: list[str] = Field(default_factory=list)
    gold_support_segment_ids: list[str] = Field(default_factory=list)
    stage_focus_segment_ids: list[str] = Field(default_factory=list)
    expected_answer_fields: dict[str, str] = Field(default_factory=dict)
    critical_markers: list[str] = Field(default_factory=list)
    distractor_markers: list[str] = Field(default_factory=list)


__all__ = [
    "BenchmarkCollectiveMemory",
    "BenchmarkKnowledgeDocument",
    "BenchmarkMessageSeed",
    "ElephantBenchmarkCase",
    "ElephantChapterConfig",
    "ElephantVariantSpec",
    "default_stage_attention_profiles",
    "flatten_stage_attention_profiles",
]
