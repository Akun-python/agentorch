import asyncio
import json

from agentorch import (
    Agent,
    AgentCapability,
    AgentRegistry,
    AgentSpec,
    ConsoleFeedbackDispatcher,
    HumanFeedbackManager,
    Runtime,
    Supervisor,
    Workflow,
)
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.observability import EventBus, Tracer
from agentorch.workflow import Edge, Node


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        last_user = [message for message in request.messages if message.role == "user"][-1]
        return ModelResponse(
            message=Message(role="assistant", content=f"handled: {last_user.content}"),
            content=f"handled: {last_user.content}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def test_human_feedback_notify_dispatches_and_traces():
    asyncio.run(_test_human_feedback_notify_dispatches_and_traces())


async def _test_human_feedback_notify_dispatches_and_traces():
    bus = EventBus()
    dispatcher = ConsoleFeedbackDispatcher()
    manager = HumanFeedbackManager(dispatcher=dispatcher)
    runtime = Runtime(model=EchoModel(), human_feedback=manager, tracer=Tracer(bus))

    handle = await runtime.human_feedback.notify(
        kind="risk_alert",
        title="Need review",
        message="Potential conflict detected.",
        thread_id="thread-1",
        run_id="run-1",
        task_id="task-1",
    )

    assert handle.status == "dispatched"
    assert len(dispatcher.dispatched_events) == 1
    assert dispatcher.dispatched_events[0].title == "Need review"
    assert "human_feedback_emitted" in [event["event_type"] for event in bus.events]


def test_human_feedback_request_input_and_wait_for_response():
    asyncio.run(_test_human_feedback_request_input_and_wait_for_response())


async def _test_human_feedback_request_input_and_wait_for_response():
    manager = HumanFeedbackManager()
    Runtime(model=EchoModel(), human_feedback=manager)

    handle = await manager.request_input(
        title="Need dataset",
        message="Choose the dataset.",
        thread_id="thread-2",
        run_id="run-2",
        task_id="task-2",
    )

    assert handle.status == "waiting_human"
    pending = await manager.get(handle.feedback_id)
    assert pending is not None
    assert pending.status.value == "pending"

    await manager.submit_response(handle.feedback_id, response={"dataset": "hybrid"}, responder="alice")
    response = await manager.wait_for_response(handle.feedback_id, timeout=0.1)

    assert response is not None
    assert response.content == {"dataset": "hybrid"}


def test_run_sync_returns_waiting_human_for_workflow_node():
    manager = HumanFeedbackManager()
    runtime = Runtime(model=EchoModel(), human_feedback=manager)
    workflow = Workflow(
        entry_node="ask",
        nodes=[
            Node(
                id="ask",
                kind="human_input",
                config={"title": "Need input", "message": "Please choose", "output_key": "human_choice"},
            )
        ],
        edges=[],
    )
    agent = Agent(runtime=runtime, workflow=workflow)

    result = agent.run_sync("start", thread_id="wf-hitl-sync")

    assert result.status == "waiting_human"
    assert result.feedback_id is not None
    assert result.requires_response is True


def test_workflow_resume_from_feedback_restores_response():
    asyncio.run(_test_workflow_resume_from_feedback_restores_response())


async def _test_workflow_resume_from_feedback_restores_response():
    manager = HumanFeedbackManager()
    runtime = Runtime(model=EchoModel(), human_feedback=manager)
    workflow = Workflow(
        entry_node="ask",
        nodes=[
            Node(
                id="ask",
                kind="human_input",
                config={
                    "title": "Need retriever",
                    "message": "Choose a retriever",
                    "response_schema": {"type": "object"},
                    "output_key": "human_choice",
                },
            ),
            Node(id="combine", kind="aggregate", config={"sources": ["human_choice"], "output_key": "combined"}),
        ],
        edges=[Edge(source="ask", target="combine", kind="success")],
    )
    agent = Agent(runtime=runtime, workflow=workflow)

    first = await agent.run("start workflow", thread_id="wf-hitl")

    assert first.status == "waiting_human"
    await manager.submit_response(first.feedback_id, response={"retriever": "hybrid"}, responder="alice")

    resumed = await runtime.resume_from_feedback(first.feedback_id, workflow=workflow, thread_id="wf-hitl")
    payload = json.loads(resumed.output_text)

    assert resumed.status == "completed"
    assert payload["combined"]["human_choice"]["response"] == {"retriever": "hybrid"}


def test_supervisor_delegated_agent_can_emit_human_feedback():
    asyncio.run(_test_supervisor_delegated_agent_can_emit_human_feedback())


async def _test_supervisor_delegated_agent_can_emit_human_feedback():
    bus = EventBus()
    manager = HumanFeedbackManager()
    specialist_workflow = Workflow(
        entry_node="ask",
        nodes=[Node(id="ask", kind="human_input", config={"title": "Need approval", "message": "Approve the plan"})],
        edges=[],
    )
    specialist = Agent(runtime=Runtime(model=EchoModel(), human_feedback=manager), workflow=specialist_workflow)

    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            capabilities=[AgentCapability.PLAN],
            tags=["plan"],
        ),
        specialist,
    )
    runtime = Runtime(
        model=EchoModel(),
        agent_registry=registry,
        supervisor=Supervisor(registry=registry),
        human_feedback=manager,
        tracer=Tracer(bus),
    )
    agent = Agent(runtime=runtime)

    result = await agent.run("plan the project", thread_id="supervisor-hitl")

    assert result.status == "completed"
    assert "human_feedback_emitted" in [event["event_type"] for event in bus.events]
    assert len(await manager.list_pending()) >= 1
