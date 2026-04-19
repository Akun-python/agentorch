from __future__ import annotations

from typing import Any

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

    def resolved_runtime_config(self, policy: MemoryPolicy) -> dict[str, Any]:
        resolved = super().resolved_runtime_config(policy)
        if policy.validation_mode == "threshold":
            resolved["validation_threshold"] = min(float(resolved.get("validation_threshold", 0.7)), 0.65)
        if policy.promotion_mode in {"hybrid", "validated"}:
            resolved["collective_promotion_threshold"] = min(float(resolved.get("collective_promotion_threshold", 2.8)), 2.4)
        return resolved


def elephant_context_policy(*, hybrid_selection: bool = False, char_budget: int = 18000) -> ContextPolicy:
    return ContextPolicy(
        sources={
            "memory_summary": True,
            "retrieval_summary": True,
            "retrieval_evidence": {"enabled": True, "max_items": 5},
            "retrieval_citations": {"enabled": True, "max_items": 6},
            "retrieval_report": True,
            "retrieval_plan": False,
            "tool_descriptions": False,
            "skill_instructions": True,
            "task_packet": {"enabled": True, "representation": "capsule"},
            "delegation_context": {"enabled": True, "representation": "capsule"},
            "shared_memory": {"enabled": True, "max_items": 6},
        },
        conversation_window=6,
        char_budget=char_budget,
        tool_observation_mode="summary",
        selection_mode="hybrid" if hybrid_selection else "rule",
        overflow_action="compress",
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


def matriarch_memory_policy() -> MemoryPolicy:
    return MemoryPolicy.long_horizon(
        promotion_mode="validated",
        validation_mode="threshold",
        thresholds_and_weights={
            "validation_threshold": 0.65,
            "allow_cross_thread_recall": True,
            "recall_top_k": 6,
            "collective_promotion_threshold": 2.4,
            "trail_knowledge_enabled": True,
        },
    )


def build_elephant_runtime_config(
    *,
    hybrid_selection: bool = False,
    distributed: bool = False,
    char_budget: int = 18000,
    **kwargs: Any,
) -> RuntimeConfig:
    return RuntimeConfig.agent(
        context_policy=elephant_context_policy(hybrid_selection=hybrid_selection, char_budget=char_budget),
        state_policy=collective_state_policy(),
        coordination_policy=distributed_coordination_policy() if distributed else matriarch_coordination_policy(),
        memory_policy=matriarch_memory_policy(),
        context_selector=ElephantContextSelector(),
        route_planner=MatriarchRoutePlanner(),
        memory_evaluator=ElephantMemoryEvaluator(),
        **kwargs,
    )
