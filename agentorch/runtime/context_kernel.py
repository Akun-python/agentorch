from __future__ import annotations

from typing import Any

from agentorch.agents import SharedNote
from agentorch.core import PromptContext
from agentorch.reasoning import ReasoningSessionContext
from agentorch.runtime.context_compaction import build_handoff_capsule, compact_task_packet
from agentorch.strategies import (
    ContextPolicy,
    ContextSelector,
    CoordinationPolicy,
    DefaultContextSelector,
    DefaultMemoryEvaluator,
    DefaultRoutePlanner,
    MemoryEvaluator,
    MemoryPolicy,
    RoutePlanner,
    StatePolicy,
)


class ContextKernel:
    """Single shared context-management kernel used across runtime paths."""

    def __init__(
        self,
        *,
        runtime: Any,
        context_selector: ContextSelector | None = None,
        route_planner: RoutePlanner | None = None,
        memory_evaluator: MemoryEvaluator | None = None,
    ) -> None:
        self.runtime = runtime
        self.context_selector = context_selector or DefaultContextSelector()
        self.route_planner = route_planner or DefaultRoutePlanner()
        self.memory_evaluator = memory_evaluator or DefaultMemoryEvaluator()

    def _agent_default(self, agent_role: str | None, field_name: str) -> Any | None:
        if not agent_role:
            return None
        try:
            registered = self.runtime.agent_registry.get(agent_role)
        except Exception:
            return None
        return getattr(registered.spec.policy_profile, field_name, None)

    def resolve_context_policy(
        self,
        *,
        metadata: dict[str, Any] | None = None,
        node_config: dict[str, Any] | None = None,
        agent_role: str | None = None,
    ) -> ContextPolicy:
        metadata = metadata or {}
        node_config = node_config or {}
        if node_config.get("context_policy") is not None:
            return ContextPolicy.from_any(node_config["context_policy"])
        if metadata.get("context_policy") is not None:
            return ContextPolicy.from_any(metadata["context_policy"])
        default_value = self._agent_default(agent_role, "default_context_policy")
        if default_value is not None:
            return ContextPolicy.from_any(default_value)
        return ContextPolicy.from_any(self.runtime.config.context_policy)

    def resolve_state_policy(
        self,
        *,
        metadata: dict[str, Any] | None = None,
        node_config: dict[str, Any] | None = None,
        agent_role: str | None = None,
    ) -> StatePolicy:
        metadata = metadata or {}
        node_config = node_config or {}
        if node_config.get("state_policy") is not None:
            return StatePolicy.from_any(node_config["state_policy"])
        if metadata.get("state_policy") is not None:
            return StatePolicy.from_any(metadata["state_policy"])
        default_value = self._agent_default(agent_role, "default_state_policy")
        if default_value is not None:
            return StatePolicy.from_any(default_value)
        return StatePolicy.from_any(self.runtime.config.state_policy)

    def resolve_coordination_policy(
        self,
        *,
        metadata: dict[str, Any] | None = None,
        node_config: dict[str, Any] | None = None,
        agent_role: str | None = None,
    ) -> CoordinationPolicy:
        metadata = metadata or {}
        node_config = node_config or {}
        if node_config.get("coordination_policy") is not None:
            return CoordinationPolicy.from_any(node_config["coordination_policy"])
        if metadata.get("coordination_policy") is not None:
            return CoordinationPolicy.from_any(metadata["coordination_policy"])
        default_value = self._agent_default(agent_role, "default_coordination_policy")
        if default_value is not None:
            return CoordinationPolicy.from_any(default_value)
        return CoordinationPolicy.from_any(self.runtime.config.coordination_policy)

    def resolve_memory_policy(
        self,
        *,
        metadata: dict[str, Any] | None = None,
        node_config: dict[str, Any] | None = None,
        agent_role: str | None = None,
    ) -> MemoryPolicy:
        metadata = metadata or {}
        node_config = node_config or {}
        if node_config.get("memory_policy") is not None:
            return MemoryPolicy.from_any(node_config["memory_policy"])
        if metadata.get("memory_policy") is not None:
            return MemoryPolicy.from_any(metadata["memory_policy"])
        default_value = self._agent_default(agent_role, "default_memory_policy")
        if default_value is not None:
            return MemoryPolicy.from_any(default_value)
        return MemoryPolicy.from_any(self.runtime.config.memory_policy)

    async def prepare_prompt_context(
        self,
        context: ReasoningSessionContext,
        *,
        output_instruction: str | None = None,
        stage: str = "respond",
    ) -> PromptContext:
        context_policy = self.resolve_context_policy(metadata=context.envelope.metadata, agent_role=context.agent_role)
        state_policy = self.resolve_state_policy(metadata=context.envelope.metadata, agent_role=context.agent_role)
        coordination_policy = self.resolve_coordination_policy(metadata=context.envelope.metadata, agent_role=context.agent_role)
        memory_policy = self.resolve_memory_policy(metadata=context.envelope.metadata, agent_role=context.agent_role)

        task_context = (context.task_packet or {}).get("context", {})
        selected_skill_routes = list(context.envelope.metadata.get("selected_skill_routes") or [])
        skill_prompt_payload = self.runtime._skill_prompt_payload(context.envelope, context.selected_skills)
        shared_memory_context = task_context.get("shared_memory_context") or task_context.get("collective_memory_context")
        shared_memory_evidence = task_context.get("shared_memory_evidence")
        if shared_memory_evidence is None:
            shared_memory_evidence = task_context.get("collective_memory_evidence", [])
        shared_memory_citations = task_context.get("shared_memory_citations")
        if shared_memory_citations is None:
            shared_memory_citations = task_context.get("collective_memory_citations", [])

        prompt_context = PromptContext(
            system_prompt=self.runtime.config.system_prompt,
            user_input=context.user_input,
            memory_summary=context.memory_summary if state_policy.retention_mode != "window_only" else None,
            retrieval_context=context.retrieval_payload.get("context"),
            collective_memory_context=shared_memory_context,
            retrieved_evidence=context.retrieval_payload.get("evidence", []),
            citations=context.retrieval_payload.get("citations", []),
            retrieval_report=context.retrieval_payload.get("report"),
            retrieval_coverage=context.retrieval_payload.get("coverage"),
            collective_memory_evidence=shared_memory_evidence,
            collective_memory_citations=shared_memory_citations,
            retrieval_plan=context.retrieval_payload.get("plan"),
            knowledge_scope=context.retrieval_payload.get("knowledge_scope", []),
            tool_descriptions=self.runtime._tool_specs_for_request(context.envelope),
            available_skills=skill_prompt_payload["available_skills"],
            skill_instructions=skill_prompt_payload["skill_instructions"],
            skill_resources=skill_prompt_payload["skill_resources"],
            task_packet=context.task_packet,
            agent_role=context.agent_role,
            delegation_context=context.delegation_context,
            conversation=context.conversation,
            output_instruction=output_instruction,
            prompt_variables={
                "thread_id": context.thread_id,
                "user_input": context.user_input,
                "task_context": task_context,
                "retrieval_payload": context.retrieval_payload,
            },
        )
        compacted, budget = await self.context_selector.select(
            prompt_context,
            context_policy=context_policy,
            state_policy=state_policy,
            stage=stage,
            selected_skill_routes=selected_skill_routes,
            rerank_callback=lambda segments, top_k: self.runtime._rerank_context_segments(
                segments,
                top_k,
                user_input=context.user_input,
                stage=stage,
                agent_role=context.agent_role,
            ),
        )
        context.envelope.metadata["context_budget_report"] = budget
        for key in ("selected_context_segments", "dropped_context_segments", "salience_report", "attention_profile", "compaction_trace"):
            if key in budget:
                context.envelope.metadata[key] = budget[key]
        context.envelope.metadata["resolved_context_policy"] = context_policy.model_dump()
        context.envelope.metadata["resolved_state_policy"] = state_policy.model_dump()
        context.envelope.metadata["resolved_coordination_policy"] = coordination_policy.model_dump()
        context.envelope.metadata["resolved_memory_policy"] = memory_policy.model_dump()
        context.envelope.metadata["resolved_policies"] = {
            "context": context_policy.model_dump(),
            "state": state_policy.model_dump(),
            "coordination": coordination_policy.model_dump(),
            "memory": memory_policy.model_dump(),
        }
        context.envelope.metadata["memory_policy_report"] = {
            "kind": memory_policy.kind,
            "policy_bundle": self.memory_evaluator.policy_bundle(memory_policy),
            "runtime_config": self.memory_evaluator.resolved_runtime_config(memory_policy),
            "collective_promotion_policy": memory_policy.collective_promotion_policy,
            "trail_knowledge_enabled": memory_policy.trail_knowledge_enabled,
            "validation_threshold": memory_policy.validation_threshold,
        }
        return compacted

    async def prepare_supervisor_task_context(
        self,
        *,
        user_input: str,
        thread_id: str,
        coordination_policy: CoordinationPolicy,
        memory_policy: MemoryPolicy,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        shared_records: list[dict[str, Any]] = []
        if memory_policy.recall_mode != "off":
            recall_config = self.memory_evaluator.resolved_runtime_config(memory_policy)
            recall_limit = max(
                1,
                int(recall_config.get("recall_top_k", self.runtime.config.max_retrieved_chunks) or self.runtime.config.max_retrieved_chunks),
            )
            shared_records = await self.runtime.memory.search_collective_memory(
                query=user_input,
                thread_id=thread_id,
                limit=recall_limit,
            )
        payload = self.runtime._collective_memory_payload(shared_records)
        payload["coordination"] = self.route_planner.build_supervisor_context(
            task_context={"goal": user_input, "scope": self.runtime.config.default_knowledge_scope},
            coordination_policy=coordination_policy,
        )
        payload["coordination_report"] = {
            "route_mode": coordination_policy.route_mode,
            "handoff_mode": coordination_policy.handoff_mode,
            "workspace_mode": coordination_policy.workspace_mode,
            "alert_mode": coordination_policy.alert_mode,
        }
        return payload, shared_records

    def build_child_handoff_payload(
        self,
        *,
        task_packet: dict[str, Any],
        handoff: dict[str, Any],
        coordination_policy: CoordinationPolicy,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        if coordination_policy.handoff_mode == "raw_allowed":
            return task_packet, handoff

        compacted_task = compact_task_packet(task_packet)
        if compacted_task is None:
            return None, build_handoff_capsule(task_packet, handoff)

        if coordination_policy.handoff_mode == "summary_plus_artifacts":
            artifact_refs = task_packet.get("artifact_refs") or []
            artifacts = task_packet.get("artifacts") or []
            if artifact_refs:
                compacted_task["artifact_refs"] = artifact_refs
            if artifacts:
                compacted_task["artifacts"] = artifacts[:2]
        return compacted_task, build_handoff_capsule(task_packet, handoff)

    async def after_agent_run(
        self,
        *,
        thread_id: str,
        user_input: str,
        final_output: str,
        metadata: dict[str, Any] | None,
        conversation: list[Any],
    ) -> dict[str, Any]:
        metadata = metadata or {}
        agent_role = metadata.get("agent_role")
        task_packet = metadata.get("task_packet")
        memory_policy = self.resolve_memory_policy(metadata=metadata, agent_role=agent_role)
        coordination_policy = self.resolve_coordination_policy(metadata=metadata, agent_role=agent_role)

        promotion_trace = await self.memory_evaluator.promote_episode(
            self.runtime.memory,
            policy=memory_policy,
            thread_id=thread_id,
            user_input=user_input,
            final_output=final_output,
            retrieval_payload=metadata.get("retrieval_payload") or {},
            task_packet=task_packet,
            agent_role=agent_role,
            knowledge_scope=metadata.get("knowledge_scope") or self.runtime.config.default_knowledge_scope,
            conversation=conversation,
        )
        if agent_role:
            await self.runtime.memory.add_shared_note(
                thread_id,
                SharedNote(
                    note_id=f"{thread_id}:{metadata.get('parent_task_id') or 'run'}:final",
                    task_id=(task_packet or {}).get("task_id", thread_id),
                    author_agent=agent_role,
                    content=final_output,
                    metadata={
                        "parent_task_id": metadata.get("parent_task_id"),
                        "collective_candidate": True,
                        "memory_kind": "lesson_learned",
                        "coordination_policy": coordination_policy.model_dump(),
                    },
                ),
            )
        state_refresh_report = await self.refresh_state(
            thread_id=thread_id,
            agent_role=agent_role,
            final_output=final_output,
            task_packet=task_packet,
        )
        return {
            "memory_promotion_trace": promotion_trace,
            "state_refresh_report": state_refresh_report,
        }

    async def refresh_state(
        self,
        *,
        thread_id: str,
        agent_role: str | None,
        final_output: str,
        task_packet: dict[str, Any] | None,
    ) -> dict[str, Any]:
        state_policy = self.resolve_state_policy(metadata=(task_packet or {}).get("metadata") or {}, agent_role=agent_role)
        messages = await self.runtime.memory.get_thread_messages(thread_id)
        message_count = len(messages)
        owner = agent_role or "runtime"
        report = {"message_count": message_count, "summary_refresh": False, "snapshot": False, "rollup": False}

        if state_policy.summary_refresh_every > 0 and message_count and message_count % state_policy.summary_refresh_every == 0:
            summary = await self.runtime.memory.summarize_thread(thread_id)
            await self.runtime.memory.append_agent_memory(
                thread_id,
                owner,
                {"kind": "thread_summary_refresh", "message_count": message_count, "summary": summary},
            )
            report["summary_refresh"] = True

        if state_policy.snapshot_every > 0 and message_count and message_count % state_policy.snapshot_every == 0:
            await self.runtime.memory.append_agent_memory(
                thread_id,
                owner,
                {
                    "kind": "state_snapshot",
                    "message_count": message_count,
                    "task_packet": compact_task_packet(task_packet) if task_packet else None,
                    "output_preview": final_output[:400],
                },
            )
            report["snapshot"] = True

        if state_policy.rollup_every > 0 and message_count and message_count % state_policy.rollup_every == 0:
            await self.runtime.memory.add_shared_note(
                thread_id,
                SharedNote(
                    note_id=f"{thread_id}:{owner}:rollup:{message_count}",
                    task_id=(task_packet or {}).get("task_id", thread_id),
                    author_agent=agent_role,
                    content=final_output[:800],
                    metadata={"state_rollup": True, "message_count": message_count},
                ),
            )
            report["rollup"] = True
        return report

    async def after_supervisor_aggregation(
        self,
        *,
        thread_id: str,
        task: Any,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        memory_policy = self.resolve_memory_policy(metadata=metadata)
        for record_id in task.metadata.get("collective_memory_refs", []):
            await self.memory_evaluator.validate_memory(self.runtime.memory, policy=memory_policy, record_id=record_id)
        await self.promote_candidate_shared_memory(thread_id=thread_id, task_id=task.task_id)

    async def promote_candidate_shared_memory(self, *, thread_id: str, task_id: str) -> None:
        candidate_notes = await self.runtime.memory.collect_candidate_notes(thread_id, task_id=task_id)
        grouped: dict[tuple[str, str], list[SharedNote]] = {}
        for note in candidate_notes:
            candidate = dict(note.metadata.get("collective_memory") or {})
            if not candidate:
                candidate = {
                    "kind": note.metadata.get("memory_kind", "lesson_learned"),
                    "content": note.content,
                    "tags": note.metadata.get("tags", []),
                    "scope": note.metadata.get("scope"),
                }
            key = (candidate.get("kind", "lesson_learned"), candidate.get("content", "").strip().lower())
            if key[1]:
                grouped.setdefault(key, []).append(note)

        for (kind, normalized_content), notes in grouped.items():
            source_agents = sorted({note.author_agent for note in notes if note.author_agent})
            task_ids = {note.task_id for note in notes if note.task_id}
            if len(source_agents) < 2 and len(task_ids) < 2:
                continue
            representative = notes[0]
            candidate = dict(representative.metadata.get("collective_memory") or {})
            content = candidate.get("content") or representative.content
            tags = candidate.get("tags") or representative.metadata.get("tags", [])
            scope = candidate.get("scope") or representative.metadata.get("scope")
            confidence = min(0.95, 0.6 + 0.1 * len(source_agents) + 0.05 * max(len(task_ids) - 1, 0))
            existing = await self.runtime.memory.search_collective_memory(query=content, thread_id=thread_id, status=None, limit=20)
            if any(item["kind"] == kind and item["content"].strip().lower() == normalized_content for item in existing):
                continue
            await self.runtime.memory.promote_collective_memory(
                thread_id=thread_id,
                kind=kind,
                content=content,
                tags=tags,
                source_agents=source_agents,
                confidence=confidence,
                scope=scope,
            )
