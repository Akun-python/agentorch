from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentorch.agents import AggregationPolicy, AgentCapability, Supervisor, SupervisorPolicy
from agentorch.config import ObservabilityConfig, RuntimeConfig
from agentorch.extensions import RuntimeExtension
from agentorch.knowledge import KnowledgeBase, RagStrategyConfig
from agentorch.memory import MemoryManager
from agentorch.reasoning import ReasoningStrategyConfig
from agentorch.runtime import Agent, Runtime
from agentorch.sandbox import SandboxManager
from agentorch.skills import SkillRegistry
from agentorch.strategies import (
    ContextPolicy,
    ContextSelector,
    CoordinationPolicy,
    MemoryEvaluator,
    MemoryPolicy,
    RoutePlanner,
    StatePolicy,
)
from agentorch.tools import BaseTool, ToolRegistry
from agentorch.workflow import Workflow


def _compact_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


class AgentDesign(BaseModel):
    """Declarative single-agent assembly spec.

    Developers can build and clone this object cheaply, then hand it to
    `build()` or `compose_agent(...)` without having to remember the full
    `create_agent(...)` surface every time.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: Any = None
    profile: str = "default"
    system_prompt: str | None = None
    name: str | None = None
    description: str | None = None
    enable_tools: bool | None = None
    tools: ToolRegistry | list[BaseTool] | tuple[BaseTool, ...] | None = None
    tool_bundles: bool | dict[str, Any] | None = None
    workspace_root: str | Path | None = None
    enable_rag: bool | None = None
    knowledge_base: KnowledgeBase | None = None
    knowledge_paths: list[str | Path] | None = None
    rag: RagStrategyConfig | str | dict[str, Any] | None = None
    knowledge_scope: list[str] | None = None
    enable_memory: bool | None = None
    memory: MemoryManager | None = None
    workflow: Workflow | None = None
    reasoning: ReasoningStrategyConfig | str | dict[str, Any] | None = None
    reasoning_framework: ReasoningStrategyConfig | str | dict[str, Any] | None = None
    sandbox: SandboxManager | None = None
    enable_streaming: bool | None = None
    human_feedback: Any | None = None
    observability: ObservabilityConfig | dict[str, Any] | None = None
    extensions: list[RuntimeExtension] | tuple[RuntimeExtension, ...] | None = None
    skills: SkillRegistry | None = None
    context_policy: ContextPolicy | dict[str, Any] | None = None
    state_policy: StatePolicy | dict[str, Any] | None = None
    coordination_policy: CoordinationPolicy | dict[str, Any] | None = None
    memory_policy: MemoryPolicy | dict[str, Any] | None = None
    context_selector: ContextSelector | None = None
    route_planner: RoutePlanner | None = None
    memory_evaluator: MemoryEvaluator | None = None
    runtime: Runtime | None = None
    runtime_config: RuntimeConfig | dict[str, Any] | None = None
    overrides: dict[str, Any] | None = None

    @classmethod
    def from_any(cls, value: "AgentDesign | dict[str, Any] | None", **overrides: Any) -> "AgentDesign":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        if overrides:
            return base.model_copy(update=overrides)
        return base

    @classmethod
    def named(
        cls,
        name: str,
        *,
        model: Any = None,
        profile: str = "default",
        description: str | None = None,
    ) -> "AgentDesign":
        return cls(name=name, model=model, profile=profile, description=description)

    def overlay(self, other: "AgentDesign | dict[str, Any] | None") -> "AgentDesign":
        incoming = AgentDesign.from_any(other)
        payload = incoming.model_dump(exclude_unset=True, round_trip=True)
        updated = self.model_copy(deep=True)
        for field_name, value in payload.items():
            if field_name == "runtime_config":
                current = getattr(updated, field_name)
                current_runtime = RuntimeConfig.from_any(current) if current is not None else RuntimeConfig()
                incoming_runtime = RuntimeConfig.from_any(value) if value is not None else RuntimeConfig()
                value = current_runtime.model_copy(
                    update=incoming_runtime.model_dump(exclude_unset=True, round_trip=True)
                )
            elif field_name == "overrides":
                current = getattr(updated, field_name)
                if isinstance(current, dict) and isinstance(value, dict):
                    value = {**current, **value}
            updated = updated.model_copy(update={field_name: value})
        return updated

    def with_reasoning(
        self,
        reasoning: ReasoningStrategyConfig | str | dict[str, Any],
    ) -> "AgentDesign":
        return self.model_copy(update={"reasoning": reasoning, "reasoning_framework": None})

    def with_tool_bundles(self, **bundles: Any) -> "AgentDesign":
        if bundles:
            base = dict(self.tool_bundles) if isinstance(self.tool_bundles, dict) else {}
            payload: bool | dict[str, Any] = {**base, **bundles}
        else:
            payload = self.tool_bundles if self.tool_bundles is not None else True
        return self.model_copy(update={"enable_tools": True, "tool_bundles": payload})

    def with_rag(
        self,
        rag: RagStrategyConfig | str | dict[str, Any] | None = None,
        *,
        scope: list[str] | None = None,
        **overrides: Any,
    ) -> "AgentDesign":
        resolved = RagStrategyConfig.from_any(rag or self.rag or RagStrategyConfig.for_hybrid())
        if scope:
            resolved = resolved.with_scope(*scope)
        if overrides:
            resolved = resolved.model_copy(update=overrides)
        return self.model_copy(
            update={
                "enable_rag": True,
                "rag": resolved,
                "knowledge_scope": list(scope) if scope is not None else self.knowledge_scope,
            }
        )

    def with_runtime_config(
        self,
        runtime_config: RuntimeConfig | dict[str, Any] | None = None,
        **overrides: Any,
    ) -> "AgentDesign":
        if runtime_config is None and not overrides:
            return self.model_copy(deep=True)
        base = RuntimeConfig.from_any(self.runtime_config) if self.runtime_config is not None else RuntimeConfig()
        if runtime_config is not None:
            incoming = RuntimeConfig.from_any(runtime_config)
            base = base.model_copy(update=incoming.model_dump(exclude_unset=True, round_trip=True))
        if overrides:
            base = base.model_copy(update=overrides)
        return self.model_copy(update={"runtime_config": base})

    def with_extensions(self, *extensions: RuntimeExtension) -> "AgentDesign":
        current = list(self.extensions or [])
        for extension in extensions:
            if extension not in current:
                current.append(extension)
        return self.model_copy(update={"extensions": current})

    def as_create_kwargs(self) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "profile": self.profile,
            "system_prompt": self.system_prompt,
            "name": self.name,
            "description": self.description,
            "enable_tools": self.enable_tools,
            "tools": self.tools,
            "tool_bundles": self.tool_bundles,
            "workspace_root": self.workspace_root,
            "enable_rag": self.enable_rag,
            "knowledge_base": self.knowledge_base,
            "knowledge_paths": self.knowledge_paths,
            "rag": self.rag,
            "knowledge_scope": self.knowledge_scope,
            "enable_memory": self.enable_memory,
            "memory": self.memory,
            "workflow": self.workflow,
            "reasoning": self.reasoning,
            "reasoning_framework": self.reasoning_framework,
            "sandbox": self.sandbox,
            "enable_streaming": self.enable_streaming,
            "human_feedback": self.human_feedback,
            "observability": self.observability,
            "extensions": self.extensions,
            "skills": self.skills,
            "context_policy": self.context_policy,
            "state_policy": self.state_policy,
            "coordination_policy": self.coordination_policy,
            "memory_policy": self.memory_policy,
            "context_selector": self.context_selector,
            "route_planner": self.route_planner,
            "memory_evaluator": self.memory_evaluator,
            "runtime": self.runtime,
            "runtime_config": self.runtime_config,
            "overrides": self.overrides,
        }
        return _compact_none(payload)

    def build(self) -> Agent:
        from agentorch.facade import create_agent

        return create_agent(**self.as_create_kwargs())


class RoleDesign(BaseModel):
    """Declarative role spec for multi-agent teams."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    role: str | None = None
    description: str | None = None
    agent: Agent | None = None
    design: AgentDesign | None = None
    capabilities: list[AgentCapability | str] | None = None
    tags: list[str] = Field(default_factory=list)
    supports_parallel_tasks: bool = False
    max_delegation_depth: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)
    knowledge_scope: list[str] | None = None

    @classmethod
    def from_any(cls, value: "RoleDesign | dict[str, Any]") -> "RoleDesign":
        if isinstance(value, cls):
            return value.model_copy(deep=True)
        return cls.model_validate(value)

    @model_validator(mode="after")
    def _validate_source(self) -> "RoleDesign":
        if self.agent is not None and self.design is not None:
            raise ValueError("RoleDesign cannot define both 'agent' and 'design'.")
        return self

    def as_role_payload(self, *, default_design: AgentDesign | dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "role": self.role or self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "tags": list(self.tags),
            "supports_parallel_tasks": self.supports_parallel_tasks,
            "max_delegation_depth": self.max_delegation_depth,
            "metadata": dict(self.metadata),
        }
        if self.agent is not None:
            payload["name"] = self.name
            payload["agent"] = self.agent
            if self.knowledge_scope is not None:
                payload["knowledge_scope"] = list(self.knowledge_scope)
            return _compact_none(payload)

        resolved_design = AgentDesign.from_any(default_design).overlay(self.design)
        identity_updates: dict[str, Any] = {}
        if resolved_design.name is None:
            identity_updates["name"] = self.name
        if self.description is not None:
            identity_updates["description"] = self.description
        if self.knowledge_scope is not None:
            identity_updates["knowledge_scope"] = list(self.knowledge_scope)
        if identity_updates:
            resolved_design = resolved_design.model_copy(update=identity_updates)
        payload.update(resolved_design.as_create_kwargs())
        return _compact_none(payload)


class TeamDesign(BaseModel):
    """Declarative multi-agent assembly spec with reusable role defaults."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str | None = None
    description: str | None = None
    agents: list[Agent] = Field(default_factory=list)
    roles: list[RoleDesign] = Field(default_factory=list)
    role_defaults: AgentDesign | None = None
    model: Any = None
    system_prompt: str | None = None
    workflow: Workflow | None = None
    supervisor: Supervisor | None = None
    routing_policy: SupervisorPolicy | None = None
    topology: str | dict[str, Any] | None = None
    shared_knowledge: KnowledgeBase | dict[str, Any] | None = None
    shared_memory: MemoryManager | None = None
    reasoning: ReasoningStrategyConfig | str | dict[str, Any] | None = None
    context_policy: ContextPolicy | dict[str, Any] | None = None
    state_policy: StatePolicy | dict[str, Any] | None = None
    coordination_policy: CoordinationPolicy | dict[str, Any] | None = None
    memory_policy: MemoryPolicy | dict[str, Any] | None = None
    context_selector: ContextSelector | None = None
    route_planner: RoutePlanner | None = None
    memory_evaluator: MemoryEvaluator | None = None
    aggregation_policy: AggregationPolicy | None = None
    sandbox: SandboxManager | None = None
    human_feedback: Any | None = None
    observability: ObservabilityConfig | dict[str, Any] | None = None
    extensions: list[RuntimeExtension] | tuple[RuntimeExtension, ...] | None = None
    runtime_config: RuntimeConfig | dict[str, Any] | None = None
    overrides: dict[str, Any] | None = None

    @classmethod
    def from_any(cls, value: "TeamDesign | dict[str, Any] | None", **overrides: Any) -> "TeamDesign":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        if overrides:
            return base.model_copy(update=overrides)
        return base

    def add_role(
        self,
        name: str,
        *,
        role: str | None = None,
        description: str | None = None,
        design: AgentDesign | dict[str, Any] | None = None,
        agent: Agent | None = None,
        capabilities: list[AgentCapability | str] | None = None,
        tags: list[str] | None = None,
        supports_parallel_tasks: bool = False,
        max_delegation_depth: int = 1,
        metadata: dict[str, Any] | None = None,
        knowledge_scope: list[str] | None = None,
    ) -> "TeamDesign":
        role_design = RoleDesign(
            name=name,
            role=role,
            description=description,
            design=AgentDesign.from_any(design) if design is not None else None,
            agent=agent,
            capabilities=capabilities,
            tags=list(tags or []),
            supports_parallel_tasks=supports_parallel_tasks,
            max_delegation_depth=max_delegation_depth,
            metadata=dict(metadata or {}),
            knowledge_scope=knowledge_scope,
        )
        return self.model_copy(update={"roles": [*self.roles, role_design]})

    def add_agent(self, agent: Agent) -> "TeamDesign":
        return self.model_copy(update={"agents": [*self.agents, agent]})

    def with_role_defaults(self, defaults: AgentDesign | dict[str, Any]) -> "TeamDesign":
        return self.model_copy(update={"role_defaults": AgentDesign.from_any(defaults)})

    def with_extensions(self, *extensions: RuntimeExtension) -> "TeamDesign":
        current = list(self.extensions or [])
        for extension in extensions:
            if extension not in current:
                current.append(extension)
        return self.model_copy(update={"extensions": current})

    def as_create_kwargs(self) -> dict[str, Any]:
        default_design = AgentDesign.from_any(self.role_defaults)
        role_payloads = [role.as_role_payload(default_design=default_design) for role in self.roles]
        payload = {
            "agents": list(self.agents) or None,
            "roles": role_payloads or None,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "workflow": self.workflow,
            "supervisor": self.supervisor,
            "routing_policy": self.routing_policy,
            "topology": self.topology,
            "shared_knowledge": self.shared_knowledge,
            "shared_memory": self.shared_memory,
            "reasoning": self.reasoning,
            "context_policy": self.context_policy,
            "state_policy": self.state_policy,
            "coordination_policy": self.coordination_policy,
            "memory_policy": self.memory_policy,
            "context_selector": self.context_selector,
            "route_planner": self.route_planner,
            "memory_evaluator": self.memory_evaluator,
            "aggregation_policy": self.aggregation_policy,
            "name": self.name,
            "description": self.description,
            "sandbox": self.sandbox,
            "human_feedback": self.human_feedback,
            "observability": self.observability,
            "extensions": self.extensions,
            "runtime_config": self.runtime_config,
            "overrides": self.overrides,
        }
        return _compact_none(payload)

    def build(self) -> Agent:
        from agentorch.facade import create_multi_agent

        return create_multi_agent(**self.as_create_kwargs())


def compose_agent(design: AgentDesign | dict[str, Any]) -> Agent:
    return AgentDesign.from_any(design).build()


def compose_team(design: TeamDesign | dict[str, Any]) -> Agent:
    return TeamDesign.from_any(design).build()


__all__ = [
    "AgentDesign",
    "RoleDesign",
    "TeamDesign",
    "compose_agent",
    "compose_team",
]
