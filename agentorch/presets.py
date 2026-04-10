from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentorch.config import RuntimeConfig
from agentorch.knowledge import RagStrategyConfig
from agentorch.reasoning import ReasoningStrategyConfig
from agentorch.runtime import Agent, Runtime
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
from agentorch.tools import BaseTool, ToolRegistry, create_brave_search_tool
from agentorch.workflow import Workflow


def build_deep_research_system_prompt() -> str:
    return (
        "You are a deep research agent. Break complex questions into sub-questions, gather evidence from local knowledge "
        "and web search when available, compare competing claims, surface uncertainty, and produce a well-structured answer. "
        "Prefer explicit evidence over speculation. When retrieval coverage is incomplete, say what is still missing. "
        "If tools are available, use them deliberately to improve factual grounding."
    )


class DeepResearchAgentConfig(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    system_prompt: str = Field(default_factory=build_deep_research_system_prompt)
    orchestration_profile: str | None = "deep_research"
    reasoning_strategy: ReasoningStrategyConfig = Field(
        default_factory=lambda: ReasoningStrategyConfig.plan_execute(
            config={"max_planning_steps": 5, "max_execution_steps": 8}
        )
    )
    rag_strategy: RagStrategyConfig = Field(
        default_factory=lambda: RagStrategyConfig.for_hybrid(
            mount="inline",
            injection_policy="full_report",
            max_steps=4,
        )
    )
    context_strategy: ContextStrategyConfig | BaseContextStrategy | None = Field(
        default_factory=lambda: ContextStrategyConfig.compact(include_retrieval_evidence=True, include_retrieval_citations=True)
    )
    long_horizon_strategy: LongHorizonStrategyConfig | BaseLongHorizonStrategy | None = Field(
        default_factory=LongHorizonStrategyConfig.long_running_safe
    )
    cooperation_strategy: CooperationStrategyConfig | BaseCooperationStrategy | None = Field(
        default_factory=CooperationStrategyConfig.matriarchal
    )
    memory_governance_strategy: MemoryGovernanceStrategyConfig | BaseMemoryGovernanceStrategy | None = Field(
        default_factory=MemoryGovernanceStrategyConfig.default
    )
    knowledge_scope: list[str] = Field(default_factory=list)
    include_web_search: bool = True
    include_workspace_tools: bool = False
    include_filesystem_tools: bool = True
    include_git_tools: bool = False
    include_execution_tools: bool = False
    workspace_root: str | Path | None = None
    brave_api_key: str | None = None
    web_search: dict[str, Any] | None = None

    @classmethod
    def from_any(cls, value: "DeepResearchAgentConfig | dict[str, Any] | None", **overrides: Any) -> "DeepResearchAgentConfig":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        if overrides:
            return base.model_copy(update=overrides)
        return base

    def runtime_config(self) -> RuntimeConfig:
        rag = self.rag_strategy
        if self.knowledge_scope and not rag.knowledge_scope:
            rag = rag.with_scope(*self.knowledge_scope)
        return RuntimeConfig.agent(
            system_prompt=self.system_prompt,
            reasoning=self.reasoning_strategy,
            rag=rag,
            orchestration_profile=self.orchestration_profile,
            context_strategy=self.context_strategy,
            long_horizon_strategy=self.long_horizon_strategy,
            cooperation_strategy=self.cooperation_strategy,
            memory_governance_strategy=self.memory_governance_strategy,
            default_knowledge_scope=self.knowledge_scope,
        )


def _coerce_tool_registry(
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


class DeepResearchAgent(Agent):
    @classmethod
    async def acreate(
        cls,
        *,
        config: DeepResearchAgentConfig | dict[str, Any] | None = None,
        workflow: Workflow | None = None,
        tools: ToolRegistry | list[BaseTool] | tuple[BaseTool, ...] | None = None,
        custom_tools: list[BaseTool] | tuple[BaseTool, ...] | None = None,
        sandbox=None,
        knowledge_base=None,
        knowledge_paths: list[str | Path] | None = None,
        knowledge_assets: list[Any] | None = None,
        knowledge_documents: list[Any] | None = None,
        model=None,
        model_config=None,
        **runtime_kwargs: Any,
    ) -> "DeepResearchAgent":
        resolved = DeepResearchAgentConfig.from_any(config)

        merged_tools = _coerce_tool_registry(tools)
        merged_tools.extend(_coerce_tool_registry(custom_tools))

        if resolved.include_workspace_tools:
            merged_tools.extend(
                ToolRegistry.with_bundles(
                    workspace_root=resolved.workspace_root or Path.cwd(),
                    sandbox=sandbox,
                    include_filesystem=resolved.include_filesystem_tools,
                    include_execution=resolved.include_execution_tools,
                    include_git=resolved.include_git_tools,
                    include_web=False,
                )
            )

        web_search_config = dict(resolved.web_search or {})
        web_search_enabled = bool(
            web_search_config.get("enabled", resolved.include_web_search)
        )
        web_search_provider = web_search_config.get("provider", "brave")
        web_search_api_key = web_search_config.get("api_key", resolved.brave_api_key)
        if web_search_enabled:
            if web_search_provider != "brave":
                raise ValueError(
                    f"Unsupported web search provider '{web_search_provider}'. "
                    "Currently only 'brave' is supported."
                )
            merged_tools.register(create_brave_search_tool(api_key=web_search_api_key))

        runtime = await Runtime.acreate(
            model=model,
            model_config=model_config,
            tools=merged_tools,
            sandbox=sandbox,
            knowledge_base=knowledge_base,
            knowledge_paths=knowledge_paths,
            knowledge_assets=knowledge_assets,
            knowledge_documents=knowledge_documents,
            knowledge_scope=resolved.knowledge_scope,
            config=resolved.runtime_config(),
            **runtime_kwargs,
        )
        return cls(runtime=runtime, workflow=workflow)

    @classmethod
    def create(cls, **kwargs: Any) -> "DeepResearchAgent":
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(cls.acreate(**kwargs))
        raise RuntimeError(
            "DeepResearchAgent.create() cannot be used inside a running event loop. "
            "Use 'await DeepResearchAgent.acreate(...)' in async applications and notebooks."
        )
