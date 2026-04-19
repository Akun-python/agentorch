from __future__ import annotations

import asyncio

import pytest

import agentorch
from agentorch.agents import AdaptiveTaskPlanner, AgentRegistry, AgentSpec, CapabilitySupervisorPolicy
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.extensions import RuntimeExtension
from agentorch.models.base import BaseModelAdapter
from agentorch.strategies import CoordinationPolicy


class DummyModel(BaseModelAdapter):
    def __init__(self, *, name: str = "dummy-model", reply: str = "ok") -> None:
        self.config = {"api_key": "sk-dummy-extension-1234567890", "model": name}
        self.reply = reply

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content=self.reply),
            content=self.reply,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=3),
        )


class ExplodingModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.config = {"api_key": "sk-dummy-extension-1234567890", "model": "exploding-model"}

    async def generate(self, request: ModelRequest) -> ModelResponse:  # pragma: no cover - exercised via exception path
        raise RuntimeError("boom")


class RecordingExtension(RuntimeExtension):
    def __init__(self) -> None:
        self.events: list[str] = []
        self.error_type: str | None = None

    async def before_run(self, context) -> None:
        self.events.append("before_run")
        context.metadata["extension_seen"] = True

    async def after_run(self, context) -> None:
        self.events.append("after_run")

    async def on_run_error(self, context) -> None:
        self.events.append("on_run_error")
        self.error_type = type(context.error).__name__ if context.error is not None else None

    async def before_supervisor_plan(self, context) -> None:
        self.events.append("before_supervisor_plan")

    async def before_handoff(self, context) -> None:
        self.events.append("before_handoff")

    async def after_handoff(self, context) -> None:
        self.events.append("after_handoff")


def test_runtime_extensions_wrap_single_agent_run_and_are_exported() -> None:
    extension = RecordingExtension()
    agent = agentorch.create_agent(model=DummyModel(reply="hello"), extensions=[extension])

    result = agent.run_sync("say hello", thread_id="ext-single")

    assert result.output_text == "hello"
    assert extension.events == ["before_run", "after_run"]
    assert agent.export_blueprint()["runtime"]["extensions"] == ["RecordingExtension"]
    agent.close()


def test_runtime_extensions_capture_run_errors() -> None:
    extension = RecordingExtension()
    agent = agentorch.create_agent(model=ExplodingModel(), extensions=[extension])

    with pytest.raises(RuntimeError, match="boom"):
        agent.run_sync("fail", thread_id="ext-error")

    assert extension.error_type == "RuntimeError"
    assert extension.events == ["before_run", "on_run_error"]
    agent.close()


def test_capability_supervisor_policy_prefers_matching_capability_and_scope() -> None:
    registry = AgentRegistry()
    registry.register(
        AgentSpec.assistant("coder", capabilities=["code"], knowledge_scopes=["codebase"]),
        object(),
    )
    registry.register(
        AgentSpec.assistant("retriever", capabilities=["retrieve"], knowledge_scopes=["policy"]),
        object(),
    )
    task = agentorch.TaskPacket(
        task_id="route-1",
        goal="Need policy evidence",
        context={"required_capabilities": ["retrieve"]},
        knowledge_scope=["policy"],
        metadata={"coordination_policy": {"route_mode": "guided"}},
    )

    decision = asyncio.run(CapabilitySupervisorPolicy().select_agents(task, registry))

    assert decision.selected_agents == ["retriever"]
    assert decision.scores["retriever"] > 0


def test_adaptive_task_planner_marks_parallel_for_distributed_parallel_agents() -> None:
    registry = AgentRegistry()
    registry.register(
        AgentSpec.assistant("researcher", capabilities=["retrieve"], supports_parallel_tasks=True),
        object(),
    )
    registry.register(
        AgentSpec.assistant("reviewer", capabilities=["review"], supports_parallel_tasks=True),
        object(),
    )
    task = agentorch.TaskPacket(
        task_id="plan-1",
        goal="Research and review",
        metadata={
            "coordination_policy": {"route_mode": "distributed"},
            "allow_parallel": True,
            "max_parallel_tasks": 2,
        },
    )

    plan = AdaptiveTaskPlanner().build_plan(
        task,
        ["researcher", "reviewer"],
        registry=registry,
        reason="parallel_test",
        scores={"researcher": 3.0, "reviewer": 2.0},
    )

    assert plan.metadata["execution_mode"] == "parallel"
    assert [step.depends_on for step in plan.steps] == [[], []]


def test_multi_agent_extensions_and_parallel_runtime_flags_are_wired() -> None:
    extension = RecordingExtension()
    system = agentorch.create_multi_agent(
        roles=[
            {
                "name": "planner",
                "description": "Planning specialist",
                "model": DummyModel(name="planner-model", reply="plan ready"),
                "capabilities": ["plan"],
                "supports_parallel_tasks": True,
            }
        ],
        coordination_policy=CoordinationPolicy.distributed(),
        extensions=[extension],
        name="team-ext",
    )

    result = system.run_sync("planning task", thread_id="ext-team")

    assert "plan ready" in result.output_text
    assert system.runtime.coordinator.execution_policy.allow_parallel is True
    assert system.export_blueprint()["runtime"]["extensions"] == ["RecordingExtension"]
    assert "before_supervisor_plan" in extension.events
    assert "before_handoff" in extension.events
    assert "after_handoff" in extension.events
    system.close()
