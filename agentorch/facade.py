from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agentorch.agents import (
    AggregationPolicy,
    AgentRegistry,
    BudgetManager,
    Coordinator,
    EscalationPolicy,
    ExecutionPolicy,
    PermissionManager,
    Supervisor,
    SupervisorPolicy,
)
from agentorch.config import ModelConfig, ObservabilityConfig, RuntimeConfig
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.evolution import EvolutionConfig, EvolutionSession, SearchSpace
from agentorch.evolution.helpers import runtime_config_from_genome, workflow_from_genome
from agentorch.extensions import RuntimeExtension
from agentorch.knowledge import KnowledgeBase, RagStrategyConfig
from agentorch.memory import MemoryManager
from agentorch.models import (
    BaseModelAdapter,
    ImageGenerationCapableModelAdapter,
    SpeechCapableModelAdapter,
    VideoAnalysisCapableModelAdapter,
    create_model_adapter,
)
from agentorch.reasoning import ReasoningStrategyConfig
from agentorch.runtime import Agent, Runtime
from agentorch.runtime._export_support import _safe_export
from agentorch.sandbox import SandboxManager
from agentorch.skills import SkillRegistry
from agentorch.strategies import (
    ContextPolicy,
    CoordinationPolicy,
    MemoryEvaluator,
    MemoryPolicy,
    RoutePlanner,
    ContextSelector,
    StatePolicy,
)
from agentorch.tools import BaseTool, ToolRegistry
from agentorch.workflow import Workflow
from agentorch._facade_support import (
    BackgroundRuntimeBridge,
    build_facade_evolution_session as _build_facade_evolution_session,
    build_multi_agent_blueprint as _build_multi_agent_blueprint,
    build_single_agent_blueprint as _build_single_agent_blueprint,
    coerce_model_inputs as _coerce_model_inputs,
    coerce_tool_registry as _coerce_tool_registry,
    normalize_tool_bundles as _normalize_tool_bundles,
    profile_defaults as _profile_defaults,
    resolve_multi_agent_member as _resolve_multi_agent_member,
    resolve_facade_runtime_config as _resolve_facade_runtime_config,
    resolve_reasoning_input as _resolve_reasoning_input,
)

_ALLOWED_MULTI_AGENT_TOPOLOGIES = {"supervisor"}
_BACKGROUND_BRIDGE = BackgroundRuntimeBridge()


class _SupervisorRuntimeModelAdapter(BaseModelAdapter):
    """Internal placeholder model for supervisor-root runtimes.

    The coordinator runtime should not borrow a member model by default. That
    creates hidden ownership coupling and can close externally managed member
    resources when the team runtime shuts down.
    """

    def __init__(self) -> None:
        self.config = {"provider": "internal", "model": "supervisor-runtime-placeholder"}

    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise RuntimeError(
            "The root runtime of a multi-agent supervisor system does not support direct model generation "
            "without an explicit coordinator model."
        )


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
    sandbox: SandboxManager | None = None,
    enable_streaming: bool | None = None,
    human_feedback: Any | None = None,
    observability: ObservabilityConfig | dict[str, Any] | None = None,
    extensions: list[RuntimeExtension] | tuple[RuntimeExtension, ...] | None = None,
    skills: SkillRegistry | None = None,
    context_policy: ContextPolicy | dict[str, Any] | None = None,
    state_policy: StatePolicy | dict[str, Any] | None = None,
    coordination_policy: CoordinationPolicy | dict[str, Any] | None = None,
    memory_policy: MemoryPolicy | dict[str, Any] | None = None,
    context_selector: ContextSelector | None = None,
    route_planner: RoutePlanner | None = None,
    memory_evaluator: MemoryEvaluator | None = None,
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
            sandbox,
            enable_streaming,
            human_feedback,
            observability,
            extensions,
            skills,
            context_policy,
            state_policy,
            coordination_policy,
            memory_policy,
            context_selector,
            route_planner,
            memory_evaluator,
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
    if enable_rag is None and "enable_rag" in profile_defaults:
        enable_rag = bool(profile_defaults["enable_rag"])
        resolved_defaults["enable_rag"] = enable_rag
    if rag is None and "rag" in profile_defaults:
        rag = profile_defaults["rag"]
        resolved_defaults["rag"] = rag
    if reasoning is None and "reasoning" in profile_defaults:
        reasoning = profile_defaults["reasoning"]
        resolved_defaults["reasoning"] = reasoning
    if context_policy is None and "context_policy" in profile_defaults:
        context_policy = profile_defaults["context_policy"]
        resolved_defaults["context_policy"] = _safe_export(context_policy)
    if state_policy is None and "state_policy" in profile_defaults:
        state_policy = profile_defaults["state_policy"]
        resolved_defaults["state_policy"] = _safe_export(state_policy)
    if coordination_policy is None and "coordination_policy" in profile_defaults:
        coordination_policy = profile_defaults["coordination_policy"]
        resolved_defaults["coordination_policy"] = _safe_export(coordination_policy)
    if memory_policy is None and "memory_policy" in profile_defaults:
        memory_policy = profile_defaults["memory_policy"]
        resolved_defaults["memory_policy"] = _safe_export(memory_policy)

    if not enable_tools and (tools is not None or tool_bundles):
        raise ValueError("enable_tools=False conflicts with explicit tools or tool_bundles.")
    if enable_rag is False and any(item is not None for item in (knowledge_base, knowledge_paths, rag, knowledge_scope)):
        raise ValueError("enable_rag=False conflicts with knowledge_base, knowledge_paths, rag, or knowledge_scope.")
    if not enable_memory and memory is not None:
        raise ValueError("enable_memory=False conflicts with an explicit memory manager.")

    rag_enabled = bool(enable_rag) or knowledge_base is not None or bool(knowledge_paths) or rag is not None
    rag_config = None
    if rag_enabled:
        rag_config = RagStrategyConfig.from_any(rag or RagStrategyConfig.for_hybrid())
        if knowledge_scope and not rag_config.knowledge_scope:
            rag_config = rag_config.with_scope(*knowledge_scope)

    resolved_reasoning = _resolve_reasoning_input(reasoning, reasoning_framework)
    runtime_config_supplied = runtime_config is not None
    resolved_runtime_config = _resolve_facade_runtime_config(
        runtime_config,
        system_prompt=system_prompt,
        enable_streaming=enable_streaming,
        reasoning_strategy=resolved_reasoning,
        context_policy=context_policy,
        state_policy=state_policy,
        coordination_policy=coordination_policy,
        memory_policy=memory_policy,
        context_selector=context_selector,
        route_planner=route_planner,
        memory_evaluator=memory_evaluator,
        observability=observability,
        default_knowledge_scope=list(knowledge_scope or []),
        apply_default_knowledge_scope=True,
        rag_config=rag_config,
        overrides=overrides,
    )

    selected_model, selected_model_config = _coerce_model_inputs(model)
    include_media_tools = bool(enable_tools) and isinstance(tool_bundles, dict) and bool(tool_bundles.get("include_media"))
    if include_media_tools:
        if selected_model is None:
            selected_model = create_model_adapter(selected_model_config)
            selected_model_config = None
        if not any(
            isinstance(selected_model, capability)
            for capability in (
                SpeechCapableModelAdapter,
                ImageGenerationCapableModelAdapter,
                VideoAnalysisCapableModelAdapter,
            )
        ):
            raise ValueError(
                "tool_bundles.include_media requires a model with at least one media capability. "
                "Use OpenAIModel, OpenAICompatibleHTTPModel, or a custom media-capable adapter."
            )

    selected_tools = ToolRegistry.empty()
    if enable_tools:
        selected_tools.extend(_coerce_tool_registry(tools))
        selected_tools.extend(
            _normalize_tool_bundles(
                tool_bundles,
                workspace_root=selected_workspace_root,
                sandbox=sandbox,
                model=selected_model,
            )
        )

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
        "extensions": extensions,
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
        "context_policy": context_policy,
        "state_policy": state_policy,
        "coordination_policy": coordination_policy,
        "memory_policy": memory_policy,
        "enable_streaming": bool(enable_streaming),
        "human_feedback": human_feedback is not None,
        "observability": observability,
        "extensions": [extension.extension_name for extension in extensions] if extensions else None,
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
    context_policy: ContextPolicy | dict[str, Any] | None = None,
    state_policy: StatePolicy | dict[str, Any] | None = None,
    coordination_policy: CoordinationPolicy | dict[str, Any] | None = None,
    memory_policy: MemoryPolicy | dict[str, Any] | None = None,
    context_selector: ContextSelector | None = None,
    route_planner: RoutePlanner | None = None,
    memory_evaluator: MemoryEvaluator | None = None,
    aggregation_policy: AggregationPolicy | None = None,
    name: str | None = None,
    description: str | None = None,
    sandbox: SandboxManager | None = None,
    human_feedback: Any | None = None,
    observability: ObservabilityConfig | dict[str, Any] | None = None,
    extensions: list[RuntimeExtension] | tuple[RuntimeExtension, ...] | None = None,
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
    assembled_members = [
        _resolve_multi_agent_member(
            item,
            index=index,
            create_agent_fn=create_agent,
            model=model,
            sandbox=sandbox,
            shared_memory=shared_memory,
            shared_knowledge=shared_knowledge,
        )
        for index, item in enumerate(member_inputs, start=1)
    ]
    members = [entry.summary for entry in assembled_members]
    managed_member_agents = [entry.agent for entry in assembled_members if entry.managed]
    resolved_coordination = CoordinationPolicy.from_any(coordination_policy) if coordination_policy is not None else CoordinationPolicy()

    for entry in assembled_members:
        registry.register(entry.spec, entry.agent)

    resolved_supervisor = supervisor or Supervisor(registry=registry, policy=routing_policy)
    resolved_coordinator = Coordinator(
        execution_policy=ExecutionPolicy(
            allow_parallel=resolved_coordination.route_mode in {"distributed", "hybrid"},
            max_parallel_tasks=max(1, len(member_inputs)),
        ),
        budget_manager=BudgetManager(),
        permission_manager=PermissionManager(),
        escalation_policy=EscalationPolicy(),
        aggregation_policy=aggregation_policy or AggregationPolicy(),
    )

    resolved_runtime_config = _resolve_facade_runtime_config(
        runtime_config,
        system_prompt=system_prompt,
        reasoning_strategy=_resolve_reasoning_input(reasoning),
        context_policy=context_policy,
        state_policy=state_policy,
        coordination_policy=coordination_policy,
        memory_policy=memory_policy,
        context_selector=context_selector,
        route_planner=route_planner,
        memory_evaluator=memory_evaluator,
        observability=observability,
        overrides=overrides,
    )
    runtime_coordination = CoordinationPolicy.from_any(resolved_runtime_config.coordination_policy)
    resolved_coordinator.execution_policy.allow_parallel = runtime_coordination.route_mode in {"distributed", "hybrid"}
    resolved_coordinator.execution_policy.max_parallel_tasks = max(1, len(member_inputs))

    selected_model, selected_model_config = _coerce_model_inputs(model)
    if selected_model is None and selected_model_config is None and registry.list_specs():
        selected_model = _SupervisorRuntimeModelAdapter()
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
        extensions=extensions,
        managed_agents=managed_member_agents,
    )
    agent = Agent(runtime=runtime, workflow=workflow)
    return agent.bind_blueprint(
        _build_multi_agent_blueprint(
            name=name,
            description=description,
            topology=resolved_topology,
            members=members,
            runtime=runtime,
            workflow=workflow,
            member_count=len(member_inputs),
            shared_knowledge=shared_knowledge,
            shared_memory=shared_memory,
            reasoning=reasoning,
            context_policy=context_policy,
            state_policy=state_policy,
            coordination_policy=coordination_policy,
            memory_policy=memory_policy,
            extensions=extensions,
        )
    )


def create_agent_evolution(
    *,
    search_space: SearchSpace | dict[str, list[Any]],
    evaluator: Any,
    tasks: list[Any] | None = None,
    evolution_config: EvolutionConfig | None = None,
    workflow_templates: dict[str, Workflow | Any] | None = None,
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
    sandbox: SandboxManager | None = None,
    enable_streaming: bool | None = None,
    human_feedback: Any | None = None,
    observability: ObservabilityConfig | dict[str, Any] | None = None,
    extensions: list[RuntimeExtension] | tuple[RuntimeExtension, ...] | None = None,
    skills: SkillRegistry | None = None,
    context_policy: ContextPolicy | dict[str, Any] | None = None,
    state_policy: StatePolicy | dict[str, Any] | None = None,
    coordination_policy: CoordinationPolicy | dict[str, Any] | None = None,
    memory_policy: MemoryPolicy | dict[str, Any] | None = None,
    context_selector: ContextSelector | None = None,
    route_planner: RoutePlanner | None = None,
    memory_evaluator: MemoryEvaluator | None = None,
    runtime_config: RuntimeConfig | dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
) -> EvolutionSession[Agent]:
    base_runtime_config = RuntimeConfig.from_any(runtime_config)

    async def build_candidate(genome):
        return create_agent(
            model=model,
            profile=profile,
            system_prompt=system_prompt,
            name=name,
            description=description,
            enable_tools=enable_tools,
            tools=tools,
            tool_bundles=tool_bundles,
            workspace_root=workspace_root,
            enable_rag=enable_rag,
            knowledge_base=knowledge_base,
            knowledge_paths=knowledge_paths,
            rag=rag,
            knowledge_scope=knowledge_scope,
            enable_memory=enable_memory,
            memory=memory,
            workflow=workflow_from_genome(genome, base=workflow, templates=workflow_templates),
            reasoning=reasoning,
            reasoning_framework=reasoning_framework,
            sandbox=sandbox,
            enable_streaming=enable_streaming,
            human_feedback=human_feedback,
            observability=observability,
            extensions=extensions,
            skills=skills,
            context_policy=context_policy,
            state_policy=state_policy,
            coordination_policy=coordination_policy,
            memory_policy=memory_policy,
            context_selector=context_selector,
            route_planner=route_planner,
            memory_evaluator=memory_evaluator,
            runtime_config=runtime_config_from_genome(genome, base=base_runtime_config),
            overrides=overrides,
        )

    return _build_facade_evolution_session(
        search_space=search_space,
        evaluator=evaluator,
        tasks=tasks,
        evolution_config=evolution_config,
        candidate_kind="agent",
        builder=build_candidate,
    )


def create_multi_agent_evolution(
    *,
    search_space: SearchSpace | dict[str, list[Any]],
    evaluator: Any,
    tasks: list[Any] | None = None,
    evolution_config: EvolutionConfig | None = None,
    workflow_templates: dict[str, Workflow | Any] | None = None,
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
    context_policy: ContextPolicy | dict[str, Any] | None = None,
    state_policy: StatePolicy | dict[str, Any] | None = None,
    coordination_policy: CoordinationPolicy | dict[str, Any] | None = None,
    memory_policy: MemoryPolicy | dict[str, Any] | None = None,
    context_selector: ContextSelector | None = None,
    route_planner: RoutePlanner | None = None,
    memory_evaluator: MemoryEvaluator | None = None,
    aggregation_policy: AggregationPolicy | None = None,
    name: str | None = None,
    description: str | None = None,
    sandbox: SandboxManager | None = None,
    human_feedback: Any | None = None,
    observability: ObservabilityConfig | dict[str, Any] | None = None,
    extensions: list[RuntimeExtension] | tuple[RuntimeExtension, ...] | None = None,
    runtime_config: RuntimeConfig | dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
) -> EvolutionSession[Agent]:
    base_runtime_config = RuntimeConfig.from_any(runtime_config)

    async def build_candidate(genome):
        return create_multi_agent(
            agents=agents,
            roles=roles,
            model=model,
            system_prompt=system_prompt,
            workflow=workflow_from_genome(genome, base=workflow, templates=workflow_templates),
            supervisor=supervisor,
            routing_policy=routing_policy,
            topology=topology,
            shared_knowledge=shared_knowledge,
            shared_memory=shared_memory,
            reasoning=reasoning,
            context_policy=context_policy,
            state_policy=state_policy,
            coordination_policy=coordination_policy,
            memory_policy=memory_policy,
            context_selector=context_selector,
            route_planner=route_planner,
            memory_evaluator=memory_evaluator,
            aggregation_policy=aggregation_policy,
            name=name,
            description=description,
            sandbox=sandbox,
            human_feedback=human_feedback,
            observability=observability,
            extensions=extensions,
            runtime_config=runtime_config_from_genome(genome, base=base_runtime_config),
            overrides=overrides,
        )

    return _build_facade_evolution_session(
        search_space=search_space,
        evaluator=evaluator,
        tasks=tasks,
        evolution_config=evolution_config,
        candidate_kind="multi_agent",
        builder=build_candidate,
    )
