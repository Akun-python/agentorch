from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .dsl import StudioAppType, StudioEdgeKind, StudioExportTarget, StudioNodeKind


class StudioCompileIssue(BaseModel):
    severity: Literal["error", "warning"] = "error"
    code: str
    message: str
    location: str | None = None


class StudioRoleIR(BaseModel):
    name: str
    role: str
    description: str | None = None
    node_id: str
    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    knowledge_scope: list[str] = Field(default_factory=list)
    tool_bindings: list[str] = Field(default_factory=list)
    model_binding: str | None = None


class StudioNodeIR(BaseModel):
    id: str
    studio_kind: StudioNodeKind
    runtime_kind: str | None = None
    name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudioEdgeIR(BaseModel):
    source: str
    target: str
    kind: StudioEdgeKind = "success"
    condition: str | None = None
    field_mapping: dict[str, Any] = Field(default_factory=dict)


class StudioAppIR(BaseModel):
    schema_version: str = "v1"
    app_type: StudioAppType
    execution_target: Literal["agent_design", "team_design", "workflow_runtime"]
    meta: dict[str, Any] = Field(default_factory=dict)
    entry_node: str | None = None
    nodes: list[StudioNodeIR] = Field(default_factory=list)
    edges: list[StudioEdgeIR] = Field(default_factory=list)
    roles: list[StudioRoleIR] = Field(default_factory=list)
    bindings: dict[str, Any] = Field(default_factory=dict)
    export_target: StudioExportTarget = "python_project"
    runtime: dict[str, Any] = Field(default_factory=dict)
    blueprint: dict[str, Any] = Field(default_factory=dict)
