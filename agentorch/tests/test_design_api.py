from __future__ import annotations

import agentorch
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.extensions import RuntimeExtension
from agentorch.models.base import BaseModelAdapter
from agentorch.strategies import CoordinationPolicy


class DummyModel(BaseModelAdapter):
    def __init__(self, *, name: str = "dummy-design-model", reply: str = "ok") -> None:
        self.config = {"api_key": "sk-dummy-design-1234567890", "model": name}
        self.reply = reply

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content=self.reply),
            content=self.reply,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=4),
        )


class RecordingExtension(RuntimeExtension):
    def __init__(self) -> None:
        self.events: list[str] = []

    async def before_run(self, context) -> None:
        self.events.append("before_run")

    async def after_run(self, context) -> None:
        self.events.append("after_run")

    async def before_supervisor_plan(self, context) -> None:
        self.events.append("before_supervisor_plan")

    async def before_handoff(self, context) -> None:
        self.events.append("before_handoff")


def test_agent_design_chainable_helpers_build_agent_cleanly() -> None:
    extension = RecordingExtension()
    design = (
        agentorch.AgentDesign.named("researcher", model=DummyModel(reply="ready"), profile="research")
        .with_reasoning("react")
        .with_tool_bundles(include_filesystem=True, include_git=True)
        .with_rag(scope=["papers"], max_steps=2)
        .with_extensions(extension)
    )

    agent = design.build()
    blueprint = agent.export_blueprint()

    assert blueprint["name"] == "researcher"
    assert blueprint["runtime"]["extensions"] == ["RecordingExtension"]
    assert agent.runtime.config.enable_retrieval is True
    assert agent.runtime.config.default_knowledge_scope == ["papers"]
    assert "read_file" in blueprint["runtime"]["tools"]
    agent.close()


def test_team_design_role_defaults_reduce_repeated_role_configuration() -> None:
    base_role = agentorch.AgentDesign(profile="coding").with_tool_bundles(include_filesystem=True, include_git=True)
    team_design = (
        agentorch.TeamDesign(
            name="delivery-team",
            role_defaults=base_role,
            coordination_policy=CoordinationPolicy.distributed(),
        )
        .add_role(
            "planner",
            description="Planning lead",
            design={"model": DummyModel(name="planner-model", reply="plan ready")},
            capabilities=["plan"],
            supports_parallel_tasks=True,
        )
        .add_role(
            "reviewer",
            description="Review lead",
            design={"model": DummyModel(name="review-model", reply="review ready")},
            capabilities=["review"],
            supports_parallel_tasks=True,
            knowledge_scope=["engineering"],
        )
    )

    system = team_design.build()
    blueprint = system.export_blueprint()

    assert blueprint["kind"] == "multi_agent"
    assert [member["name"] for member in blueprint["members"]] == ["planner", "reviewer"]
    assert system.runtime.coordinator.execution_policy.allow_parallel is True
    assert "read_file" in blueprint["members"][0]["agent_blueprint"]["runtime"]["tools"]
    assert "read_file" in blueprint["members"][1]["agent_blueprint"]["runtime"]["tools"]
    assert blueprint["members"][1]["knowledge_scope"] == ["engineering"]
    system.close()


def test_compose_helpers_accept_plain_dict_designs() -> None:
    extension = RecordingExtension()

    agent = agentorch.compose_agent(
        {
            "name": "dict-agent",
            "model": DummyModel(reply="dict-ready"),
            "extensions": [extension],
        }
    )
    result = agent.run_sync("hello", thread_id="dict-agent")
    assert result.output_text == "dict-ready"
    assert extension.events == ["before_run", "after_run"]
    agent.close()

    extension.events.clear()
    team = agentorch.compose_team(
        {
            "name": "dict-team",
            "coordination_policy": CoordinationPolicy.distributed(),
            "extensions": [extension],
            "role_defaults": {
                "profile": "workflow",
                "tool_bundles": {"include_filesystem": True},
            },
            "roles": [
                {
                    "name": "planner",
                    "design": {"model": DummyModel(name="dict-team-model", reply="team-ready")},
                    "capabilities": ["plan"],
                    "supports_parallel_tasks": True,
                }
            ],
        }
    )

    team_result = team.run_sync("plan the task", thread_id="dict-team")

    assert "team-ready" in team_result.output_text
    assert "before_supervisor_plan" in extension.events
    assert "before_handoff" in extension.events
    team.close()


def test_design_helper_methods_cover_overlay_runtime_config_and_team_payload_paths() -> None:
    base = agentorch.AgentDesign.named("base-agent", model=DummyModel(reply="base"))
    overlay = base.overlay(
        {
            "description": "overlay description",
            "tool_bundles": {"include_filesystem": True},
        }
    ).with_runtime_config({"max_steps": 5}, enable_parallel_tasks=True)

    kwargs = overlay.as_create_kwargs()
    assert kwargs["description"] == "overlay description"
    assert kwargs["tool_bundles"]["include_filesystem"] is True
    assert kwargs["runtime_config"].max_steps == 5
    assert kwargs["runtime_config"].enable_parallel_tasks is True

    external_agent = agentorch.create_agent(model=DummyModel(reply="external"), name="external-worker")
    role_payload = agentorch.RoleDesign.from_any(
        {
            "name": "existing-role",
            "agent": external_agent,
            "tags": ["existing"],
            "supports_parallel_tasks": True,
        }
    ).as_role_payload()

    team_design = agentorch.TeamDesign(name="mixed-team").with_role_defaults(
        {"profile": "workflow", "tool_bundles": {"include_filesystem": True}}
    ).add_agent(external_agent)

    team_kwargs = team_design.as_create_kwargs()

    assert role_payload["agent"] is external_agent
    assert role_payload["tags"] == ["existing"]
    assert team_kwargs["agents"] == [external_agent]
    assert team_kwargs["name"] == "mixed-team"

    external_agent.close()
