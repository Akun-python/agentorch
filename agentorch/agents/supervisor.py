from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, Iterable

from pydantic import BaseModel, Field

from .registry import AgentRegistry
from .types import AgentInvocation, AgentResult, Handoff, TaskPacket, TaskPlan, TaskStatus


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if token}


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    return [str(value).strip().lower()] if str(value).strip() else []


class AgentRouteDecision(BaseModel):
    selected_agents: list[str] = Field(default_factory=list)
    reason: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)


class DelegationPlan(BaseModel):
    invocations: list[AgentInvocation] = Field(default_factory=list)
    reason: str | None = None
    task_plan: TaskPlan | None = None


class SupervisorPolicy(ABC):
    @abstractmethod
    async def select_agents(self, task: TaskPacket, registry: AgentRegistry) -> AgentRouteDecision:
        raise NotImplementedError


class KeywordSupervisorPolicy(SupervisorPolicy):
    async def select_agents(self, task: TaskPacket, registry: AgentRegistry) -> AgentRouteDecision:
        goal = task.goal.lower()
        matched: list[str] = []
        scores: dict[str, float] = {}
        for spec in registry.list_specs():
            capabilities = [cap.value for cap in spec.capabilities]
            haystack = " ".join([spec.name, spec.description, *spec.tags, *capabilities]).lower()
            overlap = sum(1 for token in goal.split() if token in haystack)
            if overlap > 0:
                matched.append(spec.name)
                scores[spec.name] = float(overlap)
        if not matched and registry.list_specs():
            fallback = registry.list_specs()[0].name
            matched.append(fallback)
            scores[fallback] = 0.0
        return AgentRouteDecision(selected_agents=matched, reason="keyword_match", scores=scores)


class CapabilitySupervisorPolicy(SupervisorPolicy):
    """Score agents using explicit routing hints before falling back to lexical cues."""

    def __init__(
        self,
        *,
        guided_limit: int = 2,
        distributed_limit: int = 3,
        capability_weight: float = 4.0,
        tag_weight: float = 2.0,
        scope_weight: float = 2.5,
        tool_weight: float = 1.5,
        lexical_weight: float = 0.35,
        explicit_target_bonus: float = 1000.0,
    ) -> None:
        self.guided_limit = guided_limit
        self.distributed_limit = distributed_limit
        self.capability_weight = capability_weight
        self.tag_weight = tag_weight
        self.scope_weight = scope_weight
        self.tool_weight = tool_weight
        self.lexical_weight = lexical_weight
        self.explicit_target_bonus = explicit_target_bonus

    async def select_agents(self, task: TaskPacket, registry: AgentRegistry) -> AgentRouteDecision:
        task_context = dict(task.context or {})
        metadata = dict(task.metadata or {})
        route_mode = str((metadata.get("coordination_policy") or {}).get("route_mode", "guided")).lower()
        explicit_targets = set(_string_list(metadata.get("target_agents") or task_context.get("target_agents")))
        excluded_agents = set(_string_list(metadata.get("excluded_agents") or task_context.get("excluded_agents")))
        required_capabilities = set(_string_list(task_context.get("required_capabilities") or metadata.get("required_capabilities")))
        preferred_capabilities = set(_string_list(task_context.get("preferred_capabilities") or metadata.get("preferred_capabilities")))
        required_tags = set(_string_list(task_context.get("required_tags") or metadata.get("required_tags")))
        preferred_tags = set(_string_list(task_context.get("preferred_tags") or metadata.get("preferred_tags")))
        required_tools = set(_string_list(task_context.get("required_tools") or metadata.get("required_tools")))
        goal_tokens = _tokenize(task.goal)
        ranked: list[tuple[float, str, list[str]]] = []
        hard_constraints_applied = bool(explicit_targets or excluded_agents or required_capabilities or required_tags or required_tools)

        for spec in registry.list_specs():
            spec_name = spec.name.lower()
            if spec_name in excluded_agents:
                continue
            if explicit_targets and spec_name not in explicit_targets:
                continue

            capability_values = {cap.value.lower() for cap in spec.capabilities}
            tag_values = {tag.lower() for tag in spec.tags}
            tool_values = {tool.lower() for tool in spec.allowed_tools}
            scope_values = {scope.lower() for scope in spec.allowed_knowledge_scopes}
            requested_scope = {scope.lower() for scope in task.knowledge_scope}

            if required_capabilities and not required_capabilities.issubset(capability_values):
                continue
            if required_tags and not required_tags.issubset(tag_values):
                continue
            if required_tools and not required_tools.issubset(tool_values):
                continue

            score = 0.0
            reasons: list[str] = []
            if explicit_targets and spec_name in explicit_targets:
                score += self.explicit_target_bonus
                reasons.append("explicit_target")

            capability_overlap = len(required_capabilities & capability_values) + 0.5 * len(preferred_capabilities & capability_values)
            if capability_overlap:
                score += capability_overlap * self.capability_weight
                reasons.append("capability_match")

            tag_overlap = len(required_tags & tag_values) + 0.5 * len(preferred_tags & tag_values)
            if tag_overlap:
                score += tag_overlap * self.tag_weight
                reasons.append("tag_match")

            if requested_scope:
                if scope_values:
                    scope_overlap = len(requested_scope & scope_values)
                    if scope_overlap:
                        score += scope_overlap * self.scope_weight
                        reasons.append("knowledge_scope")
                        if requested_scope.issubset(scope_values):
                            score += 0.5
                    else:
                        score -= 1.0
                else:
                    score += 0.25

            tool_overlap = len(required_tools & tool_values)
            if tool_overlap:
                score += tool_overlap * self.tool_weight
                reasons.append("tool_match")

            lexical_haystack = _tokenize(" ".join([spec.name, spec.description, *spec.tags, *capability_values, *tool_values, *scope_values]))
            lexical_overlap = len(goal_tokens & lexical_haystack)
            if lexical_overlap:
                score += min(lexical_overlap, 4) * self.lexical_weight
                reasons.append("lexical_match")

            if spec.supports_parallel_tasks and route_mode in {"distributed", "hybrid"}:
                score += 0.1

            ranked.append((score, spec.name, reasons))

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        if not ranked and hard_constraints_applied:
            constraint_bits = []
            if explicit_targets:
                constraint_bits.append(f"target_agents={sorted(explicit_targets)}")
            if excluded_agents:
                constraint_bits.append(f"excluded_agents={sorted(excluded_agents)}")
            if required_capabilities:
                constraint_bits.append(f"required_capabilities={sorted(required_capabilities)}")
            if required_tags:
                constraint_bits.append(f"required_tags={sorted(required_tags)}")
            if required_tools:
                constraint_bits.append(f"required_tools={sorted(required_tools)}")
            raise ValueError(
                "No agents satisfy the routing constraints: " + ", ".join(constraint_bits)
            )
        if not ranked and registry.list_specs():
            fallback = registry.list_specs()[0].name
            return AgentRouteDecision(selected_agents=[fallback], reason="fallback_first_registered", scores={fallback: 0.0})

        max_agents = int(metadata.get("max_agents") or 0)
        if max_agents <= 0:
            max_agents = self.guided_limit if route_mode == "guided" else self.distributed_limit

        positive = [item for item in ranked if item[0] > 0]
        if route_mode == "guided":
            selected = positive[:max_agents] if positive else ranked[:1]
        else:
            selected = positive[:max_agents] if positive else ranked[:1]

        selected_names = [name for _, name, _ in selected]
        selected_scores = {name: round(score, 3) for score, name, _ in selected}
        reason_bits = []
        if route_mode:
            reason_bits.append(f"route_mode={route_mode}")
        if explicit_targets:
            reason_bits.append("explicit_targets")
        if required_capabilities or preferred_capabilities:
            reason_bits.append("capability_scored")
        if required_tags or preferred_tags:
            reason_bits.append("tag_scored")
        if task.knowledge_scope:
            reason_bits.append("scope_scored")
        reason = ",".join(reason_bits) if reason_bits else "scored_routing"
        return AgentRouteDecision(selected_agents=selected_names, reason=reason, scores=selected_scores)


class AdaptiveTaskPlanner:
    def build_plan(
        self,
        task: TaskPacket,
        selected_agents: Iterable[str],
        *,
        registry: AgentRegistry,
        reason: str | None = None,
        scores: dict[str, float] | None = None,
    ) -> TaskPlan:
        selected = list(selected_agents)
        coordination = dict(task.metadata.get("coordination_policy") or {})
        route_mode = str(coordination.get("route_mode", "guided")).lower()
        requested_parallel = bool(task.metadata.get("allow_parallel", route_mode in {"distributed", "hybrid"}))
        parallel_ready = requested_parallel and len(selected) > 1 and all(
            registry.get(agent_name).spec.supports_parallel_tasks for agent_name in selected
        )
        max_parallel_tasks = int(task.metadata.get("max_parallel_tasks") or max(len(selected), 1))
        steps = []
        previous_step_id = None
        for index, agent_name in enumerate(selected, start=1):
            step_id = f"{task.task_id}:step-{index}"
            depends_on = [] if parallel_ready else ([previous_step_id] if previous_step_id else [])
            steps.append(
                {
                    "step_id": step_id,
                    "description": f"Delegate task '{task.goal}' to {agent_name}",
                    "assigned_agent": agent_name,
                    "depends_on": depends_on,
                    "metadata": {
                        "selection_reason": reason or "unspecified",
                        "routing_score": float((scores or {}).get(agent_name, 0.0)),
                    },
                }
            )
            previous_step_id = step_id
        return TaskPlan(
            task_id=task.task_id,
            summary=reason,
            steps=steps,
            metadata={
                "execution_mode": "parallel" if parallel_ready else "sequential",
                "route_mode": route_mode,
                "selected_agents": selected,
                "scores": dict(scores or {}),
                "max_parallel_tasks": max_parallel_tasks if parallel_ready else 1,
            },
        )


class SequentialTaskPlanner(AdaptiveTaskPlanner):
    """Backward-compatible alias kept for older imports."""


class Supervisor:
    def __init__(
        self,
        registry: AgentRegistry,
        policy: SupervisorPolicy | None = None,
        planner: AdaptiveTaskPlanner | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or CapabilitySupervisorPolicy()
        self.planner = planner or AdaptiveTaskPlanner()

    async def create_plan(self, task: TaskPacket) -> DelegationPlan:
        decision = await self.policy.select_agents(task, self.registry)
        task_plan = self.planner.build_plan(
            task,
            decision.selected_agents,
            registry=self.registry,
            reason=decision.reason,
            scores=decision.scores,
        )
        invocations = [
            AgentInvocation(
                agent_name=step.assigned_agent or "",
                task=task.model_copy(
                    update={
                        "task_id": f"{task.task_id}:{step.assigned_agent}",
                        "parent_task_id": task.task_id,
                        "origin_agent": task.origin_agent or "supervisor",
                        "status": TaskStatus.PENDING,
                    }
                ),
                delegation_depth=int(task.metadata.get("delegation_depth", 0)) + 1,
                metadata={
                    "selection_reason": decision.reason or "",
                    "step_id": step.step_id,
                    "routing_score": float(decision.scores.get(step.assigned_agent or "", 0.0)),
                },
            )
            for step in task_plan.steps
        ]
        return DelegationPlan(invocations=invocations, reason=decision.reason, task_plan=task_plan)

    async def run(self, task: TaskPacket, *, parent_run_id: str | None = None) -> list[AgentResult]:
        plan = await self.create_plan(task)
        results: list[AgentResult] = []
        for invocation in plan.invocations:
            registered = self.registry.get(invocation.agent_name)
            handoff = Handoff(
                from_agent="supervisor",
                to_agent=registered.spec.name,
                task=invocation.task,
                reason=plan.reason,
                metadata={"parent_run_id": parent_run_id or str(uuid.uuid4())},
            )
            agent = registered.agent
            run_result = await agent.run(
                invocation.task.goal,
                thread_id=invocation.task.task_id,
                metadata={"task_packet": invocation.task.model_dump(), "handoff": handoff.model_dump(), "_delegated": True},
            )
            results.append(
                AgentResult(
                    agent_name=registered.spec.name,
                    output_text=run_result.output_text,
                    status=TaskStatus.COMPLETED if run_result.status == "completed" else TaskStatus.FAILED,
                    summary=run_result.output_text,
                    structured_output={"tool_results": [item.model_dump() for item in run_result.tool_results]},
                    metadata={"handoff": handoff.model_dump()},
                )
            )
        return results
