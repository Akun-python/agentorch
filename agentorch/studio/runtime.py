from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentorch._facade_support import (
    coerce_model_inputs,
    coerce_tool_registry,
    materialize_shared_knowledge_base,
    normalize_tool_bundles,
    resolve_multi_agent_member,
    split_shared_knowledge_input,
)
from agentorch.agents import AgentRegistry
from agentorch.facade import _BACKGROUND_BRIDGE, create_agent
from agentorch.config import RuntimeConfig
from agentorch.core import ModelRequest, ModelResponse, UsageInfo
from agentorch.extensions import RuntimeExtension
from agentorch.knowledge import KnowledgeBase
from agentorch.models import BaseModelAdapter
from agentorch.runtime import Agent, Runtime
from agentorch.runtime._export_support import _safe_export, _workflow_summary
from agentorch.runtime.agent import _runtime_summary
from agentorch.tools import BaseTool, ToolRegistry
from agentorch.workflow import Workflow


class _StudioWorkflowPlaceholderModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.config = {"provider": "internal", "model": "studio-workflow-placeholder"}

    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise RuntimeError(
            "当前工作流根运行时没有可用模型。请为 llm_agent 节点或默认模型绑定提供模型配置。"
        )


class StudioWorkflowRuntimePlan(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str | None = None
    description: str | None = None
    workspace_root: str | Path | None = None
    model: Any = None
    model_config_input: dict[str, Any] | str | None = None
    tools: ToolRegistry | list[BaseTool] | tuple[BaseTool, ...] | None = None
    tool_bundles: bool | dict[str, Any] | None = None
    shared_knowledge: KnowledgeBase | dict[str, Any] | None = None
    shared_memory: Any = None
    workflow: Workflow
    roles: list[dict[str, Any]] = Field(default_factory=list)
    runtime_config: RuntimeConfig | dict[str, Any] | None = None
    human_feedback: Any | None = None
    extensions: list[RuntimeExtension] | tuple[RuntimeExtension, ...] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def _create_runtime_instance(self, **runtime_kwargs: Any) -> Runtime:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return Runtime.create(**runtime_kwargs)
        runtime = _BACKGROUND_BRIDGE.run(Runtime.acreate(**runtime_kwargs))
        runtime._background_managed = True
        _BACKGROUND_BRIDGE.track(runtime)
        return runtime

    def build(self) -> Agent:
        shared_knowledge_base, shared_knowledge_payload = split_shared_knowledge_input(self.shared_knowledge)
        shared_knowledge_base = materialize_shared_knowledge_base(shared_knowledge_base, shared_knowledge_payload)
        resolved_shared_knowledge: KnowledgeBase | dict[str, Any] | None = shared_knowledge_base
        if shared_knowledge_payload:
            resolved_shared_knowledge = (
                {"knowledge_base": shared_knowledge_base, **shared_knowledge_payload}
                if shared_knowledge_base is not None
                else dict(shared_knowledge_payload)
            )

        registry = AgentRegistry()
        managed_agents: list[Any] = []
        member_summaries: list[dict[str, Any]] = []
        for index, role_payload in enumerate(self.roles, start=1):
            entry = resolve_multi_agent_member(
                role_payload,
                index=index,
                create_agent_fn=create_agent,
                model=None,
                sandbox=role_payload.get("sandbox"),
                shared_memory=self.shared_memory,
                shared_knowledge=resolved_shared_knowledge,
            )
            registry.register(entry.spec, entry.agent)
            member_summaries.append(entry.summary)
            if entry.managed:
                managed_agents.append(entry.agent)

        selected_model, selected_model_config = coerce_model_inputs(self.model if self.model is not None else self.model_config_input)
        if selected_model is None and selected_model_config is None:
            selected_model = _StudioWorkflowPlaceholderModel()

        selected_tools = ToolRegistry.empty()
        selected_tools.extend(coerce_tool_registry(self.tools))
        if self.tool_bundles:
            selected_tools.extend(
                normalize_tool_bundles(
                    self.tool_bundles,
                    workspace_root=self.workspace_root or Path.cwd(),
                    sandbox=None,
                    model=selected_model,
                )
            )

        runtime = self._create_runtime_instance(
            model=selected_model,
            model_config=selected_model_config,
            tools=selected_tools,
            knowledge_base=shared_knowledge_base,
            memory=self.shared_memory,
            agent_registry=registry,
            config=RuntimeConfig.from_any(self.runtime_config),
            human_feedback=self.human_feedback,
            extensions=self.extensions,
            managed_agents=managed_agents,
            workspace_root=self.workspace_root or Path.cwd(),
        )
        agent = Agent(runtime=runtime, workflow=self.workflow)
        blueprint = {
            "facade": "studio_workflow",
            "kind": "workflow",
            "name": self.name or "studio-workflow",
            "description": self.description,
            "runtime": _runtime_summary(runtime),
            "workflow": _workflow_summary(self.workflow),
            "members": member_summaries,
            "metadata": _safe_export(self.metadata),
            "redaction_applied": not getattr(runtime.config, "unsafe_export", False),
            "resource_state": {
                "closed": getattr(runtime, "_closed", False),
                "background_managed": getattr(runtime, "_background_managed", False),
            },
        }
        return agent.bind_blueprint(blueprint)
