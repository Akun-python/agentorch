from __future__ import annotations

import asyncio
import atexit
import contextlib
import threading
import weakref
from pathlib import Path
from typing import Any

from agentorch.agents import AgentCapability
from agentorch.config import ModelConfig, RuntimeConfig
from agentorch.knowledge import RagStrategyConfig
from agentorch.reasoning import ReasoningStrategyConfig
from agentorch.runtime import Agent, Runtime
from agentorch.runtime.agent import _runtime_summary, _safe_export, _workflow_summary
from agentorch.sandbox import SandboxManager
from agentorch.tools import BaseTool, ToolRegistry
from agentorch.workflow import Workflow


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
) -> RuntimeConfig:
    if value is None:
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
) -> ToolRegistry:
    if not tool_bundles:
        return ToolRegistry.empty()
    if tool_bundles is True:
        return ToolRegistry.with_bundles(
            workspace_root=workspace_root,
            sandbox=sandbox,
            include_execution=sandbox is not None,
        )
    payload = dict(tool_bundles)
    return ToolRegistry.with_bundles(
        workspace_root=payload.pop("workspace_root", workspace_root),
        sandbox=payload.pop("sandbox", sandbox),
        include_filesystem=payload.pop("include_filesystem", True),
        include_execution=payload.pop("include_execution", sandbox is not None),
        include_git=payload.pop("include_git", True),
        include_web=payload.pop("include_web", False),
        brave_api_key=payload.pop("brave_api_key", None),
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


def profile_defaults(profile: str, *, sandbox: SandboxManager | None) -> dict[str, Any]:
    normalized = (profile or "default").strip().lower()
    if normalized == "default":
        return {"orchestration_profile": "default_safe"}
    if normalized == "research":
        from agentorch.presets import build_deep_research_system_prompt

        return {
            "system_prompt": build_deep_research_system_prompt(),
            "orchestration_profile": "deep_research",
            "reasoning": ReasoningStrategyConfig.plan_execute(config={"max_planning_steps": 5, "max_execution_steps": 8}),
            "rag": RagStrategyConfig.for_hybrid(mount="inline", injection_policy="full_report", max_steps=4),
            "enable_rag": True,
        }
    if normalized == "coding":
        return {
            "system_prompt": (
                "You are a careful coding agent. Use tools when they improve accuracy, explain important tradeoffs, "
                "and prefer safe, minimal changes."
            ),
            "orchestration_profile": "coding_agent",
            "enable_tools": True,
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
            "orchestration_profile": "workflow_oriented",
            "reasoning": "react",
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
