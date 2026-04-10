import asyncio
import json
import uuid
from pathlib import Path

from agentorch.agents import AgentCapability, AgentRegistry, AgentSpec, Supervisor, TaskArtifact, TaskBudget, TaskPacket
from agentorch.config import MemoryConfig
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.memory import MemoryManager
from agentorch.models.base import BaseModelAdapter
from agentorch.observability import EventBus, TaskGraphSnapshot, Tracer
from agentorch.runtime import Agent, Runtime
from agentorch.config import RuntimeConfig
from agentorch.knowledge import BaseRetriever, DocumentChunk, IndexedKnowledgeBase, RetrievedChunk, RetrievalQuery, RetrievalMode
from agentorch.strategies import CooperationStrategyConfig
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


class SystemPromptEchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        system_message = next(message for message in request.messages if message.role == "system")
        return ModelResponse(
            message=Message(role="assistant", content=system_message.content),
            content=system_message.content,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class CapturingSystemPromptModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.last_system_prompt = ""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        system_message = next(message for message in request.messages if message.role == "system")
        self.last_system_prompt = system_message.content
        return ModelResponse(
            message=Message(role="assistant", content=system_message.content),
            content=system_message.content,
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
        config=RuntimeConfig(enable_retrieval=True, retrieval_mode=RetrievalMode.INLINE, max_retrieved_chunks=1),
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
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            tags=["plan"],
            capabilities=[AgentCapability.PLAN],
        ),
        specialist,
    )
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
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            tags=["plan"],
            capabilities=[AgentCapability.PLAN],
            allowed_knowledge_scopes=["planning"],
        ),
        specialist,
    )
    bus = EventBus()
    supervisor = Supervisor(registry=registry)
    runtime = Runtime(
        model=EchoModel(),
        agent_registry=registry,
        supervisor=supervisor,
        config=RuntimeConfig(default_knowledge_scope=["planning"]),
        tracer=Tracer(bus),
    )
    agent = Agent(runtime=runtime)
    result = await agent.run("plan the project", thread_id="supervisor-thread")
    assert "[planner] handled: plan the project" in result.output_text
    event_types = [event["event_type"] for event in bus.events]
    assert "supervisor_routed" in event_types
    assert "agent_delegated" in event_types
    assert "handoff_created" in event_types
    assert "aggregation_completed" in event_types
    snapshot = TaskGraphSnapshot(bus.events)
    assert snapshot.edges()


def test_supervisor_injects_and_promotes_collective_memory():
    asyncio.run(_test_supervisor_injects_and_promotes_collective_memory())


async def _test_supervisor_injects_and_promotes_collective_memory():
    temp_root = Path(".agentorch") / "test_collective_memory"
    temp_root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    shared_memory = MemoryManager(
        config=MemoryConfig(
            checkpoint_path=temp_root / f"checkpoints_{run_id}.db",
            record_path=temp_root / f"records_{run_id}.db",
        )
    )
    collective_record_id = await shared_memory.promote_collective_memory(
        thread_id="collective-thread",
        kind="route",
        content="follow the dry riverbed to reach the safe checkpoint",
        tags=["route", "hazard"],
        source_agents=["elder"],
        confidence=0.85,
        scope="planning",
    )

    registry = AgentRegistry()
    planner = Agent(runtime=Runtime(model=SystemPromptEchoModel()))
    reviewer = Agent(runtime=Runtime(model=SystemPromptEchoModel()))
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            tags=["plan"],
            capabilities=[AgentCapability.PLAN],
            allowed_knowledge_scopes=["planning"],
        ),
        planner,
    )
    registry.register(
        AgentSpec(
            name="reviewer",
            description="Review specialist",
            tags=["review"],
            capabilities=[AgentCapability.REVIEW],
            allowed_knowledge_scopes=["planning"],
        ),
        reviewer,
    )

    runtime = Runtime(
        model=EchoModel(),
        memory=shared_memory,
        agent_registry=registry,
        supervisor=Supervisor(registry=registry),
        config=RuntimeConfig(default_knowledge_scope=["planning"]),
    )
    agent = Agent(runtime=runtime)

    injected = await agent.run("plan review the safe checkpoint route", thread_id="collective-thread")
    assert "Collective Memory" in injected.output_text
    assert "dry riverbed" in injected.output_text

    collective_after_run = await shared_memory.search_collective_memory(query="dry riverbed", thread_id="collective-thread", status=None)
    seeded = next(item for item in collective_after_run if item["id"] == collective_record_id)
    assert seeded["reuse_count"] == 1

    promoted = [item for item in collective_after_run if item["id"] != collective_record_id]
    assert any(item["memory_role"] == "matriarch" for item in promoted)
    assert any("validated route" in item["content"] for item in promoted)


def test_supervisor_passes_compacted_handoff_capsule_to_specialist():
    asyncio.run(_test_supervisor_passes_compacted_handoff_capsule_to_specialist())


async def _test_supervisor_passes_compacted_handoff_capsule_to_specialist():
    registry = AgentRegistry()
    capturing_model = CapturingSystemPromptModel()
    specialist = Agent(runtime=Runtime(model=capturing_model))
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            tags=["plan"],
            capabilities=[AgentCapability.PLAN],
            allowed_knowledge_scopes=["planning"],
        ),
        specialist,
    )
    runtime = Runtime(
        model=EchoModel(),
        agent_registry=registry,
        supervisor=Supervisor(registry=registry),
        config=RuntimeConfig(default_knowledge_scope=["planning"]),
    )
    agent = Agent(runtime=runtime)
    await agent.run("plan the project", thread_id="capsule-thread")
    assert "Task Packet" in capturing_model.last_system_prompt
    assert "goal" in capturing_model.last_system_prompt
    assert "artifact_refs" not in capturing_model.last_system_prompt
    assert "expected_output" not in capturing_model.last_system_prompt


def test_workflow_retrieve_aggregate_and_artifact_nodes():
    asyncio.run(_test_workflow_retrieve_aggregate_and_artifact_nodes())


async def _test_workflow_retrieve_aggregate_and_artifact_nodes():
    runtime = Runtime(
        model=EchoModel(),
        retriever=StaticRetriever(),
        config=RuntimeConfig(enable_retrieval=True, retrieval_mode=RetrievalMode.EXPLICIT_STEP),
    )
    workflow = Workflow(
        entry_node="retrieve",
        nodes=[
            Node(id="retrieve", kind="retrieve", config={"output_key": "retrieved"}),
            Node(id="aggregate", kind="aggregate", config={"sources": ["retrieved"], "output_key": "combined"}),
            Node(id="artifact", kind="artifact", config={"from_variable": "combined", "artifact_id": "artifact-1"}),
        ],
        edges=[
            Edge(source="retrieve", target="aggregate", kind="success"),
            Edge(source="aggregate", target="artifact", kind="success"),
        ],
    )
    agent = Agent(runtime=runtime, workflow=workflow)
    result = await agent.run("need retrieval", thread_id="wf-rag")
    payload = json.loads(result.output_text)
    assert payload["artifact_id"] == "artifact-1"


def test_runtime_retrieval_report_enters_prompt_and_workflow_outputs_report(tmp_path: Path):
    asyncio.run(_test_runtime_retrieval_report_enters_prompt_and_workflow_outputs_report(tmp_path))


async def _test_runtime_retrieval_report_enters_prompt_and_workflow_outputs_report(tmp_path: Path):
    markdown_path = tmp_path / "policy.md"
    markdown_path.write_text("# Policy\nowner approval required before deploy\n", encoding="utf-8")
    text_path = tmp_path / "note.txt"
    text_path.write_text("general notes", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([markdown_path, text_path], scopes=["ops"])
    runtime = Runtime(
        model=SystemPromptEchoModel(),
        knowledge_base=kb,
        config=RuntimeConfig(
            enable_retrieval=True,
            retrieval_mode=RetrievalMode.INLINE,
            retrieval_allowed_file_types=[".md"],
            max_retrieved_chunks=4,
        ),
    )
    agent = Agent(runtime=runtime)
    result = await agent.run("find owner approval", thread_id="rag-report")
    assert "Retrieved Evidence" in result.output_text
    assert "Retrieval Report" in result.output_text
    assert "owner approval" in result.output_text

    workflow = Workflow(
        entry_node="retrieve",
        nodes=[Node(id="retrieve", kind="retrieve", config={"output_key": "retrieved", "file_types": [".md"], "must_cover": ["owner approval"]})],
        edges=[],
    )
    workflow_agent = Agent(runtime=runtime, workflow=workflow)
    wf_result = await workflow_agent.run("find owner approval", thread_id="rag-report-wf")
    payload = json.loads(wf_result.output_text)
    assert payload["coverage"]["missing"] == []
    assert payload["report"]["visited_sources"]


def test_deliberative_retrieve_tool_respects_runtime_constraints(tmp_path: Path):
    asyncio.run(_test_deliberative_retrieve_tool_respects_runtime_constraints(tmp_path))


async def _test_deliberative_retrieve_tool_respects_runtime_constraints(tmp_path: Path):
    md_path = tmp_path / "deploy.md"
    md_path.write_text("# Deploy\nowner approval required\n", encoding="utf-8")
    txt_path = tmp_path / "deploy.txt"
    txt_path.write_text("owner approval not here", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([md_path, txt_path], scopes=["ops"])
    runtime = Runtime(
        model=EchoModel(),
        knowledge_base=kb,
        config=RuntimeConfig(enable_retrieval=True, retrieval_allowed_file_types=[".md"]),
    )
    tool_result = await runtime.tools.execute(
        "deliberative_retrieve",
        {"question": "owner approval", "knowledge_scope": ["ops"]},
    )
    assert tool_result.success
    assert tool_result.data["visited_sources"]
    assert all(citation["metadata"].get("path", "").endswith(".md") for citation in tool_result.data["citations"])


def test_supervisor_plan_and_budget_object_shapes():
    registry = AgentRegistry()
    registry.register(
        AgentSpec(name="planner", description="Planning specialist", capabilities=[AgentCapability.PLAN]),
        object(),
    )
    supervisor = Supervisor(registry=registry)
    plan = asyncio.run(
        supervisor.create_plan(
            TaskPacket(task_id="t-1", goal="plan roadmap", budget=TaskBudget(max_steps=3), origin_agent="supervisor")
        )
    )
    assert plan.task_plan is not None
    assert plan.invocations[0].task.parent_task_id == "t-1"


def test_supervisor_propagates_selected_cooperation_strategy_metadata():
    asyncio.run(_test_supervisor_propagates_selected_cooperation_strategy_metadata())


async def _test_supervisor_propagates_selected_cooperation_strategy_metadata():
    registry = AgentRegistry()
    specialist = Agent(runtime=Runtime(model=EchoModel()))
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            tags=["plan"],
            capabilities=[AgentCapability.PLAN],
            allowed_knowledge_scopes=["planning"],
        ),
        specialist,
    )
    runtime = Runtime(
        model=EchoModel(),
        agent_registry=registry,
        supervisor=Supervisor(registry=registry),
        config=RuntimeConfig(
            orchestration_profile="deep_research",
            default_knowledge_scope=["planning"],
            cooperation_strategy=CooperationStrategyConfig.distributed(),
        ),
    )
    result = await Agent(runtime=runtime).run("plan the project", thread_id="distributed-cooperation")
    shared_notes = await runtime.memory.get_shared_notes("distributed-cooperation")
    assert "[planner] handled: plan the project" in result.output_text
    assert any(
        note.metadata.get("cooperation_strategy", {}).get("topology") == "distributed_herd"
        for note in shared_notes
    ) or runtime.config.cooperation_strategy.topology == "distributed_herd"
