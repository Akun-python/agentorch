from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Iterable

from pydantic import BaseModel, Field

from .registry import AgentRegistry
from .types import AgentInvocation, AgentResult, Handoff, TaskPacket, TaskPlan, TaskStatus


class AgentRouteDecision(BaseModel):
    selected_agents: list[str] = Field(default_factory=list)
    reason: str | None = None


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
        matched = []
        for spec in registry.list_specs():
            capabilities = [cap.value for cap in spec.capabilities]
            haystack = " ".join([spec.name, spec.description, *spec.tags, *capabilities]).lower()
            if any(token in haystack for token in goal.split()):
                matched.append(spec.name)
        if not matched and registry.list_specs():
            matched.append(registry.list_specs()[0].name)
        return AgentRouteDecision(selected_agents=matched, reason="keyword_match")


class SequentialTaskPlanner:
    def build_plan(self, task: TaskPacket, selected_agents: Iterable[str], *, reason: str | None = None) -> TaskPlan:
        steps = []
        previous_step_id = None
        for index, agent_name in enumerate(selected_agents, start=1):
            step_id = f"{task.task_id}:step-{index}"
            steps.append(
                {
                    "step_id": step_id,
                    "description": f"Delegate task '{task.goal}' to {agent_name}",
                    "assigned_agent": agent_name,
                    "depends_on": [previous_step_id] if previous_step_id else [],
                    "metadata": {"selection_reason": reason or "unspecified"},
                }
            )
            previous_step_id = step_id
        return TaskPlan(task_id=task.task_id, summary=reason, steps=steps)


class Supervisor:
    def __init__(
        self,
        registry: AgentRegistry,
        policy: SupervisorPolicy | None = None,
        planner: SequentialTaskPlanner | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or KeywordSupervisorPolicy()
        self.planner = planner or SequentialTaskPlanner()

    async def create_plan(self, task: TaskPacket) -> DelegationPlan:
        decision = await self.policy.select_agents(task, self.registry)
        task_plan = self.planner.build_plan(task, decision.selected_agents, reason=decision.reason)
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
                metadata={"selection_reason": decision.reason or "", "step_id": step.step_id},
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
