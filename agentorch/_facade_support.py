from __future__ import annotations

import asyncio
import atexit
import contextlib
import inspect
import threading
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agentorch.agents import AgentCapability, AgentSpec
from agentorch.config import ModelConfig, ObservabilityConfig, RuntimeConfig
from agentorch.evolution import EvolutionConfig, EvolutionManager, EvolutionSession, SearchSpace
from agentorch.knowledge import IndexedKnowledgeBase, KnowledgeBase, RagStrategyConfig
from agentorch.reasoning import ReasoningStrategyConfig
from agentorch.runtime import Agent, Runtime
from agentorch.runtime._export_support import _safe_export, _workflow_summary
from agentorch.runtime.agent import _runtime_summary
from agentorch.sandbox import SandboxManager
from agentorch.skills import SkillCatalogConfig, SkillRoutingConfig
from agentorch.strategies import ContextPolicy, CoordinationPolicy, MemoryPolicy, StatePolicy
from agentorch.tools import BaseTool, ToolRegistry
from agentorch.workflow import Workflow

CreateAgentFn = Callable[..., Agent]


@dataclass
class MultiAgentMemberAssembly:
    agent: Agent
    spec: AgentSpec
    summary: dict[str, Any]
    managed: bool = False


def compact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def is_default_value(runtime_config: RuntimeConfig, default_config: RuntimeConfig, field_name: str) -> bool:
    current = _safe_export(getattr(runtime_config, field_name))
    default = _safe_export(getattr(default_config, field_name))
    return current == default


def apply_if_unset(
    runtime_config: RuntimeConfig,
    default_config: RuntimeConfig,
    runtime_config_supplied: bool,
    field_name: str,
    value: Any,
    *,
    explicit_fields: set[str] | None = None,
) -> RuntimeConfig:
    if value is None:
        return runtime_config
    if runtime_config_supplied and field_name in (explicit_fields or set()):
        return runtime_config
    if runtime_config_supplied and not is_default_value(runtime_config, default_config, field_name):
        return runtime_config
    return runtime_config.model_copy(update={field_name: value})


def finalize_runtime_config(runtime_config: RuntimeConfig) -> RuntimeConfig:
    return RuntimeConfig.model_validate(runtime_config.model_dump())


def resolve_reasoning_input(
    reasoning: ReasoningStrategyConfig | str | dict[str, Any] | None,
    reasoning_framework: ReasoningStrategyConfig | str | dict[str, Any] | None = None,
) -> ReasoningStrategyConfig | None:
    if reasoning is not None and reasoning_framework is not None:
        left = _safe_export(ReasoningStrategyConfig.from_any(reasoning))
        right = _safe_export(ReasoningStrategyConfig.from_any(reasoning_framework))
        if left != right:
            raise ValueError("Pass only one of 'reasoning' or 'reasoning_framework'.")
    selected = reasoning if reasoning is not None else reasoning_framework
    return ReasoningStrategyConfig.from_any(selected) if selected is not None else None


def resolve_facade_runtime_config(
    runtime_config: RuntimeConfig | dict[str, Any] | None,
    *,
    system_prompt: str | None = None,
    enable_streaming: bool | None = None,
    reasoning_strategy: ReasoningStrategyConfig | None = None,
    skill_catalog: SkillCatalogConfig | dict[str, Any] | None = None,
    skill_routing: SkillRoutingConfig | str | dict[str, Any] | None = None,
    context_policy: ContextPolicy | dict[str, Any] | None = None,
    state_policy: StatePolicy | dict[str, Any] | None = None,
    coordination_policy: CoordinationPolicy | dict[str, Any] | None = None,
    memory_policy: MemoryPolicy | dict[str, Any] | None = None,
    context_selector: Any = None,
    route_planner: Any = None,
    memory_evaluator: Any = None,
    observability: Any = None,
    default_knowledge_scope: list[str] | None = None,
    apply_default_knowledge_scope: bool = False,
    rag_config: RagStrategyConfig | None = None,
    overrides: dict[str, Any] | None = None,
) -> RuntimeConfig:
    runtime_config_supplied = runtime_config is not None
    resolved_runtime_config = RuntimeConfig.from_any(runtime_config)
    default_runtime_config = RuntimeConfig()
    explicit_fields = set(getattr(resolved_runtime_config, "model_fields_set", set()))

    updates = (
        ("system_prompt", system_prompt),
        ("enable_streaming", enable_streaming),
        ("reasoning_strategy", reasoning_strategy),
        ("skill_catalog", SkillCatalogConfig.from_any(skill_catalog) if skill_catalog is not None else None),
        ("skill_routing", SkillRoutingConfig.from_any(skill_routing) if skill_routing is not None else None),
        ("context_policy", ContextPolicy.from_any(context_policy) if context_policy is not None else None),
        ("state_policy", StatePolicy.from_any(state_policy) if state_policy is not None else None),
        ("coordination_policy", CoordinationPolicy.from_any(coordination_policy) if coordination_policy is not None else None),
        ("memory_policy", MemoryPolicy.from_any(memory_policy) if memory_policy is not None else None),
        ("context_selector", context_selector),
        ("route_planner", route_planner),
        ("memory_evaluator", memory_evaluator),
        ("observability", ObservabilityConfig.from_any(observability) if observability is not None else None),
    )
    for field_name, value in updates:
        resolved_runtime_config = apply_if_unset(
            resolved_runtime_config,
            default_runtime_config,
            runtime_config_supplied,
            field_name,
            value,
            explicit_fields=explicit_fields,
        )

    if apply_default_knowledge_scope:
        resolved_runtime_config = apply_if_unset(
            resolved_runtime_config,
            default_runtime_config,
            runtime_config_supplied,
            "default_knowledge_scope",
            list(default_knowledge_scope or []),
            explicit_fields=explicit_fields,
        )
    if rag_config is not None:
        resolved_runtime_config = apply_if_unset(
            resolved_runtime_config,
            default_runtime_config,
            runtime_config_supplied,
            "rag_strategy",
            rag_config,
            explicit_fields=explicit_fields,
        )
        resolved_runtime_config = apply_if_unset(
            resolved_runtime_config,
            default_runtime_config,
            runtime_config_supplied,
            "enable_retrieval",
            rag_config.mode != "off",
            explicit_fields=explicit_fields,
        )
    if overrides:
        resolved_runtime_config = resolved_runtime_config.model_copy(update=overrides)
    return finalize_runtime_config(resolved_runtime_config)


def coerce_model_inputs(model: Any) -> tuple[Any | None, ModelConfig | dict[str, Any] | str | None]:
    if model is None:
        return None, None
    if isinstance(model, (str, ModelConfig, dict)):
        return None, model
    return model, None


def coerce_tool_registry(
    tools: ToolRegistry | list[BaseTool] | tuple[BaseTool, ...] | None,
) -> ToolRegistry:
    registry = ToolRegistry.empty()
    if tools is None:
        return registry
    if isinstance(tools, ToolRegistry):
        registry.extend(tools)
        return registry
    for tool in tools:
        registry.register(tool)
    return registry


def normalize_tool_bundles(
    tool_bundles: bool | dict[str, Any] | None,
    *,
    workspace_root: str | Path,
    sandbox: SandboxManager | None,
    model: Any | None = None,
) -> ToolRegistry:
    if not tool_bundles:
        return ToolRegistry.empty()
    if tool_bundles is True:
        return ToolRegistry.with_bundles(
            workspace_root=workspace_root,
            sandbox=sandbox,
            include_execution=sandbox is not None,
            model=model,
        )
    payload = dict(tool_bundles)
    return ToolRegistry.with_bundles(
        workspace_root=payload.pop("workspace_root", workspace_root),
        sandbox=payload.pop("sandbox", sandbox),
        include_filesystem=payload.pop("include_filesystem", True),
        include_execution=payload.pop("include_execution", sandbox is not None),
        include_git=payload.pop("include_git", True),
        include_web=payload.pop("include_web", False),
        include_media=payload.pop("include_media", False),
        brave_api_key=payload.pop("brave_api_key", None),
        model=payload.pop("model", model),
    )


def normalize_capabilities(capabilities: list[AgentCapability | str] | None, agent: Agent) -> list[AgentCapability]:
    values: list[AgentCapability] = []
    for item in capabilities or []:
        values.append(item if isinstance(item, AgentCapability) else AgentCapability(item))
    if getattr(agent.runtime.tools, "_tools", {}):
        if AgentCapability.TOOL_USE not in values:
            values.append(AgentCapability.TOOL_USE)
    if agent.runtime.knowledge_base is not None and AgentCapability.RETRIEVE not in values:
        values.append(AgentCapability.RETRIEVE)
    if agent.runtime.supervisor is not None and AgentCapability.DELEGATE not in values:
        values.append(AgentCapability.DELEGATE)
    return values


def agent_member_summary(
    agent: Agent,
    *,
    name: str,
    role: str | None,
    description: str | None,
    capabilities: list[AgentCapability] | None,
    knowledge_scope: list[str] | None,
) -> dict[str, Any]:
    exported = agent.export_blueprint()
    return {
        "name": name,
        "role": role or name,
        "description": description or exported.get("description") or name,
        "capabilities": [item.value if isinstance(item, AgentCapability) else str(item) for item in (capabilities or [])],
        "knowledge_scope": list(knowledge_scope or agent.runtime.config.default_knowledge_scope),
        "agent_blueprint": exported,
    }


def split_shared_knowledge_input(
    shared_knowledge: KnowledgeBase | dict[str, Any] | None,
) -> tuple[KnowledgeBase | None, dict[str, Any]]:
    if isinstance(shared_knowledge, KnowledgeBase):
        return shared_knowledge, {}
    if not isinstance(shared_knowledge, dict):
        return None, {}
    payload = dict(shared_knowledge)
    embedded_knowledge_base = payload.get("knowledge_base")
    if isinstance(embedded_knowledge_base, KnowledgeBase):
        payload.pop("knowledge_base", None)
        return embedded_knowledge_base, payload
    return None, payload


def materialize_shared_knowledge_base(
    shared_knowledge_base: KnowledgeBase | None,
    shared_knowledge_payload: dict[str, Any],
    *,
    run_async: Callable[[Any], Any] | None = None,
) -> KnowledgeBase | None:
    if shared_knowledge_base is not None:
        return shared_knowledge_base

    knowledge_paths = shared_knowledge_payload.get("knowledge_paths")
    knowledge_assets = shared_knowledge_payload.get("knowledge_assets")
    knowledge_documents = shared_knowledge_payload.get("knowledge_documents")
    if not any((knowledge_paths, knowledge_assets, knowledge_documents)):
        return None

    create_kwargs = {
        "paths": list(knowledge_paths or []),
        "assets": list(knowledge_assets or []),
        "documents": list(knowledge_documents or []),
        "scopes": list(shared_knowledge_payload.get("knowledge_scope") or []),
    }
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return IndexedKnowledgeBase.create(**create_kwargs)
    if run_async is None:
        raise RuntimeError("materialize_shared_knowledge_base(...) requires an async runner inside a running event loop.")
    return run_async(IndexedKnowledgeBase.acreate(**create_kwargs))


def resolve_multi_agent_member(
    item: Agent | dict[str, Any],
    *,
    index: int,
    create_agent_fn: CreateAgentFn,
    model: Any = None,
    sandbox: SandboxManager | None = None,
    shared_memory: Any = None,
    shared_knowledge: KnowledgeBase | dict[str, Any] | None = None,
) -> MultiAgentMemberAssembly:
    shared_knowledge_base, shared_knowledge_payload = split_shared_knowledge_input(shared_knowledge)
    managed = False

    if isinstance(item, Agent):
        exported = item.export_blueprint()
        member_agent = item
        member_name = exported.get("name") or f"agent_{index}"
        member_role = member_name
        member_description = exported.get("description") or member_name
        member_capabilities = normalize_capabilities(None, item)
        member_scope = shared_knowledge_payload.get("knowledge_scope") or item.runtime.config.default_knowledge_scope
        member_tags: list[str] = []
        member_supports_parallel = False
        member_max_delegation_depth = 1
        member_metadata: dict[str, Any] = {}
    else:
        payload = dict(item)
        existing_agent = payload.pop("agent", None)
        role_name = payload.pop("role", None)
        member_name = payload.pop("name", None) or role_name or f"agent_{index}"
        member_role = role_name or member_name
        member_description = payload.pop("description", None) or f"{member_name} specialist"
        requested_capabilities = payload.pop("capabilities", None)
        member_tags = list(payload.pop("tags", []) or [])
        member_supports_parallel = bool(payload.pop("supports_parallel_tasks", False))
        member_max_delegation_depth = int(payload.pop("max_delegation_depth", 1) or 1)
        member_metadata = dict(payload.pop("metadata", {}) or {})

        if existing_agent is not None:
            member_agent = existing_agent
            member_scope = (
                payload.pop("knowledge_scope", None)
                or shared_knowledge_payload.get("knowledge_scope")
                or member_agent.runtime.config.default_knowledge_scope
            )
            member_capabilities = normalize_capabilities(requested_capabilities, member_agent)
        else:
            if shared_memory is not None and "memory" not in payload:
                payload["memory"] = shared_memory
            if shared_knowledge_base is not None and "knowledge_base" not in payload:
                payload["knowledge_base"] = shared_knowledge_base
            if shared_knowledge_payload:
                shared_keys = ("knowledge_scope", "rag", "enable_rag")
                if shared_knowledge_base is None:
                    shared_keys = (
                        "knowledge_paths",
                        "knowledge_assets",
                        "knowledge_documents",
                        "knowledge_scope",
                        "rag",
                        "enable_rag",
                    )
                for key in shared_keys:
                    shared_value = shared_knowledge_payload.get(key)
                    if shared_value is not None:
                        payload.setdefault(key, shared_value)
            payload.setdefault("model", model)
            payload.setdefault("sandbox", sandbox)
            payload.setdefault("name", member_name)
            payload.setdefault("description", member_description)
            member_agent = create_agent_fn(**payload)
            managed = True
            member_scope = payload.get("knowledge_scope") or member_agent.runtime.config.default_knowledge_scope
            member_capabilities = normalize_capabilities(requested_capabilities, member_agent)

    spec = AgentSpec.assistant(
        member_name,
        description=member_description,
        tags=member_tags,
        capabilities=member_capabilities,
        tools=sorted(getattr(member_agent.runtime.tools, "_tools", {}).keys()),
        knowledge_scopes=list(member_scope or []),
        supports_parallel_tasks=member_supports_parallel,
        max_delegation_depth=member_max_delegation_depth,
        metadata=member_metadata,
    )
    summary = agent_member_summary(
        member_agent,
        name=member_name,
        role=member_role,
        description=member_description,
        capabilities=member_capabilities,
        knowledge_scope=list(member_scope or []),
    )
    return MultiAgentMemberAssembly(agent=member_agent, spec=spec, summary=summary, managed=managed)


def profile_defaults(profile: str, *, sandbox: SandboxManager | None) -> dict[str, Any]:
    normalized = (profile or "default").strip().lower()
    if normalized == "default":
        return {
            "context_policy": ContextPolicy.default(),
            "state_policy": StatePolicy(),
            "coordination_policy": CoordinationPolicy(),
            "memory_policy": MemoryPolicy(),
        }
    if normalized == "coding":
        return {
            "system_prompt": (
                "You are a careful coding agent. Use tools when they improve accuracy, explain important tradeoffs, "
                "and prefer safe, minimal changes."
            ),
            "enable_tools": True,
            "context_policy": ContextPolicy.lean(),
            "state_policy": StatePolicy(),
            "coordination_policy": CoordinationPolicy(),
            "memory_policy": MemoryPolicy(),
            "tool_bundles": {
                "include_filesystem": True,
                "include_execution": sandbox is not None,
                "include_git": True,
                "include_web": False,
            },
        }
    if normalized == "workflow":
        return {
            "system_prompt": (
                "You are a workflow-oriented agent. Follow configured workflow steps carefully, keep state explicit, "
                "and make transitions easy to inspect."
            ),
            "reasoning": "react",
            "context_policy": ContextPolicy.default(),
            "state_policy": StatePolicy(),
            "coordination_policy": CoordinationPolicy(),
            "memory_policy": MemoryPolicy(),
        }
    raise ValueError(f"Unsupported create_agent profile '{profile}'.")


def build_single_agent_blueprint(
    *,
    name: str | None,
    description: str | None,
    profile: str,
    runtime: Runtime,
    workflow: Workflow | None,
    facade_inputs: dict[str, Any],
    resolved_defaults: dict[str, Any],
    runtime_source: str = "assembled",
) -> dict[str, Any]:
    return {
        "facade": "create_agent",
        "kind": "single_agent",
        "name": name or "agent",
        "description": description,
        "profile": profile,
        "runtime_source": runtime_source,
        "runtime": _runtime_summary(runtime),
        "workflow": _workflow_summary(workflow),
        "facade_inputs": _safe_export(compact_dict(facade_inputs)),
        "resolved_defaults": _safe_export(compact_dict(resolved_defaults)),
        "redaction_applied": not getattr(runtime.config, "unsafe_export", False),
        "resource_state": {
            "closed": getattr(runtime, "_closed", False),
            "background_managed": getattr(runtime, "_background_managed", False),
        },
    }


def build_multi_agent_blueprint(
    *,
    name: str | None,
    description: str | None,
    topology: str,
    members: list[dict[str, Any]],
    runtime: Runtime,
    workflow: Workflow | None,
    member_count: int,
    shared_knowledge: KnowledgeBase | dict[str, Any] | None,
    shared_memory: Any = None,
    reasoning: Any = None,
    context_policy: Any = None,
    state_policy: Any = None,
    coordination_policy: Any = None,
    memory_policy: Any = None,
    extensions: list[Any] | tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    return {
        "facade": "create_multi_agent",
        "kind": "multi_agent",
        "name": name or "multi_agent_system",
        "description": description or "Multi-agent system assembled from create_agent members",
        "topology": topology,
        "members": members,
        "runtime": _runtime_summary(runtime),
        "workflow": _workflow_summary(workflow),
        "redaction_applied": not getattr(runtime.config, "unsafe_export", False),
        "resource_state": {
            "closed": getattr(runtime, "_closed", False),
            "background_managed": getattr(runtime, "_background_managed", False),
        },
        "facade_inputs": _safe_export(
            compact_dict(
                {
                    "member_count": member_count,
                    "shared_knowledge": shared_knowledge.__class__.__name__ if isinstance(shared_knowledge, KnowledgeBase) else shared_knowledge,
                    "shared_memory": shared_memory.__class__.__name__ if shared_memory is not None else None,
                    "reasoning": reasoning,
                    "context_policy": context_policy,
                    "state_policy": state_policy,
                    "coordination_policy": coordination_policy,
                    "memory_policy": memory_policy,
                    "topology": topology,
                    "workflow_attached": workflow is not None,
                    "extensions": [extension.extension_name for extension in extensions] if extensions else None,
                }
            )
        ),
        "resolved_defaults": {"topology": topology},
    }


async def close_resource(candidate: Any) -> None:
    if hasattr(candidate, "aclose"):
        result = candidate.aclose()
        if inspect.isawaitable(result):
            await result
        return
    if hasattr(candidate, "close"):
        candidate.close()


def build_facade_evolution_session(
    *,
    search_space: SearchSpace | dict[str, list[Any]],
    evaluator: Any,
    tasks: list[Any] | None,
    evolution_config: EvolutionConfig | None,
    candidate_kind: str,
    builder: Any,
) -> EvolutionSession[Any]:
    async def evaluate_candidate(genome: Any, candidate: Any, evaluation_tasks: list[Any] | None):
        try:
            value = evaluator(genome, candidate, evaluation_tasks)
            if inspect.isawaitable(value):
                return await value
            return value
        finally:
            await close_resource(candidate)

    manager = EvolutionManager(
        builder=builder,
        evaluator=evaluate_candidate,
        config=evolution_config,
        search_space=search_space,
    )
    return EvolutionSession(manager=manager, tasks=tasks, candidate_kind=candidate_kind)


class BackgroundRuntimeBridge:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._resources: weakref.WeakSet[Any] = weakref.WeakSet()
        atexit.register(self.shutdown)

    def ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None and self._loop.is_running():
                return self._loop

            ready = threading.Event()
            holder: dict[str, asyncio.AbstractEventLoop] = {}

            def _runner() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                holder["loop"] = loop
                ready.set()
                loop.run_forever()
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()

            thread = threading.Thread(target=_runner, name="agentorch-facade-loop", daemon=True)
            thread.start()
            ready.wait()
            self._loop = holder["loop"]
            self._thread = thread
            return self._loop

    def run(self, coro: Any) -> Any:
        loop = self.ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def track(self, resource: Any) -> None:
        self._resources.add(resource)

    def shutdown(self) -> None:
        loop = self._loop
        thread = self._thread
        if loop is None or thread is None:
            return
        if loop.is_running():
            resources = [item for item in list(self._resources) if hasattr(item, "aclose")]
            if resources:
                async def _close_resources() -> None:
                    await asyncio.gather(*(item.aclose() for item in resources), return_exceptions=True)

                future = asyncio.run_coroutine_threadsafe(_close_resources(), loop)
                with contextlib.suppress(Exception):
                    future.result(timeout=5.0)
            loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=1.0)
        self._loop = None
        self._thread = None
