from __future__ import annotations

from pathlib import Path

import pytest

import agentorch
from agentorch.config import RuntimeConfig
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.tools import ToolRegistry


class DummyModel(BaseModelAdapter):
    def __init__(self, *, name: str = "dummy-model") -> None:
        self.config = {"api_key": "sk-dummy-contract-1234567890", "model": name}
        self.closed = False

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="ok"),
            content="ok",
            tool_calls=[],
            finish_reason="stop",
            usage=UsageInfo(),
        )

    async def aclose(self) -> None:
        self.closed = True


def test_create_agent_runtime_conflict_is_enforced() -> None:
    runtime = agentorch.Runtime.create(model=DummyModel())
    with pytest.raises(ValueError):
        agentorch.create_agent(runtime=runtime, system_prompt="conflict")
    runtime.close()


def test_create_agent_rejects_tool_conflict_when_tools_disabled() -> None:
    tool_registry = ToolRegistry.with_bundles(workspace_root=Path.cwd(), include_filesystem=True, include_execution=False)
    with pytest.raises(ValueError):
        agentorch.create_agent(model=DummyModel(), enable_tools=False, tools=tool_registry)


def test_create_agent_rejects_rag_conflict_when_rag_disabled() -> None:
    with pytest.raises(ValueError):
        agentorch.create_agent(model=DummyModel(), enable_rag=False, knowledge_paths=[Path.cwd() / "README.md"])


def test_create_agent_reasoning_alias_conflict_is_enforced() -> None:
    with pytest.raises(ValueError):
        agentorch.create_agent(model=DummyModel(), reasoning="react", reasoning_framework="plan_execute")


def test_runtime_config_precedence_beats_facade_defaults() -> None:
    config = RuntimeConfig(system_prompt="runtime-config-prompt")
    agent = agentorch.create_agent(model=DummyModel(), profile="coding", system_prompt="facade-prompt", runtime_config=config)

    assert agent.runtime.config.system_prompt == "runtime-config-prompt"
    agent.close()


def test_coding_profile_without_sandbox_does_not_attach_run_command() -> None:
    agent = agentorch.create_agent(model=DummyModel(), profile="coding")

    assert "run_command" not in agent.describe()
    assert "run_command" not in str(agent.export_blueprint()["runtime"]["tools"])
    agent.close()


def test_coding_profile_with_sandbox_attaches_run_command() -> None:
    sandbox = SandboxManager(policy=SandboxPolicy(allowed_paths=[Path.cwd()], command_allowlist=["powershell"], allow_shell=False))
    agent = agentorch.create_agent(model=DummyModel(), profile="coding", sandbox=sandbox)

    assert "run_command" in agent.export_blueprint()["runtime"]["tools"]
    agent.close()


def test_tool_registry_with_bundles_omits_execution_without_sandbox() -> None:
    registry = ToolRegistry.with_bundles(workspace_root=Path.cwd(), sandbox=None, include_execution=True)

    assert "run_command" not in registry


def test_create_multi_agent_inline_member_blueprints_work() -> None:
    system = agentorch.create_multi_agent(
        roles=[
            {
                "name": "planner",
                "model": DummyModel(name="planner-model"),
                "system_prompt": "Plan carefully.",
            }
        ],
        name="inline-team",
    )

    blueprint = system.export_blueprint()
    assert blueprint["kind"] == "multi_agent"
    assert blueprint["members"][0]["name"] == "planner"
    system.close()


def test_deep_research_agent_legacy_entrypoint_respects_secure_exports() -> None:
    research = agentorch.DeepResearchAgent.create(model=DummyModel(), config={"include_web_search": False})
    exported = research.export_blueprint()

    assert "sk-dummy-contract" not in str(exported)
    assert exported["kind"] == "single_agent"
    research.close()
