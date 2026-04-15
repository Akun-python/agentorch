from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agentorch.agents import (
    AggregationPolicy,
    AgentCapability,
    AgentRegistry,
    AgentSpec,
    BudgetManager,
    Coordinator,
    EscalationPolicy,
    ExecutionPolicy,
    PermissionManager,
    Supervisor,
    SupervisorPolicy,
)
from agentorch.config import ModelConfig, ObservabilityConfig, RuntimeConfig
from agentorch.knowledge import KnowledgeBase, RagStrategyConfig
from agentorch.memory import MemoryManager
from agentorch.reasoning import ReasoningStrategyConfig
from agentorch.runtime import Agent, Runtime
from agentorch.runtime.agent import _runtime_summary, _safe_export, _workflow_summary
from agentorch.sandbox import SandboxManager
from agentorch.skills import SkillRegistry
from agentorch.strategies import (
    BaseContextStrategy,
    BaseCooperationStrategy,
    BaseLongHorizonStrategy,
    BaseMemoryGovernanceStrategy,
    ContextStrategyConfig,
    CooperationStrategyConfig,
    LongHorizonStrategyConfig,
    MemoryGovernanceStrategyConfig,
)
from agentorch.tools import BaseTool, ToolRegistry
from agentorch.workflow import Workflow
from agentorch._facade_support import (
    BackgroundRuntimeBridge,
    agent_member_summary as _agent_member_summary,
    apply_if_unset as _apply_if_unset,
    build_single_agent_blueprint as _build_single_agent_blueprint,
    coerce_model_inputs as _coerce_model_inputs,
    coerce_tool_registry as _coerce_tool_registry,
    compact_dict as _compact_dict,
    finalize_runtime_config as _finalize_runtime_config,
    normalize_capabilities as _normalize_capabilities,
    normalize_tool_bundles as _normalize_tool_bundles,
    profile_defaults as _profile_defaults,
    resolve_reasoning_input as _resolve_reasoning_input,
)

_ALLOWED_MULTI_AGENT_TOPOLOGIES = {"supervisor"}
_BACKGROUND_BRIDGE = BackgroundRuntimeBridge()


def _create_agent_instance(*, workflow: Workflow | None = None, **runtime_kwargs: Any) -> Agent:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return Agent.create(workflow=workflow, **runtime_kwargs)
    runtime = _BACKGROUND_BRIDGE.run(Runtime.acreate(**runtime_kwargs))
    runtime._background_managed = True
    agent = Agent(runtime=runtime, workflow=workflow)
    _BACKGROUND_BRIDGE.track(agent)
    return agent


def _create_runtime_instance(**runtime_kwargs: Any) -> Runtime:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return Runtime.create(**runtime_kwargs)
    runtime = _BACKGROUND_BRIDGE.run(Runtime.acreate(**runtime_kwargs))
    runtime._background_managed = True
    _BACKGROUND_BRIDGE.track(runtime)
    return runtime


def create_agent(
    *,
    model: Any = None,
    profile: str = "default",
    system_prompt: str | None = None,
    name: str | None = None,
    description: str | None = None,
    enable_tools: bool | None = None,
    tools: ToolRegistry | list[BaseTool] | tuple[BaseTool, ...] | None = None,
    tool_bundles: bool | dict[str, Any] | None = None,
    workspace_root: str | Path | None = None,
    enable_rag: bool | None = None,
    knowledge_base: KnowledgeBase | None = None,
    knowledge_paths: list[str | Path] | None = None,
    rag: RagStrategyConfig | str | dict[str, Any] | None = None,
    knowledge_scope: list[str] | None = None,
    enable_memory: bool | None = None,
    memory: MemoryManager | None = None,
    workflow: Workflow | None = None,
    reasoning: ReasoningStrategyConfig | str | dict[str, Any] | None = None,
    reasoning_framework: ReasoningStrategyConfig | str | dict[str, Any] | None = None,
    orchestration_profile: str | None = None,
    sandbox: SandboxManager | None = None,
    enable_streaming: bool | None = None,
    human_feedback: Any | None = None,
    observability: ObservabilityConfig | dict[str, Any] | None = None,
    skills: SkillRegistry | None = None,
    context_strategy: ContextStrategyConfig | BaseContextStrategy | str | dict[str, Any] | None = None,
    long_horizon_strategy: LongHorizonStrategyConfig | BaseLongHorizonStrategy | str | dict[str, Any] | None = None,
    cooperation_strategy: CooperationStrategyConfig | BaseCooperationStrategy | str | dict[str, Any] | None = None,
    memory_governance_strategy: MemoryGovernanceStrategyConfig | BaseMemoryGovernanceStrategy | str | dict[str, Any] | None = None,
    runtime: Runtime | None = None,
    runtime_config: RuntimeConfig | dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
) -> Agent:
    if runtime is not None:
        conflicting = [
            model,
            system_prompt,
            tools,
            tool_bundles,
            knowledge_base,
            knowledge_paths,
            rag,
            memory,
            reasoning,
            reasoning_framework,
            orchestration_profile,
            sandbox,
            human_feedback,
            observability,
            skills,
            context_strategy,
            long_horizon_strategy,
            cooperation_strategy,
            memory_governance_strategy,
            runtime_config,
            overrides,
        ]
        if any(item is not None for item in conflicting):
            raise ValueError("create_agent(runtime=...) cannot be mixed with other runtime assembly parameters.")
        return Agent(runtime=runtime, workflow=workflow).bind_blueprint(
            _build_single_agent_blueprint(
                name=name,
                description=description,
                profile=profile,
                runtime=runtime,
                workflow=workflow,
                facade_inputs={"runtime": "provided"},
                resolved_defaults={},
                runtime_source="provided",
            )
        )

    selected_workspace_root = Path(workspace_root or Path.cwd())
    profile_defaults = _profile_defaults(profile, sandbox=sandbox)
    resolved_defaults: dict[str, Any] = {"profile": profile}

    if enable_tools is None:
        enable_tools = bool(profile_defaults.get("enable_tools", True))
        if "enable_tools" in profile_defaults:
            resolved_defaults["enable_tools"] = enable_tools
    if enable_memory is None:
        enable_memory = bool(profile_defaults.get("enable_memory", True))
        if "enable_memory" in profile_defaults:
            resolved_defaults["enable_memory"] = enable_memory
    if tool_bundles is None and "tool_bundles" in profile_defaults:
        tool_bundles = profile_defaults["tool_bundles"]
        resolved_defaults["tool_bundles"] = tool_bundles
    if system_prompt is None and "system_prompt" in profile_defaults:
        system_prompt = profile_defaults["system_prompt"]
        resolved_defaults["system_prompt"] = system_prompt
    if orchestration_profile is None and "orchestration_profile" in profile_defaults:
        orchestration_profile = profile_defaults["orchestration_profile"]
        resolved_defaults["orchestration_profile"] = orchestration_profile
    if enable_rag is None and "enable_rag" in profile_defaults:
        enable_rag = bool(profile_defaults["enable_rag"])
        resolved_defaults["enable_rag"] = enable_rag
    if rag is None and "rag" in profile_defaults:
        rag = profile_defaults["rag"]
        resolved_defaults["rag"] = rag
    if reasoning is None and "reasoning" in profile_defaults:
        reasoning = profile_defaults["reasoning"]
        resolved_defaults["reasoning"] = reasoning

    if not enable_tools and (tools is not None or tool_bundles):
        raise ValueError("enable_tools=False conflicts with explicit tools or tool_bundles.")
    if enable_rag is False and any(item is not None for item in (knowledge_base, knowledge_paths, rag, knowledge_scope)):
        raise ValueError("enable_rag=False conflicts with knowledge_base, knowledge_paths, rag, or knowledge_scope.")
    if not enable_memory and memory is not None:
        raise ValueError("enable_memory=False conflicts with an explicit memory manager.")

    runtime_config_supplied = runtime_config is not None
    resolved_runtime_config = RuntimeConfig.from_any(runtime_config)
    default_runtime_config = RuntimeConfig()

    rag_enabled = bool(enable_rag) or knowledge_base is not None or bool(knowledge_paths) or rag is not None
    rag_config = None
    if rag_enabled:
        rag_config = RagStrategyConfig.from_any(rag or RagStrategyConfig.for_hybrid())
        if knowledge_scope and not rag_config.knowledge_scope:
            rag_config = rag_config.with_scope(*knowledge_scope)

    resolved_reasoning = _resolve_reasoning_input(reasoning, reasoning_framework)

    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config_supplied,
        "system_prompt",
        system_prompt,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config_supplied,
        "reasoning_strategy",
        resolved_reasoning,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config_supplied,
        "orchestration_profile",
        orchestration_profile,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config_supplied,
        "context_strategy",
        ContextStrategyConfig.from_any(context_strategy) if context_strategy is not None and not isinstance(context_strategy, BaseContextStrategy) else context_strategy,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config_supplied,
        "long_horizon_strategy",
        LongHorizonStrategyConfig.from_any(long_horizon_strategy) if long_horizon_strategy is not None and not isinstance(long_horizon_strategy, BaseLongHorizonStrategy) else long_horizon_strategy,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config_supplied,
        "cooperation_strategy",
        CooperationStrategyConfig.from_any(cooperation_strategy) if cooperation_strategy is not None and not isinstance(cooperation_strategy, BaseCooperationStrategy) else cooperation_strategy,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config_supplied,
        "memory_governance_strategy",
        MemoryGovernanceStrategyConfig.from_any(memory_governance_strategy) if memory_governance_strategy is not None and not isinstance(memory_governance_strategy, BaseMemoryGovernanceStrategy) else memory_governance_strategy,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config_supplied,
        "observability",
        ObservabilityConfig.from_any(observability) if observability is not None else None,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config_supplied,
        "default_knowledge_scope",
        list(knowledge_scope or []),
    )
    if rag_config is not None:
        resolved_runtime_config = _apply_if_unset(
            resolved_runtime_config,
            default_runtime_config,
            runtime_config_supplied,
            "rag_strategy",
            rag_config,
        )
        resolved_runtime_config = _apply_if_unset(
            resolved_runtime_config,
            default_runtime_config,
            runtime_config_supplied,
            "enable_retrieval",
            rag_config.mode != "off",
        )
    if overrides:
        resolved_runtime_config = resolved_runtime_config.model_copy(update=overrides)
    resolved_runtime_config = _finalize_runtime_config(resolved_runtime_config)

    selected_tools = ToolRegistry.empty()
    if enable_tools:
        selected_tools.extend(_coerce_tool_registry(tools))
        selected_tools.extend(
            _normalize_tool_bundles(
                tool_bundles,
                workspace_root=selected_workspace_root,
                sandbox=sandbox,
            )
        )

    selected_model, selected_model_config = _coerce_model_inputs(model)
    runtime_kwargs = {
        "model": selected_model,
        "model_config": selected_model_config,
        "tools": selected_tools,
        "skills": skills,
        "memory": memory if enable_memory else None,
        "knowledge_base": knowledge_base,
        "knowledge_paths": knowledge_paths,
        "knowledge_scope": knowledge_scope,
        "sandbox": sandbox,
        "config": resolved_runtime_config,
        "human_feedback": human_feedback,
    }
    agent = _create_agent_instance(workflow=workflow, **runtime_kwargs)
    facade_inputs = {
        "profile": profile,
        "name": name,
        "description": description,
        "enable_tools": enable_tools,
        "tools": sorted(getattr(selected_tools, "_tools", {}).keys()),
        "tool_bundles": tool_bundles,
        "enable_rag": rag_enabled,
        "knowledge_base": knowledge_base.__class__.__name__ if knowledge_base is not None else None,
        "knowledge_paths": [str(path) for path in knowledge_paths] if knowledge_paths else None,
        "knowledge_scope": knowledge_scope,
        "enable_memory": enable_memory,
        "workflow_attached": workflow is not None,
        "reasoning": resolved_reasoning,
        "orchestration_profile": orchestration_profile,
        "enable_streaming": bool(enable_streaming),
        "human_feedback": human_feedback is not None,
        "observability": observability,
        "runtime_config_supplied": runtime_config_supplied,
    }
    return agent.bind_blueprint(
        _build_single_agent_blueprint(
            name=name,
            description=description,
            profile=profile,
            runtime=agent.runtime,
            workflow=workflow,
            facade_inputs=facade_inputs,
            resolved_defaults=resolved_defaults,
        )
    )


def create_multi_agent(
    *,
    agents: list[Agent | dict[str, Any]] | None = None,
    roles: list[dict[str, Any]] | None = None,
    model: Any = None,
    system_prompt: str | None = None,
    workflow: Workflow | None = None,
    supervisor: Supervisor | None = None,
    routing_policy: SupervisorPolicy | None = None,
    topology: str | dict[str, Any] | None = None,
    shared_knowledge: KnowledgeBase | dict[str, Any] | None = None,
    shared_memory: MemoryManager | None = None,
    reasoning: ReasoningStrategyConfig | str | dict[str, Any] | None = None,
    cooperation_strategy: CooperationStrategyConfig | BaseCooperationStrategy | str | dict[str, Any] | None = None,
    aggregation_policy: AggregationPolicy | None = None,
    name: str | None = None,
    description: str | None = None,
    sandbox: SandboxManager | None = None,
    human_feedback: Any | None = None,
    observability: ObservabilityConfig | dict[str, Any] | None = None,
    runtime_config: RuntimeConfig | dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
) -> Agent:
    member_inputs = list(agents or []) + list(roles or [])
    if not member_inputs:
        raise ValueError("create_multi_agent(...) requires at least one member agent or role blueprint.")
    resolved_topology = topology["kind"] if isinstance(topology, dict) and "kind" in topology else (topology or "supervisor")
    if resolved_topology not in _ALLOWED_MULTI_AGENT_TOPOLOGIES:
        supported = ", ".join(sorted(_ALLOWED_MULTI_AGENT_TOPOLOGIES))
        raise ValueError(f"Unsupported multi-agent topology '{resolved_topology}'. Supported values: {supported}.")

    registry = AgentRegistry()
    members: list[dict[str, Any]] = []
    shared_knowledge_base = shared_knowledge if isinstance(shared_knowledge, KnowledgeBase) else None
    shared_knowledge_payload = shared_knowledge if isinstance(shared_knowledge, dict) else {}

    for index, item in enumerate(member_inputs, start=1):
        if isinstance(item, Agent):
            member_agent = item
            member_name = item.export_blueprint().get("name") or f"agent_{index}"
            member_role = member_name
            member_description = item.export_blueprint().get("description") or member_name
            member_capabilities = _normalize_capabilities(None, item)
            member_scope = item.runtime.config.default_knowledge_scope
        else:
            payload = dict(item)
            existing_agent = payload.pop("agent", None)
            role_name = payload.pop("role", None)
            member_name = payload.pop("name", None) or role_name or f"agent_{index}"
            member_role = role_name or member_name
            member_description = payload.pop("description", None) or f"{member_name} specialist"
            requested_capabilities = payload.pop("capabilities", None)
            if existing_agent is not None:
                member_agent = existing_agent
                member_scope = payload.pop("knowledge_scope", None) or member_agent.runtime.config.default_knowledge_scope
                member_capabilities = _normalize_capabilities(requested_capabilities, member_agent)
            else:
                if shared_memory is not None and "memory" not in payload:
                    payload["memory"] = shared_memory
                if shared_knowledge_base is not None and "knowledge_base" not in payload:
                    payload["knowledge_base"] = shared_knowledge_base
                if shared_knowledge_payload:
                    for key in ("knowledge_paths", "knowledge_scope", "rag", "enable_rag"):
                        payload.setdefault(key, shared_knowledge_payload.get(key))
                payload.setdefault("model", model)
                payload.setdefault("sandbox", sandbox)
                payload.setdefault("name", member_name)
                payload.setdefault("description", member_description)
                member_agent = create_agent(**payload)
                member_scope = payload.get("knowledge_scope") or member_agent.runtime.config.default_knowledge_scope
                member_capabilities = _normalize_capabilities(requested_capabilities, member_agent)

        spec = AgentSpec.assistant(
            member_name,
            description=member_description,
            capabilities=member_capabilities,
            tools=sorted(getattr(member_agent.runtime.tools, "_tools", {}).keys()),
            knowledge_scopes=list(member_scope or []),
        )
        registry.register(spec, member_agent)
        members.append(
            _agent_member_summary(
                member_agent,
                name=member_name,
                role=member_role,
                description=member_description,
                capabilities=member_capabilities,
                knowledge_scope=list(member_scope or []),
            )
        )

    resolved_supervisor = supervisor or Supervisor(registry=registry, policy=routing_policy)
    resolved_coordinator = Coordinator(
        execution_policy=ExecutionPolicy(),
        budget_manager=BudgetManager(),
        permission_manager=PermissionManager(),
        escalation_policy=EscalationPolicy(),
        aggregation_policy=aggregation_policy or AggregationPolicy(),
    )

    resolved_runtime_config = RuntimeConfig.from_any(runtime_config)
    default_runtime_config = RuntimeConfig()
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config is not None,
        "system_prompt",
        system_prompt,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config is not None,
        "reasoning_strategy",
        _resolve_reasoning_input(reasoning),
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config is not None,
        "cooperation_strategy",
        CooperationStrategyConfig.from_any(cooperation_strategy) if cooperation_strategy is not None and not isinstance(cooperation_strategy, BaseCooperationStrategy) else cooperation_strategy,
    )
    resolved_runtime_config = _apply_if_unset(
        resolved_runtime_config,
        default_runtime_config,
        runtime_config is not None,
        "observability",
        ObservabilityConfig.from_any(observability) if observability is not None else None,
    )
    if overrides:
        resolved_runtime_config = resolved_runtime_config.model_copy(update=overrides)
    resolved_runtime_config = _finalize_runtime_config(resolved_runtime_config)

    selected_model, selected_model_config = _coerce_model_inputs(model)
    if selected_model is None and selected_model_config is None and registry.list_specs():
        first_member_name = registry.list_specs()[0].name
        first_member = registry.get(first_member_name).agent
        selected_model = first_member.runtime.model
    runtime = _create_runtime_instance(
        model=selected_model,
        model_config=selected_model_config,
        memory=shared_memory,
        sandbox=sandbox,
        agent_registry=registry,
        supervisor=resolved_supervisor,
        coordinator=resolved_coordinator,
        config=resolved_runtime_config,
        human_feedback=human_feedback,
    )
    agent = Agent(runtime=runtime, workflow=workflow)
    return agent.bind_blueprint(
        {
            "facade": "create_multi_agent",
            "kind": "multi_agent",
            "name": name or "multi_agent_system",
            "description": description or "Multi-agent system assembled from create_agent members",
            "topology": resolved_topology,
            "members": members,
            "runtime": _runtime_summary(runtime),
            "workflow": _workflow_summary(workflow),
            "redaction_applied": not getattr(runtime.config, "unsafe_export", False),
            "resource_state": {"closed": getattr(runtime, "_closed", False), "background_managed": getattr(runtime, "_background_managed", False)},
            "facade_inputs": _safe_export(
                _compact_dict(
                    {
                        "member_count": len(member_inputs),
                        "shared_knowledge": shared_knowledge.__class__.__name__ if isinstance(shared_knowledge, KnowledgeBase) else shared_knowledge,
                        "shared_memory": shared_memory.__class__.__name__ if shared_memory is not None else None,
                        "reasoning": reasoning,
                        "cooperation_strategy": cooperation_strategy,
                        "topology": resolved_topology,
                        "workflow_attached": workflow is not None,
                    }
                )
            ),
            "resolved_defaults": {"topology": resolved_topology},
        }
    )
