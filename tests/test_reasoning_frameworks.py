import asyncio

from pydantic import BaseModel

from agentorch import Agent, Runtime, create_reasoning_framework
from agentorch.core import Message, ModelRequest, ModelResponse, ToolCall, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.observability import EventBus, Tracer
from agentorch.tools import ToolRegistry, tool


class ScenarioModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        kind = request.metadata.get("reasoning_kind")
        stage = request.metadata.get("stage")
        if kind == "cot":
            return ModelResponse(
                message=Message(role="assistant", content="1. Analyze\n2. Solve\nAnswer: 42"),
                content="1. Analyze\n2. Solve\nAnswer: 42",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=3),
            )
        if kind == "react":
            if self.calls == 1:
                tool_call = ToolCall(id="tool-1", name="lookup", arguments={"query": "weather"})
                return ModelResponse(
                    message=Message(role="assistant", content="Need a tool.", tool_calls=[tool_call]),
                    content="Need a tool.",
                    tool_calls=[tool_call],
                    finish_reason="tool_calls",
                    usage=UsageInfo(total_tokens=3),
                )
            return ModelResponse(
                message=Message(role="assistant", content="The weather is sunny."),
                content="The weather is sunny.",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=3),
            )
        if kind == "plan_execute":
            if stage == "plan":
                return ModelResponse(
                    message=Message(role="assistant", content="1. Gather facts\n2. Write answer"),
                    content="1. Gather facts\n2. Write answer",
                    finish_reason="stop",
                    usage=UsageInfo(total_tokens=2),
                )
            return ModelResponse(
                message=Message(role="assistant", content=f"Executed {stage}"),
                content=f"Executed {stage}",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=2),
            )
        if kind == "tot":
            if stage == "branch_generate":
                return ModelResponse(
                    message=Message(role="assistant", content="Path A || Path B || Path C"),
                    content="Path A || Path B || Path C",
                    finish_reason="stop",
                    usage=UsageInfo(total_tokens=2),
                )
            if stage == "branch_evaluate":
                score = 9 if "A" in request.messages[-1].content else 5
                return ModelResponse(
                    message=Message(role="assistant", content=f"{score} best"),
                    content=f"{score} best",
                    finish_reason="stop",
                    usage=UsageInfo(total_tokens=1),
                )
            return ModelResponse(
                message=Message(role="assistant", content="Final from best branch"),
                content="Final from best branch",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )
        if kind == "reflexion":
            if stage == "attempt" and self.calls == 1:
                return ModelResponse(
                    message=Message(role="assistant", content="Attempt failed, retry"),
                    content="Attempt failed, retry",
                    finish_reason="stop",
                    usage=UsageInfo(total_tokens=1),
                )
            if stage == "reflection":
                return ModelResponse(
                    message=Message(role="assistant", content="Need to simplify the solution"),
                    content="Need to simplify the solution",
                    finish_reason="stop",
                    usage=UsageInfo(total_tokens=1),
                )
            return ModelResponse(
                message=Message(role="assistant", content="Recovered answer"),
                content="Recovered answer",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )
        return ModelResponse(
            message=Message(role="assistant", content="default"),
            content="default",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class LookupInput(BaseModel):
    query: str


@tool(description="Fake lookup tool")
async def lookup(input: LookupInput):
    return {"result": "sunny", "query": input.query}


def test_reasoning_factory_creates_all_frameworks():
    assert create_reasoning_framework("cot").config.kind.value == "cot"
    assert create_reasoning_framework("react").config.kind.value == "react"
    assert create_reasoning_framework("plan_execute").config.kind.value == "plan_execute"
    assert create_reasoning_framework("tot").config.kind.value == "tot"
    assert create_reasoning_framework("reflexion").config.kind.value == "reflexion"


def test_cot_reasoning_returns_trace():
    asyncio.run(_test_cot_reasoning_returns_trace())


async def _test_cot_reasoning_returns_trace():
    runtime = Runtime(model=ScenarioModel(), policy=create_reasoning_framework("cot"))
    result = await Agent(runtime=runtime).run("solve", thread_id="cot-1")
    assert "Analyze" in result.reasoning_trace
    assert result.reasoning_kind == "cot"


def test_react_reasoning_calls_tool_and_records_trace():
    asyncio.run(_test_react_reasoning_calls_tool_and_records_trace())


async def _test_react_reasoning_calls_tool_and_records_trace():
    tools = ToolRegistry()
    tools.register(lookup)
    runtime = Runtime(model=ScenarioModel(), tools=tools, policy=create_reasoning_framework("react"))
    result = await Agent(runtime=runtime).run("weather", thread_id="react-1")
    assert result.output_text == "The weather is sunny."
    assert len(result.tool_results) == 1
    assert "observation" in result.reasoning_trace.lower()


def test_plan_execute_reasoning_produces_plan_steps():
    asyncio.run(_test_plan_execute_reasoning_produces_plan_steps())


async def _test_plan_execute_reasoning_produces_plan_steps():
    runtime = Runtime(model=ScenarioModel(), policy=create_reasoning_framework("plan_execute"))
    result = await Agent(runtime=runtime).run("do work", thread_id="plan-1")
    assert result.reasoning_kind == "plan_execute"
    assert any(step["kind"] == "plan" for step in result.reasoning["steps"])


def test_tot_reasoning_generates_and_prunes_branches():
    asyncio.run(_test_tot_reasoning_generates_and_prunes_branches())


async def _test_tot_reasoning_generates_and_prunes_branches():
    runtime = Runtime(model=ScenarioModel(), policy=create_reasoning_framework("tot", branch_factor=3, top_k=1))
    result = await Agent(runtime=runtime).run("choose best", thread_id="tot-1")
    assert result.output_text == "Final from best branch"
    assert "branch_prune" in result.reasoning_trace


def test_reflexion_reasoning_reflects_and_retries():
    asyncio.run(_test_reflexion_reasoning_reflects_and_retries())


async def _test_reflexion_reasoning_reflects_and_retries():
    runtime = Runtime(model=ScenarioModel(), policy=create_reasoning_framework("reflexion", max_attempts=3))
    result = await Agent(runtime=runtime).run("recover", thread_id="reflexion-1")
    assert result.output_text == "Recovered answer"
    assert "reflection" in result.reasoning_trace


def test_reasoning_events_are_emitted():
    asyncio.run(_test_reasoning_events_are_emitted())


async def _test_reasoning_events_are_emitted():
    bus = EventBus()
    runtime = Runtime(model=ScenarioModel(), policy=create_reasoning_framework("cot"), tracer=Tracer(bus))
    await Agent(runtime=runtime).run("trace", thread_id="trace-1")
    event_types = [event["event_type"] for event in bus.events]
    assert "reasoning_started" in event_types
    assert "reasoning_step_started" in event_types
    assert "reasoning_completed" in event_types
