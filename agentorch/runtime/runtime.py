from __future__ import annotations

import contextlib
import json
import uuid
import asyncio
import inspect
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

from agentorch.agents import (
    AgentRegistry,
    AgentResult,
    Coordinator,
    Handoff,
    SharedNote,
    Supervisor,
    TaskPacket,
    TaskStatus,
)
from agentorch.config import ModelConfig, ObservabilityConfig, RuntimeConfig, validate_supported_python
from agentorch.core import (
    CompactionDecision,
    ContextEnvelope,
    ContextSegment,
    Message,
    ModelRequest,
    ModelResponse,
    PromptContext,
    RunResult,
    RunStreamEvent,
    SalienceReport,
    SegmentScore,
    ToolExecutionResult,
    UsageInfo,
)
from agentorch.extensions import ExtensionManager, HandoffHookContext, RunHookContext, RuntimeExtension, SupervisorPlanHookContext
from agentorch.feedback import HumanFeedbackManager
from agentorch.knowledge import (
    BaseRetriever,
    Citation,
    ClassicRetriever,
    DeliberativeRetriever,
    IndexedKnowledgeBase,
    KnowledgeAsset,
    KnowledgeBase,
    RAGContextBuilder,
    RagStrategyConfig,
    RetrievalIntent,
    RetrievalMode,
    RetrievalPlan,
    RetrievalQuery,
    RetrievalReport,
    RetrievalStep,
    RetrievedEvidence,
    HybridRetriever,
    create_rag_retriever,
)
from agentorch.memory import MemoryManager, MemoryRecord
from agentorch.models import BaseModelAdapter, OpenAIModel, create_model_adapter
from agentorch.observability import ConsoleEventSink, EventBus, ObservabilityManager, SQLiteEventStore, Tracer, UsageTracker
from agentorch.prompts import PromptBuilder
from agentorch.reasoning import BasePolicy, BaseReasoningFramework, LegacyPolicyAdapter, ReactPolicy, ReasoningSessionContext, ReasoningStrategyConfig
from agentorch.security import shape_payload
from agentorch.runtime.context_compaction import (
    build_handoff_capsule,
    compact_task_packet,
    trim_message_content,
)
from agentorch.runtime.context_kernel import ContextKernel
from agentorch.runtime.workflow_execution import execute_runtime_workflow
from agentorch.sandbox import SandboxManager
from agentorch.skills import SkillLoader, SkillRegistry
from agentorch.skills import SkillRoutingConfig
from agentorch.strategies import (
    ContextPolicy,
    CoordinationPolicy,
    DefaultContextSelector,
    DefaultMemoryEvaluator,
    DefaultRoutePlanner,
    MemoryPolicy,
    StatePolicy,
)
from agentorch.tools import BaseTool, ToolError, ToolRegistry
from agentorch.tools.knowledge import (
    create_deliberative_retrieve_tool,
    create_open_retrieved_evidence_tool,
    create_search_knowledge_assets_tool,
)
from agentorch.workflow import Workflow


class Runtime:
    @classmethod
    async def acreate(
        cls,
        *,
        model: BaseModelAdapter | None = None,
        model_config: ModelConfig | dict[str, Any] | str | None = None,
        tools: ToolRegistry | list[BaseTool] | tuple[BaseTool, ...] | None = None,
        custom_tools: list[BaseTool] | tuple[BaseTool, ...] | None = None,
        tool_bundles: bool = False,
        include_web_tools: bool = False,
        web_search_api_key: str | None = None,
        workspace_root: str | Path | None = None,
        skills: SkillRegistry | None = None,
        memory: MemoryManager | None = None,
        retriever: BaseRetriever | None = None,
        knowledge_base: KnowledgeBase | None = None,
        knowledge_paths: list[str | Path] | None = None,
        knowledge_assets: list[KnowledgeAsset] | None = None,
        knowledge_documents: list[Any] | None = None,
        knowledge_scope: list[str] | None = None,
        sandbox: SandboxManager | None = None,
        agent_registry: AgentRegistry | None = None,
        supervisor: Supervisor | None = None,
        coordinator: Coordinator | None = None,
        prompt_builder: PromptBuilder | None = None,
        policy: BasePolicy | BaseReasoningFramework | None = None,
        config: RuntimeConfig | dict[str, Any] | None = None,
        tracer: Tracer | None = None,
        human_feedback: HumanFeedbackManager | None = None,
        extensions: ExtensionManager | list[RuntimeExtension] | tuple[RuntimeExtension, ...] | None = None,
        managed_agents: list[Any] | tuple[Any, ...] | None = None,
    ) -> "Runtime":
        runtime_config = RuntimeConfig.from_any(config)
        selected_model = model or create_model_adapter(model_config)
        skill_root = Path(workspace_root or Path.cwd()) / ".skills"
        selected_skills = skills or SkillRegistry()
        for discovered_skill in SkillLoader().discover(skill_root):
            selected_skills.register(discovered_skill)
        selected_tools = cls._coerce_tool_registry(tools)
        selected_tools.extend(cls._coerce_tool_registry(custom_tools))
        if not selected_tools.list_specs():
            if tool_bundles:
                selected_tools = ToolRegistry.with_bundles(
                    workspace_root=workspace_root or Path.cwd(),
                    sandbox=sandbox,
                    include_execution=sandbox is not None,
                    include_web=include_web_tools,
                    brave_api_key=web_search_api_key,
                )
            else:
                selected_tools = ToolRegistry()
        elif include_web_tools:
            selected_tools.extend(
                ToolRegistry.with_bundles(
                    workspace_root=workspace_root or Path.cwd(),
                    sandbox=sandbox,
                    include_filesystem=False,
                    include_execution=False,
                    include_git=False,
                    include_web=True,
                    brave_api_key=web_search_api_key,
                )
            )
        selected_knowledge_base = knowledge_base
        if selected_knowledge_base is None and any((knowledge_paths, knowledge_assets, knowledge_documents)):
            selected_knowledge_base = IndexedKnowledgeBase()
        if isinstance(selected_knowledge_base, IndexedKnowledgeBase):
            if knowledge_paths:
                await selected_knowledge_base.ingest_paths(list(knowledge_paths), scopes=knowledge_scope)
            if knowledge_assets:
                await selected_knowledge_base.ingest_assets(list(knowledge_assets))
            if knowledge_documents:
                await selected_knowledge_base.ingest(list(knowledge_documents))
        return cls(
            model=selected_model,
            tools=selected_tools,
            skills=selected_skills,
            memory=memory,
            retriever=retriever,
            knowledge_base=selected_knowledge_base,
            sandbox=sandbox,
            agent_registry=agent_registry,
            supervisor=supervisor,
            coordinator=coordinator,
            prompt_builder=prompt_builder,
            policy=policy,
            config=runtime_config,
            tracer=tracer,
            human_feedback=human_feedback,
            extensions=extensions,
            managed_agents=managed_agents,
        )

    @staticmethod
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

    @classmethod
    def create(cls, **kwargs: Any) -> "Runtime":
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(cls.acreate(**kwargs))
        raise RuntimeError(
            "Runtime.create() cannot be used inside a running event loop. "
            "Use 'await Runtime.acreate(...)' in async applications and notebooks."
        )

    def __init__(
        self,
        *,
        model: BaseModelAdapter,
        tools: ToolRegistry | None = None,
        skills: SkillRegistry | None = None,
        memory: MemoryManager | None = None,
        retriever: BaseRetriever | None = None,
        knowledge_base: KnowledgeBase | None = None,
        sandbox: SandboxManager | None = None,
        agent_registry: AgentRegistry | None = None,
        supervisor: Supervisor | None = None,
        coordinator: Coordinator | None = None,
        prompt_builder: PromptBuilder | None = None,
        policy: BasePolicy | None = None,
        config: RuntimeConfig | None = None,
        tracer: Tracer | None = None,
        human_feedback: HumanFeedbackManager | None = None,
        extensions: ExtensionManager | list[RuntimeExtension] | tuple[RuntimeExtension, ...] | None = None,
        managed_agents: list[Any] | tuple[Any, ...] | None = None,
    ) -> None:
        validate_supported_python()
        self.model = model
        self.tools = tools or ToolRegistry()
        self.skills = skills or SkillRegistry()
        self.memory = memory or MemoryManager()
        self.retriever = retriever or (knowledge_base.get_retriever() if knowledge_base is not None else None)
        self.knowledge_base = knowledge_base
        self.sandbox = sandbox
        self.agent_registry = agent_registry or AgentRegistry()
        self.supervisor = supervisor
        self.coordinator = coordinator or Coordinator.default()
        self.rag_context_builder = RAGContextBuilder()
        self.config = RuntimeConfig.from_any(config)
        self.policy = policy or self.config.reasoning_strategy or ReactPolicy()
        self.prompt_builder = prompt_builder or PromptBuilder(chat_template=self.config.prompt_template)
        self.observability = ObservabilityManager.disabled()
        self.tracer = tracer or Tracer(EventBus(), sinks=[])
        self._configure_observability()
        self.human_feedback = human_feedback
        if self.human_feedback is not None:
            self.human_feedback.bind_runtime(self)
        self.extensions = ExtensionManager.from_any(extensions)
        self._managed_agents = list(managed_agents or [])
        self.reasoning_framework = self._normalize_reasoning(self.policy)
        self.context_kernel = ContextKernel(
            runtime=self,
            context_selector=self.config.context_selector or DefaultContextSelector(),
            route_planner=self.config.route_planner or DefaultRoutePlanner(),
            memory_evaluator=self.config.memory_evaluator or DefaultMemoryEvaluator(),
        )
        self._register_builtin_knowledge_tools()
        self._closed = False
        self._background_managed = False

    async def _aclose_resource(self, resource: Any) -> None:
        close_async = getattr(resource, "aclose", None)
        if callable(close_async):
            outcome = close_async()
            if inspect.isawaitable(outcome):
                await outcome
            return
        close = getattr(resource, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _error_category(exc: Exception) -> str:
        message = str(exc).lower()
        exc_type = type(exc).__name__
        if "environment_error:" in message:
            return "environment_error"
        if isinstance(exc, (sqlite3.Error, OverflowError)):
            return "runtime_persistence_error"
        if exc_type in {"APIConnectionError", "APITimeoutError", "RateLimitError"}:
            return "provider_connection_error"
        if "connection error" in message or "timed out" in message or "rate limit" in message:
            return "provider_connection_error"
        return "runtime_error"

    @staticmethod
    def _error_context(exc: Exception, envelope: ContextEnvelope, *, stage: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        context_budget = envelope.metadata.get("context_budget_report", {}) if isinstance(envelope.metadata, dict) else {}
        payload = {
            **envelope.model_dump(),
            "error": str(exc),
            "error_category": Runtime._error_category(exc),
            "error_stage": stage,
            "prompt_char_estimate": context_budget.get("estimated_total_chars"),
            "context_compaction_applied": context_budget.get("compaction_applied"),
        }
        if extra:
            payload.update(extra)
        return payload

    def _configure_observability(self) -> None:
        observability_config = ObservabilityConfig.from_any(self.config.observability)
        if not observability_config.enabled:
            return
        if observability_config.store_backend != "sqlite":
            raise ValueError(f"Unsupported observability store backend '{observability_config.store_backend}'.")
        store = SQLiteEventStore(
            observability_config.sqlite_path,
            capture_todos=observability_config.capture_todos,
            redaction=observability_config.redaction,
            payload_budget=observability_config.trace_payload_budget,
        )
        self.observability = ObservabilityManager(store)
        self.tracer.add_sink(self.observability)
        if observability_config.console_mode != "silent":
            self.tracer.add_sink(
                ConsoleEventSink(
                    mode=observability_config.console_mode,
                    redaction=observability_config.redaction,
                    payload_budget=observability_config.trace_payload_budget,
                )
            )

    def _attach_observability_metadata(self, result: RunResult) -> RunResult:
        if not self.observability.enabled:
            return result
        todo_payload = self.observability.get_run_todos(result.run_id)
        reasoning_metadata = dict(result.reasoning_metadata)
        reasoning_metadata["observability_enabled"] = True
        reasoning_metadata["todo_query"] = {"run_id": result.run_id, "thread_id": result.thread_id}
        reasoning_metadata["todo_summary"] = (
            todo_payload.get("summary")
            if todo_payload is not None
            else {"total": 0, "completed": 0, "failed": 0, "waiting": 0, "in_progress": 0}
        )
        return result.model_copy(update={"reasoning_metadata": reasoning_metadata})

    def _register_builtin_knowledge_tools(self) -> None:
        if self.knowledge_base is None and self.retriever is None:
            return
        for factory in (
            create_deliberative_retrieve_tool,
            create_search_knowledge_assets_tool,
            create_open_retrieved_evidence_tool,
        ):
            tool = factory(self)
            if tool.spec.name not in self.tools:
                self.tools.register(tool)

    def _to_stream_event(self, event_type: str, payload: dict[str, Any]) -> RunStreamEvent:
        payload_copy = dict(payload)
        request_id = str(payload_copy.pop("request_id", ""))
        run_id = str(payload_copy.pop("run_id", ""))
        thread_id = str(payload_copy.pop("thread_id", ""))
        tool_calls = payload_copy.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            tool_calls = []
        else:
            payload_copy.pop("tool_calls", None)
        return RunStreamEvent(
            event_type=event_type,
            request_id=request_id,
            run_id=run_id,
            thread_id=thread_id,
            agent_name=payload_copy.pop("agent_name", None),
            task_id=payload_copy.pop("task_id", None),
            parent_task_id=payload_copy.pop("parent_task_id", None),
            delta_text=payload_copy.pop("delta_text", ""),
            tool_calls=tool_calls,
            finish_reason=payload_copy.pop("finish_reason", None),
            payload=payload_copy,
        )

    async def _emit_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        stream_writer: Callable[[RunStreamEvent], Awaitable[None]] | None = None,
    ) -> None:
        self.tracer.emit(event_type, payload)
        if stream_writer is not None:
            await stream_writer(self._to_stream_event(event_type, payload))

    def _normalize_reasoning(self, policy: BasePolicy | BaseReasoningFramework):
        if isinstance(policy, BaseReasoningFramework):
            return policy
        if isinstance(policy, ReasoningStrategyConfig):
            from agentorch.reasoning import create_reasoning_framework

            return create_reasoning_framework(policy.kind, **policy.config)
        if isinstance(policy, str):
            from agentorch.reasoning import create_reasoning_framework

            return create_reasoning_framework(policy)
        if isinstance(policy, dict):
            from agentorch.reasoning import create_reasoning_framework

            payload = dict(policy)
            kind = payload.pop("kind")
            return create_reasoning_framework(kind, **payload)
        return LegacyPolicyAdapter(policy)

    def _legacy_rag_strategy(self, *, knowledge_scope: list[str] | None = None) -> RagStrategyConfig:
        return RagStrategyConfig(
            mode="deliberative" if self.config.retrieval_backend == "deliberative" else "classic",
            mount="inline",
            injection_policy="full_report",
            knowledge_scope=list(knowledge_scope or self.config.default_knowledge_scope),
            source_types=list(self.config.retrieval_allowed_source_types),
            file_types=list(self.config.retrieval_allowed_file_types),
            top_k=self.config.max_retrieved_chunks,
            max_steps=self.config.retrieval_budget_steps,
            classic={"top_k": self.config.max_retrieved_chunks, "rerank_enabled": self.config.retrieval_backend == "classic"},
            deliberative={"max_steps": self.config.retrieval_budget_steps, "max_documents": self.config.retrieval_budget_documents},
        )

    def _resolve_rag_strategy(
        self,
        *,
        knowledge_scope: list[str] | None = None,
        retrieval_overrides: dict[str, Any] | None = None,
    ) -> RagStrategyConfig:
        retrieval_overrides = retrieval_overrides or {}
        base = self.config.rag_strategy.model_copy(deep=True) if self.config.rag_strategy is not None else self._legacy_rag_strategy(knowledge_scope=knowledge_scope)
        if knowledge_scope:
            base.knowledge_scope = list(knowledge_scope)
        if "rag_mode" in retrieval_overrides and retrieval_overrides["rag_mode"]:
            base.mode = retrieval_overrides["rag_mode"]
        if "mount" in retrieval_overrides and retrieval_overrides["mount"]:
            base.mount = retrieval_overrides["mount"]
        if "injection_policy" in retrieval_overrides and retrieval_overrides["injection_policy"]:
            base.injection_policy = retrieval_overrides["injection_policy"]
        if retrieval_overrides.get("sources"):
            base.source_types = list(retrieval_overrides["sources"])
        if retrieval_overrides.get("file_types"):
            base.file_types = list(retrieval_overrides["file_types"])
        if retrieval_overrides.get("must_cover"):
            base.must_cover = list(retrieval_overrides["must_cover"])
        if retrieval_overrides.get("max_steps"):
            base.max_steps = int(retrieval_overrides["max_steps"])
        if retrieval_overrides.get("max_documents"):
            base.top_k = int(retrieval_overrides["max_documents"])
        if base.mode == "off" and base.fallback_mode != "off":
            base.mode = base.fallback_mode
        return base

    def _select_rag_retriever(self, strategy: RagStrategyConfig) -> BaseRetriever | None:
        if strategy.mode == "off":
            return None
        if isinstance(self.knowledge_base, IndexedKnowledgeBase):
            try:
                return create_rag_retriever(self.knowledge_base, strategy)
            except Exception:
                pass
        if self.retriever is not None:
            return self.retriever
        return None

    def _apply_injection_policy(self, payload: dict[str, Any], strategy: RagStrategyConfig) -> dict[str, Any]:
        updated = dict(payload)
        if strategy.injection_policy == "disabled":
            updated["context"] = ""
            updated["evidence"] = []
            updated["citations"] = []
            updated["report"] = {}
            return updated
        if strategy.injection_policy == "summary_only":
            updated["evidence"] = []
            updated["citations"] = []
        elif strategy.injection_policy == "evidence_only":
            updated["context"] = ""
        return updated

    def _resolve_context_policy(self, *, metadata: dict[str, Any] | None = None, node_config: dict[str, Any] | None = None, agent_role: str | None = None) -> ContextPolicy:
        return self.context_kernel.resolve_context_policy(metadata=metadata, node_config=node_config, agent_role=agent_role)

    def _resolve_state_policy(self, *, metadata: dict[str, Any] | None = None, node_config: dict[str, Any] | None = None, agent_role: str | None = None) -> StatePolicy:
        return self.context_kernel.resolve_state_policy(metadata=metadata, node_config=node_config, agent_role=agent_role)

    def _resolve_coordination_policy(self, *, metadata: dict[str, Any] | None = None, node_config: dict[str, Any] | None = None, agent_role: str | None = None) -> CoordinationPolicy:
        return self.context_kernel.resolve_coordination_policy(metadata=metadata, node_config=node_config, agent_role=agent_role)

    def _resolve_memory_policy(self, *, metadata: dict[str, Any] | None = None, node_config: dict[str, Any] | None = None, agent_role: str | None = None) -> MemoryPolicy:
        return self.context_kernel.resolve_memory_policy(metadata=metadata, node_config=node_config, agent_role=agent_role)

    async def _rerank_context_segments(
        self,
        segments: list[ContextSegment],
        top_k: int,
        *,
        user_input: str,
        stage: str,
        agent_role: str | None,
    ) -> dict[str, tuple[float, str]]:
        if not segments:
            return {}
        try:
            response = await self.model.generate(
                ModelRequest(
                    messages=[
                        Message(
                            role="system",
                            content=(
                                "You are a context salience reranker. Return JSON with key 'adjustments'. "
                                "Each item must contain segment_id, adjustment between -0.25 and 0.25, and reason."
                            ),
                        ),
                        Message(
                            role="user",
                            content=json.dumps(
                                {
                                    "user_input": user_input,
                                    "stage": stage,
                                    "agent_role": agent_role,
                                    "candidates": [
                                        {
                                            "segment_id": segment.segment_id,
                                            "segment_type": segment.segment_type,
                                            "source": segment.source,
                                            "content": segment.display_content[:240],
                                        }
                                        for segment in segments[:top_k]
                                    ],
                                },
                                ensure_ascii=False,
                            ),
                        ),
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=256,
                    metadata={"purpose": "context_salience_rerank", "stage": stage},
                )
            )
            payload = json.loads(response.content or "{}")
            reranked: dict[str, tuple[float, str]] = {}
            for item in payload.get("adjustments", []):
                segment_id = str(item.get("segment_id") or "")
                if not segment_id:
                    continue
                adjustment = max(-0.25, min(0.25, float(item.get("adjustment", 0.0))))
                reranked[segment_id] = (adjustment, str(item.get("reason") or "model_rerank"))
            return reranked
        except Exception:
            return {}

    def _create_context_envelope(self, *, thread_id: str, metadata: dict[str, Any] | None = None) -> ContextEnvelope:
        return ContextEnvelope(
            request_id=str(uuid.uuid4()),
            run_id=str(uuid.uuid4()),
            thread_id=thread_id,
            trace_id=str(uuid.uuid4()),
            metadata=metadata or {},
        )

    def run(
        self,
        user_input: str,
        *,
        thread_id: str,
        workflow: Workflow | None = None,
        metadata: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> Any:
        if stream:
            return self._run_stream(user_input, thread_id=thread_id, workflow=workflow, metadata=metadata)
        return self._run(user_input, thread_id=thread_id, workflow=workflow, metadata=metadata)

    async def _run(
        self,
        user_input: str,
        *,
        thread_id: str,
        workflow: Workflow | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunResult:
        return await self._run_impl(user_input, thread_id=thread_id, workflow=workflow, metadata=metadata, stream_writer=None)

    async def _run_stream(
        self,
        user_input: str,
        *,
        thread_id: str,
        workflow: Workflow | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[RunStreamEvent]:
        queue: asyncio.Queue[RunStreamEvent | None] = asyncio.Queue()
        error: Exception | None = None

        async def writer(event: RunStreamEvent) -> None:
            await queue.put(event)

        async def producer() -> None:
            nonlocal error
            try:
                result = await self._run_impl(
                    user_input,
                    thread_id=thread_id,
                    workflow=workflow,
                    metadata=metadata,
                    stream_writer=writer,
                )
                final_payload = {
                    "status": result.status,
                    "finish_reason": result.finish_reason,
                    "error_category": None,
                    "context_budget_report": result.reasoning_metadata.get("context_budget_report"),
                    "output_text": result.output_text,
                    "usage": result.usage.model_dump(),
                }
                self.tracer.emit(
                    "final_result",
                    {
                        "request_id": result.request_id,
                        "run_id": result.run_id,
                        "thread_id": result.thread_id,
                        **final_payload,
                    },
                )
                await writer(
                    RunStreamEvent(
                        event_type="final_result",
                        request_id=result.request_id,
                        run_id=result.run_id,
                        thread_id=result.thread_id,
                        payload=final_payload,
                        result=result,
                    )
                )
            except Exception as exc:  # pragma: no cover
                error = exc
            finally:
                await queue.put(None)

        task = asyncio.create_task(producer())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
            if error is not None:
                raise error
            await task
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _run_impl(
        self,
        user_input: str,
        *,
        thread_id: str,
        workflow: Workflow | None = None,
        metadata: dict[str, Any] | None = None,
        stream_writer: Callable[[RunStreamEvent], Awaitable[None]] | None = None,
    ) -> RunResult:
        metadata = dict(metadata or {})
        hook_context = RunHookContext(
            runtime=self,
            thread_id=thread_id,
            user_input=user_input,
            metadata=metadata,
            workflow=workflow,
        )
        await self.extensions.before_run(hook_context)
        user_input = hook_context.user_input
        metadata = hook_context.metadata
        workflow = hook_context.workflow
        envelope = self._create_context_envelope(thread_id=thread_id, metadata=metadata)
        hook_context.envelope = envelope
        usage_tracker = UsageTracker()
        tool_results: list[ToolExecutionResult] = []
        await self._emit_event("run_started", envelope.model_dump(), stream_writer=stream_writer)
        await self._emit_event(
            "task_created",
            {**envelope.model_dump(), "task_id": envelope.run_id, "parent_task_id": metadata.get("parent_task_id")},
            stream_writer=stream_writer,
        )
        feedback_token = None
        if self.human_feedback is not None:
            feedback_token = self.human_feedback.set_context(
                thread_id=thread_id,
                run_id=envelope.run_id,
                task_id=(metadata.get("task_packet") or {}).get("task_id"),
                source_agent=metadata.get("agent_role"),
            )

        try:
            await self.memory.append_message(thread_id, Message(role="user", content=user_input))

            if self.supervisor is not None and not metadata.get("_delegated"):
                result = await self._run_supervisor(user_input, envelope, stream_writer=stream_writer)
                await self._emit_event("run_completed", {**envelope.model_dump(), "status": result.status}, stream_writer=stream_writer)
                result = self._attach_observability_metadata(result)
                hook_context.result = result
                await self.extensions.after_run(hook_context)
                return hook_context.result or result

            if workflow is not None:
                result = await self._run_workflow(workflow, thread_id=thread_id, user_input=user_input, metadata=metadata)
                status = result.get("status", "completed")
                await self._emit_event("run_completed", {**envelope.model_dump(), "status": status}, stream_writer=stream_writer)
                run_result = self._attach_observability_metadata(
                    RunResult(
                        request_id=envelope.request_id,
                        run_id=envelope.run_id,
                        thread_id=thread_id,
                        output_text=json.dumps(result, ensure_ascii=False),
                        usage=usage_tracker.summary(),
                        status=status,
                        feedback_id=result.get("feedback_id"),
                        await_reason=result.get("await_reason"),
                        requires_response=bool(result.get("requires_response", False)),
                        response_schema=result.get("response_schema"),
                    )
                )
                hook_context.result = run_result
                await self.extensions.after_run(hook_context)
                return hook_context.result or run_result

            conversation = await self.memory.get_context_window(thread_id)
            selected_skill_routes = (
                self.skills.route_for(
                    user_input,
                    config=metadata.get("skill_routing") or self.config.skill_routing or SkillRoutingConfig(),
                    available_tools=[spec["function"]["name"] for spec in self.tools.list_specs()],
                )
                if self.config.auto_select_skills
                else []
            )
            selected_skills = [route.content for route in selected_skill_routes]
            envelope.metadata["resolved_skill_routing"] = SkillRoutingConfig.from_any(
                metadata.get("skill_routing") or self.config.skill_routing or SkillRoutingConfig()
            ).model_dump()
            envelope.metadata["selected_skill_routes"] = [route.model_dump() for route in selected_skill_routes]
            memory_summary = await self.memory.summarize_thread(thread_id)
            local_reasoning = self.reasoning_framework
            if metadata.get("reasoning_strategy") is not None:
                local_reasoning = self._normalize_reasoning(metadata["reasoning_strategy"])
            retrieval_payload = await self._build_retrieval_context(
                user_input,
                envelope,
                knowledge_scope=metadata.get("knowledge_scope") or self.config.default_knowledge_scope,
                retrieval_overrides={"mount_context": "runtime", "rag_mode": (metadata.get("rag_strategy") or {}).get("mode"), "mount": (metadata.get("rag_strategy") or {}).get("mount"), "injection_policy": (metadata.get("rag_strategy") or {}).get("injection_policy"), "sources": (metadata.get("rag_strategy") or {}).get("source_types", []), "file_types": (metadata.get("rag_strategy") or {}).get("file_types", []), "must_cover": (metadata.get("rag_strategy") or {}).get("must_cover", []), "max_steps": (metadata.get("rag_strategy") or {}).get("max_steps"), "max_documents": (metadata.get("rag_strategy") or {}).get("top_k")},
                stream_writer=stream_writer,
            )
            task_packet = metadata.get("task_packet")
            delegation_context = {"handoff": metadata.get("handoff")} if metadata.get("handoff") else {}
            agent_role = metadata.get("agent_role")
            if agent_role:
                await self.memory.append_agent_memory(thread_id, agent_role, {"task_packet": task_packet, "user_input": user_input})

            reasoning_context = ReasoningSessionContext(
                user_input=user_input,
                thread_id=thread_id,
                envelope=envelope,
                conversation=conversation,
                memory_summary=memory_summary,
                retrieval_payload=retrieval_payload,
                task_packet=task_packet,
                delegation_context=delegation_context,
                agent_role=agent_role,
                selected_skills=selected_skills,
                usage=usage_tracker.summary(),
                messages=[],
                tool_results=tool_results,
                stream_enabled=stream_writer is not None,
                stream_writer=stream_writer,
            )
            await self._emit_event(
                "reasoning_started",
                {**envelope.model_dump(), "reasoning_kind": local_reasoning.config.kind.value},
                stream_writer=stream_writer,
            )
            reasoning_result = await local_reasoning.execute(self, reasoning_context)
            final_text = reasoning_result.final_output
            messages = reasoning_context.messages
            tool_results = reasoning_context.tool_results
            usage_tracker.prompt_tokens = reasoning_context.usage.prompt_tokens
            usage_tracker.completion_tokens = reasoning_context.usage.completion_tokens
            usage_tracker.total_tokens = reasoning_context.usage.total_tokens
            await self._emit_event(
                "reasoning_completed",
                {
                    **envelope.model_dump(),
                    "reasoning_kind": local_reasoning.config.kind.value,
                    "step_count": len(reasoning_result.steps),
                },
                stream_writer=stream_writer,
            )
            await self.memory.remember(MemoryRecord(thread_id=thread_id, kind="run_summary", content=final_text, tags=["run"]))
            await self._emit_event("memory_written", {**envelope.model_dump(), "kind": "run_summary"}, stream_writer=stream_writer)
            post_run_report = await self.context_kernel.after_agent_run(
                thread_id=thread_id,
                user_input=user_input,
                final_output=final_text,
                metadata={
                    **metadata,
                    "retrieval_payload": retrieval_payload,
                    "task_packet": task_packet,
                    "agent_role": agent_role,
                },
                conversation=conversation,
            )
            if post_run_report.get("memory_promotion_trace"):
                envelope.metadata["memory_promotion_trace"] = post_run_report["memory_promotion_trace"]
            if post_run_report.get("state_refresh_report"):
                envelope.metadata["state_refresh_report"] = post_run_report["state_refresh_report"]

            reasoning_metadata = dict(reasoning_result.metadata)
            for key in (
                "resolved_policies",
                "resolved_context_policy",
                "resolved_state_policy",
                "resolved_coordination_policy",
                "resolved_memory_policy",
                "resolved_skill_routing",
                "selected_skill_routes",
                "context_budget_report",
                "memory_policy_report",
                "memory_recall_report",
                "memory_promotion_trace",
                "state_refresh_report",
                "selected_context_segments",
                "dropped_context_segments",
                "salience_report",
                "attention_profile",
                "compaction_trace",
            ):
                if key in envelope.metadata:
                    reasoning_metadata[key] = envelope.metadata[key]
            if stream_writer is None:
                self.tracer.emit(
                    "final_result",
                    {
                        **envelope.model_dump(),
                        "status": "completed",
                        "finish_reason": "completed",
                        "error_category": None,
                        "context_budget_report": reasoning_metadata.get("context_budget_report"),
                        "output_text": final_text,
                        "usage": usage_tracker.summary().model_dump(),
                    },
                )
            await self._emit_event("run_completed", {**envelope.model_dump(), "status": "completed"}, stream_writer=stream_writer)
            run_result = self._attach_observability_metadata(
                RunResult(
                    request_id=envelope.request_id,
                    run_id=envelope.run_id,
                    thread_id=thread_id,
                    output_text=final_text,
                    messages=messages,
                    tool_results=tool_results,
                    usage=usage_tracker.summary(),
                    finish_reason="completed",
                    reasoning={
                        "final_output": reasoning_result.final_output,
                        "steps": [step.model_dump() for step in reasoning_result.steps],
                        "trace_text": reasoning_result.trace_text,
                    },
                    reasoning_trace=reasoning_result.trace_text,
                    reasoning_kind=local_reasoning.config.kind.value,
                    reasoning_metadata=reasoning_metadata,
                )
            )
            hook_context.result = run_result
            await self.extensions.after_run(hook_context)
            return hook_context.result or run_result
        except Exception as exc:
            hook_context.error = exc
            await self.extensions.on_run_error(hook_context)
            await self._emit_event(
                "run_failed",
                self._error_context(exc, envelope, stage="run_impl"),
                stream_writer=stream_writer,
            )
            raise
        finally:
            if self.human_feedback is not None and feedback_token is not None:
                self.human_feedback.reset_context(feedback_token)

    async def _execute_tool(self, name: str, arguments: dict[str, Any], envelope: ContextEnvelope):
        tool = self.tools.get(name)
        try:
            if tool.spec.needs_sandbox:
                if self.sandbox is None:
                    raise ToolError("This tool requires a configured sandbox, but no sandbox is attached.", tool_name=name)
                sandbox_result = await self.sandbox.execute(
                    "python",
                    arguments.get("code", ""),
                    workdir=arguments.get("workdir"),
                )
                from agentorch.tools.base import ToolResult

                return ToolResult(tool_name=name, data=sandbox_result.model_dump(), success=sandbox_result.exit_code == 0)
            return await self.tools.execute(name, arguments)
        except ToolError as exc:
            self.tracer.emit(
                "run_failed",
                self._error_context(exc, envelope, stage="tool_execution", extra={"tool_name": name}),
            )
            from agentorch.tools.base import ToolResult

            return ToolResult(tool_name=name, data={}, success=False, error=str(exc))

    async def _build_retrieval_context(
        self,
        user_input: str,
        envelope: ContextEnvelope,
        *,
        knowledge_scope: list[str] | None = None,
        retrieval_overrides: dict[str, Any] | None = None,
        stream_writer: Callable[[RunStreamEvent], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        retrieval_enabled = self.config.enable_retrieval or self.config.retrieval_mode != RetrievalMode.OFF
        strategy = self._resolve_rag_strategy(knowledge_scope=knowledge_scope, retrieval_overrides=retrieval_overrides)
        selected_retriever = self._select_rag_retriever(strategy)
        mount_context = (retrieval_overrides or {}).get("mount_context", "runtime")
        if strategy.mount == "workflow_only" and mount_context != "workflow":
            selected_retriever = None
        if strategy.mount == "agent_only" and mount_context not in {"runtime", "agent"}:
            selected_retriever = None
        if not retrieval_enabled or selected_retriever is None or strategy.mount == "tool_only":
            return {
                "context": "",
                "evidence": [],
                "citations": [],
                "plan": None,
                "knowledge_scope": knowledge_scope or [],
                "report": {},
                "coverage": {"covered": [], "missing": []},
                "visited_sources": [],
                "rag_strategy": strategy.model_dump(),
            }
        retrieval_overrides = retrieval_overrides or {}
        effective_scope = strategy.knowledge_scope or knowledge_scope or []
        filters = {
            "source_types": retrieval_overrides.get("sources") or strategy.source_types or self.config.retrieval_allowed_source_types,
            "file_types": retrieval_overrides.get("file_types") or strategy.file_types or self.config.retrieval_allowed_file_types,
            "path_filters": retrieval_overrides.get("path_filters", []),
            "mime_filters": retrieval_overrides.get("mime_filters", []),
        }
        requested_top_k = retrieval_overrides.get("max_documents")
        if requested_top_k is None:
            requested_top_k = strategy.top_k
        plan = RetrievalPlan(
            query=user_input,
            top_k=max(1, min(strategy.top_k, int(requested_top_k))),
            scopes=effective_scope,
            strategy=strategy.mode,
            metadata=filters,
        )
        await self._emit_event(
            "retrieval_started",
            {**envelope.model_dump(), "query": user_input},
            stream_writer=stream_writer,
        )
        intent = RetrievalIntent(
            question=user_input,
            goal=retrieval_overrides.get("goal"),
            must_cover=list(retrieval_overrides.get("must_cover", strategy.must_cover)),
            constraints=filters,
            preferred_sources=list(retrieval_overrides.get("sources", [])),
            knowledge_scope=plan.scopes,
            file_types=list(retrieval_overrides.get("file_types", strategy.file_types)),
            max_steps=int(retrieval_overrides.get("max_steps") or strategy.max_steps),
            max_documents=int(retrieval_overrides.get("max_documents") or strategy.top_k),
            metadata={"retrieval_mode": self.config.retrieval_mode.value, "rag_strategy": strategy.model_dump()},
            rag_mode=strategy.mode,
        )
        if hasattr(selected_retriever, "retrieve_report"):
            report = await selected_retriever.retrieve_report(intent)
        else:
            chunks = await selected_retriever.retrieve(
                RetrievalQuery(query=user_input, top_k=plan.top_k, scopes=plan.scopes, filters=filters)
            )
            report = RetrievalReport(
                summary=self.rag_context_builder.build(chunks),
                retrieval_context=self.rag_context_builder.build(chunks),
                evidence=self.rag_context_builder.build_evidence(chunks),
                citations=[item.citation for item in self.rag_context_builder.build_evidence(chunks)],
                plan=[RetrievalStep(step_type="retrieve", query=user_input)],
                visited_documents=[item.chunk.document_id for item in chunks],
                visited_sources=sorted({item.source for item in chunks}),
            )
        memory_policy = self._resolve_memory_policy(metadata=envelope.metadata)
        report, memory_recall_report = await self._augment_report_with_memory_sources(
            report,
            thread_id=envelope.thread_id,
            query=user_input,
            knowledge_scope=plan.scopes,
            source_filters=filters.get("source_types", []),
            memory_policy=memory_policy,
            task_packet=envelope.metadata.get("task_packet"),
            agent_role=envelope.metadata.get("agent_role"),
        )
        envelope.metadata["memory_recall_report"] = memory_recall_report
        context = self.rag_context_builder.build_report(report)
        evidence = report.evidence
        await self._emit_event(
            "retrieval_completed",
            {
                **envelope.model_dump(),
                "query": user_input,
                "chunk_count": len(evidence),
                "knowledge_scope": plan.scopes,
                "visited_sources": report.visited_sources,
            },
            stream_writer=stream_writer,
        )
        payload = {
            "context": context,
            "evidence": [item.model_dump() for item in evidence],
            "citations": [item.model_dump() if isinstance(item, Citation) else item.citation.model_dump() for item in report.citations],
            "plan": plan.model_dump(),
            "knowledge_scope": plan.scopes,
            "report": report.model_dump(),
            "coverage": report.coverage.model_dump(),
            "visited_sources": report.visited_sources,
            "rag_strategy": strategy.model_dump(),
        }
        return self._apply_injection_policy(payload, strategy)

    async def _augment_report_with_memory_sources(
        self,
        report: RetrievalReport,
        *,
        thread_id: str,
        query: str,
        knowledge_scope: list[str],
        source_filters: list[str],
        memory_policy: MemoryPolicy,
        task_packet: dict[str, Any] | None = None,
        agent_role: str | None = None,
    ) -> tuple[RetrievalReport, dict[str, Any]]:
        allowed = {item.lower() for item in source_filters if item}
        include_workspace = not allowed or "workspace_artifact" in allowed or "workspace_records" in allowed
        include_notes = not allowed or "shared_notes" in allowed
        evidence = list(report.evidence)
        citations = list(report.citations)
        visited_sources = set(report.visited_sources)
        visited_documents = set(report.visited_documents)
        if include_workspace:
            for artifact in await self.memory.read_workspace_records(thread_id):
                text = artifact.content if isinstance(artifact.content, str) else json.dumps(artifact.content, ensure_ascii=False)
                if query.lower() not in text.lower():
                    continue
                citation = Citation(
                    source="workspace_artifact",
                    document_id=f"artifact:{artifact.artifact_id}",
                    chunk_id=f"artifact:{artifact.artifact_id}",
                    quote=text,
                    locator={"artifact_id": artifact.artifact_id, "task_id": artifact.task_id},
                    metadata={"owner_agent": artifact.owner_agent},
                )
                evidence.append(
                    RetrievedEvidence(
                        chunk=self._memory_evidence_chunk(citation.document_id, citation.chunk_id, text, "workspace_artifact", citation.locator, []),
                        citation=citation,
                        summary=text,
                        source_type="workspace_artifact",
                        locator=citation.locator,
                        claim=artifact.name,
                        snippet=text,
                        relevance_score=0.7,
                        support_score=0.7,
                    )
                )
                citations.append(citation)
                visited_sources.add("workspace_artifact")
                visited_documents.add(citation.document_id)
        if include_notes:
            for note in await self.memory.get_shared_notes(thread_id):
                if query.lower() not in note.content.lower():
                    continue
                citation = Citation(
                    source="shared_notes",
                    document_id=f"note:{note.note_id}",
                    chunk_id=f"note:{note.note_id}",
                    quote=note.content,
                    locator={"note_id": note.note_id, "task_id": note.task_id},
                    metadata={"author_agent": note.author_agent},
                )
                evidence.append(
                    RetrievedEvidence(
                        chunk=self._memory_evidence_chunk(citation.document_id, citation.chunk_id, note.content, "shared_notes", citation.locator, []),
                        citation=citation,
                        summary=note.content,
                        source_type="shared_notes",
                        locator=citation.locator,
                        claim=note.author_agent,
                        snippet=note.content,
                        relevance_score=0.65,
                        support_score=0.65,
                    )
                )
                citations.append(citation)
                visited_sources.add("shared_notes")
                visited_documents.add(citation.document_id)
        long_term_candidates = await self.context_kernel.memory_evaluator.search_long_term_memory(
            self.memory,
            policy=memory_policy,
            thread_id=thread_id,
            query=query,
            knowledge_scope=knowledge_scope,
            task_packet=task_packet,
            agent_role=agent_role,
            source_filters=source_filters,
        )
        memory_evidence, memory_citations, memory_recall_report = self.context_kernel.memory_evaluator.build_memory_evidence(
            policy=memory_policy,
            runtime=self,
            candidates=long_term_candidates,
            thread_id=thread_id,
            knowledge_scope=knowledge_scope,
        )
        evidence.extend(memory_evidence)
        citations.extend(memory_citations)
        for citation in memory_citations:
            visited_sources.add(citation.source)
            visited_documents.add(citation.document_id)
        evidence.sort(key=lambda item: item.relevance_score, reverse=True)
        evidence = evidence[: max(self.config.max_retrieved_chunks, 1)]
        return (
            report.model_copy(
                update={
                    "evidence": evidence,
                    "citations": [item.citation for item in evidence] if evidence else citations,
                    "visited_sources": sorted(visited_sources),
                    "visited_documents": sorted(visited_documents),
                }
            ),
            memory_recall_report,
        )

    def _memory_evidence_chunk(
        self,
        document_id: str,
        chunk_id: str,
        text: str,
        source_type: str,
        locator: dict[str, Any],
        scopes: list[str],
    ):
        from agentorch.knowledge import RetrievedChunk, DocumentChunk

        return RetrievedChunk(
            chunk=DocumentChunk(
                id=chunk_id,
                document_id=document_id,
                text=text,
                metadata={"source_type": source_type, "locator": locator, "scopes": scopes},
            ),
            score=0.7,
            source=source_type,
        )

    async def _build_prompt_context(
        self,
        context: ReasoningSessionContext,
        *,
        output_instruction: str | None = None,
        stage: str = "respond",
    ) -> PromptContext:
        return await self.context_kernel.prepare_prompt_context(
            context,
            output_instruction=output_instruction,
            stage=stage,
        )

    async def _model_round(
        self,
        context: ReasoningSessionContext,
        *,
        reasoning_kind: str,
        stage: str,
        output_instruction: str | None = None,
        prompt_profile=None,
    ):
        prompt_context = await self._build_prompt_context(context, output_instruction=output_instruction, stage=stage)
        if prompt_profile is not None:
            request_messages = self.prompt_builder.build_reasoning_messages(prompt_context, prompt_profile)
        else:
            request_messages = self.prompt_builder.build_messages(prompt_context)
        step_index = len(context.messages) + len(context.tool_results)
        await self._emit_event(
            "reasoning_step_started",
            {**context.envelope.model_dump(), "reasoning_kind": reasoning_kind, "stage": stage, "step_index": step_index},
            stream_writer=context.stream_writer,
        )
        await self._emit_event(
            "prompt_built",
            {**context.envelope.model_dump(), "step": step_index, "message_count": len(request_messages)},
            stream_writer=context.stream_writer,
        )
        if context.envelope.metadata.get("context_budget_report"):
            await self._emit_event(
                "context_budget_reported",
                {**context.envelope.model_dump(), "step": step_index, "context_budget": context.envelope.metadata["context_budget_report"]},
                stream_writer=context.stream_writer,
            )
        request = ModelRequest(
            messages=request_messages,
            tools=self.tools.list_specs(),
            metadata={
                "reasoning_kind": reasoning_kind,
                "stage": stage,
                **(
                    {"model_override": context.envelope.metadata["model_override"]}
                    if context.envelope.metadata.get("model_override") is not None
                    else {}
                ),
            },
        )
        if context.stream_enabled:
            accumulated_text = ""
            accumulated_tool_calls: list[Any] = []
            tool_call_by_id: dict[str, Any] = {}
            finish_reason = None
            async for chunk in self.model.stream(request):
                accumulated_text += chunk.delta_text or ""
                finish_reason = chunk.finish_reason or finish_reason
                for tool_call in chunk.tool_calls:
                    key = tool_call.id or f"{tool_call.name}:{len(accumulated_tool_calls)}"
                    existing = tool_call_by_id.get(key)
                    if existing is None:
                        existing = tool_call.model_copy(deep=True)
                        tool_call_by_id[key] = existing
                        accumulated_tool_calls.append(existing)
                    else:
                        if tool_call.name:
                            existing.name = tool_call.name
                        if tool_call.arguments:
                            existing.arguments.update(tool_call.arguments)
                await self._emit_event(
                    "model_delta",
                    {
                        **context.envelope.model_dump(),
                        "step": step_index,
                        "delta_text": chunk.delta_text or "",
                        "tool_calls": [call.model_dump() for call in chunk.tool_calls],
                        "finish_reason": chunk.finish_reason,
                    },
                    stream_writer=context.stream_writer,
                )
            response = ModelResponse(
                message=Message(
                    role="assistant",
                    content=accumulated_text,
                    tool_calls=[call.model_copy(deep=True) for call in accumulated_tool_calls],
                    metadata={"tool_calls": [call.model_dump() for call in accumulated_tool_calls]},
                ),
                content=accumulated_text,
                tool_calls=[call.model_copy(deep=True) for call in accumulated_tool_calls],
                finish_reason=finish_reason,
            )
        else:
            response = await self.model.generate(request)
            context.usage.prompt_tokens += response.usage.prompt_tokens
            context.usage.completion_tokens += response.usage.completion_tokens
            context.usage.total_tokens += response.usage.total_tokens
        await self._emit_event(
            "budget_consumed",
            {
                **context.envelope.model_dump(),
                "task_id": (context.task_packet or {}).get("task_id", context.envelope.run_id),
                "total_tokens": context.usage.total_tokens,
            },
            stream_writer=context.stream_writer,
        )
        await self._emit_event(
            "model_called",
            {**context.envelope.model_dump(), "step": step_index, "finish_reason": response.finish_reason, "tool_calls": len(response.tool_calls)},
            stream_writer=context.stream_writer,
        )
        if response.message:
            await self.memory.append_message(context.thread_id, response.message)
            context.conversation.append(response.message)
            context.messages.append(response.message)
        await self._emit_event(
            "reasoning_step_completed",
            {**context.envelope.model_dump(), "reasoning_kind": reasoning_kind, "stage": stage, "step_index": step_index},
            stream_writer=context.stream_writer,
        )
        return response

    async def _append_tool_observation(self, context: ReasoningSessionContext, tool_call, result) -> None:
        tool_result = ToolExecutionResult(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            output=result.data,
            is_error=not result.success,
            error_message=result.error,
            duration=result.duration,
        )
        context.tool_results.append(tool_result)
        tool_message_payload = result.data
        if not result.success:
            tool_message_payload = {
                "success": False,
                "error": result.error or f"Tool '{tool_call.name}' failed.",
            }
            if result.data:
                tool_message_payload["output"] = result.data
        tool_message_content, tool_message_truncated = self._tool_message_content(tool_message_payload)
        tool_message = Message(
            role="tool",
            content=tool_message_content,
            name=tool_call.name,
            tool_call_id=tool_call.id,
            metadata={"truncated": tool_message_truncated},
        )
        await self.memory.append_message(context.thread_id, tool_message)
        context.conversation.append(tool_message)
        await self._emit_event(
            "tool_called",
            {**context.envelope.model_dump(), "tool_name": tool_call.name, "tool_call_id": tool_call.id},
            stream_writer=context.stream_writer,
        )
        await self._emit_event(
            "tool_result",
            {
                **context.envelope.model_dump(),
                "tool_name": tool_call.name,
                "tool_call_id": tool_call.id,
                "is_error": not result.success,
                "output": self._summarize_tool_output(result.data),
                "error": result.error,
                "error_category": "runtime_error" if (not result.success and result.error) else None,
            },
            stream_writer=context.stream_writer,
        )

    def _aggregate_supervisor_usage(self, results: list[AgentResult]) -> UsageInfo:
        usage = UsageInfo()
        for result in results:
            budget = result.budget_used or {}
            usage.prompt_tokens += int(budget.get("prompt_tokens", 0) or 0)
            usage.completion_tokens += int(budget.get("completion_tokens", 0) or 0)
            usage.total_tokens += int(budget.get("total_tokens", 0) or 0)
        return usage

    def _aggregate_supervisor_reasoning(self, results: list[AgentResult], aggregation_metadata: dict[str, Any]) -> dict[str, Any]:
        child_reasoning: dict[str, Any] = {}
        for result in results:
            child_reasoning[result.agent_name] = {
                "status": result.status.value,
                "task_id": result.metadata.get("task_id"),
                "reasoning_kind": result.metadata.get("reasoning_kind"),
                "reasoning_metadata": result.metadata.get("reasoning_metadata", {}),
            }
        return {
            "aggregation": aggregation_metadata,
            "child_reasoning": child_reasoning,
            "completed_agents": [result.agent_name for result in results if result.status == TaskStatus.COMPLETED],
            "failed_agents": [result.agent_name for result in results if result.status == TaskStatus.FAILED],
        }

    def _summarize_tool_output(self, value: Any, *, depth: int = 0) -> Any:
        budget = self.config.tool_output_budget
        if depth == 0 and isinstance(value, dict):
            return shape_payload(value, budget=budget, redaction=self.config.redaction)
        if depth >= 2:
            if isinstance(value, dict):
                return {"type": "dict", "size": len(value)}
            if isinstance(value, list):
                return {"type": "list", "size": len(value)}
        if isinstance(value, dict):
            items = list(value.items())
            summary = {str(key): self._summarize_tool_output(item, depth=depth + 1) for key, item in items[:8]}
            if len(items) > 8:
                summary["_truncated_keys"] = len(items) - 8
            return summary
        if isinstance(value, list):
            summary = [self._summarize_tool_output(item, depth=depth + 1) for item in value[:5]]
            if len(value) > 5:
                summary.append({"_truncated_items": len(value) - 5})
            return summary
        if isinstance(value, str):
            return trim_message_content(value, max_chars=500)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return trim_message_content(str(value), max_chars=500)

    def _tool_message_content(self, output: dict[str, Any], *, max_chars: int = 8000) -> tuple[str, bool]:
        try:
            summarized = self._summarize_tool_output(output)
            serialized = json.dumps(summarized, ensure_ascii=False)
        except Exception:
            serialized = trim_message_content(str(type(output)), max_chars=200)
        effective_max_chars = min(max_chars, self.config.tool_output_budget.max_string_chars)
        return trim_message_content(serialized, max_chars=effective_max_chars), len(serialized) > effective_max_chars

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        for managed_agent in self._managed_agents:
            await self._aclose_resource(managed_agent)
        for resource in (
            self.tools,
            self.model,
            self.retriever,
            self.knowledge_base,
            self.observability,
            self.tracer,
            self.memory,
            self.sandbox,
            self.extensions,
        ):
            await self._aclose_resource(resource)

    def close(self) -> None:
        if self._closed:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.aclose())
            return
        raise RuntimeError(
            "Runtime.close() cannot be used inside a running event loop. "
            "Use 'await Runtime.aclose()' in notebooks and async applications."
        )

    def _supervisor_plan_settings(self, plan: Any) -> tuple[str, int]:
        task_plan = getattr(plan, "task_plan", None)
        metadata = dict(getattr(task_plan, "metadata", {}) or {})
        execution_mode = str(metadata.get("execution_mode", "sequential")).lower()
        max_parallel_tasks = int(metadata.get("max_parallel_tasks") or 1)
        return execution_mode, max(1, max_parallel_tasks)

    async def _run_supervisor_invocation(
        self,
        *,
        invocation: Any,
        plan: Any,
        task: TaskPacket,
        envelope: ContextEnvelope,
        collective_payload: dict[str, Any],
        coordination_policy: CoordinationPolicy,
        memory_policy: MemoryPolicy,
        stream_writer: Callable[[RunStreamEvent], Awaitable[None]] | None = None,
    ) -> AgentResult:
        registered = self.agent_registry.get(invocation.agent_name)
        self.coordinator.permission_manager.ensure_knowledge_scope(
            registered.spec.allowed_knowledge_scopes,
            invocation.task.knowledge_scope,
        )
        if not self.coordinator.permission_manager.can_delegate(
            current_depth=invocation.delegation_depth - 1,
            allowed_depth=min(self.config.max_delegation_depth, registered.spec.max_delegation_depth),
        ):
            raise RuntimeError(f"Delegation depth exceeded for agent '{registered.spec.name}'.")

        handoff = Handoff(
            from_agent="supervisor",
            to_agent=registered.spec.name,
            task=invocation.task,
            reason=plan.reason,
            metadata={"parent_run_id": envelope.run_id},
        )
        compacted_task_packet, compacted_handoff = self.context_kernel.build_child_handoff_payload(
            task_packet=invocation.task.model_dump(),
            handoff=handoff.model_dump(),
            coordination_policy=coordination_policy,
        )
        child_metadata = {
            "task_packet": compacted_task_packet,
            "handoff": compacted_handoff,
            "_delegated": True,
            "agent_role": registered.spec.name,
            "knowledge_scope": invocation.task.knowledge_scope,
            "parent_task_id": invocation.task.parent_task_id,
            "coordination_policy": coordination_policy.model_dump(),
            "memory_policy": memory_policy.model_dump(),
        }
        handoff_context = HandoffHookContext(
            runtime=self,
            envelope=envelope,
            invocation=invocation,
            handoff=handoff,
            metadata=child_metadata,
        )
        await self.extensions.before_handoff(handoff_context)
        invocation = handoff_context.invocation
        handoff = handoff_context.handoff
        child_metadata = handoff_context.metadata

        await self._emit_event(
            "handoff_created",
            {
                **envelope.model_dump(),
                "agent_name": registered.spec.name,
                "task_id": invocation.task.task_id,
                "parent_task_id": invocation.task.parent_task_id,
                "delegation_depth": invocation.delegation_depth,
            },
            stream_writer=stream_writer,
        )
        await self._emit_event(
            "agent_delegated",
            {
                **envelope.model_dump(),
                "agent_name": registered.spec.name,
                "task_id": invocation.task.task_id,
                "parent_task_id": invocation.task.parent_task_id,
                "delegation_depth": invocation.delegation_depth,
                "knowledge_scope": invocation.task.knowledge_scope,
            },
            stream_writer=stream_writer,
        )

        if stream_writer is None:
            run_result = await registered.agent.run(
                invocation.task.goal,
                thread_id=invocation.task.task_id,
                metadata=child_metadata,
                stream=False,
            )
        else:
            run_result = None
            async for child_event in registered.agent.run(
                invocation.task.goal,
                thread_id=invocation.task.task_id,
                metadata=child_metadata,
                stream=True,
            ):
                forwarded = child_event.model_copy(deep=True)
                if not forwarded.agent_name:
                    forwarded.agent_name = registered.spec.name
                if not forwarded.task_id:
                    forwarded.task_id = invocation.task.task_id
                if not forwarded.parent_task_id:
                    forwarded.parent_task_id = invocation.task.parent_task_id
                await stream_writer(forwarded)
                if child_event.event_type == "final_result" and child_event.result is not None:
                    run_result = child_event.result
            if run_result is None:  # pragma: no cover
                raise RuntimeError(f"Delegated agent '{registered.spec.name}' did not produce a final_result event.")

        run_status = (
            TaskStatus.COMPLETED
            if run_result.status == "completed"
            else TaskStatus.WAITING_HUMAN
            if run_result.status == "waiting_human"
            else TaskStatus.FAILED
        )
        agent_result = AgentResult(
            agent_name=registered.spec.name,
            output_text=run_result.output_text,
            status=run_status,
            summary=run_result.output_text,
            structured_output={
                "reasoning_kind": run_result.reasoning_kind,
                "reasoning_metadata": run_result.reasoning_metadata,
                "reasoning_trace": run_result.reasoning_trace,
                "usage": run_result.usage.model_dump(),
                "tool_results": [item.model_dump() for item in run_result.tool_results],
                "messages": [message.model_dump() for message in run_result.messages],
            },
            metadata={
                "task_id": invocation.task.task_id,
                "parent_task_id": invocation.task.parent_task_id,
                "handoff": handoff.model_dump(),
                "coordination_policy": coordination_policy.model_dump(),
                "coordination_report": collective_payload["coordination_report"],
                "reasoning_kind": run_result.reasoning_kind,
                "reasoning_metadata": run_result.reasoning_metadata,
                "routing_score": invocation.metadata.get("routing_score", 0.0),
            },
            budget_used=run_result.usage.model_dump(),
        )
        collective_candidate = self._build_collective_candidate(
            task=task,
            invocation_task=invocation.task,
            result=agent_result,
        )
        await self.memory.add_shared_note(
            envelope.thread_id,
            SharedNote(
                note_id=f"{invocation.task.task_id}:candidate",
                task_id=invocation.task.task_id,
                author_agent=registered.spec.name,
                content=run_result.output_text,
                metadata={
                    "parent_task_id": task.task_id,
                    "collective_candidate": True,
                    "memory_kind": "lesson_learned",
                    "scope": ",".join(invocation.task.knowledge_scope) if invocation.task.knowledge_scope else None,
                    "collective_memory": collective_candidate,
                    "coordination_policy": coordination_policy.model_dump(),
                },
            ),
        )
        await self._emit_event(
            "handoff_completed",
            {
                **envelope.model_dump(),
                "agent_name": registered.spec.name,
                "task_id": invocation.task.task_id,
                "parent_task_id": invocation.task.parent_task_id,
            },
            stream_writer=stream_writer,
        )
        handoff_context.result = agent_result
        await self.extensions.after_handoff(handoff_context)
        return handoff_context.result or agent_result

    async def _run_supervisor(
        self,
        user_input: str,
        envelope: ContextEnvelope,
        *,
        stream_writer: Callable[[RunStreamEvent], Awaitable[None]] | None = None,
    ) -> RunResult:
        coordination_policy = self._resolve_coordination_policy()
        memory_policy = self._resolve_memory_policy()
        collective_payload, collective_memory = await self.context_kernel.prepare_supervisor_task_context(
            user_input=user_input,
            thread_id=envelope.thread_id,
            coordination_policy=coordination_policy,
            memory_policy=memory_policy,
        )
        task = TaskPacket(
            task_id=envelope.run_id,
            goal=user_input,
            context=collective_payload,
            origin_agent="supervisor",
            knowledge_scope=self.config.default_knowledge_scope,
            metadata={
                "thread_id": envelope.thread_id,
                "delegation_depth": 0,
                "collective_memory_refs": [item["id"] for item in collective_memory],
                "coordination_policy": coordination_policy.model_dump(),
            },
        )
        plan_context = SupervisorPlanHookContext(
            runtime=self,
            task=task,
            coordination_policy=coordination_policy,
        )
        await self.extensions.before_supervisor_plan(plan_context)
        task = plan_context.task
        coordination_policy = plan_context.coordination_policy

        self.coordinator.validate_task(task)
        await self._emit_event("supervisor_routed", {**envelope.model_dump(), "task_id": task.task_id}, stream_writer=stream_writer)
        await self._emit_event("aggregation_started", {**envelope.model_dump(), "task_id": task.task_id}, stream_writer=stream_writer)
        plan = await self.context_kernel.route_planner.plan(
            supervisor=self.supervisor,
            task=task,
            registry=self.agent_registry,
            coordination_policy=coordination_policy,
        )
        plan_context.plan = plan
        await self.extensions.after_supervisor_plan(plan_context)
        plan = plan_context.plan or plan

        execution_mode, max_parallel_tasks = self._supervisor_plan_settings(plan)
        delegated_results: list[AgentResult] = []
        parallel_enabled = (
            execution_mode == "parallel"
            and stream_writer is None
            and self.coordinator.execution_policy.allow_parallel
            and len(plan.invocations) > 1
        )
        if parallel_enabled:
            limit = min(max_parallel_tasks, max(1, self.coordinator.execution_policy.max_parallel_tasks))
            semaphore = asyncio.Semaphore(limit)

            async def _worker(invocation: Any) -> AgentResult:
                async with semaphore:
                    return await self._run_supervisor_invocation(
                        invocation=invocation,
                        plan=plan,
                        task=task,
                        envelope=envelope,
                        collective_payload=collective_payload,
                        coordination_policy=coordination_policy,
                        memory_policy=memory_policy,
                        stream_writer=None,
                    )

            delegated_results = list(await asyncio.gather(*(_worker(invocation) for invocation in plan.invocations)))
        else:
            for invocation in plan.invocations:
                delegated_results.append(
                    await self._run_supervisor_invocation(
                        invocation=invocation,
                        plan=plan,
                        task=task,
                        envelope=envelope,
                        collective_payload=collective_payload,
                        coordination_policy=coordination_policy,
                        memory_policy=memory_policy,
                        stream_writer=stream_writer,
                    )
                )

        for result in delegated_results:
            await self._emit_event(
                "agent_completed",
                {
                    **envelope.model_dump(),
                    "agent_name": result.agent_name,
                    "task_id": result.metadata.get("task_id"),
                    "parent_task_id": result.metadata.get("parent_task_id"),
                },
                stream_writer=stream_writer,
            )
            for artifact in result.artifacts:
                workspace_record = await self.memory.write_workspace_record(
                    envelope.thread_id,
                    task_id=result.metadata.get("task_id", envelope.run_id),
                    owner_agent=result.agent_name,
                    artifact=artifact,
                )
                await self._emit_event(
                    "artifact_created",
                    {
                        **envelope.model_dump(),
                        "artifact_id": workspace_record.artifact_id,
                        "agent_name": result.agent_name,
                        "task_id": result.metadata.get("task_id"),
                    },
                    stream_writer=stream_writer,
                )

        aggregated = self.coordinator.aggregate_results(delegated_results)
        aggregation_metadata = dict(aggregated.metadata)
        aggregation_metadata["plan"] = {
            "reason": plan.reason,
            "execution_mode": execution_mode,
            "max_parallel_tasks": max_parallel_tasks,
            "selected_agents": [invocation.agent_name for invocation in plan.invocations],
            "task_plan": plan.task_plan.model_dump() if plan.task_plan is not None else None,
        }
        aggregated_reasoning_metadata = self._aggregate_supervisor_reasoning(delegated_results, aggregation_metadata)
        aggregated_usage = self._aggregate_supervisor_usage(delegated_results)
        await self.context_kernel.after_supervisor_aggregation(thread_id=envelope.thread_id, task=task)
        await self._emit_event(
            "aggregation_completed",
            {**envelope.model_dump(), "task_id": task.task_id, "agent_count": len(delegated_results)},
            stream_writer=stream_writer,
        )
        return RunResult(
            request_id=envelope.request_id,
            run_id=envelope.run_id,
            thread_id=envelope.thread_id,
            output_text=aggregated.summary,
            usage=aggregated_usage,
            finish_reason="completed",
            reasoning_kind="supervisor_aggregate",
            reasoning_metadata=aggregated_reasoning_metadata,
        )

    async def _run_workflow(self, workflow: Workflow, *, thread_id: str, user_input: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return await execute_runtime_workflow(
            self,
            workflow,
            thread_id=thread_id,
            user_input=user_input,
            metadata=metadata,
        )


    def _next_workflow_node(self, workflow: Workflow, node_id: str) -> str | None:
        for edge in workflow.get_edges(node_id):
            if edge.kind == "success":
                return edge.target
        return None

    async def resume_from_feedback(
        self,
        feedback_id: str,
        *,
        workflow: Workflow,
        thread_id: str,
        user_input: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RunResult:
        if self.human_feedback is None:
            raise RuntimeError("Human feedback is not configured.")
        pending = await self.human_feedback.get(feedback_id)
        if pending is None or pending.response is None:
            raise RuntimeError(f"No submitted response found for feedback '{feedback_id}'.")
        resume_metadata = dict(metadata or {})
        resume_metadata.setdefault("resume_from", pending.event.metadata.get("resume_from"))
        resume_metadata.setdefault("workflow_state", dict(pending.event.metadata.get("workflow_state", {})))
        resume_metadata.setdefault("workflow_variables", dict(pending.event.metadata.get("workflow_variables", {})))
        workflow_node_id = pending.event.metadata.get("workflow_node_id")
        if workflow_node_id:
            resume_metadata["workflow_state"][f"{workflow_node_id}:feedback_id"] = feedback_id
        return await self.run(user_input, thread_id=thread_id, workflow=workflow, metadata=resume_metadata)

    def _collective_memory_payload(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        if not records:
            return {
                "collective_memory_context": "",
                "collective_memory_evidence": [],
                "collective_memory_citations": [],
                "collective_memory_refs": [],
            }
        evidence = [
            {
                "id": item["id"],
                "kind": item["kind"],
                "content": item["content"],
                "confidence": item["confidence"],
                "source_agents": item["source_agents"],
            }
            for item in records
        ]
        context = "\n".join(f"- [{item['kind']}] {item['content']}" for item in records)
        citations = [{"record_id": item["id"], "kind": item["kind"]} for item in records]
        return {
            "collective_memory_context": context,
            "collective_memory_evidence": evidence,
            "collective_memory_citations": citations,
            "collective_memory_refs": [item["id"] for item in records],
        }

    def _build_collective_candidate(
        self,
        *,
        task: TaskPacket,
        invocation_task: TaskPacket,
        result: AgentResult,
    ) -> dict[str, Any] | None:
        evidence = list((invocation_task.context or {}).get("collective_memory_evidence", []))
        if not evidence:
            return None
        primary = evidence[0]
        kind = primary.get("kind", "lesson_learned")
        content = primary.get("content", "").strip()
        if not content:
            return None
        source_name = result.agent_name or "specialist"
        candidate_content = f"validated {kind}: {content}"
        return {
            "kind": "lesson_learned",
            "content": candidate_content,
            "tags": sorted(
                {
                    "collective-memory",
                    "validated",
                    kind,
                    source_name,
                }
            ),
            "scope": ",".join(invocation_task.knowledge_scope) if invocation_task.knowledge_scope else None,
            "source_memory_refs": [item.get("id") for item in evidence if item.get("id") is not None],
            "validation_task_goal": task.goal,
        }

    async def _promote_candidate_collective_memory(self, thread_id: str, task_id: str) -> None:
        await self.context_kernel.promote_candidate_shared_memory(thread_id=thread_id, task_id=task_id)
