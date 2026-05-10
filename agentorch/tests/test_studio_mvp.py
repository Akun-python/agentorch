from __future__ import annotations

import json

from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.studio import (
    StudioBindingResolver,
    StudioDslDocument,
    StudioService,
    compile_studio_dsl,
    export_studio_artifact,
)


class DummyModel(BaseModelAdapter):
    def __init__(self, *, name: str = "dummy-studio-model", reply: str = "studio-ok") -> None:
        self.config = {"api_key": "sk-dummy-studio-1234567890", "model": name}
        self.reply = reply

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content=self.reply),
            content=self.reply,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=3),
        )


def test_studio_agent_compile_and_run_with_resolved_model() -> None:
    dsl = StudioDslDocument.model_validate(
        {
            "app_type": "agent",
            "meta": {"name": "single-agent"},
            "canvas": {
                "nodes": [
                    {"id": "start", "kind": "start"},
                    {
                        "id": "assistant",
                        "kind": "llm_agent",
                        "name": "assistant",
                        "config": {
                            "model_binding": "default_model",
                            "system_prompt": "You are concise.",
                        },
                    },
                    {"id": "end", "kind": "end"},
                ],
                "edges": [
                    {"source": "start", "target": "assistant"},
                    {"source": "assistant", "target": "end"},
                ],
            },
            "bindings": {
                "models": [
                    {"name": "default_model", "model": "dummy-model", "default": True},
                ]
            },
        }
    )
    compiled = compile_studio_dsl(
        dsl,
        resolver=StudioBindingResolver(models={"default_model": DummyModel(reply="agent-ready")}),
    )
    agent = compiled.build()
    try:
        result = agent.run_sync("hello", thread_id="studio-agent")
        assert result.output_text == "agent-ready"
    finally:
        agent.close()


def test_studio_team_compile_builds_multi_agent_runtime() -> None:
    dsl = StudioDslDocument.model_validate(
        {
            "app_type": "team",
            "meta": {"name": "team-app"},
            "canvas": {
                "nodes": [
                    {
                        "id": "planner",
                        "kind": "sub_agent",
                        "name": "planner",
                        "config": {
                            "agent_name": "planner",
                            "model_binding": "planner_model",
                            "description": "Planning role",
                            "capabilities": ["plan"],
                        },
                    }
                ]
            },
            "bindings": {
                "models": [
                    {"name": "planner_model", "model": "dummy-planner"},
                ]
            },
        }
    )
    compiled = compile_studio_dsl(
        dsl,
        resolver=StudioBindingResolver(models={"planner_model": DummyModel(reply="plan-complete")}),
    )
    system = compiled.build()
    try:
        result = system.run_sync("plan this task", thread_id="studio-team")
        assert "plan-complete" in result.output_text
    finally:
        system.close()


def test_studio_workflow_with_sub_agent_runs_end_to_end() -> None:
    dsl = StudioDslDocument.model_validate(
        {
            "app_type": "workflow",
            "meta": {"name": "workflow-app"},
            "canvas": {
                "nodes": [
                    {"id": "start", "kind": "start"},
                    {
                        "id": "researcher",
                        "kind": "sub_agent",
                        "name": "researcher",
                        "config": {
                            "agent_name": "researcher",
                            "model_binding": "worker_model",
                            "goal": "Research the topic",
                            "description": "Research role",
                            "output_key": "research_payload",
                        },
                    },
                    {
                        "id": "aggregate",
                        "kind": "aggregate",
                        "config": {
                            "sources": ["researcher"],
                            "output_key": "summary_payload",
                        },
                    },
                    {"id": "end", "kind": "end"},
                ],
                "edges": [
                    {"source": "start", "target": "researcher"},
                    {"source": "researcher", "target": "aggregate"},
                    {"source": "aggregate", "target": "end"},
                ],
            },
            "bindings": {
                "models": [
                    {"name": "worker_model", "model": "dummy-worker"},
                ]
            },
            "runtime": {"debug": {"max_steps": 8}},
        }
    )
    compiled = compile_studio_dsl(
        dsl,
        resolver=StudioBindingResolver(models={"worker_model": DummyModel(reply="research-complete")}),
    )
    agent = compiled.build()
    try:
        result = agent.run_sync("collect findings", thread_id="studio-workflow")
        payload = json.loads(result.output_text)
        assert payload["status"] == "completed"
        assert "research-complete" in payload["summary"]
    finally:
        agent.close()


def test_studio_python_export_contains_core_files() -> None:
    dsl = StudioDslDocument.model_validate(
        {
            "app_type": "agent",
            "meta": {"name": "exported-agent", "slug": "exported-agent"},
            "canvas": {
                "nodes": [
                    {"id": "start", "kind": "start"},
                    {"id": "assistant", "kind": "llm_agent", "config": {"model_binding": "default_model"}},
                    {"id": "end", "kind": "end"},
                ],
                "edges": [
                    {"source": "start", "target": "assistant"},
                    {"source": "assistant", "target": "end"},
                ],
            },
            "bindings": {
                "models": [{"name": "default_model", "model": "gpt-4.1-mini", "default": True}],
            },
        }
    )
    artifact = export_studio_artifact(dsl, target="python_project")
    assert artifact.target == "python_project"
    assert "app/main.py" in artifact.files
    assert "app/diamond.py" in artifact.files
    assert "app/agents/main_agent.py" in artifact.files
    assert "configs/app.json" in artifact.files
    assert "app/studio_dsl.json" in artifact.files
    assert "tests/test_smoke.py" in artifact.files
    assert "AgentDesign(" in artifact.files["app/agents/main_agent.py"]


def test_studio_sdk_export_uses_framework_builder_entry() -> None:
    dsl = StudioDslDocument.model_validate(
        {
            "app_type": "agent",
            "canvas": {
                "nodes": [
                    {"id": "start", "kind": "start"},
                    {"id": "assistant", "kind": "llm_agent"},
                    {"id": "end", "kind": "end"},
                ],
                "edges": [
                    {"source": "start", "target": "assistant"},
                    {"source": "assistant", "target": "end"},
                ],
            },
        }
    )
    artifact = export_studio_artifact(dsl, target="sdk_snippet")
    assert "build_agent" in artifact.files["studio_sdk.py"]


def test_studio_workflow_export_contains_python_diamond_runtime() -> None:
    dsl = StudioDslDocument.model_validate(
        {
            "app_type": "workflow",
            "meta": {"name": "workflow-export", "slug": "workflow-export"},
            "canvas": {
                "nodes": [
                    {"id": "start", "kind": "start"},
                    {
                        "id": "assistant",
                        "kind": "llm_agent",
                        "config": {
                            "model_binding": "default_model",
                            "output_key": "assistant_output",
                        },
                    },
                    {"id": "end", "kind": "end"},
                ],
                "edges": [
                    {"source": "start", "target": "assistant"},
                    {"source": "assistant", "target": "end"},
                ],
            },
            "bindings": {
                "models": [{"name": "default_model", "model": "gpt-4.1-mini", "default": True}],
            },
            "runtime": {"debug": {"max_steps": 6}},
        }
    )
    artifact = export_studio_artifact(dsl, target="python_project")
    assert "app/workflows/main_workflow.py" in artifact.files
    assert "StudioWorkflowRuntimePlan" in artifact.files["app/workflows/main_workflow.py"]
    assert "build_diamond" in artifact.files["app/diamond.py"]


def test_studio_service_validate_surfaces_errors() -> None:
    service = StudioService()
    issues = service.validate(
        {
            "app_type": "workflow",
            "canvas": {
                "nodes": [{"id": "start", "kind": "start"}],
                "edges": [],
            },
        }
    )
    assert any(issue.code == "workflow_requires_single_end" for issue in issues)
