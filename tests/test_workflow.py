import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from agentorch import Agent, AgentRegistry, AgentSpec, OpenAIModel, WorkflowBuilder
from agentorch.config import RuntimeConfig
from agentorch.knowledge import IndexedKnowledgeBase, RetrievalMode
from agentorch.models.base import BaseModelAdapter
from agentorch.runtime import Runtime
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.workflow import Context, Edge, Node, Workflow, WorkflowRunner


def test_workflow_condition_routing():
    asyncio.run(_test_workflow_condition_routing())


async def _test_workflow_condition_routing():
    async def router_handler(node, context):
        return {"status": "completed", "route": "yes"}

    async def tool_handler(node, context):
        return {"status": "completed", "value": 1}

    workflow = Workflow(
        entry_node="r1",
        nodes=[
            Node(id="r1", kind="router"),
            Node(id="t1", kind="tool"),
        ],
        edges=[Edge(source="r1", target="t1", kind="condition", condition="yes")],
    )
    runner = WorkflowRunner({"router": router_handler, "tool": tool_handler})
    result = await runner.run(workflow, Context(thread_id="t", user_input="hi"))
    assert result["value"] == 1


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="ok"),
            content="ok",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class SystemEchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        system_message = next(message for message in request.messages if message.role == "system")
        return ModelResponse(
            message=Message(role="assistant", content=system_message.content),
            content=system_message.content,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def test_retrieve_node_returns_report_payload(tmp_path: Path):
    asyncio.run(_test_retrieve_node_returns_report_payload(tmp_path))


async def _test_retrieve_node_returns_report_payload(tmp_path: Path):
    md_path = tmp_path / "ops.md"
    md_path.write_text("# Ops\nowner approval required\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([md_path], scopes=["ops"])
    runtime = Runtime(
        model=EchoModel(),
        knowledge_base=kb,
        config=RuntimeConfig(enable_retrieval=True, retrieval_mode=RetrievalMode.EXPLICIT_STEP),
    )
    workflow = Workflow(
        entry_node="retrieve",
        nodes=[Node(id="retrieve", kind="retrieve", config={"output_key": "retrieved", "must_cover": ["owner approval"], "file_types": [".md"]})],
        edges=[],
    )
    agent = Agent(runtime=runtime, workflow=workflow)
    result = await agent.run("find owner approval", thread_id="wf-retrieve-report")
    payload = json.loads(result.output_text)
    assert "report" in payload
    assert "coverage" in payload
    assert payload["coverage"]["missing"] == []


def test_rag_router_mount_and_evaluate_nodes(tmp_path: Path):
    asyncio.run(_test_rag_router_mount_and_evaluate_nodes(tmp_path))


async def _test_rag_router_mount_and_evaluate_nodes(tmp_path: Path):
    md_path = tmp_path / "ops.md"
    md_path.write_text("# Ops\nowner approval required\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([md_path], scopes=["ops"])
    runtime = Runtime(
        model=EchoModel(),
        knowledge_base=kb,
        config=RuntimeConfig(enable_retrieval=True, retrieval_mode=RetrievalMode.EXPLICIT_STEP),
    )
    workflow = Workflow(
        entry_node="router",
        nodes=[
            Node(id="router", kind="rag_router", config={"output_key": "route"}),
            Node(id="retrieve", kind="retrieve", config={"output_key": "retrieved", "rag_mode": "deliberative", "must_cover": ["owner approval"]}),
            Node(id="mount", kind="rag_mount", config={"from_variable": "retrieved", "target_key": "mounted", "mount_result_to": "variable"}),
            Node(id="score", kind="rag_evaluate", config={"from_variable": "retrieved", "output_key": "scored"}),
        ],
        edges=[
            Edge(source="router", target="retrieve", kind="success"),
            Edge(source="retrieve", target="mount", kind="success"),
            Edge(source="mount", target="score", kind="success"),
        ],
    )
    agent = Agent(runtime=runtime, workflow=workflow)
    result = await agent.run("Where is the evidence?", thread_id="wf-rag-ops")
    payload = json.loads(result.output_text)
    assert payload["score"] >= 1.0


def test_rag_mount_agent_input_flows_into_agent_node(tmp_path: Path):
    asyncio.run(_test_rag_mount_agent_input_flows_into_agent_node(tmp_path))


async def _test_rag_mount_agent_input_flows_into_agent_node(tmp_path: Path):
    md_path = tmp_path / "ops.md"
    md_path.write_text("# Ops\nowner approval required before release\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([md_path], scopes=["ops"])

    specialist_runtime = Runtime(model=SystemEchoModel())
    registry = AgentRegistry()
    registry.register(AgentSpec(name="specialist", description="Retrieval consumer", allowed_knowledge_scopes=["ops"]), Agent(runtime=specialist_runtime))

    runtime = Runtime(
        model=EchoModel(),
        knowledge_base=kb,
        agent_registry=registry,
        config=RuntimeConfig(enable_retrieval=True, retrieval_mode=RetrievalMode.EXPLICIT_STEP),
    )
    workflow = Workflow(
        entry_node="retrieve",
        nodes=[
            Node(id="retrieve", kind="retrieve", config={"output_key": "retrieved", "must_cover": ["owner approval"], "file_types": [".md"]}),
            Node(id="mount", kind="rag_mount", config={"from_variable": "retrieved", "target_key": "agent_retrieval", "mount_result_to": "agent_input"}),
            Node(id="delegate", kind="agent", config={"agent_name": "specialist", "input_from_variable": "agent_retrieval"}),
        ],
        edges=[
            Edge(source="retrieve", target="mount", kind="success"),
            Edge(source="mount", target="delegate", kind="success"),
        ],
    )

    result = await Agent(runtime=runtime, workflow=workflow).run("find owner approval", thread_id="wf-agent-input")

    assert "Task Packet" in result.output_text
    assert "owner approval required before release" in result.output_text


def test_workflow_builder_and_node_shortcuts_create_runnable_graph(tmp_path: Path):
    asyncio.run(_test_workflow_builder_and_node_shortcuts_create_runnable_graph(tmp_path))


async def _test_workflow_builder_and_node_shortcuts_create_runnable_graph(tmp_path: Path):
    md_path = tmp_path / "ops.md"
    md_path.write_text("# Ops\nowner approval required before release\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([md_path], scopes=["ops"])

    runtime = Runtime(
        model=EchoModel(),
        knowledge_base=kb,
        config=RuntimeConfig.workflow(rag="deliberative"),
    )

    workflow = (
        WorkflowBuilder()
        .then(Node.retrieve("retrieve", output_key="retrieved", must_cover=["owner approval"], file_types=[".md"]))
        .then(Node.rag_mount("mount", from_variable="retrieved", target_key="mounted", mount_result_to="variable"))
        .then(Node.rag_evaluate("score", from_variable="retrieved", output_key="scored"))
        .build()
    )

    result = await Agent(runtime=runtime, workflow=workflow).run("find owner approval", thread_id="workflow-builder")
    payload = json.loads(result.output_text)
    assert payload["score"] >= 1.0


def test_workflow_chain_shortcut_connects_success_edges():
    workflow = Workflow.chain(
        Node.tool("one", "lookup", arguments={"query": "x"}),
        Node.aggregate("two", sources=["one"], output_key="combined"),
    )

    assert workflow.entry_node == "one"
    assert len(workflow.edges) == 1
    assert workflow.edges[0].source == "one"
    assert workflow.edges[0].target == "two"


def test_workflow_agent_node_can_override_context_strategy(tmp_path: Path):
    asyncio.run(_test_workflow_agent_node_can_override_context_strategy(tmp_path))


async def _test_workflow_agent_node_can_override_context_strategy(tmp_path: Path):
    specialist_runtime = Runtime(model=SystemEchoModel())
    registry = AgentRegistry()
    registry.register(AgentSpec(name="specialist", description="Context-aware specialist"), Agent(runtime=specialist_runtime))

    runtime = Runtime(
        model=EchoModel(),
        agent_registry=registry,
        config=RuntimeConfig.agent(orchestration_profile="deep_research"),
    )
    workflow = Workflow(
        entry_node="delegate",
        nodes=[
            Node(
                id="delegate",
                kind="agent",
                config={
                    "agent_name": "specialist",
                    "goal": "review compact context",
                    "context_strategy": {"kind": "research_heavy", "mode": "research_heavy", "include_retrieval_report": True},
                },
            )
        ],
        edges=[],
    )

    result = await Agent(runtime=runtime, workflow=workflow).run("unused", thread_id="wf-strategy-override")
    assert "Task Packet" in result.output_text


def test_workflow_model_node_can_override_model():
    asyncio.run(_test_workflow_model_node_can_override_model())


async def _test_workflow_model_node_can_override_model():
    class FakeChatCompletions:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="node-ok", tool_calls=[]), finish_reason="stop")],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            )

    fake_chat = FakeChatCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_chat))
    runtime = Runtime(model=OpenAIModel(model="gpt-4.1-mini", api_key="test-key", base_url="https://api.openai.com/v1"))
    runtime.model._client = fake_client

    workflow = Workflow(
        entry_node="draft",
        nodes=[
            Node.model_node("draft", prompt="write draft", model="gpt-4.1"),
        ],
        edges=[],
    )

    result = await Agent(runtime=runtime, workflow=workflow).run("unused", thread_id="wf-model-override")

    payload = json.loads(result.output_text)
    assert payload["output_text"] == "node-ok"
    assert fake_chat.calls[0]["model"] == "gpt-4.1"
