from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from .registry import AgentRegistry, RegisteredAgent
from .types import AgentInvocation, AgentResult, Handoff, TaskPacket


class AgentRouteDecision(BaseModel):
    selected_agents: list[str] = Field(default_factory=list)
    reason: str | None = None


class DelegationPlan(BaseModel):
    invocations: list[AgentInvocation] = Field(default_factory=list)
    reason: str | None = None


class SupervisorPolicy(ABC):
    @abstractmethod
    async def select_agents(self, task: TaskPacket, registry: AgentRegistry) -> AgentRouteDecision:
        raise NotImplementedError


class KeywordSupervisorPolicy(SupervisorPolicy):
    async def select_agents(self, task: TaskPacket, registry: AgentRegistry) -> AgentRouteDecision:
        goal = task.goal.lower()
        matched = []
        for spec in registry.list_specs():
            haystack = " ".join([spec.name, spec.description, *spec.tags]).lower()
            if any(token in haystack for token in goal.split()):
                matched.append(spec.name)
        if not matched and registry.list_specs():
            matched.append(registry.list_specs()[0].name)
        return AgentRouteDecision(selected_agents=matched[:1], reason="keyword_match")


class Supervisor:
    def __init__(self, registry: AgentRegistry, policy: SupervisorPolicy | None = None) -> None:
        self.registry = registry
        self.policy = policy or KeywordSupervisorPolicy()

    async def create_plan(self, task: TaskPacket) -> DelegationPlan:
        decision = await self.policy.select_agents(task, self.registry)
        invocations = [
            AgentInvocation(
                agent_name=name,
                task=task.model_copy(update={"task_id": f"{task.task_id}:{name}"}),
                delegation_depth=int(task.metadata.get("delegation_depth", 0)) + 1,
                metadata={"selection_reason": decision.reason or ""},
            )
            for name in decision.selected_agents
        ]
        return DelegationPlan(invocations=invocations, reason=decision.reason)

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
                thread_id=invocation.task.metadata.get("thread_id", invocation.task.task_id),
                metadata={"task_packet": invocation.task.model_dump(), "handoff": handoff.model_dump(), "_delegated": True},
            )
            results.append(
                AgentResult(
                    agent_name=registered.spec.name,
                    output_text=run_result.output_text,
                    structured_output={"tool_results": [item.model_dump() for item in run_result.tool_results]},
                    metadata={"handoff": handoff.model_dump()},
                )
            )
        return results
