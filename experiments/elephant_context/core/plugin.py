from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import Field

from agentorch.agents import AgentCapability
from agentorch.config import RuntimeConfig
from agentorch.strategies import (
    ContextPolicy,
    CoordinationPolicy,
    DefaultContextSelector,
    DefaultMemoryEvaluator,
    DefaultRoutePlanner,
    MemoryPolicy,
    StatePolicy,
)

from .models import ElephantChapterConfig
from .variants import get_elephant_variant


class ElephantContextPolicy(ContextPolicy):
    elephant_stage_attention_profiles: dict[str, dict[str, float]] = Field(default_factory=dict)
    elephant_use_builtin_stage_profiles: bool = False
    elephant_redundancy_inhibition_enabled: bool = True
    elephant_salience_rerank_top_k: int = 8
    elephant_segment_min_keep: int = 6

    @property
    def stage_attention_profiles(self) -> dict[str, dict[str, float]]:
        return deepcopy(self.elephant_stage_attention_profiles)

    @property
    def use_builtin_stage_profiles(self) -> bool:
        return self.elephant_use_builtin_stage_profiles

    @property
    def redundancy_inhibition_enabled(self) -> bool:
        return self.elephant_redundancy_inhibition_enabled

    @property
    def salience_rerank_top_k(self) -> int:
        return self.elephant_salience_rerank_top_k

    @property
    def segment_min_keep(self) -> int:
        return self.elephant_segment_min_keep


class ElephantContextSelector(DefaultContextSelector):
    """Research selector that keeps herd-memory blocks compact and foregrounded."""

    async def select(self, prompt_context, **kwargs):
        if prompt_context.collective_memory_evidence and prompt_context.collective_memory_citations:
            prompt_context = prompt_context.model_copy(update={"collective_memory_citations": []})
        return await super().select(prompt_context, **kwargs)


class MatriarchRoutePlanner(DefaultRoutePlanner):
    """Guided planner that routes stabilizing roles first when shared memory exists."""

    async def plan(self, *, supervisor, task, registry, coordination_policy):
        plan = await super().plan(
            supervisor=supervisor,
            task=task,
            registry=registry,
            coordination_policy=coordination_policy,
        )
        if coordination_policy.route_mode == "distributed":
            return plan
        if not (task.context or {}).get("collective_memory_evidence"):
            return plan

        def _priority(invocation):
            registered = registry.get(invocation.agent_name)
            capabilities = set(registered.spec.capabilities)
            if AgentCapability.PLAN in capabilities:
                return 0
            if AgentCapability.RETRIEVE in capabilities:
                return 1
            if AgentCapability.AGGREGATE in capabilities:
                return 2
            return 3

        ordered = sorted(plan.invocations, key=_priority)
        return plan.model_copy(update={"invocations": ordered, "reason": (plan.reason or "keyword_match") + ":matriarch_reordered"})

    def build_supervisor_context(self, *, task_context: dict[str, Any], coordination_policy: CoordinationPolicy) -> dict[str, Any]:
        context = super().build_supervisor_context(task_context=task_context, coordination_policy=coordination_policy)
        context["matriarch_guidance"] = {
            "route_mode": coordination_policy.route_mode,
            "alert_mode": coordination_policy.alert_mode,
            "workspace_mode": coordination_policy.workspace_mode,
        }
        return context


class ElephantMemoryEvaluator(DefaultMemoryEvaluator):
    """Evaluator tuned for validated collective promotion in elephant-context studies."""

    def __init__(self, *, validation_threshold: float = 0.65, collective_promotion_threshold: float = 2.4) -> None:
        self.validation_threshold = validation_threshold
        self.collective_promotion_threshold = collective_promotion_threshold

    def resolved_runtime_config(self, policy: MemoryPolicy) -> dict[str, Any]:
        resolved = super().resolved_runtime_config(policy)
        if policy.validation_mode == "threshold":
            resolved["validation_threshold"] = min(float(resolved.get("validation_threshold", 0.7)), self.validation_threshold)
        if policy.promotion_mode in {"hybrid", "validated"}:
            resolved["collective_promotion_threshold"] = min(
                float(resolved.get("collective_promotion_threshold", 2.8)),
                self.collective_promotion_threshold,
            )
        return resolved


def _elephant_sources(chapter_config: ElephantChapterConfig) -> dict[str, Any]:
    return {
        "memory_summary": True,
        "retrieval_summary": True,
        "retrieval_evidence": {"enabled": True, "max_items": chapter_config.retrieval_evidence_max_items},
        "retrieval_citations": {"enabled": True, "max_items": chapter_config.retrieval_citation_max_items},
        "retrieval_report": True,
        "retrieval_plan": False,
        "tool_descriptions": False,
        "skill_catalog": True,
        "skill_instructions": True,
        "skill_resources": {"enabled": True, "max_items": 4},
        "task_packet": {"enabled": True, "representation": "capsule"},
        "delegation_context": {"enabled": True, "representation": "capsule"},
        "shared_memory": {"enabled": True, "max_items": chapter_config.shared_memory_max_items},
    }


def _baseline_sources(chapter_config: ElephantChapterConfig, *, multi_agent: bool) -> dict[str, Any]:
    return {
        "memory_summary": True,
        "retrieval_summary": True,
        "retrieval_evidence": {"enabled": True, "max_items": chapter_config.retrieval_evidence_max_items},
        "retrieval_citations": {"enabled": True, "max_items": chapter_config.retrieval_citation_max_items},
        "retrieval_report": True,
        "retrieval_plan": False,
        "tool_descriptions": False,
        "skill_catalog": True,
        "skill_instructions": True,
        "skill_resources": {"enabled": True, "max_items": 4},
        "task_packet": {"enabled": True, "representation": "capsule"},
        "delegation_context": {"enabled": multi_agent, "representation": "capsule"},
        # Strict baselines must not receive elephant collective-memory injection.
        "shared_memory": {"enabled": False, "max_items": 0},
    }


def elephant_context_policy(
    *,
    chapter_config: ElephantChapterConfig | None = None,
    hybrid_selection: bool = False,
    char_budget: int | None = None,
) -> ElephantContextPolicy:
    resolved = (chapter_config or ElephantChapterConfig()).model_copy(deep=True)
    if hybrid_selection:
        resolved = resolved.merged(selection_mode="hybrid")
    if char_budget is not None and char_budget != resolved.char_budget:
        resolved = resolved.merged(char_budget=char_budget)
    return ElephantContextPolicy(
        sources=_elephant_sources(resolved),
        conversation_window=resolved.conversation_window,
        char_budget=resolved.char_budget,
        tool_observation_mode=resolved.tool_observation_mode,
        selection_mode=resolved.selection_mode,
        overflow_action=resolved.overflow_action,
        elephant_stage_attention_profiles=resolved.stage_attention_profiles,
        elephant_use_builtin_stage_profiles=resolved.use_builtin_stage_profiles,
        elephant_redundancy_inhibition_enabled=resolved.redundancy_inhibition_enabled,
        elephant_salience_rerank_top_k=resolved.salience_rerank_top_k,
        elephant_segment_min_keep=resolved.segment_min_keep,
    )


def baseline_context_policy(*, chapter_config: ElephantChapterConfig, multi_agent: bool = True) -> ContextPolicy:
    return ContextPolicy(
        sources=_baseline_sources(chapter_config, multi_agent=multi_agent),
        conversation_window=chapter_config.conversation_window,
        char_budget=chapter_config.char_budget,
        tool_observation_mode=chapter_config.tool_observation_mode,
        selection_mode="rule",
        overflow_action=chapter_config.overflow_action,
    )


def collective_state_policy() -> StatePolicy:
    return StatePolicy(
        retention_mode="state_plus_memory",
        summary_refresh_every=12,
        snapshot_every=24,
        rollup_every=12,
    )


def matriarch_coordination_policy() -> CoordinationPolicy:
    return CoordinationPolicy(
        handoff_mode="summary_plus_artifacts",
        workspace_mode="artifacts_first",
        route_mode="guided",
        alert_mode="direct",
    )


def distributed_coordination_policy() -> CoordinationPolicy:
    return CoordinationPolicy.distributed(workspace_mode="balanced")


def matriarch_memory_policy(*, chapter_config: ElephantChapterConfig | None = None) -> MemoryPolicy:
    resolved = chapter_config or ElephantChapterConfig()
    return MemoryPolicy.long_horizon(
        promotion_mode="validated",
        validation_mode="threshold",
        thresholds_and_weights={
            "validation_threshold": resolved.validation_threshold,
            "allow_cross_thread_recall": True,
            "recall_top_k": 6,
            "collective_promotion_threshold": resolved.collective_promotion_threshold,
            "trail_knowledge_enabled": True,
        },
    )


def baseline_memory_policy() -> MemoryPolicy:
    default_thresholds = MemoryPolicy().thresholds_and_weights
    return MemoryPolicy(
        recall_mode="off",
        promotion_mode="off",
        validation_mode="off",
        thresholds_and_weights={
            **default_thresholds,
            "allow_cross_thread_recall": False,
            "trail_knowledge_enabled": False,
            "recency_weight": 0.0,
        },
    )


def build_elephant_runtime_config(
    *,
    variant: str = "elephant_full",
    chapter_config: ElephantChapterConfig | None = None,
    hybrid_selection: bool = False,
    distributed: bool = False,
    char_budget: int | None = None,
    **kwargs: Any,
) -> RuntimeConfig:
    spec = get_elephant_variant(variant)
    resolved_chapter = spec.chapter_config.model_copy(deep=True)
    if chapter_config is not None:
        resolved_chapter = resolved_chapter.model_copy(update=chapter_config.model_dump(exclude_unset=True), deep=True)
    if variant == "elephant_full":
        if hybrid_selection:
            resolved_chapter = resolved_chapter.merged(selection_mode="hybrid")
        if distributed:
            resolved_chapter = resolved_chapter.merged(route_mode="distributed")
    if char_budget is not None and char_budget != spec.chapter_config.char_budget:
        resolved_chapter = resolved_chapter.merged(char_budget=char_budget)

    context_policy: ContextPolicy
    if spec.use_elephant_selector:
        context_policy = elephant_context_policy(chapter_config=resolved_chapter)
    else:
        context_policy = baseline_context_policy(
            chapter_config=resolved_chapter,
            multi_agent=spec.multi_agent,
        )
    coordination_policy = distributed_coordination_policy() if resolved_chapter.route_mode == "distributed" else matriarch_coordination_policy()
    memory_policy = (
        matriarch_memory_policy(chapter_config=resolved_chapter)
        if spec.use_mgcm_memory_policy
        else baseline_memory_policy()
    )

    default_scope = kwargs.pop("default_knowledge_scope", spec.default_knowledge_scope or resolved_chapter.default_knowledge_scope)
    enable_parallel_tasks = kwargs.pop("enable_parallel_tasks", resolved_chapter.route_mode == "distributed")
    return RuntimeConfig.agent(
        context_policy=context_policy,
        state_policy=collective_state_policy(),
        coordination_policy=coordination_policy,
        memory_policy=memory_policy,
        context_selector=ElephantContextSelector() if spec.use_elephant_selector else None,
        route_planner=MatriarchRoutePlanner() if spec.use_elephant_route_planner else None,
        memory_evaluator=(
            ElephantMemoryEvaluator(
                validation_threshold=resolved_chapter.validation_threshold,
                collective_promotion_threshold=resolved_chapter.collective_promotion_threshold,
            )
            if spec.use_elephant_memory_evaluator
            else None
        ),
        default_knowledge_scope=list(default_scope),
        enable_parallel_tasks=enable_parallel_tasks,
        **kwargs,
    )
