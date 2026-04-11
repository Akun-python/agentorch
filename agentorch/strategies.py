from __future__ import annotations

from abc import ABC
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, model_validator


class ContextStrategyConfig(BaseModel):
    kind: str = "compact"
    mode: Literal["compact", "balanced", "research_heavy", "custom"] = "compact"
    max_conversation_messages: int = 6
    include_memory_summary: bool = False
    include_retrieval_summary: bool = True
    include_retrieval_evidence: bool = False
    include_retrieval_citations: bool = True
    include_retrieval_report: bool = False
    include_retrieval_plan: bool = False
    include_tool_descriptions: bool = False
    include_skill_instructions: bool = True
    include_task_packet: bool = True
    include_delegation_context: bool = True
    tool_result_policy: Literal["full", "summary", "truncate", "off"] = "summary"
    tool_result_max_chars: int = 500
    retrieval_evidence_max_items: int = 3
    citation_max_items: int = 4
    prompt_char_budget: int = 12000
    prefer_system_compaction: bool = True
    budget_aware_compaction: bool = False
    salience_mode: Literal["off", "rule", "hybrid"] = "off"
    salience_rerank_top_k: int = 8
    segment_char_budget: int | None = None
    segment_min_keep: int = 6
    stage_attention_profiles: dict[str, dict[str, float]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, str):
            mapping = {
                "compact": cls.compact().model_dump(),
                "balanced": cls.balanced().model_dump(),
                "research_heavy": cls.research_heavy().model_dump(),
            }
            return mapping.get(data, {"kind": data, "mode": "custom"})
        return data

    @classmethod
    def from_any(cls, value: "ContextStrategyConfig | str | dict[str, Any] | None", **overrides: Any) -> "ContextStrategyConfig":
        if value is None:
            base = cls.compact()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        return base.model_copy(update=overrides) if overrides else base

    @classmethod
    def compact(cls, **kwargs: Any) -> "ContextStrategyConfig":
        payload = {"kind": "compact", "mode": "compact"}
        payload.update(kwargs)
        return cls(**payload)

    @classmethod
    def balanced(cls, **kwargs: Any) -> "ContextStrategyConfig":
        payload = {
            "kind": "balanced",
            "mode": "balanced",
            "max_conversation_messages": 8,
            "include_memory_summary": True,
            "include_retrieval_evidence": True,
            "include_retrieval_citations": True,
            "include_retrieval_report": False,
            "include_retrieval_plan": False,
            "include_tool_descriptions": False,
            "citation_max_items": 6,
            "retrieval_evidence_max_items": 5,
            "prompt_char_budget": 18000,
            "budget_aware_compaction": True,
            "salience_mode": "rule",
        }
        payload.update(kwargs)
        return cls(**payload)

    @classmethod
    def research_heavy(cls, **kwargs: Any) -> "ContextStrategyConfig":
        payload = {
            "kind": "research_heavy",
            "mode": "research_heavy",
            "max_conversation_messages": 10,
            "include_memory_summary": True,
            "include_retrieval_evidence": True,
            "include_retrieval_citations": True,
            "include_retrieval_report": True,
            "include_retrieval_plan": True,
            "include_tool_descriptions": False,
            "citation_max_items": 8,
            "retrieval_evidence_max_items": 8,
            "prompt_char_budget": 24000,
            "tool_result_policy": "truncate",
            "tool_result_max_chars": 800,
            "budget_aware_compaction": True,
            "salience_mode": "hybrid",
            "salience_rerank_top_k": 10,
        }
        payload.update(kwargs)
        return cls(**payload)


class LongHorizonStrategyConfig(BaseModel):
    kind: str = "long_running_safe"
    history_retention_policy: Literal["window_only", "window_plus_summary", "state_plus_memory"] = "window_plus_summary"
    max_prompt_chars: int = 16000
    max_prompt_messages: int = 14
    summary_refresh_interval: int = 25
    state_snapshot_interval: int = 50
    artifact_rollup_interval: int = 20
    overflow_strategy: Literal["compress", "drop_low_priority", "disable_heavy_blocks", "fail_closed"] = "compress"

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, str):
            if data == "long_running_safe":
                return cls.long_running_safe().model_dump()
            if data == "state_centric":
                return cls.state_centric().model_dump()
            if data == "artifact_first":
                return cls.artifact_first().model_dump()
            return {"kind": data}
        return data

    @classmethod
    def from_any(cls, value: "LongHorizonStrategyConfig | str | dict[str, Any] | None", **overrides: Any) -> "LongHorizonStrategyConfig":
        if value is None:
            base = cls.long_running_safe()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        return base.model_copy(update=overrides) if overrides else base

    @classmethod
    def long_running_safe(cls, **kwargs: Any) -> "LongHorizonStrategyConfig":
        return cls(kind="long_running_safe", **kwargs)

    @classmethod
    def state_centric(cls, **kwargs: Any) -> "LongHorizonStrategyConfig":
        return cls(kind="state_centric", history_retention_policy="state_plus_memory", max_prompt_chars=14000, **kwargs)

    @classmethod
    def artifact_first(cls, **kwargs: Any) -> "LongHorizonStrategyConfig":
        return cls(kind="artifact_first", history_retention_policy="state_plus_memory", artifact_rollup_interval=10, **kwargs)


class CooperationStrategyConfig(BaseModel):
    kind: str = "matriarchal_elephant"
    topology: Literal["matriarchal_elephant", "distributed_herd", "hybrid_herd", "custom"] = "matriarchal_elephant"
    matriarch_agent_name: str | None = "supervisor"
    individual_memory_window: int = 6
    shared_workspace_policy: Literal["artifacts_first", "notes_first", "balanced"] = "artifacts_first"
    collective_memory_promotion_policy: Literal["matriarch_validated", "distributed_consensus", "hybrid"] = "matriarch_validated"
    trail_knowledge_policy: Literal["enabled", "disabled"] = "enabled"
    handoff_policy: Literal["summary_only", "summary_plus_artifacts", "raw_allowed"] = "summary_plus_artifacts"
    route_guidance_policy: Literal["matriarch_guided", "distributed", "hybrid"] = "matriarch_guided"
    risk_alert_policy: Literal["matriarch", "distributed", "hybrid"] = "matriarch"

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, str):
            mapping = {
                "matriarchal_elephant": cls.matriarchal().model_dump(),
                "distributed_herd": cls.distributed().model_dump(),
                "distributed_swarm": cls.distributed().model_dump(),
                "hybrid_herd": cls.hybrid().model_dump(),
            }
            return mapping.get(data, {"kind": data, "topology": "custom"})
        return data

    @classmethod
    def from_any(cls, value: "CooperationStrategyConfig | str | dict[str, Any] | None", **overrides: Any) -> "CooperationStrategyConfig":
        if value is None:
            base = cls.matriarchal()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        return base.model_copy(update=overrides) if overrides else base

    @classmethod
    def matriarchal(cls, **kwargs: Any) -> "CooperationStrategyConfig":
        return cls(kind="matriarchal_elephant", topology="matriarchal_elephant", **kwargs)

    @classmethod
    def distributed(cls, **kwargs: Any) -> "CooperationStrategyConfig":
        return cls(
            kind="distributed_herd",
            topology="distributed_herd",
            matriarch_agent_name=None,
            collective_memory_promotion_policy="distributed_consensus",
            handoff_policy="summary_only",
            route_guidance_policy="distributed",
            risk_alert_policy="distributed",
            **kwargs,
        )

    @classmethod
    def hybrid(cls, **kwargs: Any) -> "CooperationStrategyConfig":
        return cls(
            kind="hybrid_herd",
            topology="hybrid_herd",
            collective_memory_promotion_policy="hybrid",
            route_guidance_policy="hybrid",
            risk_alert_policy="hybrid",
            **kwargs,
        )


class MemoryGovernanceStrategyConfig(BaseModel):
    kind: str = "mgcm"
    promotion_policy: str | None = None
    index_policy: str | None = None
    recall_policy: str | None = None
    decay_policy: str | None = None
    collective_promotion_policy: Literal["validated_only", "evidence_weighted", "manual"] = "validated_only"
    trail_knowledge_enabled: bool = True
    validation_threshold: float = 0.7
    episodic_memory_enabled: bool = True
    episodic_capsule_limit: int = 4
    scene_index_fields: list[str] = Field(default_factory=lambda: ["goal", "knowledge_scope", "agent_role", "thread_id"])
    capsule_promotion_threshold: float = 1.5
    recall_top_k: int = 4
    allow_cross_thread_recall: bool = False
    relevance_weight: float = 4.0
    evidence_weight: float = 1.8
    reuse_weight: float = 0.8
    outcome_weight: float = 1.2
    recency_weight: float = 0.0
    semantic_promotion_threshold: float = 2.3
    collective_promotion_threshold: float = 2.8
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, str):
            if data in {"mgcm", "default"}:
                return cls.default().model_dump()
            if data == "nutcracker_memory":
                return cls.nutcracker().model_dump()
            if data == "episodic_only":
                return cls.episodic_only().model_dump()
            if data == "semantic_only":
                return cls.semantic_only().model_dump()
            if data == "hybrid_long_memory":
                return cls.hybrid_long_memory().model_dump()
            return {"kind": data}
        if isinstance(data, dict):
            normalized = dict(data)
            legacy = normalized.get("promotion_policy")
            if (
                isinstance(legacy, str)
                and legacy in {"validated_only", "evidence_weighted", "manual"}
                and "collective_promotion_policy" not in normalized
            ):
                normalized["collective_promotion_policy"] = legacy
            return normalized
        return data

    @classmethod
    def from_any(cls, value: "MemoryGovernanceStrategyConfig | str | dict[str, Any] | None", **overrides: Any) -> "MemoryGovernanceStrategyConfig":
        if value is None:
            base = cls.default()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        elif isinstance(value, dict):
            raw = dict(value)
            kind = raw.get("kind")
            preset_map = {
                "mgcm": cls.default,
                "default": cls.default,
                "nutcracker_memory": cls.nutcracker,
                "episodic_only": cls.episodic_only,
                "semantic_only": cls.semantic_only,
                "hybrid_long_memory": cls.hybrid_long_memory,
            }
            if kind in preset_map:
                base = preset_map[kind]().model_copy(update=raw)
            else:
                base = cls.model_validate(raw)
        else:
            base = cls.model_validate(value)
        return base.model_copy(update=overrides) if overrides else base

    @classmethod
    def default(cls, **kwargs: Any) -> "MemoryGovernanceStrategyConfig":
        payload = {
            "kind": "mgcm",
            "collective_promotion_policy": "validated_only",
            "index_policy": "scene_hash",
            "recall_policy": "scene_first",
            "decay_policy": "relevance_only",
        }
        payload.update(kwargs)
        return cls(**payload)

    @classmethod
    def nutcracker(cls, **kwargs: Any) -> "MemoryGovernanceStrategyConfig":
        payload = {
            "kind": "nutcracker_memory",
            "promotion_policy": "episodic_salience",
            "index_policy": "scene_hash",
            "recall_policy": "scene_first",
            "decay_policy": "relevance_only",
        }
        payload.update(kwargs)
        return cls(**payload)

    @classmethod
    def episodic_only(cls, **kwargs: Any) -> "MemoryGovernanceStrategyConfig":
        payload = cls.nutcracker().model_dump()
        payload.update({"kind": "episodic_only", "semantic_promotion_threshold": 9999.0})
        payload.update(kwargs)
        return cls(**payload)

    @classmethod
    def semantic_only(cls, **kwargs: Any) -> "MemoryGovernanceStrategyConfig":
        payload = cls.nutcracker().model_dump()
        payload.update({"kind": "semantic_only", "episodic_memory_enabled": False})
        payload.update(kwargs)
        return cls(**payload)

    @classmethod
    def hybrid_long_memory(cls, **kwargs: Any) -> "MemoryGovernanceStrategyConfig":
        payload = cls.nutcracker().model_dump()
        payload.update({"kind": "hybrid_long_memory", "allow_cross_thread_recall": True, "recall_top_k": 6})
        payload.update(kwargs)
        return cls(**payload)


class BaseContextStrategy(ABC):
    def __init__(self, config: ContextStrategyConfig) -> None:
        self.config = config


class BaseLongHorizonStrategy(ABC):
    def __init__(self, config: LongHorizonStrategyConfig) -> None:
        self.config = config


class BaseCooperationStrategy(ABC):
    def __init__(self, config: CooperationStrategyConfig) -> None:
        self.config = config

    def build_handoff_packet(self, *, task_context: dict[str, Any], artifacts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if self.config.handoff_policy == "raw_allowed":
            return {**task_context, "artifact_refs": artifacts or []}
        if self.config.handoff_policy == "summary_only":
            return {"summary": task_context.get("summary") or task_context.get("goal") or "", "artifact_refs": []}
        return {"summary": task_context.get("summary") or task_context.get("goal") or "", "artifact_refs": artifacts or []}

    def select_shared_context(self, *, task_context: dict[str, Any]) -> dict[str, Any]:
        return {"topology": self.config.topology, "task_context": task_context}

    def build_shared_workspace_view(self, *, notes: list[dict[str, Any]] | None = None, artifacts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {"policy": self.config.shared_workspace_policy, "notes": notes or [], "artifacts": artifacts or []}

    def route_collective_memory(self, *, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {"policy": self.config.collective_memory_promotion_policy, "records": records or []}

    def promote_trail_knowledge(self, *, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {"enabled": self.config.trail_knowledge_policy == "enabled", "records": records or []}

    def build_supervisor_context(self, *, task_context: dict[str, Any]) -> dict[str, Any]:
        return {"topology": self.config.topology, "matriarch_agent_name": self.config.matriarch_agent_name, "task_context": task_context}

    def should_share_raw_history(self) -> bool:
        return self.config.handoff_policy == "raw_allowed"


class BaseMemoryGovernanceStrategy(ABC):
    def __init__(self, config: MemoryGovernanceStrategyConfig) -> None:
        self.config = config

    def policy_bundle(self) -> dict[str, str | None]:
        return {
            "promotion_policy": self.config.promotion_policy,
            "index_policy": self.config.index_policy,
            "recall_policy": self.config.recall_policy,
            "decay_policy": self.config.decay_policy,
        }

    def resolved_runtime_config(self) -> dict[str, Any]:
        return {
            "episodic_memory_enabled": self.config.episodic_memory_enabled,
            "episodic_capsule_limit": self.config.episodic_capsule_limit,
            "scene_index_fields": list(self.config.scene_index_fields),
            "capsule_promotion_threshold": self.config.capsule_promotion_threshold,
            "recall_top_k": self.config.recall_top_k,
            "allow_cross_thread_recall": self.config.allow_cross_thread_recall,
            "relevance_weight": self.config.relevance_weight,
            "evidence_weight": self.config.evidence_weight,
            "reuse_weight": self.config.reuse_weight,
            "outcome_weight": self.config.outcome_weight,
            "recency_weight": self.config.recency_weight,
            "semantic_promotion_threshold": self.config.semantic_promotion_threshold,
            "collective_promotion_threshold": self.config.collective_promotion_threshold,
            **dict(self.config.config or {}),
        }

    def _policy_instance(self, policy_kind: str | None, factory_name: str):
        if not policy_kind:
            return None
        from agentorch.memory.factory import (
            create_memory_decay_policy,
            create_memory_index_policy,
            create_memory_promotion_policy,
            create_memory_recall_policy,
        )

        factories = {
            "promotion": create_memory_promotion_policy,
            "index": create_memory_index_policy,
            "recall": create_memory_recall_policy,
            "decay": create_memory_decay_policy,
        }
        return factories[factory_name](policy_kind)

    async def promote_episode(self, manager: Any, **kwargs: Any) -> list[dict[str, Any]]:
        promotion_policy = self._policy_instance(self.config.promotion_policy, "promotion")
        index_policy = self._policy_instance(self.config.index_policy, "index")
        if promotion_policy is None or index_policy is None:
            return []
        return await promotion_policy.promote(
            manager,
            config=self.resolved_runtime_config(),
            strategy_kind=self.config.kind,
            index_policy=index_policy,
            **kwargs,
        )

    async def search_long_term_memory(self, manager: Any, **kwargs: Any) -> list[dict[str, Any]]:
        recall_policy = self._policy_instance(self.config.recall_policy, "recall")
        index_policy = self._policy_instance(self.config.index_policy, "index")
        decay_policy = self._policy_instance(self.config.decay_policy, "decay")
        if recall_policy is None or index_policy is None or decay_policy is None:
            return []
        return await recall_policy.recall(
            manager,
            config=self.resolved_runtime_config(),
            strategy_kind=self.config.kind,
            index_policy=index_policy,
            decay_policy=decay_policy,
            **kwargs,
        )

    def build_memory_evidence(
        self,
        *,
        runtime: Any,
        candidates: list[dict[str, Any]],
        thread_id: str,
        knowledge_scope: list[str],
    ) -> tuple[list[Any], list[Any], dict[str, Any]]:
        from agentorch.knowledge import Citation, RetrievedEvidence

        evidence = []
        citations = []
        selected = []
        for candidate in candidates:
            record = dict(candidate.get("record") or {})
            metadata = dict(record.get("metadata") or {})
            source_type = candidate.get("source_type") or record.get("kind") or "memory_record"
            document_id = f"{source_type}:{record.get('id')}"
            citation = Citation(
                source=source_type,
                document_id=document_id,
                chunk_id=document_id,
                quote=record.get("content"),
                locator={"record_id": record.get("id"), "thread_id": record.get("thread_id", thread_id)},
                metadata={
                    "kind": record.get("kind"),
                    "score": candidate.get("score", 0.0),
                    "scene_index": metadata.get("scene_index"),
                },
            )
            evidence.append(
                RetrievedEvidence(
                    chunk=runtime._memory_evidence_chunk(
                        citation.document_id,
                        citation.chunk_id,
                        record.get("content", ""),
                        source_type,
                        citation.locator,
                        knowledge_scope,
                    ),
                    citation=citation,
                    summary=record.get("content"),
                    source_type=source_type,
                    locator=citation.locator,
                    claim=record.get("kind"),
                    snippet=record.get("content"),
                    relevance_score=float(candidate.get("score", 0.0)),
                    support_score=float(metadata.get("confidence", 0.5)),
                    scope_tags=list(knowledge_scope),
                )
            )
            citations.append(citation)
            selected.append(
                {
                    "record_id": record.get("id"),
                    "kind": record.get("kind"),
                    "source_type": source_type,
                    "score": candidate.get("score", 0.0),
                    "score_breakdown": candidate.get("score_breakdown", {}),
                }
            )
        report = {
            "mechanism": self.config.kind,
            "policy_bundle": self.policy_bundle(),
            "config": self.resolved_runtime_config(),
            "selected_count": len(selected),
            "selected": selected,
        }
        return evidence, citations, report

    async def validate_memory(self, manager: Any, record_id: int) -> dict[str, Any] | None:
        return await manager.validate_collective_memory(record_id)


class CompactContextStrategy(BaseContextStrategy):
    pass


class BalancedContextStrategy(BaseContextStrategy):
    pass


class ResearchHeavyContextStrategy(BaseContextStrategy):
    pass


class LongRunningSafeStrategy(BaseLongHorizonStrategy):
    pass


class StateCentricStrategy(BaseLongHorizonStrategy):
    pass


class ArtifactFirstStrategy(BaseLongHorizonStrategy):
    pass


class MatriarchalElephantStrategy(BaseCooperationStrategy):
    pass


class DistributedHerdStrategy(BaseCooperationStrategy):
    pass


class HybridHerdStrategy(BaseCooperationStrategy):
    pass


class DefaultMemoryGovernanceStrategy(BaseMemoryGovernanceStrategy):
    pass


class NutcrackerMemoryStrategy(BaseMemoryGovernanceStrategy):
    pass


class EpisodicOnlyMemoryStrategy(BaseMemoryGovernanceStrategy):
    pass


class SemanticOnlyMemoryStrategy(BaseMemoryGovernanceStrategy):
    pass


class HybridLongMemoryStrategy(BaseMemoryGovernanceStrategy):
    pass


class CustomMemoryGovernanceStrategy(BaseMemoryGovernanceStrategy):
    pass


class StrategyRegistration(BaseModel):
    kind: str
    factory: Callable[..., Any]


_CONTEXT_REGISTRY: dict[str, Callable[..., Any]] = {}
_LONG_HORIZON_REGISTRY: dict[str, Callable[..., Any]] = {}
_COOPERATION_REGISTRY: dict[str, Callable[..., Any]] = {}
_MEMORY_GOVERNANCE_REGISTRY: dict[str, Callable[..., Any]] = {}
_PROFILE_REGISTRY: dict[str, Callable[[], dict[str, Any]]] = {}


def register_context_strategy(kind: str, strategy_cls_or_factory: Callable[..., Any], config_cls=None) -> None:
    _CONTEXT_REGISTRY[kind] = strategy_cls_or_factory


def register_long_horizon_strategy(kind: str, strategy_cls_or_factory: Callable[..., Any], config_cls=None) -> None:
    _LONG_HORIZON_REGISTRY[kind] = strategy_cls_or_factory


def register_cooperation_strategy(kind: str, strategy_cls_or_factory: Callable[..., Any], config_cls=None) -> None:
    _COOPERATION_REGISTRY[kind] = strategy_cls_or_factory


def register_memory_governance_strategy(kind: str, strategy_cls_or_factory: Callable[..., Any], config_cls=None) -> None:
    _MEMORY_GOVERNANCE_REGISTRY[kind] = strategy_cls_or_factory


def register_orchestration_profile(name: str, profile_builder: Callable[[], dict[str, Any]]) -> None:
    _PROFILE_REGISTRY[name] = profile_builder


def list_context_strategies() -> list[str]:
    return sorted(_CONTEXT_REGISTRY)


def list_long_horizon_strategies() -> list[str]:
    return sorted(_LONG_HORIZON_REGISTRY)


def list_cooperation_strategies() -> list[str]:
    return sorted(_COOPERATION_REGISTRY)


def list_memory_governance_strategies() -> list[str]:
    return sorted(_MEMORY_GOVERNANCE_REGISTRY)


def list_orchestration_profiles() -> list[str]:
    return sorted(_PROFILE_REGISTRY)


def create_context_strategy(config: ContextStrategyConfig | str | dict[str, Any] | None = None) -> BaseContextStrategy:
    if isinstance(config, BaseContextStrategy):
        return config
    resolved = ContextStrategyConfig.from_any(config)
    factory = _CONTEXT_REGISTRY[resolved.kind]
    return factory(resolved)


def create_long_horizon_strategy(config: LongHorizonStrategyConfig | str | dict[str, Any] | None = None) -> BaseLongHorizonStrategy:
    if isinstance(config, BaseLongHorizonStrategy):
        return config
    resolved = LongHorizonStrategyConfig.from_any(config)
    factory = _LONG_HORIZON_REGISTRY[resolved.kind]
    return factory(resolved)


def create_cooperation_strategy(config: CooperationStrategyConfig | str | dict[str, Any] | None = None) -> BaseCooperationStrategy:
    if isinstance(config, BaseCooperationStrategy):
        return config
    resolved = CooperationStrategyConfig.from_any(config)
    factory = _COOPERATION_REGISTRY[resolved.kind]
    return factory(resolved)


def create_memory_governance_strategy(config: MemoryGovernanceStrategyConfig | str | dict[str, Any] | None = None) -> BaseMemoryGovernanceStrategy:
    if isinstance(config, BaseMemoryGovernanceStrategy):
        return config
    resolved = MemoryGovernanceStrategyConfig.from_any(config)
    factory = _MEMORY_GOVERNANCE_REGISTRY[resolved.kind]
    return factory(resolved)


def resolve_orchestration_profile(name: str | None) -> dict[str, Any]:
    if not name:
        return {}
    builder = _PROFILE_REGISTRY[name]
    return builder()


def bootstrap_strategy_defaults() -> None:
    register_context_strategy("compact", CompactContextStrategy)
    register_context_strategy("balanced", BalancedContextStrategy)
    register_context_strategy("research_heavy", ResearchHeavyContextStrategy)
    register_long_horizon_strategy("long_running_safe", LongRunningSafeStrategy)
    register_long_horizon_strategy("state_centric", StateCentricStrategy)
    register_long_horizon_strategy("artifact_first", ArtifactFirstStrategy)
    register_cooperation_strategy("matriarchal_elephant", MatriarchalElephantStrategy)
    register_cooperation_strategy("distributed_herd", DistributedHerdStrategy)
    register_cooperation_strategy("hybrid_herd", HybridHerdStrategy)
    register_memory_governance_strategy("mgcm", DefaultMemoryGovernanceStrategy)
    register_memory_governance_strategy("nutcracker_memory", NutcrackerMemoryStrategy)
    register_memory_governance_strategy("episodic_only", EpisodicOnlyMemoryStrategy)
    register_memory_governance_strategy("semantic_only", SemanticOnlyMemoryStrategy)
    register_memory_governance_strategy("hybrid_long_memory", HybridLongMemoryStrategy)
    register_memory_governance_strategy("custom", CustomMemoryGovernanceStrategy)
    register_orchestration_profile(
        "default_safe",
        lambda: {
            "context_strategy": ContextStrategyConfig.compact().model_dump(),
            "long_horizon_strategy": LongHorizonStrategyConfig.long_running_safe().model_dump(),
            "cooperation_strategy": CooperationStrategyConfig.matriarchal().model_dump(),
            "memory_governance_strategy": MemoryGovernanceStrategyConfig.default().model_dump(),
        },
    )
    register_orchestration_profile(
        "compact_single_agent",
        lambda: {
            "context_strategy": ContextStrategyConfig.compact().model_dump(),
            "long_horizon_strategy": LongHorizonStrategyConfig.state_centric().model_dump(),
            "cooperation_strategy": CooperationStrategyConfig.distributed().model_dump(),
            "memory_governance_strategy": MemoryGovernanceStrategyConfig.default().model_dump(),
        },
    )
    register_orchestration_profile(
        "deep_research",
        lambda: {
            "context_strategy": ContextStrategyConfig.compact(include_retrieval_evidence=True, include_retrieval_citations=True).model_dump(),
            "long_horizon_strategy": LongHorizonStrategyConfig.long_running_safe().model_dump(),
            "cooperation_strategy": CooperationStrategyConfig.matriarchal().model_dump(),
            "memory_governance_strategy": MemoryGovernanceStrategyConfig.default().model_dump(),
        },
    )
    register_orchestration_profile(
        "matriarchal_elephant",
        lambda: {
            "context_strategy": ContextStrategyConfig.compact().model_dump(),
            "long_horizon_strategy": LongHorizonStrategyConfig.long_running_safe().model_dump(),
            "cooperation_strategy": CooperationStrategyConfig.matriarchal().model_dump(),
            "memory_governance_strategy": MemoryGovernanceStrategyConfig.default().model_dump(),
        },
    )
    register_orchestration_profile(
        "distributed_swarm",
        lambda: {
            "context_strategy": ContextStrategyConfig.balanced().model_dump(),
            "long_horizon_strategy": LongHorizonStrategyConfig.state_centric().model_dump(),
            "cooperation_strategy": CooperationStrategyConfig.distributed().model_dump(),
            "memory_governance_strategy": MemoryGovernanceStrategyConfig.default().model_dump(),
        },
    )
    register_orchestration_profile(
        "research_heavy",
        lambda: {
            "context_strategy": ContextStrategyConfig.research_heavy().model_dump(),
            "long_horizon_strategy": LongHorizonStrategyConfig.artifact_first().model_dump(),
            "cooperation_strategy": CooperationStrategyConfig.hybrid().model_dump(),
            "memory_governance_strategy": MemoryGovernanceStrategyConfig.default().model_dump(),
        },
    )
    register_orchestration_profile(
        "coding_agent",
        lambda: {
            "context_strategy": ContextStrategyConfig.compact(
                include_tool_descriptions=False,
                max_conversation_messages=4,
                tool_result_policy="truncate",
                tool_result_max_chars=320,
                budget_aware_compaction=True,
                salience_mode="rule",
                prompt_char_budget=10000,
            ).model_dump(),
            "long_horizon_strategy": LongHorizonStrategyConfig.state_centric().model_dump(),
            "cooperation_strategy": CooperationStrategyConfig.distributed().model_dump(),
            "memory_governance_strategy": MemoryGovernanceStrategyConfig.default().model_dump(),
        },
    )
    register_orchestration_profile(
        "workflow_oriented",
        lambda: {
            "context_strategy": ContextStrategyConfig.balanced(include_retrieval_plan=True).model_dump(),
            "long_horizon_strategy": LongHorizonStrategyConfig.artifact_first().model_dump(),
            "cooperation_strategy": CooperationStrategyConfig.hybrid().model_dump(),
            "memory_governance_strategy": MemoryGovernanceStrategyConfig.default().model_dump(),
        },
    )


bootstrap_strategy_defaults()
