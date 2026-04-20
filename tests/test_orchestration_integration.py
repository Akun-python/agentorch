import asyncio
from pathlib import Path

from pydantic import BaseModel

from agentorch import (
    Agent,
    AgentCapability,
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
from agentorch.models.base import BaseModelAdapter
from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.skills import SkillRoutingConfig
from agentorch.strategies import ContextPolicy
from agentorch.tools import register_default_agent_tools
from agentorch.workflow import Edge, Node, Workflow


class SumInput(BaseModel):
    a: int
    b: int


@tool(description="Add two integers and return the sum.")
async def add_numbers(input: SumInput):
    return {"sum": input.a + input.b}


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


class ProgressiveSkillActivationModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.calls = 0
        self.system_prompts: list[str] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        system_text = next(message.content for message in request.messages if message.role == "system")
        self.system_prompts.append(system_text)
        latest_tool = next((message.content for message in reversed(request.messages) if message.role == "tool"), "")

        if self.calls == 1:
            assert "Available Skills:" in system_text
            assert "finance_helper" in system_text
            assert "When the user asks for finance totals, use add_numbers." not in system_text
            assert "load_skill" in str(request.tools)
            tool_call = ToolCall(id="load-skill-1", name="load_skill", arguments={"name": "finance_helper"})
            return ModelResponse(
                message=Message(role="assistant", content="Load the finance skill first.", tool_calls=[tool_call]),
                content="Load the finance skill first.",
                tool_calls=[tool_call],
                finish_reason="tool_calls",
                usage=UsageInfo(total_tokens=1),
            )

        if self.calls == 2:
            assert "Skill Instructions:" in system_text
            assert "When the user asks for finance totals, use add_numbers." in system_text
            assert "Loaded Skill Resources:" not in system_text
            tool_call = ToolCall(
                id="load-resource-1",
                name="load_skill_resource",
                arguments={"name": "finance_helper", "path": "references/checklist.md"},
            )
            return ModelResponse(
                message=Message(role="assistant", content="Read the finance checklist.", tool_calls=[tool_call]),
                content="Read the finance checklist.",
                tool_calls=[tool_call],
                finish_reason="tool_calls",
                usage=UsageInfo(total_tokens=1),
            )

        if self.calls == 3:
            assert "Loaded Skill Resources:" in system_text
            assert "Checklist: confirm the arithmetic tool before finalizing." in system_text
            tool_call = ToolCall(id="call-add-3", name="add_numbers", arguments={"a": 10, "b": 32})
            return ModelResponse(
                message=Message(role="assistant", content="Now use the calculator.", tool_calls=[tool_call]),
                content="Now use the calculator.",
                tool_calls=[tool_call],
                finish_reason="tool_calls",
                usage=UsageInfo(total_tokens=1),
            )

        assert latest_tool
        return ModelResponse(
            message=Message(role="assistant", content=f"Progressive result: {latest_tool}"),
            content=f"Progressive result: {latest_tool}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class DuplicateSkillLoadModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.calls = 0
        self.system_prompts: list[str] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        system_text = next(message.content for message in request.messages if message.role == "system")
        self.system_prompts.append(system_text)
        body = "When the user asks for finance totals, use add_numbers."

        if self.calls == 1:
            assert body not in system_text
            tool_call = ToolCall(id="dup-load-1", name="load_skill", arguments={"name": "finance_helper"})
            return ModelResponse(
                message=Message(role="assistant", content="Load the finance skill.", tool_calls=[tool_call]),
                content="Load the finance skill.",
                tool_calls=[tool_call],
                finish_reason="tool_calls",
                usage=UsageInfo(total_tokens=1),
            )

        assert system_text.count(body) == 1
        if self.calls == 2:
            tool_call = ToolCall(id="dup-load-2", name="load_skill", arguments={"name": "finance_helper"})
            return ModelResponse(
                message=Message(role="assistant", content="Load it again without duplication.", tool_calls=[tool_call]),
                content="Load it again without duplication.",
                tool_calls=[tool_call],
                finish_reason="tool_calls",
                usage=UsageInfo(total_tokens=1),
            )

        return ModelResponse(
            message=Message(role="assistant", content="Duplicate load handled once."),
            content="Duplicate load handled once.",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def _tool_visible_context_policy() -> ContextPolicy:
    base_sources = ContextPolicy.default().sources
    return ContextPolicy.default(sources={**base_sources, "tool_descriptions": True})


def _build_skill_registry(tmp_path: Path) -> SkillRegistry:
    skill_dir = tmp_path / "finance-skill"
    skill_dir.mkdir()
    (skill_dir / "references").mkdir()
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
    (skill_dir / "references" / "checklist.md").write_text(
        "Checklist: confirm the arithmetic tool before finalizing.",
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
        config=RuntimeConfig.agent(
            context_policy=_tool_visible_context_policy(),
            skill_routing=SkillRoutingConfig(mode="full", disclosure_level="full", selection_mode="rule"),
        ),
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
        config=RuntimeConfig.agent(
            context_policy=_tool_visible_context_policy(),
            skill_routing=SkillRoutingConfig(mode="full", disclosure_level="full", selection_mode="rule"),
        ),
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


def test_model_driven_skill_activation_and_resource_loading(tmp_path: Path):
    asyncio.run(_test_model_driven_skill_activation_and_resource_loading(tmp_path))


async def _test_model_driven_skill_activation_and_resource_loading(tmp_path: Path):
    tools = ToolRegistry()
    tools.register(add_numbers)
    model = ProgressiveSkillActivationModel()
    runtime = Runtime(
        model=model,
        tools=tools,
        skills=_build_skill_registry(tmp_path),
        policy=create_reasoning_framework("react"),
        config=RuntimeConfig.agent(context_policy=_tool_visible_context_policy()),
    )

    result = await Agent(runtime=runtime).run("Need the finance total and follow the checklist.", thread_id="progressive-skill-thread")

    assert '"sum": 42' in result.output_text
    assert [tool_result.tool_name for tool_result in result.tool_results] == ["load_skill", "load_skill_resource", "add_numbers"]
    assert any("Available Skills:" in prompt for prompt in model.system_prompts)
    assert any("Loaded Skill Resources:" in prompt for prompt in model.system_prompts)


def test_duplicate_skill_activation_does_not_duplicate_prompt_state(tmp_path: Path):
    asyncio.run(_test_duplicate_skill_activation_does_not_duplicate_prompt_state(tmp_path))


async def _test_duplicate_skill_activation_does_not_duplicate_prompt_state(tmp_path: Path):
    model = DuplicateSkillLoadModel()
    runtime = Runtime(
        model=model,
        tools=ToolRegistry(),
        skills=_build_skill_registry(tmp_path),
        policy=create_reasoning_framework("react"),
        config=RuntimeConfig.agent(context_policy=_tool_visible_context_policy()),
    )

    result = await Agent(runtime=runtime).run("Load the finance skill twice.", thread_id="duplicate-skill-thread")

    assert result.output_text == "Duplicate load handled once."
    assert [tool_result.tool_name for tool_result in result.tool_results] == ["load_skill", "load_skill"]
    assert len(result.reasoning_metadata["loaded_skills"]) == 1
    assert result.reasoning_metadata["loaded_skills"][0]["skill_name"] == "finance_helper"


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

