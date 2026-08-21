from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StudioAppType = Literal["agent", "team", "workflow"]
StudioNodeKind = Literal[
    "start",
    "llm_agent",
    "tool",
    "router",
    "knowledge_retrieve",
    "memory_read",
    "memory_write",
    "sub_agent",
    "aggregate",
    "human_input",
    "human_approval",
    "end",
]
StudioEdgeKind = Literal["success", "failure", "condition", "join"]
StudioExportTarget = Literal["blueprint", "python_project", "sdk_snippet"]


class StudioCanvasNode(BaseModel):
    id: str
    kind: StudioNodeKind
    name: str | None = None
    position: dict[str, float] | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudioCanvasEdge(BaseModel):
    source: str
    target: str
    kind: StudioEdgeKind = "success"
    condition: str | None = None
    field_mapping: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudioCanvasGroup(BaseModel):
    id: str
    name: str
    node_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudioCanvas(BaseModel):
    nodes: list[StudioCanvasNode] = Field(default_factory=list)
    edges: list[StudioCanvasEdge] = Field(default_factory=list)
    groups: list[StudioCanvasGroup] = Field(default_factory=list)


class StudioModelBinding(BaseModel):
    name: str
    provider: str = "openai"
    model: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    default: bool = False
    description: str | None = None

    def as_model_input(self) -> dict[str, Any] | str | None:
        payload = dict(self.config)
        if self.provider and "provider" not in payload:
            payload["provider"] = self.provider
        if self.model and "model" not in payload:
            payload["model"] = self.model
        if payload:
            return payload
        return self.model


class StudioToolBinding(BaseModel):
    name: str
    tool_name: str | None = None
    bundle: Literal["filesystem", "execution", "git", "web", "media"] | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class StudioKnowledgeBinding(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    path: str | Path | None = None
    scope: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class StudioSecretBinding(BaseModel):
    name: str
    env_var: str
    required: bool = False
    description: str | None = None


class StudioBindings(BaseModel):
    models: list[StudioModelBinding] = Field(default_factory=list)
    tools: list[StudioToolBinding] = Field(default_factory=list)
    knowledge_sources: list[StudioKnowledgeBinding] = Field(default_factory=list)
    secrets: list[StudioSecretBinding] = Field(default_factory=list)


class StudioExportConfig(BaseModel):
    target: StudioExportTarget = "python_project"
    entry_style: Literal["cli", "api"] = "cli"
    include_tests: bool = True


class StudioRuntimeSpec(BaseModel):
    mode: Literal["draft", "published"] = "draft"
    debug: dict[str, Any] = Field(default_factory=dict)
    policies: dict[str, Any] = Field(default_factory=dict)


class StudioDslDocument(BaseModel):
    schema_version: str = "v1"
    app_type: StudioAppType
    meta: dict[str, Any] = Field(default_factory=dict)
    canvas: StudioCanvas = Field(default_factory=StudioCanvas)
    bindings: StudioBindings = Field(default_factory=StudioBindings)
    export: StudioExportConfig = Field(default_factory=StudioExportConfig)
    runtime: StudioRuntimeSpec = Field(default_factory=StudioRuntimeSpec)
