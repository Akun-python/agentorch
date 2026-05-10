from __future__ import annotations

import inspect
import json
from typing import Any

from agentorch.agents import TaskArtifact, TaskPacket
from agentorch.config import ModelConfig
from agentorch.feedback import FeedbackKind
from agentorch.memory import MemoryRecord
from agentorch.workflow import Context, Workflow, WorkflowRunner


class RuntimeWorkflowExecutor:
    """Internal workflow-node executor for Runtime."""

    def __init__(
        self,
        *,
        runtime: Any,
        workflow: Workflow,
        thread_id: str,
        user_input: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.runtime = runtime
        self.workflow = workflow
        self.thread_id = thread_id
        self.user_input = user_input
        self.metadata = dict(metadata or {})

    async def run(self) -> dict[str, Any]:
        context = Context(
            thread_id=self.thread_id,
            user_input=self.user_input,
            state=dict(self.metadata.get("workflow_state", {})),
            variables=dict(self.metadata.get("workflow_variables", {})),
            resume_from=self.metadata.get("resume_from"),
        )
        runner = WorkflowRunner(self._build_handlers())
        return await runner.run(self.workflow, context)

    async def _resolve(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    async def _close_candidate(self, candidate: Any) -> None:
        if hasattr(candidate, "aclose"):
            await self._resolve(candidate.aclose())
        elif hasattr(candidate, "close"):
            candidate.close()

    def _resolve_variable_path(self, path: str, ctx: Context) -> Any:
        current: Any = ctx.variables
        for part in str(path).split("."):
            if isinstance(current, dict):
                if part not in current:
                    raise KeyError(f"Unknown workflow variable path: {path}")
                current = current[part]
                continue
            if isinstance(current, list):
                current = current[int(part)]
                continue
            raise KeyError(f"Unknown workflow variable path: {path}")
        return current

    def _resolve_tool_arguments(self, value: Any, ctx: Context) -> Any:
        if isinstance(value, dict):
            if set(value.keys()) == {"$from"}:
                return self._resolve_variable_path(str(value["$from"]), ctx)
            return {key: self._resolve_tool_arguments(item, ctx) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_tool_arguments(item, ctx) for item in value]
        return value

    async def handle_model(self, node, ctx):
        child_metadata = dict(self.metadata)
        if node.config.get("model") is not None:
            child_metadata["model_override"] = node.config["model"]
        elif node.config.get("model_config") is not None:
            child_metadata["model_override"] = ModelConfig.from_any(node.config["model_config"]).model
        for key in (
            "reasoning_strategy",
            "rag_strategy",
            "context_policy",
            "state_policy",
            "coordination_policy",
            "memory_policy",
            "knowledge_scope",
            "skill_routing",
        ):
            if node.config.get(key) is not None:
                child_metadata[key] = node.config[key]
        task_context_from_variables = list(node.config.get("task_context_from_variables", []))
        if task_context_from_variables:
            upstream_context = {
                variable: ctx.variables.get(variable)
                for variable in task_context_from_variables
                if variable in ctx.variables
            }
            if upstream_context:
                task_packet = dict(child_metadata.get("task_packet") or {})
                task_context = dict(task_packet.get("context") or {})
                workflow_variables = dict(task_context.get("workflow_variables") or {})
                workflow_variables.update(upstream_context)
                task_context["workflow_variables"] = workflow_variables
                task_context.update(upstream_context)
                task_packet.setdefault("task_id", f"{self.thread_id}:{node.id}")
                task_packet.setdefault("goal", node.config.get("goal", ctx.user_input))
                task_packet.setdefault("origin_agent", "workflow")
                task_packet["context"] = task_context
                child_metadata["task_packet"] = task_packet
        result = await self.runtime.run(
            node.config.get("prompt", ctx.user_input),
            thread_id=self.thread_id,
            metadata=child_metadata,
        )
        payload = {"status": "completed", "output_text": result.output_text}
        if output_key := node.config.get("output_key"):
            ctx.variables[output_key] = payload
        return payload

    async def handle_tool(self, node, ctx):
        arguments = self._resolve_tool_arguments(dict(node.config.get("arguments", {})), ctx)
        if "__from_input__" in arguments:
            arguments["query"] = ctx.user_input
            del arguments["__from_input__"]
        result = await self.runtime.tools.execute(node.config["tool_name"], arguments)
        payload = {"status": "completed" if result.success else "failed", "output": result.data}
        if output_key := node.config.get("output_key"):
            ctx.variables[output_key] = payload
        return payload

    async def handle_router(self, node, ctx):
        route = node.config.get("default_route")
        variable = node.config.get("variable")
        if variable and ctx.variables.get(variable):
            route = ctx.variables[variable].get("route", route)
        return {"status": "completed", "route": route}

    async def handle_retrieve(self, node, ctx):
        query = node.config.get("question", node.config.get("query", ctx.user_input))
        local_envelope = self.runtime._create_context_envelope(thread_id=self.thread_id)
        payload = await self.runtime._build_retrieval_context(
            query,
            local_envelope,
            knowledge_scope=node.config.get("knowledge_scope", self.runtime.config.default_knowledge_scope),
            retrieval_overrides={
                "mount_context": "workflow",
                "goal": node.config.get("goal"),
                "must_cover": node.config.get("must_cover", []),
                "rag_mode": node.config.get("rag_mode"),
                "mount": node.config.get("mount", "workflow_only"),
                "injection_policy": node.config.get("injection_policy"),
                "sources": node.config.get("sources", []),
                "file_types": node.config.get("file_types", []),
                "path_filters": node.config.get("path_filters", []),
                "mime_filters": node.config.get("mime_filters", []),
                "max_steps": node.config.get("max_steps", self.runtime.config.retrieval_budget_steps),
                "max_documents": node.config.get("max_documents", self.runtime.config.retrieval_budget_documents),
            },
        )
        result = {
            "status": "completed",
            "summary": payload.get("report", {}).get("summary", payload["context"]),
            "retrieval_context": payload["context"],
            "evidence": payload["evidence"],
            "citations": payload["citations"],
            "coverage": payload.get("coverage", {}),
            "visited_sources": payload.get("visited_sources", []),
            "visited_documents": payload.get("report", {}).get("visited_documents", []),
            "report": payload.get("report", {}),
        }
        if output_key := node.config.get("output_key"):
            ctx.variables[output_key] = result
        return result

    async def handle_rag_router(self, node, ctx):
        route = node.config.get("default_route", "deliberative")
        query = node.config.get("question", ctx.user_input).lower()
        if any(token in query for token in ("summary", "summarize", "overview", "概述", "总结")):
            route = "classic"
        elif any(token in query for token in ("page", "section", "evidence", "where", "哪一页", "证据")):
            route = "deliberative"
        if output_key := node.config.get("output_key"):
            ctx.variables[output_key] = {"route": route}
        return {"status": "completed", "route": route}

    async def handle_rag_mount(self, node, ctx):
        source = ctx.variables.get(node.config.get("from_variable", ""), {})
        mount_to = node.config.get("mount_result_to", "context")
        target_key = node.config.get("target_key", "mounted_retrieval")
        if mount_to in {"context", "variable", "agent_input"}:
            ctx.variables[target_key] = source
            return {"status": "completed", "mounted_to": mount_to, "target_key": target_key}
        artifact = TaskArtifact(
            name=node.config.get("name", node.id),
            kind="retrieval_report",
            content=source,
            metadata={"artifact_id": node.config.get("artifact_id", f"{self.thread_id}:{node.id}")},
        )
        record = await self.runtime.memory.write_workspace_record(
            self.thread_id,
            task_id=f"{self.thread_id}:{node.id}",
            owner_agent="workflow",
            artifact=artifact,
        )
        ctx.variables[target_key] = {"artifact_id": record.artifact_id, "report": source}
        return {"status": "completed", "mounted_to": "artifact", "artifact_id": record.artifact_id, "target_key": target_key}

    async def handle_rag_evaluate(self, node, ctx):
        source = ctx.variables.get(node.config.get("from_variable", ""), {})
        coverage = source.get("coverage", {})
        evidence = source.get("evidence", [])
        missing = coverage.get("missing", [])
        result = {
            "status": "completed",
            "score": float(len(evidence)) - 2.0 * float(len(missing)),
            "coverage": coverage,
            "evidence_count": len(evidence),
            "visited_sources": source.get("visited_sources", []),
        }
        if output_key := node.config.get("output_key"):
            ctx.variables[output_key] = result
        return result

    async def handle_memory(self, node, ctx):
        action = node.config.get("action")
        if action == "remember":
            await self.runtime.memory.remember(
                MemoryRecord(
                    thread_id=self.thread_id,
                    kind=node.config.get("kind", "note"),
                    content=node.config.get("content", ctx.user_input),
                    tags=node.config.get("tags", []),
                )
            )
            return {"status": "completed"}
        if action == "search":
            return {
                "status": "completed",
                "records": await self.runtime.memory.search(thread_id=self.thread_id, query=node.config.get("query")),
            }
        return {"status": "completed"}

    async def handle_agent(self, node, ctx):
        registered = self.runtime.agent_registry.get(node.config["agent_name"])
        task_input = dict(node.config.get("input", {}))
        if input_var := node.config.get("input_from_variable"):
            task_input["retrieval_input"] = ctx.variables.get(input_var, {})
        knowledge_scope = node.config.get("knowledge_scope")
        if knowledge_scope is None:
            knowledge_scope = list(registered.spec.allowed_knowledge_scopes)
        task = TaskPacket(
            task_id=f"{self.thread_id}:{node.id}",
            goal=node.config.get("goal", ctx.user_input),
            input=task_input,
            context={"workflow_node": node.id, "variables": ctx.variables},
            expected_output=node.config.get("expected_output"),
            parent_task_id=node.config.get("parent_task_id"),
            origin_agent=node.config.get("origin_agent", "workflow"),
            knowledge_scope=knowledge_scope,
            metadata={"thread_id": self.thread_id, "delegation_depth": 1},
        )
        self.runtime.tracer.emit(
            "agent_delegated",
            {"thread_id": self.thread_id, "agent_name": registered.spec.name, "task_id": task.task_id, "node_id": node.id},
        )
        run_result = await registered.agent.run(
            task.goal,
            thread_id=node.config.get("share_thread_id", self.thread_id) if node.config.get("share_thread_id", True) else task.task_id,
            metadata={
                "task_packet": task.model_dump(),
                "_delegated": True,
                "agent_role": registered.spec.name,
                "knowledge_scope": task.knowledge_scope,
                "parent_task_id": task.parent_task_id,
                "rag_strategy": node.config.get("rag_strategy"),
                "reasoning_strategy": node.config.get("reasoning_strategy"),
                "context_policy": node.config.get("context_policy"),
                "state_policy": node.config.get("state_policy"),
                "coordination_policy": node.config.get("coordination_policy"),
                "memory_policy": node.config.get("memory_policy"),
            },
        )
        result = {
            "status": run_result.status,
            "output_text": run_result.output_text,
            "structured_output": {"messages": [message.model_dump() for message in run_result.messages]},
            "route": node.config.get("success_route"),
        }
        if run_result.status == "waiting_human":
            result.update(
                {
                    "feedback_id": run_result.feedback_id,
                    "await_reason": run_result.await_reason,
                    "requires_response": run_result.requires_response,
                    "response_schema": run_result.response_schema,
                }
            )
        if output_key := node.config.get("output_key"):
            ctx.variables[output_key] = result
        self.runtime.tracer.emit(
            "agent_completed",
            {"thread_id": self.thread_id, "agent_name": registered.spec.name, "task_id": task.task_id, "node_id": node.id},
        )
        return result

    async def handle_artifact(self, node, ctx):
        payload = ctx.variables.get(node.config.get("from_variable", ""), {})
        artifact = TaskArtifact(
            name=node.config.get("name", node.id),
            kind=node.config.get("artifact_kind", "text"),
            content=payload,
            metadata={"artifact_id": node.config.get("artifact_id", f"{self.thread_id}:{node.id}")},
        )
        record = await self.runtime.memory.write_workspace_record(
            self.thread_id,
            task_id=f"{self.thread_id}:{node.id}",
            owner_agent="workflow",
            artifact=artifact,
        )
        self.runtime.tracer.emit(
            "artifact_created",
            {"thread_id": self.thread_id, "artifact_id": record.artifact_id, "node_id": node.id},
        )
        return {"status": "completed", "artifact_id": record.artifact_id}

    async def handle_aggregate(self, node, ctx):
        sources = node.config.get("sources", [])
        combined = {source: ctx.variables.get(source, {}) for source in sources}
        result = {"status": "completed", "summary": json.dumps(combined, ensure_ascii=False), "combined": combined}
        if output_key := node.config.get("output_key"):
            ctx.variables[output_key] = result
        self.runtime.tracer.emit(
            "aggregation_completed",
            {"thread_id": self.thread_id, "node_id": node.id, "source_count": len(sources)},
        )
        return result

    async def handle_evolution(self, node, ctx):
        target = node.config.get("session") or node.config.get("manager")
        if target is None:
            return {"status": "failed", "error": "evolution_target_missing"}

        tasks = node.config.get("tasks")
        if node.config.get("tasks_from_variable"):
            tasks = ctx.variables.get(node.config["tasks_from_variable"], tasks)
        tasks = list(tasks or [])

        result = await self._resolve(target.evolve(tasks=tasks))
        best_candidate_summary = None
        if node.config.get("build_best_candidate", True):
            candidate = None
            if hasattr(target, "build_best_candidate"):
                candidate = await self._resolve(target.build_best_candidate(result))
            elif hasattr(target, "build_candidate"):
                candidate = await self._resolve(target.build_candidate(result.best_genome))
            if candidate is not None:
                summarize = getattr(target, "summarize_candidate", None)
                if callable(summarize):
                    best_candidate_summary = await self._resolve(summarize(candidate))
                else:
                    from agentorch.evolution.session import summarize_evolution_candidate

                    best_candidate_summary = summarize_evolution_candidate(candidate)
                await self._close_candidate(candidate)

        payload = {
            "status": "completed",
            "best_genome": result.best_genome.model_dump(),
            "best_evaluation": result.best_evaluation.model_dump(),
            "best_candidate": best_candidate_summary,
        }
        if node.config.get("include_history"):
            payload["history"] = [generation.model_dump() for generation in result.history]
        if node.config.get("persist_artifact", True):
            artifact = TaskArtifact(
                name=node.config.get("name", node.id),
                kind="evolution_result",
                content=payload,
                metadata={"artifact_id": node.config.get("artifact_id", f"{self.thread_id}:{node.id}")},
            )
            record = await self.runtime.memory.write_workspace_record(
                self.thread_id,
                task_id=f"{self.thread_id}:{node.id}",
                owner_agent="workflow",
                artifact=artifact,
            )
            payload["artifact_id"] = record.artifact_id
        if output_key := node.config.get("output_key"):
            ctx.variables[output_key] = payload
        self.runtime.tracer.emit(
            "evolution_completed",
            {
                "thread_id": self.thread_id,
                "node_id": node.id,
                "best_genome_id": result.best_genome.id,
                "fitness": result.best_evaluation.fitness,
            },
        )
        return payload

    async def handle_approval(self, node, ctx):
        approved = node.config.get("approved", True)
        return {
            "status": "completed",
            "approved": approved,
            "route": node.config.get("approved_route", "approved" if approved else "rejected"),
        }

    async def _resolved_human_response(self, node, ctx):
        feedback_id = node.config.get("feedback_id") or ctx.state.get(f"{node.id}:feedback_id")
        if feedback_id and self.runtime.human_feedback is not None:
            pending = await self.runtime.human_feedback.get(feedback_id)
            if pending is not None and pending.response is not None:
                return feedback_id, pending.response
        return feedback_id, None

    async def handle_human_notify(self, node, ctx):
        if self.runtime.human_feedback is None:
            return {"status": "completed", "skipped": True}
        handle = await self.runtime.human_feedback.notify(
            kind=node.config.get("kind", FeedbackKind.PROGRESS_UPDATE),
            title=node.config.get("title", node.id),
            message=node.config.get("message", ctx.user_input),
            task_id=f"{self.thread_id}:{node.id}",
            metadata={"workflow_node_id": node.id},
        )
        return {"status": "completed", "feedback_id": handle.feedback_id}

    async def handle_human_input(self, node, ctx):
        if self.runtime.human_feedback is None:
            return {"status": "failed", "error": "human_feedback_not_configured"}
        feedback_id, response = await self._resolved_human_response(node, ctx)
        if response is not None:
            result = {"status": "completed", "feedback_id": feedback_id, "response": response.content}
            if output_key := node.config.get("output_key"):
                ctx.variables[output_key] = result
            return result
        handle = await self.runtime.human_feedback.request_input(
            title=node.config.get("title", node.id),
            message=node.config.get("message", ctx.user_input),
            response_schema=node.config.get("response_schema"),
            task_id=f"{self.thread_id}:{node.id}",
            metadata={
                "workflow_node_id": node.id,
                "resume_from": node.id,
                "workflow_state": dict(ctx.state),
                "workflow_variables": dict(ctx.variables),
            },
            blocking=True,
        )
        ctx.state[f"{node.id}:feedback_id"] = handle.feedback_id
        return {
            "status": "waiting_human",
            "feedback_id": handle.feedback_id,
            "await_reason": node.config.get("title", node.id),
            "requires_response": True,
            "response_schema": node.config.get("response_schema"),
            "resume_from": node.id,
            "workflow_state": dict(ctx.state),
            "workflow_variables": dict(ctx.variables),
        }

    async def handle_human_approval(self, node, ctx):
        if self.runtime.human_feedback is None:
            return {"status": "failed", "error": "human_feedback_not_configured"}
        feedback_id, response = await self._resolved_human_response(node, ctx)
        if response is not None:
            approved = bool(response.content.get("approved")) if isinstance(response.content, dict) else bool(response.content)
            return {
                "status": "completed",
                "feedback_id": feedback_id,
                "approved": approved,
                "response": response.content,
                "route": node.config.get("approved_route", "approved" if approved else "rejected"),
            }
        handle = await self.runtime.human_feedback.request_approval(
            title=node.config.get("title", node.id),
            message=node.config.get("message", ctx.user_input),
            response_schema=node.config.get("response_schema"),
            task_id=f"{self.thread_id}:{node.id}",
            metadata={
                "workflow_node_id": node.id,
                "resume_from": node.id,
                "workflow_state": dict(ctx.state),
                "workflow_variables": dict(ctx.variables),
            },
            blocking=True,
        )
        ctx.state[f"{node.id}:feedback_id"] = handle.feedback_id
        return {
            "status": "waiting_human",
            "feedback_id": handle.feedback_id,
            "await_reason": node.config.get("title", node.id),
            "requires_response": True,
            "response_schema": node.config.get("response_schema"),
            "resume_from": node.id,
            "workflow_state": dict(ctx.state),
            "workflow_variables": dict(ctx.variables),
        }

    def _build_handlers(self) -> dict[str, Any]:
        return {
            "agent": self.handle_agent,
            "aggregate": self.handle_aggregate,
            "approval": self.handle_approval,
            "artifact": self.handle_artifact,
            "evolution": self.handle_evolution,
            "human_approval": self.handle_human_approval,
            "human_input": self.handle_human_input,
            "human_notify": self.handle_human_notify,
            "memory": self.handle_memory,
            "model": self.handle_model,
            "rag_evaluate": self.handle_rag_evaluate,
            "rag_mount": self.handle_rag_mount,
            "rag_router": self.handle_rag_router,
            "retrieve": self.handle_retrieve,
            "router": self.handle_router,
            "tool": self.handle_tool,
        }


async def execute_runtime_workflow(
    runtime: Any,
    workflow: Workflow,
    *,
    thread_id: str,
    user_input: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await RuntimeWorkflowExecutor(
        runtime=runtime,
        workflow=workflow,
        thread_id=thread_id,
        user_input=user_input,
        metadata=metadata,
    ).run()
