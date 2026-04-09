from __future__ import annotations

import json
import uuid
from typing import Any

from agentorch.agents import AgentRegistry, Handoff, Supervisor, TaskPacket
from agentorch.config import RuntimeConfig
from agentorch.core import ActionType, ContextEnvelope, Message, ModelRequest, PromptContext, RunResult, ToolExecutionResult
from agentorch.knowledge import BaseRetriever, KnowledgeBase, RAGContextBuilder, RetrievalQuery
from agentorch.memory import MemoryManager, MemoryRecord
from agentorch.models import BaseModelAdapter
from agentorch.observability import EventBus, Logger, Tracer, UsageTracker
from agentorch.prompts import PromptBuilder
from agentorch.reasoning import BasePolicy, ReactPolicy
from agentorch.sandbox import SandboxManager
from agentorch.skills import SkillRegistry
from agentorch.tools import ToolError, ToolRegistry
from agentorch.workflow import Context, Workflow, WorkflowRunner


class Runtime:
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
        prompt_builder: PromptBuilder | None = None,
        policy: BasePolicy | None = None,
        config: RuntimeConfig | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.model = model
        self.tools = tools or ToolRegistry()
        self.skills = skills or SkillRegistry()
        self.memory = memory or MemoryManager()
        self.retriever = retriever or (knowledge_base.get_retriever() if knowledge_base is not None else None)
        self.knowledge_base = knowledge_base
        self.sandbox = sandbox or SandboxManager()
        self.agent_registry = agent_registry or AgentRegistry()
        self.supervisor = supervisor
        self.rag_context_builder = RAGContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.policy = policy or ReactPolicy()
        self.config = config or RuntimeConfig()
        self.tracer = tracer or Tracer(EventBus(), Logger(file_path=".agentorch/runtime.log"))

    async def run(
        self,
        user_input: str,
        *,
        thread_id: str,
        workflow: Workflow | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunResult:
        envelope = ContextEnvelope(
            request_id=str(uuid.uuid4()),
            run_id=str(uuid.uuid4()),
            thread_id=thread_id,
            trace_id=str(uuid.uuid4()),
            metadata=metadata or {},
        )
        usage_tracker = UsageTracker()
        tool_results: list[ToolExecutionResult] = []
        self.tracer.emit("run_started", envelope.model_dump())

        await self.memory.append_message(thread_id, Message(role="user", content=user_input))

        if self.supervisor is not None and not (metadata or {}).get("_delegated"):
            result = await self._run_supervisor(user_input, envelope)
            self.tracer.emit("run_completed", {**envelope.model_dump(), "status": "completed"})
            return result

        if workflow is not None:
            result = await self._run_workflow(workflow, thread_id=thread_id, user_input=user_input)
            self.tracer.emit("run_completed", {**envelope.model_dump(), "status": "completed"})
            return RunResult(
                request_id=envelope.request_id,
                run_id=envelope.run_id,
                thread_id=thread_id,
                output_text=json.dumps(result, ensure_ascii=False),
                usage=usage_tracker.summary(),
            )

        conversation = await self.memory.get_context_window(thread_id)
        selected_skills = self.skills.instructions_for(user_input) if self.config.auto_select_skills else []
        memory_summary = await self.memory.summarize_thread(thread_id)
        retrieval_context = await self._build_retrieval_context(user_input, envelope)
        task_packet = (metadata or {}).get("task_packet")
        delegation_context = {"handoff": (metadata or {}).get("handoff")} if (metadata or {}).get("handoff") else {}
        agent_role = (metadata or {}).get("agent_role")

        final_text = ""
        messages: list[Message] = []
        for step in range(self.config.max_steps):
            prompt_context = PromptContext(
                system_prompt=self.config.system_prompt,
                user_input=user_input,
                memory_summary=memory_summary,
                retrieval_context=retrieval_context,
                tool_descriptions=self.tools.list_specs(),
                skill_instructions=selected_skills,
                task_packet=task_packet,
                agent_role=agent_role,
                delegation_context=delegation_context,
                conversation=conversation,
            )
            request_messages = self.prompt_builder.build_messages(prompt_context)
            self.tracer.emit("prompt_built", {**envelope.model_dump(), "step": step, "message_count": len(request_messages)})

            response = await self.model.generate(ModelRequest(messages=request_messages, tools=self.tools.list_specs()))
            usage_tracker.add(response.usage)
            self.tracer.emit(
                "model_called",
                {**envelope.model_dump(), "step": step, "finish_reason": response.finish_reason, "tool_calls": len(response.tool_calls)},
            )

            if response.message:
                await self.memory.append_message(thread_id, response.message)
                conversation.append(response.message)
                messages.append(response.message)

            decision = await self.policy.decide(response)
            if decision.action == ActionType.CALL_TOOL:
                for tool_call in decision.tool_calls:
                    result = await self._execute_tool(tool_call.name, tool_call.arguments, envelope)
                    tool_result = ToolExecutionResult(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        output=result.data,
                        is_error=not result.success,
                        error_message=result.error,
                        duration=result.duration,
                    )
                    tool_results.append(tool_result)
                    tool_message = Message(
                        role="tool",
                        content=json.dumps(result.data, ensure_ascii=False),
                        name=tool_call.name,
                        tool_call_id=tool_call.id,
                    )
                    await self.memory.append_message(thread_id, tool_message)
                    conversation.append(tool_message)
                    self.tracer.emit("tool_called", {**envelope.model_dump(), "tool_name": tool_call.name})
                continue

            final_text = decision.content or response.content
            await self.memory.remember(MemoryRecord(thread_id=thread_id, kind="run_summary", content=final_text, tags=["run"]))
            self.tracer.emit("memory_written", {**envelope.model_dump(), "kind": "run_summary"})
            break

        self.tracer.emit("run_completed", {**envelope.model_dump(), "status": "completed"})
        return RunResult(
            request_id=envelope.request_id,
            run_id=envelope.run_id,
            thread_id=thread_id,
            output_text=final_text,
            messages=messages,
            tool_results=tool_results,
            usage=usage_tracker.summary(),
            finish_reason="completed",
        )

    async def _execute_tool(self, name: str, arguments: dict[str, Any], envelope: ContextEnvelope):
        tool = self.tools.get(name)
        try:
            if tool.spec.needs_sandbox:
                sandbox_result = await self.sandbox.execute(
                    "python",
                    arguments.get("code", ""),
                    workdir=arguments.get("workdir"),
                )
                from agentorch.tools.base import ToolResult

                return ToolResult(tool_name=name, data=sandbox_result.model_dump(), success=sandbox_result.exit_code == 0)
            return await self.tools.execute(name, arguments)
        except ToolError as exc:
            self.tracer.emit("run_failed", {**envelope.model_dump(), "error": str(exc), "tool_name": name})
            from agentorch.tools.base import ToolResult

            return ToolResult(tool_name=name, data={}, success=False, error=str(exc))

    async def _build_retrieval_context(self, user_input: str, envelope: ContextEnvelope) -> str:
        if not self.config.enable_retrieval or self.retriever is None:
            return ""
        self.tracer.emit("retrieval_started", {**envelope.model_dump(), "query": user_input})
        chunks = await self.retriever.retrieve(
            RetrievalQuery(query=user_input, top_k=self.config.max_retrieved_chunks)
        )
        context = self.rag_context_builder.build(chunks)
        self.tracer.emit(
            "retrieval_completed",
            {**envelope.model_dump(), "query": user_input, "chunk_count": len(chunks)},
        )
        return context

    async def _run_supervisor(self, user_input: str, envelope: ContextEnvelope) -> RunResult:
        task = TaskPacket(
            task_id=envelope.run_id,
            goal=user_input,
            metadata={"thread_id": envelope.thread_id, "delegation_depth": 0},
        )
        self.tracer.emit("supervisor_routed", {**envelope.model_dump(), "task_id": task.task_id})
        plan = await self.supervisor.create_plan(task)
        delegated_results = []
        for invocation in plan.invocations:
            registered = self.agent_registry.get(invocation.agent_name)
            handoff = Handoff(
                from_agent="supervisor",
                to_agent=registered.spec.name,
                task=invocation.task,
                reason=plan.reason,
                metadata={"parent_run_id": envelope.run_id},
            )
            self.tracer.emit(
                "handoff_created",
                {**envelope.model_dump(), "agent_name": registered.spec.name, "task_id": invocation.task.task_id},
            )
            self.tracer.emit(
                "agent_delegated",
                {**envelope.model_dump(), "agent_name": registered.spec.name, "task_id": invocation.task.task_id},
            )
            run_result = await registered.agent.run(
                invocation.task.goal,
                thread_id=invocation.task.metadata.get("thread_id", invocation.task.task_id),
                metadata={"task_packet": invocation.task.model_dump(), "handoff": handoff.model_dump(), "_delegated": True},
            )
            delegated_results.append((registered.spec.name, invocation.task.task_id, run_result.output_text))
            self.tracer.emit(
                "handoff_completed",
                {**envelope.model_dump(), "agent_name": registered.spec.name, "task_id": invocation.task.task_id},
            )
        for result in delegated_results:
            self.tracer.emit(
                "agent_completed",
                {**envelope.model_dump(), "agent_name": result[0], "task_id": result[1]},
            )
        output = "\n\n".join(f"[{item[0]}] {item[2]}" for item in delegated_results)
        return RunResult(
            request_id=envelope.request_id,
            run_id=envelope.run_id,
            thread_id=envelope.thread_id,
            output_text=output,
            usage=UsageTracker().summary(),
        )

    async def _run_workflow(self, workflow: Workflow, *, thread_id: str, user_input: str) -> dict[str, Any]:
        context = Context(thread_id=thread_id, user_input=user_input)

        async def handle_model(node, ctx):
            result = await self.run(node.config.get("prompt", ctx.user_input), thread_id=thread_id)
            return {"status": "completed", "output_text": result.output_text}

        async def handle_tool(node, ctx):
            arguments = dict(node.config.get("arguments", {}))
            if "__from_input__" in arguments:
                arguments["query"] = ctx.user_input
                del arguments["__from_input__"]
            result = await self.tools.execute(node.config["tool_name"], arguments)
            return {"status": "completed" if result.success else "failed", "output": result.data}

        async def handle_router(node, ctx):
            route = node.config.get("default_route")
            variable = node.config.get("variable")
            if variable and ctx.variables.get(variable):
                route = ctx.variables[variable].get("route", route)
            return {"status": "completed", "route": route}

        async def handle_memory(node, ctx):
            action = node.config.get("action")
            if action == "remember":
                await self.memory.remember(
                    MemoryRecord(
                        thread_id=thread_id,
                        kind=node.config.get("kind", "note"),
                        content=node.config.get("content", ctx.user_input),
                        tags=node.config.get("tags", []),
                    )
                )
                return {"status": "completed"}
            if action == "search":
                return {"status": "completed", "records": await self.memory.search(thread_id=thread_id, query=node.config.get("query"))}
            return {"status": "completed"}

        async def handle_agent(node, ctx):
            registered = self.agent_registry.get(node.config["agent_name"])
            task = TaskPacket(
                task_id=f"{thread_id}:{node.id}",
                goal=node.config.get("goal", ctx.user_input),
                input=node.config.get("input", {}),
                context={"workflow_node": node.id, "variables": ctx.variables},
                expected_output=node.config.get("expected_output"),
                metadata={"thread_id": thread_id, "delegation_depth": 1},
            )
            self.tracer.emit(
                "agent_delegated",
                {"thread_id": thread_id, "agent_name": registered.spec.name, "task_id": task.task_id, "node_id": node.id},
            )
            run_result = await registered.agent.run(
                task.goal,
                thread_id=node.config.get("share_thread_id", thread_id) if node.config.get("share_thread_id", True) else task.task_id,
                metadata={"task_packet": task.model_dump(), "_delegated": True, "agent_role": registered.spec.description},
            )
            result = {
                "status": "completed",
                "output_text": run_result.output_text,
                "route": node.config.get("success_route"),
            }
            if output_key := node.config.get("output_key"):
                ctx.variables[output_key] = result
            self.tracer.emit(
                "agent_completed",
                {"thread_id": thread_id, "agent_name": registered.spec.name, "task_id": task.task_id, "node_id": node.id},
            )
            return result

        runner = WorkflowRunner(
            handlers={
                "agent": handle_agent,
                "model": handle_model,
                "tool": handle_tool,
                "router": handle_router,
                "memory": handle_memory,
            }
        )
        return await runner.run(workflow, context)
