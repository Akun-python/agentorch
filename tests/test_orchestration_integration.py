import asyncio
from pathlib import Path

from pydantic import BaseModel

from agentorch import (
    Agent,
    AgentCapability,
    DeepResearchAgent,
    DeepResearchAgentConfig,
    AgentRegistry,
    AgentSpec,
    Runtime,
    SkillLoader,
    SkillRegistry,
    Supervisor,
    ToolRegistry,
    create_reasoning_framework,
    tool,
)
from agentorch.config import RuntimeConfig
from agentorch.core import Message, ModelRequest, ModelResponse, ToolCall, UsageInfo
from agentorch.knowledge import Document
from agentorch.models.base import BaseModelAdapter
from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.strategies import ContextPolicy, CoordinationPolicy
from agentorch.tools import register_default_agent_tools
from agentorch.workflow import Edge, Node, Workflow


class SumInput(BaseModel):
    a: int
    b: int


@tool(description="Add two integers and return the sum.")
async def add_numbers(input: SumInput):
    return {"sum": input.a + input.b}


class CustomSignalInput(BaseModel):
    query: str


class SkillAwareToolModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.system_prompts: list[str] = []
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        system_text = next(message.content for message in request.messages if message.role == "system")
        self.system_prompts.append(system_text)
        latest_tool = next((message.content for message in reversed(request.messages) if message.role == "tool"), "")

        if latest_tool:
            return ModelResponse(
                message=Message(role="assistant", content=f"Final answer based on tool result: {latest_tool}"),
                content=f"Final answer based on tool result: {latest_tool}",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )

        assert "Skill Instructions:" in system_text
        assert "When the user asks for finance totals, use add_numbers." in system_text
        assert "Available Tools:" in system_text
        assert "add_numbers" in system_text

        tool_call = ToolCall(id="call-add-1", name="add_numbers", arguments={"a": 20, "b": 22})
        return ModelResponse(
            message=Message(role="assistant", content="Using the calculator tool.", tool_calls=[tool_call]),
            content="Using the calculator tool.",
            tool_calls=[tool_call],
            finish_reason="tool_calls",
            usage=UsageInfo(total_tokens=1),
        )


class DelegatedSkillModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.system_prompts: list[str] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        system_text = next(message.content for message in request.messages if message.role == "system")
        self.system_prompts.append(system_text)
        latest_tool = next((message.content for message in reversed(request.messages) if message.role == "tool"), "")

        if latest_tool:
            return ModelResponse(
                message=Message(role="assistant", content=f"Specialist completed: {latest_tool}"),
                content=f"Specialist completed: {latest_tool}",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )

        assert "Agent Role:" in system_text
        assert "planner" in system_text
        assert "Skill Instructions:" in system_text
        assert "Available Tools:" in system_text
        assert "add_numbers" in system_text

        tool_call = ToolCall(id="call-add-2", name="add_numbers", arguments={"a": 5, "b": 7})
        return ModelResponse(
            message=Message(role="assistant", content="Delegated tool use.", tool_calls=[tool_call]),
            content="Delegated tool use.",
            tool_calls=[tool_call],
            finish_reason="tool_calls",
            usage=UsageInfo(total_tokens=1),
        )


class AggregatorEchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        last_user = next((message.content for message in reversed(request.messages) if message.role == "user"), "")
        return ModelResponse(
            message=Message(role="assistant", content=f"Aggregate: {last_user}"),
            content=f"Aggregate: {last_user}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class DeepResearchEchoModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.system_prompts: list[str] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        system_message = next(message.content for message in request.messages if message.role == "system")
        self.system_prompts.append(system_message)
        return ModelResponse(
            message=Message(role="assistant", content=system_message[:160]),
            content=system_message[:160],
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def _tool_visible_context_policy() -> ContextPolicy:
    base_sources = ContextPolicy.default().sources
    return ContextPolicy.default(sources={**base_sources, "tool_descriptions": True})


def _build_skill_registry(tmp_path: Path) -> SkillRegistry:
    skill_dir = tmp_path / "finance-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: finance_helper\n"
            "description: Finance totals helper\n"
            "triggers: finance,total,budget\n"
            "allowed_tools: add_numbers\n"
            "---\n"
            "When the user asks for finance totals, use add_numbers."
        ),
        encoding="utf-8",
    )
    registry = SkillRegistry()
    registry.register(SkillLoader().load(skill_dir))
    return registry


def test_skill_loading_prompt_injection_and_tool_orchestration(tmp_path: Path):
    asyncio.run(_test_skill_loading_prompt_injection_and_tool_orchestration(tmp_path))


async def _test_skill_loading_prompt_injection_and_tool_orchestration(tmp_path: Path):
    skills = _build_skill_registry(tmp_path)
    tools = ToolRegistry()
    tools.register(add_numbers)
    model = SkillAwareToolModel()
    runtime = Runtime(
        model=model,
        tools=tools,
        skills=skills,
        policy=create_reasoning_framework("react"),
        config=RuntimeConfig.agent(context_policy=_tool_visible_context_policy()),
    )

    result = await Agent(runtime=runtime).run("Please help with this finance total.", thread_id="skill-tool-thread")

    assert '"sum": 42' in result.output_text
    assert len(result.tool_results) == 1
    assert result.tool_results[0].tool_name == "add_numbers"
    assert any("Skill Instructions:" in prompt for prompt in model.system_prompts)


def test_supervisor_delegation_preserves_skill_and_tool_orchestration(tmp_path: Path):
    asyncio.run(_test_supervisor_delegation_preserves_skill_and_tool_orchestration(tmp_path))


async def _test_supervisor_delegation_preserves_skill_and_tool_orchestration(tmp_path: Path):
    specialist_tools = ToolRegistry()
    specialist_tools.register(add_numbers)
    specialist_model = DelegatedSkillModel()
    specialist_runtime = Runtime(
        model=specialist_model,
        tools=specialist_tools,
        skills=_build_skill_registry(tmp_path),
        policy=create_reasoning_framework("react"),
        config=RuntimeConfig.agent(context_policy=_tool_visible_context_policy()),
    )
    specialist = Agent(runtime=specialist_runtime)

    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist for finance tasks",
            tags=["plan", "finance"],
            capabilities=[AgentCapability.PLAN, AgentCapability.TOOL_USE],
            allowed_knowledge_scopes=["finance"],
        ),
        specialist,
    )

    runtime = Runtime(
        model=AggregatorEchoModel(),
        agent_registry=registry,
        supervisor=Supervisor(registry=registry),
        config=RuntimeConfig(default_knowledge_scope=["finance"]),
    )

    result = await Agent(runtime=runtime).run("Need a finance total for the plan.", thread_id="delegated-skill-thread")

    assert "[planner] Specialist completed:" in result.output_text
    assert any("Skill Instructions:" in prompt for prompt in specialist_model.system_prompts)
    assert any("add_numbers" in prompt for prompt in specialist_model.system_prompts)


def test_workflow_runs_default_tool_bundle_end_to_end(tmp_path: Path):
    asyncio.run(_test_workflow_runs_default_tool_bundle_end_to_end(tmp_path))


async def _test_workflow_runs_default_tool_bundle_end_to_end(tmp_path: Path):
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[tmp_path],
            command_allowlist=["echo"],
            timeout=10.0,
        )
    )
    registry = ToolRegistry()
    register_default_agent_tools(registry, workspace_root=tmp_path, sandbox=sandbox)

    runtime = Runtime(model=AggregatorEchoModel(), tools=registry)
    workflow = Workflow(
        entry_node="mkdir",
        nodes=[
            Node(id="mkdir", kind="tool", config={"tool_name": "make_directory", "arguments": {"path": "logs"}}),
            Node(id="write", kind="tool", config={"tool_name": "write_file", "arguments": {"path": "logs/run.txt", "content": "workflow-ok"}}),
            Node(id="read", kind="tool", config={"tool_name": "read_file", "arguments": {"path": "logs/run.txt"}}),
            Node(id="cmd", kind="tool", config={"tool_name": "run_command", "arguments": {"command": "echo workflow-bundle", "workdir": str(tmp_path)}}),
        ],
        edges=[
            Edge(source="mkdir", target="write", kind="success"),
            Edge(source="write", target="read", kind="success"),
            Edge(source="read", target="cmd", kind="success"),
        ],
    )

    result = await Agent(runtime=runtime, workflow=workflow).run("unused", thread_id="workflow-bundles")

    assert (tmp_path / "logs" / "run.txt").read_text(encoding="utf-8") == "workflow-ok"
    assert "workflow-bundle" in result.output_text


def test_deep_research_agent_preset_builds_research_ready_runtime():
    asyncio.run(_test_deep_research_agent_preset_builds_research_ready_runtime())


async def _test_deep_research_agent_preset_builds_research_ready_runtime():
    model = DeepResearchEchoModel()
    skill_dir = Path.cwd() / ".tmp-deep-research-skill-test"
    skill_dir.mkdir(exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: deep_research_protocol\n"
            "description: Research guidance\n"
            "triggers: research,evidence\n"
            "allowed_tools: brave_search,deliberative_retrieve\n"
            "---\n"
            "Always gather evidence before concluding and cite uncertainty explicitly."
        ),
        encoding="utf-8",
    )
    skills = SkillRegistry()
    skills.register(SkillLoader().load(skill_dir))

    agent = await DeepResearchAgent.acreate(
        model=model,
        knowledge_documents=[
            Document(
                id="research-1",
                text="Deep research agents should collect evidence and cite it clearly.",
                metadata={"scopes": ["research"]},
            )
        ],
        skills=skills,
        config={"knowledge_scope": ["research"], "include_web_search": True},
    )

    assert "brave_search" in agent.runtime.tools
    assert "deliberative_retrieve" in agent.runtime.tools
    assert agent.runtime.reasoning_framework.config.kind.value == "plan_execute"
    assert agent.runtime.config.rag_strategy is not None
    assert agent.runtime.config.rag_strategy.mode == "hybrid"

    result = await agent.run("Research how evidence quality should be handled.", thread_id="deep-research-test")
    assert "deep research agent" in result.output_text.lower()
    assert any("Skill Instructions:" in prompt for prompt in model.system_prompts)


@tool(description="Return a custom signal for testing.")
async def custom_signal(input: CustomSignalInput):
    return {"query": input.query, "result": "custom"}


def test_deep_research_agent_accepts_web_search_config_and_custom_tools():
    asyncio.run(_test_deep_research_agent_accepts_web_search_config_and_custom_tools())


async def _test_deep_research_agent_accepts_web_search_config_and_custom_tools():
    model = DeepResearchEchoModel()
    agent = await DeepResearchAgent.acreate(
        model=model,
        knowledge_documents=[
            Document(
                id="research-1",
                text="Deep research agents should collect evidence and cite it clearly.",
                metadata={"scopes": ["research"]},
            )
        ],
        custom_tools=[custom_signal],
        config={
            "knowledge_scope": ["research"],
            "web_search": {"provider": "brave", "enabled": True, "api_key": "test-key"},
        },
    )

    assert "brave_search" in agent.runtime.tools
    assert "custom_signal" in agent.runtime.tools


def test_deep_research_config_exposes_policy_overrides():
    config = DeepResearchAgentConfig(
        coordination_policy=CoordinationPolicy.distributed(),
    )
    runtime_config = config.runtime_config()
    assert runtime_config.coordination_policy is not None
    assert runtime_config.coordination_policy.route_mode == "distributed"
