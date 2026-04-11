from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from .types import AgentCapability, AgentPolicyProfile


class AgentSpec(BaseModel):
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[AgentCapability] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_knowledge_scopes: list[str] = Field(default_factory=list)
    max_delegation_depth: int = 1
    supports_parallel_tasks: bool = False
    policy_profile: AgentPolicyProfile = Field(default_factory=AgentPolicyProfile)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def assistant(
        cls,
        name: str,
        *,
        description: str | None = None,
        tags: list[str] | None = None,
        capabilities: list[AgentCapability | str] | None = None,
        tools: list[str] | None = None,
        knowledge_scopes: list[str] | None = None,
        default_rag_strategy: Any | None = None,
        default_context_strategy: Any | None = None,
        default_long_horizon_strategy: Any | None = None,
        default_cooperation_strategy: Any | None = None,
        preferred_reasoning_kind: str | None = None,
        **kwargs: Any,
    ) -> "AgentSpec":
        normalized_capabilities = [
            item if isinstance(item, AgentCapability) else AgentCapability(item)
            for item in (capabilities or [])
        ]
        profile = kwargs.pop("policy_profile", AgentPolicyProfile())
        if default_rag_strategy is not None:
            from agentorch.knowledge import RagStrategyConfig

            profile = profile.model_copy(update={"default_rag_strategy": RagStrategyConfig.from_any(default_rag_strategy)})
        if default_context_strategy is not None:
            from agentorch.strategies import ContextStrategyConfig

            profile = profile.model_copy(update={"default_context_strategy": ContextStrategyConfig.from_any(default_context_strategy)})
        if default_long_horizon_strategy is not None:
            from agentorch.strategies import LongHorizonStrategyConfig

            profile = profile.model_copy(update={"default_long_horizon_strategy": LongHorizonStrategyConfig.from_any(default_long_horizon_strategy)})
        if default_cooperation_strategy is not None:
            from agentorch.strategies import CooperationStrategyConfig

            profile = profile.model_copy(update={"default_cooperation_strategy": CooperationStrategyConfig.from_any(default_cooperation_strategy)})
        if preferred_reasoning_kind is not None:
            profile = profile.model_copy(update={"preferred_reasoning_kind": preferred_reasoning_kind})
        return cls(
            name=name,
            description=description or f"{name} assistant",
            tags=list(tags or []),
            capabilities=normalized_capabilities,
            allowed_tools=list(tools or []),
            allowed_knowledge_scopes=list(knowledge_scopes or []),
            policy_profile=profile,
            **kwargs,
        )


@dataclass
class RegisteredAgent:
    spec: AgentSpec
    agent: Any


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, RegisteredAgent] = {}

    def register(self, spec: AgentSpec, agent: Any) -> None:
        if spec.name in self._agents:
            raise ValueError(f"Agent '{spec.name}' is already registered.")
        self._agents[spec.name] = RegisteredAgent(spec=spec, agent=agent)

    def get(self, name: str) -> RegisteredAgent:
        if name not in self._agents:
            raise KeyError(f"Unknown agent: {name}")
        return self._agents[name]

    def list_specs(self) -> list[AgentSpec]:
        return [entry.spec for entry in self._agents.values()]

    def find_by_tags(self, tags: list[str]) -> list[RegisteredAgent]:
        wanted = set(tags)
        return [entry for entry in self._agents.values() if wanted.intersection(entry.spec.tags)]

    def find_by_capabilities(self, capabilities: list[AgentCapability]) -> list[RegisteredAgent]:
        wanted = set(capabilities)
        return [entry for entry in self._agents.values() if wanted.intersection(entry.spec.capabilities)]

    def find_by_knowledge_scope(self, scopes: list[str]) -> list[RegisteredAgent]:
        wanted = set(scopes)
        return [entry for entry in self._agents.values() if wanted.intersection(entry.spec.allowed_knowledge_scopes)]
