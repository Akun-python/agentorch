import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel

from agentorch import Agent, AgentRegistry, AgentSpec, EvaluationResult, EvolutionConfig, OpenAIModel, SandboxManager, SearchSpace, WorkflowBuilder, create_agent_evolution, create_python_interpreter_tool, tool
from agentorch.config import RuntimeConfig
from agentorch.knowledge import IndexedKnowledgeBase, RetrievalMode
from agentorch.models.base import BaseModelAdapter
from agentorch.runtime import Runtime
from agentorch.sandbox import SandboxPolicy
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.tools import ToolRegistry
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


def test_workflow_agent_node_can_override_context_policy(tmp_path: Path):
    asyncio.run(_test_workflow_agent_node_can_override_context_policy(tmp_path))


async def _test_workflow_agent_node_can_override_context_policy(tmp_path: Path):
    specialist_runtime = Runtime(model=SystemEchoModel())
    registry = AgentRegistry()
    registry.register(AgentSpec(name="specialist", description="Context-aware specialist"), Agent(runtime=specialist_runtime))

    runtime = Runtime(
        model=EchoModel(),
        agent_registry=registry,
        config=RuntimeConfig.agent(),
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
                    "context_policy": {
                        "sources": {
                            "memory_summary": True,
                            "retrieval_summary": True,
                            "retrieval_evidence": {"enabled": True, "max_items": 6},
                            "retrieval_citations": {"enabled": True, "max_items": 6},
                            "retrieval_report": True,
                            "retrieval_plan": True,
                            "tool_descriptions": False,
                            "skill_instructions": True,
                            "task_packet": {"enabled": True, "representation": "capsule"},
                            "delegation_context": {"enabled": True, "representation": "capsule"},
                            "shared_memory": {"enabled": True, "max_items": 4},
                        },
                        "char_budget": 22000,
                        "selection_mode": "hybrid",
                    },
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


def test_workflow_model_node_can_include_prior_variables_in_task_packet():
    asyncio.run(_test_workflow_model_node_can_include_prior_variables_in_task_packet())


async def _test_workflow_model_node_can_include_prior_variables_in_task_packet():
    class EmptyInput(BaseModel):
        value: str | None = None

    @tool(description="Emit a deterministic workflow payload.")
    async def emit_payload(input: EmptyInput):
        return {"stage": "alpha", "score": 3}

    registry = ToolRegistry.empty()
    registry.register(emit_payload)
    runtime = Runtime(model=SystemEchoModel(), tools=registry)
    workflow = Workflow(
        entry_node="emit",
        nodes=[
            Node.tool("emit", "emit_payload"),
            Node.model_node("consume", prompt="use workflow context", task_context_from_variables=["emit"]),
        ],
        edges=[Edge(source="emit", target="consume", kind="success")],
    )

    result = await Agent(runtime=runtime, workflow=workflow).run("unused", thread_id="wf-model-task-context")

    assert "Task Packet" in result.output_text
    assert "workflow_variables" in result.output_text
    assert "alpha" in result.output_text


def test_workflow_model_node_preserves_large_task_packet_context_without_budget_compaction():
    asyncio.run(_test_workflow_model_node_preserves_large_task_packet_context_without_budget_compaction())


async def _test_workflow_model_node_preserves_large_task_packet_context_without_budget_compaction():
    class EmptyInput(BaseModel):
        value: str | None = None

    @tool(description="Emit a large workflow payload.")
    async def emit_large_payload(input: EmptyInput):
        return {
            "artifact_name": "workflow-evolution-summary",
            "best_candidate": {
                "workflow": {
                    "nodes": [{"id": "retrieve", "kind": "retrieve"}, {"id": "review", "kind": "model"}],
                    "edges": [{"source": "retrieve", "target": "review", "kind": "success"}],
                }
            },
            "notes": ["x" * 800, "y" * 800],
        }

    registry = ToolRegistry.empty()
    registry.register(emit_large_payload)
    runtime = Runtime(model=SystemEchoModel(), tools=registry)
    workflow = Workflow(
        entry_node="emit",
        nodes=[
            Node.tool("emit", "emit_large_payload"),
            Node.model_node("consume", prompt="use workflow context", task_context_from_variables=["emit"]),
        ],
        edges=[Edge(source="emit", target="consume", kind="success")],
    )

    result = await Agent(runtime=runtime, workflow=workflow).run("unused", thread_id="wf-large-task-context")

    assert "workflow_variables" in result.output_text
    assert "workflow-evolution-summary" in result.output_text
    assert "best_candidate" in result.output_text


def test_workflow_tool_node_can_chain_persistent_python_session_arguments(tmp_path: Path):
    asyncio.run(_test_workflow_tool_node_can_chain_persistent_python_session_arguments(tmp_path))


async def _test_workflow_tool_node_can_chain_persistent_python_session_arguments(tmp_path: Path):
    sandbox = SandboxManager(policy=SandboxPolicy(allowed_paths=[tmp_path], command_allowlist=["python"], timeout=10.0))
    registry = ToolRegistry.empty()
    registry.register(create_python_interpreter_tool(sandbox))
    runtime = Runtime(model=EchoModel(), tools=registry, sandbox=sandbox)
    workflow = Workflow(
        entry_node="start",
        nodes=[
            Node.tool("start", "python_interpreter", arguments={"create_session": True, "workdir": str(tmp_path)}),
            Node.tool(
                "seed",
                "python_interpreter",
                arguments={
                    "session_id": {"$from": "start.output.session_id"},
                    "code": "numbers = [2, 3, 5]\nprint(sum(numbers))",
                    "workdir": str(tmp_path),
                },
            ),
            Node.tool(
                "extend",
                "python_interpreter",
                arguments={
                    "session_id": {"$from": "start.output.session_id"},
                    "code": "numbers.append(7)\nprint(sum(numbers))",
                    "workdir": str(tmp_path),
                },
            ),
            Node.tool(
                "close",
                "python_interpreter",
                arguments={"session_id": {"$from": "start.output.session_id"}, "close_session": True},
            ),
            Node.aggregate("finalize", sources=["start", "seed", "extend", "close"]),
        ],
        edges=[
            Edge(source="start", target="seed", kind="success"),
            Edge(source="seed", target="extend", kind="success"),
            Edge(source="extend", target="close", kind="success"),
            Edge(source="close", target="finalize", kind="success"),
        ],
    )

    result = await Agent(runtime=runtime, workflow=workflow).run("unused", thread_id="wf-python-session")
    payload = json.loads(result.output_text)
    combined = payload["combined"]

    assert combined["start"]["output"]["session_id"] == combined["extend"]["output"]["session_id"]
    assert "10" in combined["seed"]["output"]["stdout"]
    assert "17" in combined["extend"]["output"]["stdout"]
    assert combined["close"]["output"]["closed"] is True


def test_workflow_evolution_node_runs_session_and_returns_summary():
    asyncio.run(_test_workflow_evolution_node_runs_session_and_returns_summary())


async def _test_workflow_evolution_node_runs_session_and_returns_summary():
    session = create_agent_evolution(
        model=EchoModel(),
        search_space=SearchSpace({"workflow.template": ["classic_inline_answer", "retrieve_plan_review"]}),
        evolution_config=EvolutionConfig(population_size=2, generations=1, seed=7),
        evaluator=lambda genome, candidate, tasks: EvaluationResult(
            genome_id=genome.id,
            fitness=3.0 if candidate.workflow and any(node.kind == "retrieve" for node in candidate.workflow.nodes) else 1.0,
        ),
    )
    runtime = Runtime(model=EchoModel())
    workflow = Workflow(
        entry_node="search",
        nodes=[Node.evolution("search", session=session, output_key="search_result", include_history=False)],
        edges=[],
    )

    result = await Agent(runtime=runtime, workflow=workflow).run("search", thread_id="wf-evolution")
    payload = json.loads(result.output_text)

    assert payload["best_candidate"]["workflow"]["nodes"][0]["kind"] == "retrieve"
    assert payload["best_evaluation"]["fitness"] == 3.0
