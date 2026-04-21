from __future__ import annotations

from pathlib import Path
from typing import Any

from agentorch import Agent, AgentCapability, AgentRegistry, AgentSpec, Runtime, Supervisor
from agentorch.config import ContextPolicy, CoordinationPolicy, MemoryConfig, MemoryPolicy, RuntimeConfig, StatePolicy
from agentorch.memory import MemoryManager
from agentorch.models import OpenAIModel
from experiments.elephant_context import build_elephant_runtime_config

from .config import ExperimentConfig
from .model_presets import resolve_model_runtime_profile
from .models import MockBalancedModel, MockEchoModel, MockFailureModel, MockJudgeModel, MockStrongModel, MockToolModel, MockWeakModel
from .tooling import build_tool_registry


def build_model(model_name: str):
    if model_name == "mock:echo":
        return MockEchoModel()
    if model_name == "mock:tool":
        return MockToolModel()
    if model_name == "mock:fail":
        return MockFailureModel()
    if model_name == "mock:judge":
        return MockJudgeModel()
    if model_name == "mock:strong":
        return MockStrongModel()
    if model_name == "mock:balanced":
        return MockBalancedModel()
    if model_name == "mock:weak":
        return MockWeakModel()
    return OpenAIModel(model=model_name, **resolve_model_runtime_profile(model_name))


def build_runtime_variant(
    config: ExperimentConfig,
    *,
    workspace_root: Path,
    output_dir: Path,
) -> tuple[Runtime, dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tools, tool_meta = build_tool_registry(enable_live_web_search=config.enable_live_web_search)
    sqlite_path = output_dir / "observability.db"
    memory_dir = output_dir / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_manager = MemoryManager(
        config=MemoryConfig(
            checkpoint_path=memory_dir / "checkpoints.db",
            record_path=memory_dir / "records.db",
        )
    )

    if config.enable_multi_agent:
        runtime_config = build_elephant_runtime_config(
            hybrid_selection=False,
            distributed=not config.enable_elephant_attention,
            char_budget=config.prompt_budget,
            max_steps=config.max_steps,
            observability={
                "enabled": config.enable_observability,
                "sqlite_path": sqlite_path,
                "console_mode": "silent",
                "capture_todos": True,
            },
            enable_retrieval=config.enable_retrieval,
        )
    else:
        runtime_config = RuntimeConfig.agent(
            max_steps=config.max_steps,
            context_policy=ContextPolicy(
                char_budget=config.prompt_budget,
                selection_mode="rule" if config.enable_context_compression else "rule",
                overflow_action="compress" if config.enable_context_compression else "drop_low_priority",
            ),
            state_policy=StatePolicy(retention_mode="state_plus_memory" if config.enable_long_horizon_attention else "window_only"),
            coordination_policy=CoordinationPolicy.distributed(),
            memory_policy=(
                MemoryPolicy.long_horizon()
                if config.enable_seagull_memory
                else MemoryPolicy(thresholds_and_weights={"allow_cross_thread_recall": False, "recall_top_k": 2})
            ),
            observability={
                "enabled": config.enable_observability,
                "sqlite_path": sqlite_path,
                "console_mode": "silent",
                "capture_todos": True,
            },
            enable_retrieval=config.enable_retrieval,
        )

    agent_registry = AgentRegistry()
    supervisor = None
    if config.enable_multi_agent:
        specialist_specs = [
            (
                "planner",
                "Planning specialist",
                ["plan", "research"],
                [AgentCapability.PLAN, AgentCapability.RETRIEVE],
                ["planning", "research"],
            ),
            (
                "reviewer",
                "Review specialist",
                ["review", "quality"],
                [AgentCapability.AGGREGATE],
                ["quality", "research"],
            ),
            (
                "analyst",
                "Analysis specialist",
                ["analysis", "metrics"],
                [AgentCapability.RETRIEVE, AgentCapability.REVIEW],
                ["analysis", "metrics"],
            ),
            (
                "writer",
                "Writing specialist",
                ["writing", "synthesis"],
                [AgentCapability.AGGREGATE],
                ["writing", "synthesis"],
            ),
        ]
        for name, description, tags, capabilities, scopes in specialist_specs[: max(1, config.agent_count)]:
            agent_registry.register(
                AgentSpec(
                    name=name,
                    description=description,
                    tags=tags,
                    capabilities=capabilities,
                    allowed_knowledge_scopes=scopes,
                ),
                Agent(runtime=Runtime(model=build_model(config.model_name), tools=tools, memory=memory_manager, config=runtime_config)),
            )
        supervisor = Supervisor(registry=agent_registry)

    runtime = Runtime(
        model=build_model(config.model_name),
        tools=tools,
        memory=memory_manager,
        config=runtime_config,
        agent_registry=agent_registry if config.enable_multi_agent else None,
        supervisor=supervisor,
    )
    return runtime, {
        **tool_meta,
        "sqlite_path": str(sqlite_path) if config.enable_observability else None,
        "memory_record_path": str(memory_dir / "records.db"),
        "method_flags": {
            "elephant_attention": config.enable_elephant_attention,
            "seagull_memory": config.enable_seagull_memory,
            "long_horizon_attention": config.enable_long_horizon_attention,
            "context_compression": config.enable_context_compression,
            "observability": config.enable_observability,
            "multi_agent": config.enable_multi_agent,
            "agent_count": config.agent_count,
            "history_length": config.history_length,
        },
    }
