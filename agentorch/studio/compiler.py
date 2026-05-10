from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentorch.config import ModelConfig, RuntimeConfig
from agentorch.design import AgentDesign, RoleDesign, TeamDesign
from agentorch.knowledge import KnowledgeBase, RagStrategyConfig
from agentorch.runtime._export_support import _safe_export, _workflow_summary
from agentorch.tools import BaseTool, ToolRegistry
from agentorch.workflow import Edge, Node, Workflow

from .dsl import (
    StudioDslDocument,
    StudioKnowledgeBinding,
    StudioModelBinding,
    StudioToolBinding,
)
from .ir import StudioAppIR, StudioCompileIssue, StudioEdgeIR, StudioNodeIR, StudioRoleIR
from .runtime import StudioWorkflowRuntimePlan

_EXECUTION_BUNDLE_FLAGS = {
    "filesystem": "include_filesystem",
    "execution": "include_execution",
    "git": "include_git",
    "web": "include_web",
    "media": "include_media",
}


@dataclass
class StudioBindingResolver:
    models: dict[str, Any] | None = None
    tools: dict[str, Any] | None = None
    knowledge_sources: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None

    def model_value(self, name: str) -> Any:
        return (self.models or {}).get(name)

    def tool_value(self, name: str) -> Any:
        return (self.tools or {}).get(name)

    def knowledge_value(self, name: str) -> Any:
        return (self.knowledge_sources or {}).get(name)

    def secret_value(self, name: str) -> Any:
        return (self.secrets or {}).get(name)


class StudioCompileError(ValueError):
    def __init__(self, issues: list[StudioCompileIssue]) -> None:
        self.issues = issues
        detail = "; ".join(issue.message for issue in issues) or "Studio DSL compile failed."
        super().__init__(detail)


class StudioCompiledArtifact(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    dsl: StudioDslDocument
    ir: StudioAppIR
    issues: list[StudioCompileIssue] = Field(default_factory=list)
    design: AgentDesign | TeamDesign | None = None
    workflow_plan: StudioWorkflowRuntimePlan | None = None

    def build(self):
        if self.workflow_plan is not None:
            return self.workflow_plan.build()
        if self.design is None:
            raise RuntimeError("Compiled artifact has no executable design.")
        return self.design.build()

    def export_blueprint(self) -> dict[str, Any]:
        return self.ir.blueprint


def validate_studio_dsl(document: StudioDslDocument | dict[str, Any]) -> list[StudioCompileIssue]:
    dsl = StudioDslDocument.model_validate(document)
    issues: list[StudioCompileIssue] = []
    node_index: dict[str, Any] = {}
    for node in dsl.canvas.nodes:
        if node.id in node_index:
            issues.append(
                StudioCompileIssue(
                    code="duplicate_node_id",
                    message=f"Node id '{node.id}' is duplicated.",
                    location=f"canvas.nodes.{node.id}",
                )
            )
            continue
        node_index[node.id] = node
    for edge_index, edge in enumerate(dsl.canvas.edges):
        if edge.source not in node_index:
            issues.append(
                StudioCompileIssue(
                    code="unknown_edge_source",
                    message=f"Edge source '{edge.source}' does not exist.",
                    location=f"canvas.edges.{edge_index}.source",
                )
            )
        if edge.target not in node_index:
            issues.append(
                StudioCompileIssue(
                    code="unknown_edge_target",
                    message=f"Edge target '{edge.target}' does not exist.",
                    location=f"canvas.edges.{edge_index}.target",
                )
            )
    _validate_binding_uniqueness(dsl, issues)
    if dsl.app_type == "agent":
        _validate_agent_canvas(dsl, issues)
    elif dsl.app_type == "team":
        _validate_team_canvas(dsl, issues)
    else:
        _validate_workflow_canvas(dsl, issues, node_index)
    return issues


def compile_studio_dsl(
    document: StudioDslDocument | dict[str, Any],
    *,
    resolver: StudioBindingResolver | None = None,
) -> StudioCompiledArtifact:
    dsl = StudioDslDocument.model_validate(document)
    issues = validate_studio_dsl(dsl)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        raise StudioCompileError(errors)
    if dsl.app_type == "agent":
        return _compile_agent_dsl(dsl, issues=issues, resolver=resolver)
    if dsl.app_type == "team":
        return _compile_team_dsl(dsl, issues=issues, resolver=resolver)
    return _compile_workflow_dsl(dsl, issues=issues, resolver=resolver)


def _validate_binding_uniqueness(dsl: StudioDslDocument, issues: list[StudioCompileIssue]) -> None:
    for label, bindings in (
        ("models", dsl.bindings.models),
        ("tools", dsl.bindings.tools),
        ("knowledge_sources", dsl.bindings.knowledge_sources),
        ("secrets", dsl.bindings.secrets),
    ):
        seen: set[str] = set()
        for binding in bindings:
            name = binding.name
            if name in seen:
                issues.append(
                    StudioCompileIssue(
                        code="duplicate_binding_name",
                        message=f"{label} binding '{name}' is duplicated.",
                        location=f"bindings.{label}.{name}",
                    )
                )
            seen.add(name)


def _validate_agent_canvas(dsl: StudioDslDocument, issues: list[StudioCompileIssue]) -> None:
    llm_nodes = [node for node in dsl.canvas.nodes if node.kind == "llm_agent"]
    if len(llm_nodes) != 1:
        issues.append(
            StudioCompileIssue(
                code="agent_requires_single_llm_node",
                message="Agent app must contain exactly one llm_agent node.",
                location="canvas.nodes",
            )
        )
    invalid = [node.id for node in dsl.canvas.nodes if node.kind not in {"start", "llm_agent", "end"}]
    if invalid:
        issues.append(
            StudioCompileIssue(
                code="agent_has_unsupported_nodes",
                message=f"Agent app does not support nodes: {', '.join(invalid)}.",
                location="canvas.nodes",
            )
        )


def _validate_team_canvas(dsl: StudioDslDocument, issues: list[StudioCompileIssue]) -> None:
    role_nodes = [node for node in dsl.canvas.nodes if node.kind == "sub_agent"]
    if not role_nodes:
        issues.append(
            StudioCompileIssue(
                code="team_requires_sub_agents",
                message="Team app must contain at least one sub_agent node.",
                location="canvas.nodes",
            )
        )
    invalid = [node.id for node in dsl.canvas.nodes if node.kind not in {"start", "sub_agent", "end"}]
    if invalid:
        issues.append(
            StudioCompileIssue(
                code="team_has_unsupported_nodes",
                message=f"Team app does not support nodes: {', '.join(invalid)}.",
                location="canvas.nodes",
            )
        )


def _validate_workflow_canvas(
    dsl: StudioDslDocument,
    issues: list[StudioCompileIssue],
    node_index: dict[str, Any],
) -> None:
    start_nodes = [node for node in dsl.canvas.nodes if node.kind == "start"]
    end_nodes = [node for node in dsl.canvas.nodes if node.kind == "end"]
    if len(start_nodes) != 1:
        issues.append(
            StudioCompileIssue(
                code="workflow_requires_single_start",
                message="Workflow app must contain exactly one start node.",
                location="canvas.nodes",
            )
        )
    if len(end_nodes) != 1:
        issues.append(
            StudioCompileIssue(
                code="workflow_requires_single_end",
                message="Workflow app must contain exactly one end node.",
                location="canvas.nodes",
            )
        )
    if not start_nodes:
        return
    adjacency: dict[str, list[str]] = defaultdict(list)
    reverse: dict[str, list[str]] = defaultdict(list)
    for edge in dsl.canvas.edges:
        if edge.source in node_index and edge.target in node_index:
            adjacency[edge.source].append(edge.target)
            reverse[edge.target].append(edge.source)
    reachable = set()
    queue: deque[str] = deque([start_nodes[0].id])
    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        queue.extend(adjacency.get(current, []))
    executable = {node.id for node in dsl.canvas.nodes if node.kind not in {"start"}}
    unreachable = sorted(executable - reachable)
    if unreachable:
        issues.append(
            StudioCompileIssue(
                code="workflow_unreachable_nodes",
                message=f"Workflow contains unreachable nodes: {', '.join(unreachable)}.",
                location="canvas.nodes",
            )
        )
    if _has_cycle(node_index, adjacency):
        issues.append(
            StudioCompileIssue(
                code="workflow_cycle_detected",
                message="Workflow currently does not support graph cycles.",
                location="canvas.edges",
            )
        )
    for node in dsl.canvas.nodes:
        if node.kind == "start" and not adjacency.get(node.id):
            issues.append(
                StudioCompileIssue(
                    code="start_node_has_no_edge",
                    message="Start node must have at least one outgoing edge.",
                    location=f"canvas.nodes.{node.id}",
                )
            )
        if node.kind == "end" and reverse.get(node.id):
            continue


def _has_cycle(node_index: dict[str, Any], adjacency: dict[str, list[str]]) -> bool:
    color: dict[str, int] = {node_id: 0 for node_id in node_index}

    def visit(node_id: str) -> bool:
        color[node_id] = 1
        for target in adjacency.get(node_id, []):
            if node_index[target].kind == "end":
                continue
            if color[target] == 1:
                return True
            if color[target] == 0 and visit(target):
                return True
        color[node_id] = 2
        return False

    return any(visit(node_id) for node_id in node_index if color[node_id] == 0 and node_index[node_id].kind != "end")


def _model_binding_index(dsl: StudioDslDocument) -> dict[str, StudioModelBinding]:
    return {binding.name: binding for binding in dsl.bindings.models}


def _tool_binding_index(dsl: StudioDslDocument) -> dict[str, StudioToolBinding]:
    return {binding.name: binding for binding in dsl.bindings.tools}


def _knowledge_binding_index(dsl: StudioDslDocument) -> dict[str, StudioKnowledgeBinding]:
    return {binding.name: binding for binding in dsl.bindings.knowledge_sources}


def _default_model_binding(dsl: StudioDslDocument) -> StudioModelBinding | None:
    for binding in dsl.bindings.models:
        if binding.default:
            return binding
    return dsl.bindings.models[0] if dsl.bindings.models else None


def _resolve_model_input(
    binding_name: str | None,
    *,
    dsl: StudioDslDocument,
    resolver: StudioBindingResolver | None,
) -> tuple[Any, str | None, dict[str, Any] | None]:
    if binding_name is None:
        default_binding = _default_model_binding(dsl)
        if default_binding is None:
            return None, None, None
        binding_name = default_binding.name
    binding = _model_binding_index(dsl).get(binding_name)
    if binding is None:
        raise ValueError(f"Unknown model binding '{binding_name}'.")
    runtime_value = resolver.model_value(binding_name) if resolver is not None else None
    if runtime_value is not None:
        return runtime_value, binding.model, dict(binding.config)
    model_input = binding.as_model_input()
    if model_input is None:
        return None, None, None
    config = ModelConfig.from_any(model_input)
    return model_input, config.model, config.model_dump(exclude_none=True)


def _collect_tool_resources(
    binding_names: list[str],
    *,
    dsl: StudioDslDocument,
    resolver: StudioBindingResolver | None,
) -> tuple[ToolRegistry | list[BaseTool] | None, dict[str, bool] | None, list[str]]:
    tool_index = _tool_binding_index(dsl)
    custom_tools: list[BaseTool] = []
    bundle_flags: dict[str, bool] = {flag: False for flag in _EXECUTION_BUNDLE_FLAGS.values()}
    tool_names: list[str] = []
    for binding_name in binding_names:
        binding = tool_index.get(binding_name)
        if binding is None:
            raise ValueError(f"Unknown tool binding '{binding_name}'.")
        resolved = resolver.tool_value(binding_name) if resolver is not None else None
        if isinstance(resolved, ToolRegistry):
            for spec in resolved.list_specs():
                tool_names.append(spec["function"]["name"])
            custom_tools.extend(getattr(resolved, "_tools", {}).values())
        elif isinstance(resolved, BaseTool):
            custom_tools.append(resolved)
            tool_names.append(resolved.spec.name)
        else:
            if binding.bundle is not None:
                bundle_flags[_EXECUTION_BUNDLE_FLAGS[binding.bundle]] = True
            if binding.tool_name:
                tool_names.append(binding.tool_name)
    custom_tools = [tool for tool in custom_tools if tool is not None]
    compact_bundles = {key: value for key, value in bundle_flags.items() if value}
    return (custom_tools or None), (compact_bundles or None), sorted(set(tool_names))


def _collect_knowledge_resources(
    binding_names: list[str],
    *,
    dsl: StudioDslDocument,
    resolver: StudioBindingResolver | None,
) -> tuple[KnowledgeBase | None, list[str | Path] | None, list[str]]:
    knowledge_index = _knowledge_binding_index(dsl)
    runtime_knowledge_base: KnowledgeBase | None = None
    paths: list[str | Path] = []
    scopes: list[str] = []
    for binding_name in binding_names:
        binding = knowledge_index.get(binding_name)
        if binding is None:
            raise ValueError(f"Unknown knowledge binding '{binding_name}'.")
        scopes.extend(binding.scope)
        resolved = resolver.knowledge_value(binding_name) if resolver is not None else None
        if isinstance(resolved, KnowledgeBase):
            if runtime_knowledge_base is not None and runtime_knowledge_base is not resolved:
                raise ValueError("Studio MVP currently supports at most one resolved runtime knowledge base.")
            runtime_knowledge_base = resolved
        elif resolved is not None:
            if isinstance(resolved, (str, Path)):
                paths.append(resolved)
            elif isinstance(resolved, list):
                paths.extend(resolved)
        elif binding.path is not None:
            paths.append(binding.path)
    unique_scope = sorted(set(scope for scope in scopes if scope))
    unique_paths = list(dict.fromkeys(paths))
    return runtime_knowledge_base, (unique_paths or None), unique_scope


def _runtime_payload(
    dsl: StudioDslDocument,
    *,
    system_prompt: str | None = None,
    reasoning: str | dict[str, Any] | None = None,
    knowledge_scope: list[str] | None = None,
) -> RuntimeConfig:
    policies = dict(dsl.runtime.policies)
    payload: dict[str, Any] = {}
    if system_prompt is not None:
        payload["system_prompt"] = system_prompt
    if reasoning is not None:
        payload["reasoning_strategy"] = reasoning
    if "context_policy" in policies:
        payload["context_policy"] = policies["context_policy"]
    if "state_policy" in policies:
        payload["state_policy"] = policies["state_policy"]
    if "coordination_policy" in policies:
        payload["coordination_policy"] = policies["coordination_policy"]
    if "memory_policy" in policies:
        payload["memory_policy"] = policies["memory_policy"]
    if "rag_strategy" in policies:
        payload["rag_strategy"] = RagStrategyConfig.from_any(policies["rag_strategy"])
        payload["enable_retrieval"] = payload["rag_strategy"].mode != "off"
    if knowledge_scope:
        payload["default_knowledge_scope"] = list(knowledge_scope)
    if "enable_streaming" in dsl.runtime.debug:
        payload["enable_streaming"] = bool(dsl.runtime.debug["enable_streaming"])
    return RuntimeConfig.from_any(payload)


def _compile_agent_dsl(
    dsl: StudioDslDocument,
    *,
    issues: list[StudioCompileIssue],
    resolver: StudioBindingResolver | None,
) -> StudioCompiledArtifact:
    llm_node = next(node for node in dsl.canvas.nodes if node.kind == "llm_agent")
    tool_bindings = list(llm_node.config.get("tool_bindings", []))
    knowledge_bindings = list(llm_node.config.get("knowledge_bindings", []))
    model_input, _, _ = _resolve_model_input(llm_node.config.get("model_binding"), dsl=dsl, resolver=resolver)
    custom_tools, tool_bundles, tool_names = _collect_tool_resources(tool_bindings, dsl=dsl, resolver=resolver)
    knowledge_base, knowledge_paths, knowledge_scope = _collect_knowledge_resources(knowledge_bindings, dsl=dsl, resolver=resolver)
    design = AgentDesign(
        name=llm_node.name or dsl.meta.get("name"),
        description=llm_node.config.get("description") or dsl.meta.get("description"),
        profile=llm_node.config.get("profile", "default"),
        model=model_input,
        system_prompt=llm_node.config.get("system_prompt"),
        tools=custom_tools,
        tool_bundles=tool_bundles,
        knowledge_base=knowledge_base,
        knowledge_paths=knowledge_paths,
        knowledge_scope=knowledge_scope or None,
        runtime_config=_runtime_payload(
            dsl,
            system_prompt=llm_node.config.get("system_prompt"),
            reasoning=llm_node.config.get("reasoning"),
            knowledge_scope=knowledge_scope,
        ),
    )
    ir = StudioAppIR(
        app_type="agent",
        execution_target="agent_design",
        meta=dict(dsl.meta),
        nodes=[StudioNodeIR(id=llm_node.id, studio_kind=llm_node.kind, runtime_kind="model", name=llm_node.name, config=dict(llm_node.config), metadata=dict(llm_node.metadata))],
        bindings={
            "models": [binding.name for binding in dsl.bindings.models],
            "tools": tool_names,
            "knowledge_sources": [binding.name for binding in dsl.bindings.knowledge_sources],
        },
        export_target=dsl.export.target,
        runtime={
            "profile": llm_node.config.get("profile", "default"),
            "tool_bundles": tool_bundles or {},
            "tool_names": tool_names,
            "knowledge_paths": [str(path) for path in (knowledge_paths or [])],
            "knowledge_scope": knowledge_scope,
            "model_binding": llm_node.config.get("model_binding"),
        },
        blueprint={
            "facade": "studio_agent",
            "kind": "single_agent",
            "name": design.name or "agent",
            "description": design.description,
            "tool_names": tool_names,
            "knowledge_scope": knowledge_scope,
        },
    )
    return StudioCompiledArtifact(dsl=dsl, ir=ir, issues=issues, design=design)


def _role_payload_from_sub_agent(
    node,
    *,
    dsl: StudioDslDocument,
    resolver: StudioBindingResolver | None,
) -> tuple[dict[str, Any], StudioRoleIR]:
    model_input, _, _ = _resolve_model_input(node.config.get("model_binding"), dsl=dsl, resolver=resolver)
    tool_bindings = list(node.config.get("tool_bindings", []))
    custom_tools, tool_bundles, _ = _collect_tool_resources(tool_bindings, dsl=dsl, resolver=resolver)
    knowledge_bindings = list(node.config.get("knowledge_bindings", []))
    knowledge_base, knowledge_paths, knowledge_scope = _collect_knowledge_resources(knowledge_bindings, dsl=dsl, resolver=resolver)
    role_name = node.config.get("agent_name") or node.name or node.id
    payload = {
        "name": role_name,
        "role": node.config.get("role", role_name),
        "description": node.config.get("description"),
        "profile": node.config.get("profile", "default"),
        "model": model_input,
        "system_prompt": node.config.get("system_prompt"),
        "tools": custom_tools,
        "tool_bundles": tool_bundles,
        "knowledge_base": knowledge_base,
        "knowledge_paths": knowledge_paths,
        "knowledge_scope": knowledge_scope or None,
        "capabilities": node.config.get("capabilities"),
        "tags": node.config.get("tags"),
        "supports_parallel_tasks": node.config.get("supports_parallel_tasks", False),
        "max_delegation_depth": node.config.get("max_delegation_depth", 1),
        "runtime_config": _runtime_payload(
            dsl,
            system_prompt=node.config.get("system_prompt"),
            reasoning=node.config.get("reasoning"),
            knowledge_scope=knowledge_scope,
        ),
    }
    role_ir = StudioRoleIR(
        name=role_name,
        role=node.config.get("role", role_name),
        description=node.config.get("description"),
        node_id=node.id,
        capabilities=[str(item) for item in node.config.get("capabilities", [])],
        tags=list(node.config.get("tags", []) or []),
        knowledge_scope=knowledge_scope,
        tool_bindings=tool_bindings,
        model_binding=node.config.get("model_binding"),
    )
    return {key: value for key, value in payload.items() if value is not None}, role_ir


def _compile_team_dsl(
    dsl: StudioDslDocument,
    *,
    issues: list[StudioCompileIssue],
    resolver: StudioBindingResolver | None,
) -> StudioCompiledArtifact:
    roles: list[RoleDesign] = []
    role_irs: list[StudioRoleIR] = []
    for node in dsl.canvas.nodes:
        if node.kind != "sub_agent":
            continue
        payload, role_ir = _role_payload_from_sub_agent(node, dsl=dsl, resolver=resolver)
        design_payload = {
            key: payload.get(key)
            for key in (
                "profile",
                "model",
                "system_prompt",
                "tools",
                "tool_bundles",
                "knowledge_base",
                "knowledge_paths",
                "knowledge_scope",
                "runtime_config",
            )
            if payload.get(key) is not None
        }
        roles.append(
            RoleDesign(
                name=payload["name"],
                role=payload.get("role"),
                description=payload.get("description"),
                design=AgentDesign.from_any(design_payload),
                capabilities=payload.get("capabilities"),
                tags=list(payload.get("tags", []) or []),
                supports_parallel_tasks=bool(payload.get("supports_parallel_tasks", False)),
                max_delegation_depth=int(payload.get("max_delegation_depth", 1) or 1),
                metadata=dict(payload.get("metadata", {}) or {}),
                knowledge_scope=payload.get("knowledge_scope"),
            )
        )
        role_irs.append(role_ir)
    design = TeamDesign(
        name=dsl.meta.get("name"),
        description=dsl.meta.get("description"),
        roles=roles,
        topology=dsl.meta.get("topology", "supervisor"),
        runtime_config=_runtime_payload(dsl),
    )
    ir = StudioAppIR(
        app_type="team",
        execution_target="team_design",
        meta=dict(dsl.meta),
        roles=role_irs,
        nodes=[
            StudioNodeIR(
                id=node.id,
                studio_kind=node.kind,
                runtime_kind="team_role",
                name=node.name,
                config=dict(node.config),
                metadata=dict(node.metadata),
            )
            for node in dsl.canvas.nodes
            if node.kind == "sub_agent"
        ],
        export_target=dsl.export.target,
        runtime={
            "topology": dsl.meta.get("topology", "supervisor"),
            "role_count": len(role_irs),
            "role_names": [role.name for role in role_irs],
        },
        blueprint={
            "facade": "studio_team",
            "kind": "multi_agent",
            "name": design.name or "studio-team",
            "description": design.description,
            "roles": [role.model_dump() for role in role_irs],
        },
    )
    return StudioCompiledArtifact(dsl=dsl, ir=ir, issues=issues, design=design)


def _compile_workflow_dsl(
    dsl: StudioDslDocument,
    *,
    issues: list[StudioCompileIssue],
    resolver: StudioBindingResolver | None,
) -> StudioCompiledArtifact:
    node_index = {node.id: node for node in dsl.canvas.nodes}
    executable_nodes = [node for node in dsl.canvas.nodes if node.kind not in {"start", "end"}]
    start_node = next(node for node in dsl.canvas.nodes if node.kind == "start")
    entry_edge = next(edge for edge in dsl.canvas.edges if edge.source == start_node.id)
    workflow_nodes: list[Node] = []
    workflow_node_irs: list[StudioNodeIR] = []
    role_payloads: list[dict[str, Any]] = []
    role_irs: list[StudioRoleIR] = []
    root_tool_bindings: set[str] = set()
    root_knowledge_bindings: set[str] = set()
    root_model_binding: str | None = None

    for node in executable_nodes:
        if node.kind == "llm_agent":
            root_model_binding = root_model_binding or node.config.get("model_binding")
            root_tool_bindings.update(node.config.get("tool_bindings", []))
            root_knowledge_bindings.update(node.config.get("knowledge_bindings", []))
            _, model_name, model_config = _resolve_model_input(node.config.get("model_binding"), dsl=dsl, resolver=resolver)
            compiled_node = Node.model_node(
                node.id,
                prompt=node.config.get("prompt"),
                task_context_from_variables=node.config.get("task_context_from_variables"),
                model=model_name,
                model_config=model_config,
                goal=node.config.get("goal"),
                output_key=node.config.get("output_key"),
            )
            runtime_kind = "model"
        elif node.kind == "tool":
            binding_name = node.config.get("tool_binding")
            resolved_tool_name = node.config.get("tool_name")
            if binding_name is not None:
                binding = _tool_binding_index(dsl)[binding_name]
                resolved_tool_name = binding.tool_name or resolved_tool_name
                root_tool_bindings.add(binding_name)
                resolved_runtime_tool = resolver.tool_value(binding_name) if resolver is not None else None
                if isinstance(resolved_runtime_tool, BaseTool):
                    resolved_tool_name = resolved_runtime_tool.spec.name
            compiled_node = Node.tool(
                node.id,
                resolved_tool_name,
                arguments=dict(node.config.get("arguments", {})),
                output_key=node.config.get("output_key"),
            )
            runtime_kind = "tool"
        elif node.kind == "router":
            compiled_node = Node(id=node.id, kind="router", config=dict(node.config))
            runtime_kind = "router"
        elif node.kind == "knowledge_retrieve":
            root_knowledge_bindings.update(node.config.get("knowledge_bindings", []))
            retrieve_config = dict(node.config)
            if retrieve_config.get("knowledge_scope") is None and node.config.get("knowledge_bindings"):
                _, _, scope = _collect_knowledge_resources(node.config.get("knowledge_bindings", []), dsl=dsl, resolver=resolver)
                if scope:
                    retrieve_config["knowledge_scope"] = scope
            compiled_node = Node.retrieve(
                node.id,
                question=retrieve_config.get("question") or retrieve_config.get("query"),
                output_key=retrieve_config.get("output_key"),
                **{key: value for key, value in retrieve_config.items() if key not in {"question", "query", "output_key"}},
            )
            runtime_kind = "retrieve"
        elif node.kind == "memory_read":
            compiled_node = Node(id=node.id, kind="memory", config={"action": "search", **dict(node.config)})
            runtime_kind = "memory"
        elif node.kind == "memory_write":
            compiled_node = Node(id=node.id, kind="memory", config={"action": "remember", **dict(node.config)})
            runtime_kind = "memory"
        elif node.kind == "sub_agent":
            payload, role_ir = _role_payload_from_sub_agent(node, dsl=dsl, resolver=resolver)
            role_payloads.append(payload)
            role_irs.append(role_ir)
            agent_node_config = {
                "output_key": node.config.get("output_key"),
                "reasoning_strategy": node.config.get("reasoning"),
                "context_policy": dsl.runtime.policies.get("context_policy"),
                "state_policy": dsl.runtime.policies.get("state_policy"),
                "coordination_policy": dsl.runtime.policies.get("coordination_policy"),
                "memory_policy": dsl.runtime.policies.get("memory_policy"),
            }
            if payload.get("knowledge_scope"):
                agent_node_config["knowledge_scope"] = payload.get("knowledge_scope")
            compiled_node = Node.agent(
                node.id,
                agent_name=payload["name"],
                input_from_variable=node.config.get("input_from_variable"),
                goal=node.config.get("goal"),
                **{key: value for key, value in agent_node_config.items() if value is not None},
            )
            runtime_kind = "agent"
        elif node.kind == "aggregate":
            compiled_node = Node.aggregate(
                node.id,
                sources=list(node.config.get("sources", [])),
                output_key=node.config.get("output_key"),
            )
            runtime_kind = "aggregate"
        elif node.kind == "human_input":
            compiled_node = Node(id=node.id, kind="human_input", config=dict(node.config))
            runtime_kind = "human_input"
        elif node.kind == "human_approval":
            compiled_node = Node(id=node.id, kind="human_approval", config=dict(node.config))
            runtime_kind = "human_approval"
        else:
            raise ValueError(f"Unsupported workflow node kind '{node.kind}'.")
        workflow_nodes.append(compiled_node)
        workflow_node_irs.append(
            StudioNodeIR(
                id=node.id,
                studio_kind=node.kind,
                runtime_kind=runtime_kind,
                name=node.name,
                config=dict(node.config),
                metadata=dict(node.metadata),
            )
        )

    workflow_edges: list[Edge] = []
    workflow_edge_irs: list[StudioEdgeIR] = []
    for edge in dsl.canvas.edges:
        if node_index[edge.source].kind == "start":
            continue
        if node_index[edge.target].kind == "end":
            continue
        workflow_edges.append(Edge(source=edge.source, target=edge.target, kind=edge.kind, condition=edge.condition))
        workflow_edge_irs.append(
            StudioEdgeIR(
                source=edge.source,
                target=edge.target,
                kind=edge.kind,
                condition=edge.condition,
                field_mapping=dict(edge.field_mapping),
            )
        )

    root_model_input, _, root_model_config = _resolve_model_input(root_model_binding, dsl=dsl, resolver=resolver)
    knowledge_base, knowledge_paths, knowledge_scope = _collect_knowledge_resources(
        sorted(root_knowledge_bindings),
        dsl=dsl,
        resolver=resolver,
    )
    custom_tools, tool_bundles, tool_names = _collect_tool_resources(sorted(root_tool_bindings), dsl=dsl, resolver=resolver)
    workflow = Workflow(
        entry_node=entry_edge.target,
        nodes=workflow_nodes,
        edges=workflow_edges,
        max_steps=int(dsl.runtime.debug.get("max_steps", 20) or 20),
    )
    workflow_plan = StudioWorkflowRuntimePlan(
        name=dsl.meta.get("name"),
        description=dsl.meta.get("description"),
        workspace_root=Path.cwd(),
        model=root_model_input if root_model_input is not None and not isinstance(root_model_input, (str, dict)) else None,
        model_config_input=root_model_input if isinstance(root_model_input, (str, dict)) else root_model_config,
        tools=custom_tools,
        tool_bundles=tool_bundles,
        shared_knowledge=knowledge_base
        if knowledge_base is not None
        else {"knowledge_paths": knowledge_paths or [], "knowledge_scope": knowledge_scope},
        workflow=workflow,
        roles=role_payloads,
        runtime_config=_runtime_payload(dsl, knowledge_scope=knowledge_scope),
        metadata={"app_type": "workflow"},
    )
    ir = StudioAppIR(
        app_type="workflow",
        execution_target="workflow_runtime",
        meta=dict(dsl.meta),
        entry_node=entry_edge.target,
        nodes=workflow_node_irs,
        edges=workflow_edge_irs,
        roles=role_irs,
        bindings={
            "model_binding": root_model_binding,
            "tool_names": tool_names,
            "knowledge_paths": [str(path) for path in (knowledge_paths or [])],
            "knowledge_scope": knowledge_scope,
        },
        export_target=dsl.export.target,
        runtime={
            "tool_bundles": tool_bundles or {},
            "tool_names": tool_names,
            "knowledge_scope": knowledge_scope,
        },
        blueprint={
            "facade": "studio_workflow",
            "kind": "workflow",
            "name": dsl.meta.get("name", "studio-workflow"),
            "description": dsl.meta.get("description"),
            "entry_node": entry_edge.target,
            "roles": [role.model_dump() for role in role_irs],
            "workflow": _workflow_summary(workflow),
        },
    )
    return StudioCompiledArtifact(dsl=dsl, ir=ir, issues=issues, workflow_plan=workflow_plan)
