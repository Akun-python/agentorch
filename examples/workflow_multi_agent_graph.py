import asyncio

from agentorch import Agent, AgentCapability, AgentRegistry, AgentSpec, InMemoryKnowledgeBase, OpenAIModel, Runtime, Workflow
from agentorch.config import RuntimeConfig
from agentorch.knowledge import Document, RetrievalMode
from agentorch.workflow import Edge, Node


async def build_specialist(role: str) -> Agent:
    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        config=RuntimeConfig(
            system_prompt=f"You are the {role} specialist. Return concise, useful output.",
            enable_retrieval=True,
            retrieval_mode=RetrievalMode.INLINE,
        ),
    )
    return Agent(runtime=runtime)


async def main() -> None:
    knowledge_base = InMemoryKnowledgeBase()
    await knowledge_base.ingest(
        [
            Document(id="arch-1", text="Use structured task handoff and aggregation for multi-agent systems.", metadata={"scopes": ["architecture"]}),
        ]
    )

    registry = AgentRegistry()
    registry.register(
        AgentSpec(name="planner", description="Plans work", capabilities=[AgentCapability.PLAN], allowed_knowledge_scopes=["architecture"]),
        await build_specialist("planner"),
    )
    registry.register(
        AgentSpec(name="reviewer", description="Reviews outputs", capabilities=[AgentCapability.REVIEW], allowed_knowledge_scopes=["architecture"]),
        await build_specialist("reviewer"),
    )

    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        knowledge_base=knowledge_base,
        agent_registry=registry,
        config=RuntimeConfig(enable_retrieval=True, retrieval_mode=RetrievalMode.EXPLICIT_STEP, default_knowledge_scope=["architecture"]),
    )

    workflow = Workflow(
        entry_node="retrieve",
        nodes=[
            Node(id="retrieve", kind="retrieve", config={"output_key": "knowledge"}),
            Node(id="plan", kind="agent", config={"agent_name": "planner", "goal": "Design the multi-agent plan", "output_key": "plan", "knowledge_scope": ["architecture"]}),
            Node(id="review", kind="agent", config={"agent_name": "reviewer", "goal": "Review the plan for missing risks", "output_key": "review", "knowledge_scope": ["architecture"]}),
            Node(id="aggregate", kind="aggregate", config={"sources": ["knowledge", "plan", "review"], "output_key": "final"}),
        ],
        edges=[
            Edge(source="retrieve", target="plan", kind="success"),
            Edge(source="plan", target="review", kind="success"),
            Edge(source="review", target="aggregate", kind="success"),
        ],
    )

    agent = Agent(runtime=runtime, workflow=workflow)
    result = await agent.run("Design a research-oriented multi-agent stack.", thread_id="workflow-multi-agent")
    print(result.output_text)


if __name__ == "__main__":
    asyncio.run(main())
