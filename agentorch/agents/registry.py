from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class AgentSpec(BaseModel):
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


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
