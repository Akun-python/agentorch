from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def _deepcopy_dict(value: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(value)


_DEFAULT_CONTEXT_SOURCES: dict[str, Any] = {
    "memory_summary": True,
    "retrieval_summary": True,
    "retrieval_evidence": {"enabled": False, "max_items": 3},
    "retrieval_citations": {"enabled": True, "max_items": 4},
    "retrieval_report": False,
    "retrieval_plan": False,
    "tool_descriptions": False,
    "skill_instructions": True,
    "task_packet": {"enabled": True, "representation": "capsule"},
    "delegation_context": {"enabled": True, "representation": "capsule"},
    "shared_memory": {"enabled": True, "max_items": 4},
}

_DEFAULT_MEMORY_THRESHOLDS: dict[str, Any] = {
    "validation_threshold": 0.7,
    "recall_top_k": 4,
    "allow_cross_thread_recall": False,
    "index_policy": "scene_hash",
    "decay_policy": "relevance_only",
    "episodic_memory_enabled": True,
    "episodic_capsule_limit": 4,
    "scene_index_fields": ["goal", "knowledge_scope", "agent_role", "thread_id"],
    "capsule_promotion_threshold": 1.5,
    "semantic_promotion_threshold": 2.3,
    "collective_promotion_threshold": 2.8,
    "relevance_weight": 4.0,
    "evidence_weight": 1.8,
    "reuse_weight": 0.8,
    "outcome_weight": 1.2,
    "recency_weight": 0.0,
    "trail_knowledge_enabled": True,
}


class ContextPolicy(BaseModel):
    """Neutral prompt-context governance policy."""

    sources: dict[str, Any] = Field(default_factory=lambda: _deepcopy_dict(_DEFAULT_CONTEXT_SOURCES))
    conversation_window: int = 8
    char_budget: int = 18000
    tool_observation_mode: Literal["full", "summary", "truncate", "off"] = "summary"
    selection_mode: Literal["rule", "hybrid"] = "rule"
    overflow_action: Literal["compress", "drop_low_priority", "disable_heavy_blocks", "fail_closed"] = "compress"

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if data is None:
            return cls.default().model_dump()
        if isinstance(data, cls):
            return data
        if isinstance(data, dict):
            normalized = dict(data)
            normalized.setdefault("sources", _deepcopy_dict(_DEFAULT_CONTEXT_SOURCES))
            return normalized
        raise TypeError("ContextPolicy accepts a ContextPolicy instance or a mapping.")

    @classmethod
    def from_any(cls, value: "ContextPolicy | dict[str, Any] | None", **overrides: Any) -> "ContextPolicy":
        if value is None:
            base = cls.default()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        return base.model_copy(update=overrides) if overrides else base

    @classmethod
    def default(cls, **overrides: Any) -> "ContextPolicy":
        return cls(**overrides)

    @classmethod
    def lean(cls, **overrides: Any) -> "ContextPolicy":
        payload = {
            "conversation_window": 6,
            "char_budget": 12000,
            "sources": {
                **_deepcopy_dict(_DEFAULT_CONTEXT_SOURCES),
                "memory_summary": False,
                "retrieval_evidence": False,
                "retrieval_report": False,
                "tool_descriptions": False,
            },
        }
        payload.update(overrides)
        return cls(**payload)

    @classmethod
    def evidence_friendly(cls, **overrides: Any) -> "ContextPolicy":
        payload = {
            "conversation_window": 10,
            "char_budget": 22000,
            "sources": {
                **_deepcopy_dict(_DEFAULT_CONTEXT_SOURCES),
                "memory_summary": True,
                "retrieval_evidence": {"enabled": True, "max_items": 6},
                "retrieval_citations": {"enabled": True, "max_items": 8},
                "retrieval_report": True,
                "retrieval_plan": True,
            },
        }
        payload.update(overrides)
        return cls(**payload)

    @classmethod
    def hybrid_budgeted(cls, **overrides: Any) -> "ContextPolicy":
        payload = cls.evidence_friendly(selection_mode="hybrid").model_dump()
        payload.update(overrides)
        return cls(**payload)

    def _source_config(self, name: str) -> dict[str, Any]:
        raw = self.sources.get(name, False)
        if isinstance(raw, bool):
            return {"enabled": raw}
        if isinstance(raw, dict):
            return {"enabled": raw.get("enabled", True), **raw}
        return {"enabled": bool(raw)}

    def source_enabled(self, name: str) -> bool:
        return bool(self._source_config(name).get("enabled", False))

    def source_limit(self, name: str, default: int | None = None) -> int | None:
        value = self._source_config(name).get("max_items", default)
        return int(value) if value is not None else None

    def source_representation(self, name: str, default: str = "full") -> str:
        return str(self._source_config(name).get("representation", default))

    @property
    def include_memory_summary(self) -> bool:
        return self.source_enabled("memory_summary")

    @property
    def include_retrieval_summary(self) -> bool:
        return self.source_enabled("retrieval_summary")

    @property
    def include_retrieval_evidence(self) -> bool:
        return self.source_enabled("retrieval_evidence")

    @property
    def retrieval_evidence_max_items(self) -> int:
        return int(self.source_limit("retrieval_evidence", 3) or 3)

    @property
    def include_retrieval_citations(self) -> bool:
        return self.source_enabled("retrieval_citations")

    @property
    def citation_max_items(self) -> int:
        return int(self.source_limit("retrieval_citations", 4) or 4)

    @property
    def include_retrieval_report(self) -> bool:
        return self.source_enabled("retrieval_report")

    @property
    def include_retrieval_plan(self) -> bool:
        return self.source_enabled("retrieval_plan")

    @property
    def include_tool_descriptions(self) -> bool:
        return self.source_enabled("tool_descriptions")

    @property
    def include_skill_instructions(self) -> bool:
        return self.source_enabled("skill_instructions")

    @property
    def include_task_packet(self) -> bool:
        return self.source_enabled("task_packet")

    @property
    def include_delegation_context(self) -> bool:
        return self.source_enabled("delegation_context")

    @property
    def include_collective_memory(self) -> bool:
        return self.source_enabled("shared_memory")

    @property
    def collective_memory_max_items(self) -> int:
        return int(self.source_limit("shared_memory", 4) or 4)

    @property
    def max_conversation_messages(self) -> int:
        return self.conversation_window

    @property
    def prompt_char_budget(self) -> int:
        return self.char_budget

    @property
    def segment_char_budget(self) -> int:
        return self.char_budget

    @property
    def salience_mode(self) -> str:
        return self.selection_mode

    @property
    def salience_rerank_top_k(self) -> int:
        return 8

    @property
    def segment_min_keep(self) -> int:
        return 6

    @property
    def budget_aware_compaction(self) -> bool:
        return self.overflow_action in {"compress", "drop_low_priority", "disable_heavy_blocks"}

    @property
    def tool_result_policy(self) -> str:
        return self.tool_observation_mode

    @property
    def tool_result_max_chars(self) -> int:
        if self.tool_observation_mode == "truncate":
            return 800
        if self.tool_observation_mode == "summary":
            return 500
        return self.char_budget

    @property
    def stage_attention_profiles(self) -> dict[str, dict[str, float]]:
        return {}


class StatePolicy(BaseModel):
    """Neutral state-retention and refresh policy."""

    retention_mode: Literal["window_only", "window_plus_summary", "state_plus_memory"] = "window_plus_summary"
    summary_refresh_every: int = 25
    snapshot_every: int = 50
    rollup_every: int = 20

    @classmethod
    def from_any(cls, value: "StatePolicy | dict[str, Any] | None", **overrides: Any) -> "StatePolicy":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        return base.model_copy(update=overrides) if overrides else base

    @property
    def history_retention_policy(self) -> str:
        return self.retention_mode

    @property
    def max_prompt_messages(self) -> int:
        return 10 if self.retention_mode == "window_only" else 14


class CoordinationPolicy(BaseModel):
    """Neutral multi-agent coordination policy."""

    handoff_mode: Literal["summary_only", "summary_plus_artifacts", "raw_allowed"] = "summary_plus_artifacts"
    workspace_mode: Literal["artifacts_first", "notes_first", "balanced"] = "artifacts_first"
    route_mode: Literal["guided", "distributed", "hybrid"] = "guided"
    alert_mode: Literal["direct", "shared", "hybrid"] = "direct"

    @classmethod
    def from_any(cls, value: "CoordinationPolicy | dict[str, Any] | None", **overrides: Any) -> "CoordinationPolicy":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        return base.model_copy(update=overrides) if overrides else base

    @classmethod
    def distributed(cls, **overrides: Any) -> "CoordinationPolicy":
        return cls(route_mode="distributed", handoff_mode="summary_only", alert_mode="shared", **overrides)

    @classmethod
    def hybrid(cls, **overrides: Any) -> "CoordinationPolicy":
        return cls(route_mode="hybrid", alert_mode="hybrid", **overrides)

    @property
    def handoff_policy(self) -> str:
        return self.handoff_mode

    @property
    def shared_workspace_policy(self) -> str:
        return self.workspace_mode

    @property
    def route_guidance_policy(self) -> str:
        return self.route_mode

    @property
    def risk_alert_policy(self) -> str:
        return self.alert_mode

    @property
    def topology(self) -> str:
        return self.route_mode

    @property
    def trail_knowledge_policy(self) -> str:
        return "enabled"


class MemoryPolicy(BaseModel):
    """Neutral long-memory governance policy."""

    recall_mode: Literal["off", "thread", "scene", "hybrid"] = "scene"
    promotion_mode: Literal["off", "episodic", "semantic", "hybrid", "validated"] = "episodic"
    validation_mode: Literal["off", "threshold", "manual"] = "threshold"
    thresholds_and_weights: dict[str, Any] = Field(default_factory=lambda: _deepcopy_dict(_DEFAULT_MEMORY_THRESHOLDS))

    @classmethod
    def from_any(cls, value: "MemoryPolicy | dict[str, Any] | None", **overrides: Any) -> "MemoryPolicy":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        return base.model_copy(update=overrides) if overrides else base

    @classmethod
    def long_horizon(cls, **overrides: Any) -> "MemoryPolicy":
        payload = {
            "recall_mode": "hybrid",
            "promotion_mode": "hybrid",
            "validation_mode": "threshold",
            "thresholds_and_weights": {
                **_deepcopy_dict(_DEFAULT_MEMORY_THRESHOLDS),
                "allow_cross_thread_recall": True,
                "recall_top_k": 6,
            },
        }
        payload.update(overrides)
        return cls(**payload)

    @property
    def promotion_policy(self) -> str | None:
        if self.promotion_mode in {"episodic", "hybrid", "validated"}:
            return "episodic_salience"
        return None

    @property
    def index_policy(self) -> str | None:
        return str(self.thresholds_and_weights.get("index_policy", "scene_hash"))

    @property
    def recall_policy(self) -> str | None:
        if self.recall_mode in {"scene", "hybrid"}:
            return "scene_first"
        return None

    @property
    def decay_policy(self) -> str | None:
        if self.recall_mode in {"scene", "hybrid"}:
            return str(self.thresholds_and_weights.get("decay_policy", "relevance_only"))
        return None

    @property
    def validation_threshold(self) -> float:
        return float(self.thresholds_and_weights.get("validation_threshold", 0.7))

    @property
    def trail_knowledge_enabled(self) -> bool:
        return bool(self.thresholds_and_weights.get("trail_knowledge_enabled", True))

    @property
    def collective_promotion_policy(self) -> str:
        if self.validation_mode == "manual":
            return "manual"
        if self.promotion_mode == "validated":
            return "validated_only"
        return "evidence_weighted"

    @property
    def episodic_memory_enabled(self) -> bool:
        return bool(self.thresholds_and_weights.get("episodic_memory_enabled", True))

    @property
    def kind(self) -> str:
        return "memory_policy"


class ContextSelector(ABC):
    @abstractmethod
    async def select(
        self,
        prompt_context: Any,
        *,
        context_policy: ContextPolicy,
        state_policy: StatePolicy,
        stage: str,
        selected_skill_routes: list[dict[str, Any]],
        rerank_callback: Any,
    ) -> tuple[Any, dict[str, Any]]:
        raise NotImplementedError


class DefaultContextSelector(ContextSelector):
    async def select(
        self,
        prompt_context: Any,
        *,
        context_policy: ContextPolicy,
        state_policy: StatePolicy,
        stage: str,
        selected_skill_routes: list[dict[str, Any]],
        rerank_callback: Any,
    ) -> tuple[Any, dict[str, Any]]:
        from agentorch.runtime.context_compaction import (
            apply_budget_aware_compaction,
            apply_static_context_filters,
            estimate_prompt_context_budget,
        )

        updated, truncated_sections = apply_static_context_filters(
            prompt_context,
            context_policy=context_policy,
            state_policy=state_policy,
        )
        before_budget = estimate_prompt_context_budget(updated, truncated_sections=truncated_sections)
        if before_budget["estimated_total_chars"] <= context_policy.char_budget:
            before_budget.update(
                {
                    "estimated_total_chars_before": before_budget["estimated_total_chars"],
                    "estimated_total_chars_after": before_budget["estimated_total_chars"],
                    "selected_segment_count": 0,
                    "dropped_segment_count": 0,
                    "segment_scores": [],
                    "inhibition_events": [],
                    "compression_reason": "within_budget",
                    "compaction_applied": False,
                    "overflow_action": context_policy.overflow_action,
                }
            )
            return updated, before_budget

        if context_policy.overflow_action == "fail_closed":
            raise RuntimeError(
                f"Context budget exceeded for thread {prompt_context.prompt_variables.get('thread_id', '<unknown>')} "
                f"with overflow_action='fail_closed'."
            )

        if context_policy.overflow_action == "disable_heavy_blocks":
            stripped = updated.model_copy(
                update={
                    "retrieval_report": None,
                    "retrieval_plan": None,
                    "tool_descriptions": [],
                    "skill_instructions": [],
                }
            )
            stripped_budget = estimate_prompt_context_budget(stripped, truncated_sections=truncated_sections + ["heavy_blocks"])
            if stripped_budget["estimated_total_chars"] <= context_policy.char_budget:
                stripped_budget.update(
                    {
                        "estimated_total_chars_before": before_budget["estimated_total_chars"],
                        "estimated_total_chars_after": stripped_budget["estimated_total_chars"],
                        "selected_segment_count": 0,
                        "dropped_segment_count": 0,
                        "segment_scores": [],
                        "inhibition_events": [],
                        "compression_reason": "heavy_blocks_disabled",
                        "compaction_applied": True,
                        "overflow_action": context_policy.overflow_action,
                    }
                )
                return stripped, stripped_budget
            updated = stripped

        compacted, budget = await apply_budget_aware_compaction(
            updated,
            context_policy=context_policy,
            stage=stage,
            selected_skill_routes=selected_skill_routes,
            rerank_callback=rerank_callback,
        )
        budget["overflow_action"] = context_policy.overflow_action
        return compacted, budget


class RoutePlanner(ABC):
    @abstractmethod
    async def plan(
        self,
        *,
        supervisor: Any,
        task: Any,
        registry: Any,
        coordination_policy: CoordinationPolicy,
    ) -> Any:
        raise NotImplementedError

    def build_supervisor_context(
        self,
        *,
        task_context: dict[str, Any],
        coordination_policy: CoordinationPolicy,
    ) -> dict[str, Any]:
        return {
            "route_mode": coordination_policy.route_mode,
            "workspace_mode": coordination_policy.workspace_mode,
            "alert_mode": coordination_policy.alert_mode,
            "task_context": task_context,
        }

    def build_shared_workspace_view(
        self,
        *,
        notes: list[dict[str, Any]] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        coordination_policy: CoordinationPolicy,
    ) -> dict[str, Any]:
        return {
            "workspace_mode": coordination_policy.workspace_mode,
            "notes": notes or [],
            "artifacts": artifacts or [],
        }

    def should_share_raw_history(self, coordination_policy: CoordinationPolicy) -> bool:
        return coordination_policy.handoff_mode == "raw_allowed"


class DefaultRoutePlanner(RoutePlanner):
    async def plan(
        self,
        *,
        supervisor: Any,
        task: Any,
        registry: Any,
        coordination_policy: CoordinationPolicy,
    ) -> Any:
        return await supervisor.create_plan(task)


class MemoryEvaluator(ABC):
    @abstractmethod
    def policy_bundle(self, policy: MemoryPolicy) -> dict[str, str | None]:
        raise NotImplementedError

    @abstractmethod
    def resolved_runtime_config(self, policy: MemoryPolicy) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def promote_episode(self, manager: Any, *, policy: MemoryPolicy, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def search_long_term_memory(self, manager: Any, *, policy: MemoryPolicy, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def build_memory_evidence(
        self,
        *,
        policy: MemoryPolicy,
        runtime: Any,
        candidates: list[dict[str, Any]],
        thread_id: str,
        knowledge_scope: list[str],
    ) -> tuple[list[Any], list[Any], dict[str, Any]]:
        raise NotImplementedError

    async def validate_memory(self, manager: Any, *, policy: MemoryPolicy, record_id: int) -> dict[str, Any] | None:
        if policy.validation_mode == "off":
            return None
        return await manager.validate_collective_memory(record_id)


class DefaultMemoryEvaluator(MemoryEvaluator):
    def policy_bundle(self, policy: MemoryPolicy) -> dict[str, str | None]:
        return {
            "promotion_mode": policy.promotion_mode,
            "recall_mode": policy.recall_mode,
            "validation_mode": policy.validation_mode,
            "promotion_policy": policy.promotion_policy,
            "index_policy": policy.index_policy,
            "recall_policy": policy.recall_policy,
            "decay_policy": policy.decay_policy,
        }

    def resolved_runtime_config(self, policy: MemoryPolicy) -> dict[str, Any]:
        resolved = _deepcopy_dict(_DEFAULT_MEMORY_THRESHOLDS)
        resolved.update(policy.thresholds_and_weights)
        return resolved

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

    async def promote_episode(self, manager: Any, *, policy: MemoryPolicy, **kwargs: Any) -> list[dict[str, Any]]:
        if policy.promotion_mode == "off":
            return []
        promotion_policy = self._policy_instance(policy.promotion_policy, "promotion")
        index_policy = self._policy_instance(policy.index_policy, "index")
        if promotion_policy is None or index_policy is None:
            return []
        return await promotion_policy.promote(
            manager,
            config=self.resolved_runtime_config(policy),
            strategy_kind=policy.kind,
            index_policy=index_policy,
            **kwargs,
        )

    async def search_long_term_memory(self, manager: Any, *, policy: MemoryPolicy, **kwargs: Any) -> list[dict[str, Any]]:
        if policy.recall_mode in {"off", "thread"}:
            return []
        recall_policy = self._policy_instance(policy.recall_policy, "recall")
        index_policy = self._policy_instance(policy.index_policy, "index")
        decay_policy = self._policy_instance(policy.decay_policy, "decay")
        if recall_policy is None or index_policy is None or decay_policy is None:
            return []
        return await recall_policy.recall(
            manager,
            config=self.resolved_runtime_config(policy),
            strategy_kind=policy.kind,
            index_policy=index_policy,
            decay_policy=decay_policy,
            **kwargs,
        )

    def build_memory_evidence(
        self,
        *,
        policy: MemoryPolicy,
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
            "mechanism": policy.kind,
            "policy_bundle": self.policy_bundle(policy),
            "config": self.resolved_runtime_config(policy),
            "selected_count": len(selected),
            "selected": selected,
        }
        return evidence, citations, report


__all__ = [
    "ContextPolicy",
    "StatePolicy",
    "CoordinationPolicy",
    "MemoryPolicy",
    "ContextSelector",
    "RoutePlanner",
    "MemoryEvaluator",
    "DefaultContextSelector",
    "DefaultRoutePlanner",
    "DefaultMemoryEvaluator",
]
