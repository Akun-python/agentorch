import asyncio

from pydantic import BaseModel

from agentorch import (
    AgentCapability,
    HumanFeedbackManager,
    Workflow,
    create_agent,
    create_multi_agent,
    tool,
)
from agentorch.core import Message, ModelRequest, ModelResponse, ToolCall, UsageInfo
from agentorch.knowledge import RagStrategyConfig
from agentorch.models.base import BaseModelAdapter
from agentorch.workflow import Node


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        last_user = [message for message in request.messages if message.role == "user"][-1]
        return ModelResponse(
            message=Message(role="assistant", content=f"handled: {last_user.content}"),
            content=f"handled: {last_user.content}",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class ToolCallingModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        latest_tool = next((message for message in reversed(request.messages) if message.role == "tool"), None)
        if latest_tool is not None:
            return ModelResponse(
                message=Message(role="assistant", content=f"tool-finished: {latest_tool.content}"),
                content=f"tool-finished: {latest_tool.content}",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )
        tool_call = ToolCall(id="call-1", name="add_numbers", arguments={"a": 2, "b": 3})
        return ModelResponse(
            message=Message(role="assistant", content="", tool_calls=[tool_call]),
            content="",
            tool_calls=[tool_call],
            finish_reason="tool_calls",
            usage=UsageInfo(total_tokens=1),
        )


class AddInput(BaseModel):
    a: int
    b: int


@tool(description="Add two integers together.")
async def add_numbers(input: AddInput):
    return {"sum": input.a + input.b}


def test_create_agent_minimal_smoke_and_exports():
    agent = create_agent(
        model=EchoModel(),
        system_prompt="You are concise.",
        name="solo",
        description="Single agent facade",
    )

    result = agent.run_sync("hello", thread_id="facade-minimal")

    assert result.output_text == "handled: hello"
    assert agent.export_blueprint()["facade"] == "create_agent"
    assert agent.export_blueprint()["name"] == "solo"
    assert agent.export_config()["runtime"]["system_prompt"] == "You are concise."
    assert agent.export_core_assembly()["runtime_constructor"] == "Runtime.create(...)"
    assert "facade=create_agent" in agent.describe()


def test_create_agent_supports_tools_rag_workflow_and_feedback():
    manager = HumanFeedbackManager()
    tool_agent = create_agent(
        model=ToolCallingModel(),
        tools=[add_numbers],
        enable_rag=True,
        rag=RagStrategyConfig.for_hybrid(knowledge_scope=["docs"]),
        knowledge_scope=["docs"],
        enable_streaming=True,
        name="tool-agent",
    )
    workflow = Workflow(
        entry_node="ask",
        nodes=[Node(id="ask", kind="human_input", config={"title": "Need input", "message": "Please choose"})],
        edges=[],
    )
    feedback_agent = create_agent(
        model=EchoModel(),
        workflow=workflow,
        human_feedback=manager,
        name="feedback-agent",
    )

    tool_result = tool_agent.run_sync("please calculate", thread_id="facade-tool")
    feedback_result = feedback_agent.run_sync("start approval", thread_id="facade-hitl")

    blueprint = tool_agent.inspect()
    assert "tool-finished" in tool_result.output_text
    assert blueprint["runtime"]["tools"] == ["add_numbers"]
    assert blueprint["runtime"]["config"]["enable_retrieval"] is True
    assert feedback_agent.export_blueprint()["workflow"]["nodes"][0]["kind"] == "human_input"
    assert feedback_result.status == "waiting_human"
    assert feedback_result.feedback_id is not None


def test_create_agent_profile_and_runtime_config_precedence():
    agent = create_agent(
        model=EchoModel(),
        profile="research",
        runtime_config={"system_prompt": "Pinned by runtime config."},
        name="researcher",
    )
    coding_agent = create_agent(
        model=EchoModel(),
        profile="coding",
        sandbox=None,
        name="coder",
    )

    research_blueprint = agent.export_blueprint()
    coding_blueprint = coding_agent.export_blueprint()

    assert research_blueprint["profile"] == "research"
    assert research_blueprint["runtime"]["config"]["system_prompt"] == "Pinned by runtime config."
    assert research_blueprint["resolved_defaults"]["enable_rag"] is True
    assert research_blueprint["runtime"]["resolved_strategies"]["context"]["kind"] == "compact"
    assert research_blueprint["runtime"]["resolved_strategies"]["context"]["include_retrieval_evidence"] is True
    assert coding_blueprint["resolved_defaults"]["tool_bundles"]["include_git"] is True
    assert "replace_in_file" in coding_blueprint["runtime"]["tools"]
    assert coding_blueprint["runtime"]["config"]["orchestration_profile"] == "coding_agent"
    assert coding_blueprint["runtime"]["resolved_strategies"]["context"]["kind"] == "compact"
    assert coding_blueprint["runtime"]["resolved_strategies"]["context"]["tool_result_policy"] == "truncate"
    assert coding_blueprint["runtime"]["resolved_strategies"]["context"]["tool_result_max_chars"] == 320
    assert coding_blueprint["runtime"]["resolved_strategies"]["context"]["budget_aware_compaction"] is True
    assert coding_blueprint["runtime"]["resolved_strategies"]["context"]["max_conversation_messages"] == 4
    assert coding_blueprint["runtime"]["resolved_strategies"]["long_horizon"]["kind"] == "state_centric"
    assert coding_blueprint["runtime"]["resolved_strategies"]["memory_governance"]["kind"] == "mgcm"


def test_create_multi_agent_accepts_inline_blueprints_and_existing_agents():
    planner = create_agent(
        model=EchoModel(),
        system_prompt="You are a planner.",
        name="planner",
    )
    orchestrator = create_multi_agent(
        model=EchoModel(),
        agents=[
            {
                "agent": planner,
                "name": "planner",
                "role": "planner",
                "description": "Planning specialist",
                "capabilities": [AgentCapability.PLAN],
                "knowledge_scope": ["planning"],
            },
            {
                "name": "reviewer",
                "role": "reviewer",
                "description": "Review specialist",
                "capabilities": [AgentCapability.REVIEW],
                "system_prompt": "You review plans carefully.",
                "model": EchoModel(),
                "knowledge_scope": ["planning"],
            },
        ],
        system_prompt="You supervise the specialist team.",
        topology="supervisor",
    )

    result = orchestrator.run_sync("plan the project", thread_id="facade-multi")

    blueprint = orchestrator.export_blueprint()
    assert "[planner] handled: plan the project" in result.output_text
    assert blueprint["facade"] == "create_multi_agent"
    assert blueprint["topology"] == "supervisor"
    assert [member["name"] for member in blueprint["members"]] == ["planner", "reviewer"]
    assert orchestrator.export_core_assembly()["supervisor_constructor"] == "Supervisor(registry=...)"
    assert "planner" in orchestrator.describe()
