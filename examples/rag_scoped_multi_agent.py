import asyncio

from agentorch import Agent, AgentCapability, AgentRegistry, AgentSpec, InMemoryKnowledgeBase, OpenAIModel, Runtime, Supervisor
from agentorch.agents import AgentInvocation, AgentRouteDecision, DelegationPlan, TaskPacket, TaskStatus
from agentorch.config import RuntimeConfig
from agentorch.knowledge import Document, RetrievalMode


async def build_specialist(name: str, scope: str) -> Agent:
    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        knowledge_base=KNOWLEDGE_BASE,
        config=RuntimeConfig(
            system_prompt=f"You are {name}. Use only the knowledge scope assigned to you.",
            enable_retrieval=True,
            retrieval_mode=RetrievalMode.INLINE,
            default_knowledge_scope=[scope],
        ),
    )
    return Agent(runtime=runtime)


KNOWLEDGE_BASE = InMemoryKnowledgeBase()


class ScopedSupervisor(Supervisor):
    async def create_plan(self, task: TaskPacket):
        decision: AgentRouteDecision = await self.policy.select_agents(task, self.registry)
        task_plan = self.planner.build_plan(
            task,
            decision.selected_agents,
            registry=self.registry,
            reason=decision.reason,
            scores=decision.scores,
        )
        invocations = []
        for step in task_plan.steps:
            registered = self.registry.get(step.assigned_agent or "")
            invocations.append(
                AgentInvocation(
                    agent_name=registered.spec.name,
                    task=task.model_copy(
                        update={
                            "task_id": f"{task.task_id}:{registered.spec.name}",
                            "parent_task_id": task.task_id,
                            "origin_agent": task.origin_agent or "supervisor",
                            "status": TaskStatus.PENDING,
                            "knowledge_scope": registered.spec.allowed_knowledge_scopes,
                        }
                    ),
                    delegation_depth=int(task.metadata.get("delegation_depth", 0)) + 1,
                    metadata={"selection_reason": decision.reason or "", "step_id": step.step_id},
                )
            )
        return DelegationPlan(invocations=invocations, reason=decision.reason, task_plan=task_plan)


async def main() -> None:
    await KNOWLEDGE_BASE.ingest(
        [
            Document(id="fin-1", text="Quarterly revenue increased by 12 percent.", metadata={"scopes": ["finance"]}),
            Document(id="law-1", text="Regulatory review is required before external publication.", metadata={"scopes": ["policy"]}),
        ]
    )

    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            name="finance_analyst",
            description="Answers finance questions",
            capabilities=[AgentCapability.RETRIEVE],
            allowed_knowledge_scopes=["finance"],
        ),
        await build_specialist("finance_analyst", "finance"),
    )
    registry.register(
        AgentSpec(
            name="legal_reviewer",
            description="Answers policy questions",
            capabilities=[AgentCapability.REVIEW],
            allowed_knowledge_scopes=["policy"],
        ),
        await build_specialist("legal_reviewer", "policy"),
    )

    supervisor = ScopedSupervisor(registry=registry)
    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        knowledge_base=KNOWLEDGE_BASE,
        agent_registry=registry,
        supervisor=supervisor,
        config=RuntimeConfig(default_knowledge_scope=[]),
    )
    agent = Agent(runtime=runtime)
    result = await agent.run(
        "Summarize the finance update and the policy risk for publication.",
        thread_id="rag-scoped-multi-agent",
    )
    print(result.output_text)


if __name__ == "__main__":
    asyncio.run(main())
