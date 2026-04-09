import asyncio

from agentorch.agents import AgentRegistry, AgentSpec, Supervisor
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.observability import EventBus, Tracer
from agentorch.runtime import Agent, Runtime
from agentorch.config import RuntimeConfig
from agentorch.knowledge import BaseRetriever, RetrievedChunk, DocumentChunk, RetrievalQuery
from agentorch.workflow import Edge, Node, Workflow


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        last_user = [message for message in request.messages if message.role == "user"][-1]
        return ModelResponse(
            message=Message(role="assistant", content=f"handled: {last_user.content}"),
            content=f"handled: {last_user.content}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class StaticRetriever(BaseRetriever):
    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk=DocumentChunk(id="c1", document_id="d1", text="retrieved context"),
                score=1.0,
                source="stub",
            )
        ]


def test_runtime_injects_retrieval_and_emits_events():
    asyncio.run(_test_runtime_injects_retrieval_and_emits_events())


async def _test_runtime_injects_retrieval_and_emits_events():
    bus = EventBus()
    runtime = Runtime(
        model=EchoModel(),
        retriever=StaticRetriever(),
        config=RuntimeConfig(enable_retrieval=True, max_retrieved_chunks=1),
        tracer=Tracer(bus),
    )
    agent = Agent(runtime=runtime)
    result = await agent.run("hello retrieval", thread_id="retrieval-thread")
    assert "handled: hello retrieval" == result.output_text
    event_types = [event["event_type"] for event in bus.events]
    assert "retrieval_started" in event_types
    assert "retrieval_completed" in event_types


def test_workflow_agent_node_executes_registered_agent():
    asyncio.run(_test_workflow_agent_node_executes_registered_agent())


async def _test_workflow_agent_node_executes_registered_agent():
    registry = AgentRegistry()
    specialist = Agent(runtime=Runtime(model=EchoModel()))
    registry.register(AgentSpec(name="planner", description="Planning specialist", tags=["plan"]), specialist)
    runtime = Runtime(model=EchoModel(), agent_registry=registry)
    workflow = Workflow(
        entry_node="delegate",
        nodes=[Node(id="delegate", kind="agent", config={"agent_name": "planner", "goal": "plan this", "output_key": "planner_output"})],
        edges=[],
    )
    agent = Agent(runtime=runtime, workflow=workflow)
    result = await agent.run("ignored", thread_id="wf-agent")
    assert "handled: plan this" in result.output_text


def test_supervisor_delegates_registered_agent():
    asyncio.run(_test_supervisor_delegates_registered_agent())


async def _test_supervisor_delegates_registered_agent():
    registry = AgentRegistry()
    specialist = Agent(runtime=Runtime(model=EchoModel()))
    registry.register(AgentSpec(name="planner", description="Planning specialist", tags=["plan"]), specialist)
    bus = EventBus()
    supervisor = Supervisor(registry=registry)
    runtime = Runtime(model=EchoModel(), agent_registry=registry, supervisor=supervisor, tracer=Tracer(bus))
    agent = Agent(runtime=runtime)
    result = await agent.run("plan the project", thread_id="supervisor-thread")
    assert "[planner] handled: plan the project" in result.output_text
    event_types = [event["event_type"] for event in bus.events]
    assert "supervisor_routed" in event_types
    assert "agent_delegated" in event_types
    assert "handoff_created" in event_types
