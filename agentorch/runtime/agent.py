from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from agentorch.core import RunResult, RunStreamEvent
from agentorch.parsing import OutputParser, ParsedRunResult, TextParser
from agentorch.workflow import Workflow

from .runtime import Runtime
from agentorch.security import RedactionConfig, sanitize_for_export


def _safe_export(value: Any, *, config: RedactionConfig | dict[str, object] | None = None, unsafe: bool = False) -> Any:
    return sanitize_for_export(value, config=config, unsafe=unsafe)


def _workflow_summary(workflow: Workflow | None) -> dict[str, Any] | None:
    if workflow is None:
        return None
    return {
        "entry_node": workflow.entry_node,
        "max_steps": workflow.max_steps,
        "nodes": [
            {"id": node.id, "kind": node.kind, "config": _safe_export(node.config)}
            for node in workflow.nodes
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "kind": edge.kind,
                "condition": edge.condition,
            }
            for edge in workflow.edges
        ],
    }


def _tool_names(runtime: Runtime) -> list[str]:
    tool_index = getattr(runtime.tools, "_tools", {})
    return sorted(tool_index.keys())


def _skill_names(runtime: Runtime) -> list[str]:
    skill_index = getattr(runtime.skills, "_skills", {})
    return sorted(skill_index.keys())


def _model_summary(runtime: Runtime) -> dict[str, Any]:
    model = runtime.model
    config = getattr(model, "config", None)
    return {
        "adapter": model.__class__.__name__,
        "config": _safe_export(config, config=runtime.config.redaction, unsafe=runtime.config.unsafe_export) if config is not None else None,
    }


def _resolved_strategy_summary(runtime: Runtime) -> dict[str, Any]:
    config = runtime.config
    return {
        "orchestration_profile": config.orchestration_profile,
        "context": _safe_export(config.context_strategy, config=config.redaction, unsafe=config.unsafe_export),
        "long_horizon": _safe_export(config.long_horizon_strategy, config=config.redaction, unsafe=config.unsafe_export),
        "cooperation": _safe_export(config.cooperation_strategy, config=config.redaction, unsafe=config.unsafe_export),
        "memory_governance": _safe_export(config.memory_governance_strategy, config=config.redaction, unsafe=config.unsafe_export),
    }


def _runtime_summary(runtime: Runtime) -> dict[str, Any]:
    return {
        "config": _safe_export(runtime.config, config=runtime.config.redaction, unsafe=runtime.config.unsafe_export),
        "model": _model_summary(runtime),
        "tools": _tool_names(runtime),
        "skills": _skill_names(runtime),
        "knowledge_base": runtime.knowledge_base.__class__.__name__ if runtime.knowledge_base is not None else None,
        "memory": runtime.memory.__class__.__name__ if runtime.memory is not None else None,
        "sandbox": runtime.sandbox.__class__.__name__ if runtime.sandbox is not None else None,
        "has_supervisor": runtime.supervisor is not None,
        "registered_agents": [spec.name for spec in runtime.agent_registry.list_specs()],
        "resolved_strategies": _resolved_strategy_summary(runtime),
    }


def _resource_state(runtime: Runtime) -> dict[str, Any]:
    return {
        "closed": getattr(runtime, "_closed", False),
        "has_sandbox": runtime.sandbox is not None,
        "has_observability": runtime.observability.enabled,
        "background_managed": getattr(runtime, "_background_managed", False),
    }


def _core_assembly(runtime: Runtime, workflow: Workflow | None, blueprint: dict[str, Any] | None = None) -> dict[str, Any]:
    assembly = {
        "agent_constructor": "Agent(runtime=..., workflow=...)",
        "runtime_constructor": "Runtime.create(...)",
        "runtime": _runtime_summary(runtime),
        "workflow": _workflow_summary(workflow),
        "redaction_applied": not getattr(runtime.config, "unsafe_export", False),
        "resource_state": _resource_state(runtime),
    }
    if blueprint is not None:
        assembly["facade"] = blueprint.get("facade", "core")
        assembly["kind"] = blueprint.get("kind", "single_agent")
        if blueprint.get("members"):
            assembly["members"] = [
                {
                    "name": member.get("name"),
                    "role": member.get("role"),
                    "description": member.get("description"),
                    "capabilities": member.get("capabilities"),
                    "knowledge_scope": member.get("knowledge_scope"),
                }
                for member in blueprint["members"]
            ]
        if runtime.supervisor is not None:
            assembly["supervisor_constructor"] = "Supervisor(registry=...)"
            assembly["registry_constructor"] = "AgentRegistry().register(...)"
    elif runtime.supervisor is not None:
        assembly["kind"] = "multi_agent"
        assembly["supervisor_constructor"] = "Supervisor(registry=...)"
        assembly["registry_constructor"] = "AgentRegistry().register(...)"
    else:
        assembly["kind"] = "single_agent"
    return assembly


class Agent:
    @classmethod
    async def acreate(cls, *, workflow: Workflow | None = None, **runtime_kwargs: Any) -> "Agent":
        runtime = await Runtime.acreate(**runtime_kwargs)
        return cls(runtime=runtime, workflow=workflow)

    @classmethod
    def create(cls, *, workflow: Workflow | None = None, **runtime_kwargs: Any) -> "Agent":
        runtime = Runtime.create(**runtime_kwargs)
        return cls(runtime=runtime, workflow=workflow)

    def __init__(self, *, runtime: Runtime, workflow: Workflow | None = None) -> None:
        self.runtime = runtime
        self.workflow = workflow
        self._assembly_blueprint: dict[str, Any] | None = None

    def run(
        self,
        user_input: str,
        *,
        thread_id: str,
        metadata: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> Any:
        return self.runtime.run(
            user_input,
            thread_id=thread_id,
            workflow=self.workflow,
            metadata=metadata,
            stream=stream,
        )

    def run_sync(
        self,
        user_input: str,
        *,
        thread_id: str,
        metadata: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> RunResult:
        if stream:
            raise RuntimeError("Agent.run_sync() does not support stream=True. Use 'async for event in agent.run(..., stream=True)' instead.")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(user_input, thread_id=thread_id, metadata=metadata, stream=False))
        raise RuntimeError(
            "Agent.run_sync() cannot be used inside a running event loop such as Jupyter. "
            "Use 'await agent.run(...)' in notebooks and async applications."
        )

    async def run_parsed(
        self,
        user_input: str,
        *,
        thread_id: str,
        parser: OutputParser[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedRunResult[Any]:
        selected_parser = parser or TextParser()
        prompt = selected_parser.with_prompt(user_input)
        raw = await self.run(prompt, thread_id=thread_id, metadata=metadata, stream=False)
        parsed = await selected_parser.parse(raw.output_text)
        return ParsedRunResult(raw=raw, parsed=parsed, parser_name=selected_parser.__class__.__name__)

    def run_parsed_sync(
        self,
        user_input: str,
        *,
        thread_id: str,
        parser: OutputParser[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedRunResult[Any]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_parsed(user_input, thread_id=thread_id, parser=parser, metadata=metadata))
        raise RuntimeError(
            "Agent.run_parsed_sync() cannot be used inside a running event loop such as Jupyter. "
            "Use 'await agent.run_parsed(...)' in notebooks and async applications."
        )

    def bind_blueprint(self, blueprint: dict[str, Any]) -> "Agent":
        self._assembly_blueprint = _safe_export(blueprint, config=self.runtime.config.redaction, unsafe=self.runtime.config.unsafe_export)
        return self

    def export_config(self) -> dict[str, Any]:
        base = {
            "model": _model_summary(self.runtime),
            "runtime": _safe_export(self.runtime.config, config=self.runtime.config.redaction, unsafe=self.runtime.config.unsafe_export),
            "workflow": _workflow_summary(self.workflow),
            "redaction_applied": not getattr(self.runtime.config, "unsafe_export", False),
            "resource_state": _resource_state(self.runtime),
        }
        if self._assembly_blueprint is not None:
            base["facade"] = self._assembly_blueprint.get("facade")
        return base

    def export_blueprint(self) -> dict[str, Any]:
        if self._assembly_blueprint is not None:
            return _safe_export(self._assembly_blueprint, config=self.runtime.config.redaction, unsafe=self.runtime.config.unsafe_export)
        return {
            "facade": "core",
            "kind": "multi_agent" if self.runtime.supervisor is not None else "single_agent",
            "runtime": _runtime_summary(self.runtime),
            "workflow": _workflow_summary(self.workflow),
            "redaction_applied": not getattr(self.runtime.config, "unsafe_export", False),
            "resource_state": _resource_state(self.runtime),
        }

    def inspect(self) -> dict[str, Any]:
        blueprint = self.export_blueprint()
        blueprint["config"] = self.export_config()
        return blueprint

    def export_core_assembly(self) -> dict[str, Any]:
        return _core_assembly(self.runtime, self.workflow, self._assembly_blueprint)

    async def aclose(self) -> None:
        await self.runtime.aclose()

    def close(self) -> None:
        self.runtime.close()

    def describe(self) -> str:
        blueprint = self.export_blueprint()
        runtime_summary = blueprint.get("runtime", {})
        lines = [
            f"facade={blueprint.get('facade', 'core')}",
            f"kind={blueprint.get('kind', 'single_agent')}",
            f"model={runtime_summary.get('model', {}).get('adapter', self.runtime.model.__class__.__name__)}",
            f"tools={', '.join(runtime_summary.get('tools', [])) or 'none'}",
        ]
        strategy_summary = runtime_summary.get("resolved_strategies", {})
        context_strategy = strategy_summary.get("context") or {}
        memory_strategy = strategy_summary.get("memory_governance") or {}
        if context_strategy.get("kind"):
            lines.append(f"context_strategy={context_strategy['kind']}")
        if memory_strategy.get("kind"):
            lines.append(f"memory_governance={memory_strategy['kind']}")
        if runtime_summary.get("registered_agents"):
            lines.append(f"registered_agents={', '.join(runtime_summary['registered_agents'])}")
        if blueprint.get("members"):
            member_names = [member.get("name", "unnamed") for member in blueprint["members"]]
            lines.append(f"members={', '.join(member_names)}")
        if self.workflow is not None:
            lines.append(f"workflow_nodes={len(self.workflow.nodes)}")
        if blueprint.get("profile"):
            lines.append(f"profile={blueprint['profile']}")
        return "\n".join(lines)
