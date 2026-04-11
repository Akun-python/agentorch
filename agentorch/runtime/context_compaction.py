from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Awaitable, Callable

from agentorch.core import CompactionDecision, ContextSegment, Message, PromptContext, SalienceReport, SegmentScore
from agentorch.strategies import ContextStrategyConfig, LongHorizonStrategyConfig


def trim_message_content(content: str, *, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rstrip() + "...[truncated]"


def estimate_prompt_context_budget(prompt_context: PromptContext, *, truncated_sections: list[str] | None = None) -> dict[str, Any]:
    evidence_chars = len(json.dumps(prompt_context.retrieved_evidence, ensure_ascii=False)) if prompt_context.retrieved_evidence else 0
    citation_chars = len(json.dumps(prompt_context.citations, ensure_ascii=False)) if prompt_context.citations else 0
    retrieval_report_chars = len(json.dumps(prompt_context.retrieval_report, ensure_ascii=False)) if prompt_context.retrieval_report else 0
    retrieval_plan_chars = len(json.dumps(prompt_context.retrieval_plan, ensure_ascii=False)) if prompt_context.retrieval_plan else 0
    task_packet_chars = len(json.dumps(prompt_context.task_packet, ensure_ascii=False)) if prompt_context.task_packet else 0
    delegation_context_chars = len(json.dumps(prompt_context.delegation_context, ensure_ascii=False)) if prompt_context.delegation_context else 0
    collective_evidence_chars = len(json.dumps(prompt_context.collective_memory_evidence, ensure_ascii=False)) if prompt_context.collective_memory_evidence else 0
    skill_instruction_chars = sum(len(item) for item in prompt_context.skill_instructions)
    tool_description_chars = len(json.dumps(prompt_context.tool_descriptions, ensure_ascii=False)) if prompt_context.tool_descriptions else 0
    system_chars = len(prompt_context.system_prompt or "")
    conversation_chars = sum(len(message.content or "") for message in prompt_context.conversation)
    memory_summary_chars = len(prompt_context.memory_summary or "")
    retrieval_context_chars = len(prompt_context.retrieval_context or "")
    collective_memory_context_chars = len(prompt_context.collective_memory_context or "")
    estimated_total_chars = (
        system_chars
        + conversation_chars
        + memory_summary_chars
        + retrieval_context_chars
        + collective_memory_context_chars
        + evidence_chars
        + citation_chars
        + retrieval_report_chars
        + retrieval_plan_chars
        + task_packet_chars
        + delegation_context_chars
        + collective_evidence_chars
        + skill_instruction_chars
        + tool_description_chars
    )
    return {
        "conversation_messages": len(prompt_context.conversation),
        "conversation_chars": conversation_chars,
        "memory_summary_chars": memory_summary_chars,
        "retrieval_context_chars": retrieval_context_chars,
        "collective_memory_context_chars": collective_memory_context_chars,
        "retrieval_evidence_items": len(prompt_context.retrieved_evidence),
        "citation_items": len(prompt_context.citations),
        "tool_description_count": len(prompt_context.tool_descriptions),
        "tool_description_chars": tool_description_chars,
        "skill_instruction_count": len(prompt_context.skill_instructions),
        "skill_instruction_chars": skill_instruction_chars,
        "task_packet_chars": task_packet_chars,
        "delegation_context_chars": delegation_context_chars,
        "collective_memory_evidence_items": len(prompt_context.collective_memory_evidence),
        "collective_memory_evidence_chars": collective_evidence_chars,
        "evidence_chars": evidence_chars,
        "citation_chars": citation_chars,
        "retrieval_report_chars": retrieval_report_chars,
        "retrieval_plan_chars": retrieval_plan_chars,
        "estimated_total_chars": estimated_total_chars,
        "truncated_sections": list(truncated_sections or []),
    }


def apply_static_context_filters(
    prompt_context: PromptContext,
    *,
    context_strategy: ContextStrategyConfig,
    long_horizon_strategy: LongHorizonStrategyConfig,
) -> tuple[PromptContext, list[str]]:
    conversation = list(prompt_context.conversation)[-min(context_strategy.max_conversation_messages, long_horizon_strategy.max_prompt_messages) :]
    truncated_sections: list[str] = []
    if len(prompt_context.conversation) > len(conversation):
        truncated_sections.append("conversation")
    if context_strategy.tool_result_policy in {"summary", "truncate"}:
        compressed: list[Message] = []
        for message in conversation:
            if message.role == "tool" and message.content:
                compressed.append(message.model_copy(update={"content": trim_message_content(message.content, max_chars=context_strategy.tool_result_max_chars)}))
            else:
                compressed.append(message)
        conversation = compressed
    elif context_strategy.tool_result_policy == "off":
        filtered = [message for message in conversation if message.role != "tool"]
        if len(filtered) != len(conversation):
            truncated_sections.append("tool_results")
        conversation = filtered
    updated = prompt_context.model_copy(
        update={
            "conversation": conversation,
            "memory_summary": prompt_context.memory_summary if context_strategy.include_memory_summary else None,
            "retrieval_context": prompt_context.retrieval_context if context_strategy.include_retrieval_summary else None,
            "retrieved_evidence": (list(prompt_context.retrieved_evidence[: context_strategy.retrieval_evidence_max_items]) if context_strategy.include_retrieval_evidence else []),
            "citations": (list(prompt_context.citations[: context_strategy.citation_max_items]) if context_strategy.include_retrieval_citations else []),
            "retrieval_report": prompt_context.retrieval_report if context_strategy.include_retrieval_report else None,
            "retrieval_coverage": prompt_context.retrieval_coverage if context_strategy.include_retrieval_report else None,
            "retrieval_plan": prompt_context.retrieval_plan if context_strategy.include_retrieval_plan else None,
            "tool_descriptions": prompt_context.tool_descriptions if context_strategy.include_tool_descriptions else [],
            "skill_instructions": prompt_context.skill_instructions if context_strategy.include_skill_instructions else [],
            "task_packet": prompt_context.task_packet if context_strategy.include_task_packet else None,
            "delegation_context": prompt_context.delegation_context if context_strategy.include_delegation_context else {},
        }
    )
    if prompt_context.retrieved_evidence and not context_strategy.include_retrieval_evidence:
        truncated_sections.append("retrieval_evidence")
    if prompt_context.citations and len(updated.citations) < len(prompt_context.citations):
        truncated_sections.append("citations")
    if prompt_context.retrieval_report and not context_strategy.include_retrieval_report:
        truncated_sections.append("retrieval_report")
    if prompt_context.retrieval_plan and not context_strategy.include_retrieval_plan:
        truncated_sections.append("retrieval_plan")
    if prompt_context.tool_descriptions and not context_strategy.include_tool_descriptions:
        truncated_sections.append("tool_descriptions")
    if prompt_context.skill_instructions and not context_strategy.include_skill_instructions:
        truncated_sections.append("skill_instructions")
    if prompt_context.task_packet and not context_strategy.include_task_packet:
        truncated_sections.append("task_packet")
    if prompt_context.delegation_context and not context_strategy.include_delegation_context:
        truncated_sections.append("delegation_context")
    return updated, truncated_sections


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]+", (value or "").lower()) if len(token) > 2}


def _serialize(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, sort_keys=True)


def compact_task_packet(task_packet: dict[str, Any] | None) -> dict[str, Any] | None:
    if not task_packet:
        return None
    context = task_packet.get("context") or {}
    return {
        "task_id": task_packet.get("task_id"),
        "goal": task_packet.get("goal"),
        # Preserve task input so delegated workflow/agent-node paths can still
        # consume mounted retrieval payloads after context compaction.
        "input": task_packet.get("input"),
        "parent_task_id": task_packet.get("parent_task_id"),
        "origin_agent": task_packet.get("origin_agent"),
        "knowledge_scope": task_packet.get("knowledge_scope") or [],
        "metadata": {
            key: value
            for key, value in (task_packet.get("metadata") or {}).items()
            if key in {"thread_id", "delegation_depth"}
        },
        "context": {
            "collective_memory_context": context.get("collective_memory_context"),
            "collective_memory_evidence": list(context.get("collective_memory_evidence") or [])[:2],
            "cooperation_report": context.get("cooperation_report"),
        },
    }


def build_handoff_capsule(task_packet: dict[str, Any] | None, handoff: dict[str, Any] | None) -> dict[str, Any]:
    task_packet = task_packet or {}
    handoff = handoff or {}
    context = task_packet.get("context") or {}
    return {
        "goal": task_packet.get("goal"),
        "scope": task_packet.get("knowledge_scope") or [],
        "from_agent": handoff.get("from_agent"),
        "to_agent": handoff.get("to_agent"),
        "reason": handoff.get("reason"),
        "collective_memory": list(context.get("collective_memory_evidence") or [])[:2],
    }


def resolve_attention_profile(context_strategy: ContextStrategyConfig, *, stage: str, agent_role: str | None) -> dict[str, float]:
    defaults = {"retrieval_evidence": 1.15, "citation": 0.65, "retrieval_report": 0.7, "skill": 0.95, "collective_memory": 0.9, "delegation_context": 0.92, "conversation": 0.86, "tool_observation": 0.88, "task_packet": 1.0}
    if stage.startswith("execute"):
        stage_profile = {"tool_observation": 1.2, "retrieval_evidence": 1.1, "delegation_context": 1.0, "skill": 0.82}
    elif stage == "plan":
        stage_profile = {"task_packet": 1.18, "skill": 1.1, "retrieval_evidence": 1.08, "tool_observation": 0.72}
    else:
        stage_profile = {}
    role_profile: dict[str, float] = {}
    if agent_role == "evidence_scout":
        role_profile = {"retrieval_evidence": 1.18, "citation": 0.8}
    elif agent_role == "synthesis_analyst":
        role_profile = {"retrieval_report": 1.08, "conversation": 0.9}
    elif agent_role == "supervisor":
        role_profile = {"delegation_context": 1.18, "task_packet": 1.12}
    configured = dict(context_strategy.stage_attention_profiles.get("default", {}))
    configured.update(context_strategy.stage_attention_profiles.get(stage, {}))
    if agent_role:
        configured.update(context_strategy.stage_attention_profiles.get(f"agent:{agent_role}", {}))
    resolved = dict(defaults)
    for overlay in (stage_profile, role_profile, configured):
        resolved.update(overlay)
    return resolved


def _segment_type_priority(segment_type: str) -> int:
    order = {"citation": 0, "retrieval_report": 1, "skill": 2, "collective_memory": 3, "delegation_context": 4, "tool_observation": 5, "conversation": 6, "retrieval_evidence": 7, "task_packet": 8}
    return order.get(segment_type, 99)


def segment_prompt_context(prompt_context: PromptContext, *, user_input: str, thread_id: str, agent_role: str | None, stage: str, selected_skill_routes: list[dict[str, Any]]) -> list[ContextSegment]:
    query_tokens = _tokens(" ".join([user_input, " ".join(prompt_context.knowledge_scope), agent_role or "", stage]))
    segments: list[ContextSegment] = []

    def add_segment(segment_id: str, segment_type: str, source: str, content: Any, metadata: dict[str, Any], recency: float = 0.0, delegation_depth: int = 0) -> None:
        serialized = _serialize(content)
        relevance = (len(query_tokens.intersection(_tokens(serialized))) / max(1, len(query_tokens))) if query_tokens else 0.0
        reliability = 0.62
        if segment_type == "retrieval_evidence":
            reliability = 0.92 if source != "web" else 0.72
        elif segment_type == "collective_memory":
            reliability = 0.88 if metadata.get("memory_role") == "matriarch" else 0.74
        elif segment_type == "citation":
            reliability = 0.58
        elif segment_type == "retrieval_report":
            reliability = 0.54
        elif segment_type == "task_packet":
            reliability = 0.76
        segments.append(ContextSegment(segment_id=segment_id, segment_type=segment_type, source=source, content=content, display_content=serialized, char_count=len(serialized), agent_scope=agent_role, thread_scope=thread_id, recency=recency, reliability=reliability, task_relevance=relevance, delegation_depth=delegation_depth, novelty=1.0, redundancy_group=f"{segment_type}:{hashlib.sha1(serialized.encode('utf-8')).hexdigest()[:12]}", metadata=metadata))

    total_messages = max(1, len(prompt_context.conversation))
    for idx, message in enumerate(prompt_context.conversation):
        add_segment(f"conversation:{idx}", "tool_observation" if message.role == "tool" else "conversation", message.role, message.model_dump(), {"index": idx}, (idx + 1) / total_messages)
    for idx, item in enumerate(prompt_context.retrieved_evidence):
        add_segment(f"evidence:{idx}", "retrieval_evidence", str(item.get("source_type") or item.get("source") or "retrieval"), item, {"index": idx}, 0.8)
    for idx, item in enumerate(prompt_context.citations):
        add_segment(f"citation:{idx}", "citation", str(item.get("source_type") or "citation"), item, {"index": idx}, 0.7)
    if prompt_context.retrieval_report:
        for key, value in prompt_context.retrieval_report.items():
            add_segment(f"retrieval_report:{key}", "retrieval_report", "retrieval_report", {key: value}, {"key": key}, 0.65)
    for idx, item in enumerate(prompt_context.collective_memory_evidence):
        add_segment(f"collective:{idx}", "collective_memory", str(item.get("kind") or "collective_memory"), item, {"index": idx, "record_id": item.get("id"), "memory_role": item.get("memory_role")}, 0.75)
    for idx, route in enumerate(selected_skill_routes):
        descriptor = route.get("descriptor") or {}
        descriptor_text = f"Skill: {descriptor.get('name')}\nPurpose: {descriptor.get('description')}\nRecommended Tools: {', '.join(descriptor.get('allowed_tools', []))}".strip()
        add_segment(f"skill:{idx}", "skill", "skill", {"descriptor": descriptor_text, "summary": route.get("content") or descriptor_text, "full": route.get("content") or descriptor_text}, {"index": idx, "skill_name": route.get("skill_name")}, 0.82)
    if prompt_context.task_packet:
        add_segment("task_packet", "task_packet", "task_packet", {"full": prompt_context.task_packet, "capsule": compact_task_packet(prompt_context.task_packet)}, {"kind": "task_packet"}, 0.9, int((prompt_context.task_packet.get("metadata") or {}).get("delegation_depth", 0) or 0))
    if prompt_context.delegation_context:
        handoff = prompt_context.delegation_context.get("handoff") if isinstance(prompt_context.delegation_context, dict) else None
        if handoff:
            add_segment("delegation_context:handoff", "delegation_context", "handoff", {"full": handoff, "capsule": build_handoff_capsule(prompt_context.task_packet, handoff)}, {"key": "handoff"}, 0.92, int(((handoff.get("task") or {}).get("metadata") or {}).get("delegation_depth", 0) or 0))
    return segments


def select_segment_representation(segment: ContextSegment, *, compact: bool) -> tuple[Any, str]:
    if segment.segment_type == "skill" and isinstance(segment.content, dict):
        return (segment.content.get("descriptor"), "descriptor") if compact else (segment.content.get("summary") or segment.content.get("full"), "summary")
    if segment.segment_type in {"task_packet", "delegation_context"} and isinstance(segment.content, dict) and "capsule" in segment.content:
        return segment.content.get("capsule"), "capsule"
    return segment.content, "full"


async def apply_budget_aware_compaction(
    prompt_context: PromptContext,
    *,
    context_strategy: ContextStrategyConfig,
    stage: str,
    selected_skill_routes: list[dict[str, Any]],
    rerank_callback: Callable[[list[ContextSegment], int], Awaitable[dict[str, tuple[float, str]]]],
) -> tuple[PromptContext, dict[str, Any]]:
    before_budget = estimate_prompt_context_budget(prompt_context)
    char_budget = context_strategy.segment_char_budget or context_strategy.prompt_char_budget
    if before_budget["estimated_total_chars"] <= char_budget:
        before_budget.update({"estimated_total_chars_before": before_budget["estimated_total_chars"], "estimated_total_chars_after": before_budget["estimated_total_chars"], "selected_segment_count": 0, "dropped_segment_count": 0, "segment_scores": [], "inhibition_events": [], "compression_reason": "within_budget", "compaction_applied": False})
        return prompt_context, before_budget

    segments = segment_prompt_context(prompt_context, user_input=prompt_context.user_input, thread_id=prompt_context.prompt_variables.get("thread_id", ""), agent_role=prompt_context.agent_role, stage=stage, selected_skill_routes=selected_skill_routes)
    attention_profile = resolve_attention_profile(context_strategy, stage=stage, agent_role=prompt_context.agent_role)
    counts_by_group: dict[str, int] = {}
    for segment in segments:
        counts_by_group[segment.redundancy_group] = counts_by_group.get(segment.redundancy_group, 0) + 1
    scores: dict[str, SegmentScore] = {}
    for segment in segments:
        redundancy_penalty = max(0.0, (counts_by_group.get(segment.redundancy_group, 1) - 1) * 0.2)
        handoff_priority = 0.2 if segment.segment_type in {"delegation_context", "task_packet"} else 0.0
        rule_score = (segment.task_relevance * 4.0 + segment.reliability * 2.5 + segment.recency * 1.5 + segment.novelty + handoff_priority) * attention_profile.get(segment.segment_type, 1.0)
        scores[segment.segment_id] = SegmentScore(segment_id=segment.segment_id, rule_score=rule_score, redundancy_penalty=redundancy_penalty, salience_score=rule_score - redundancy_penalty, keep_reason="rule_score", score_breakdown={"relevance": segment.task_relevance, "reliability": segment.reliability, "recency": segment.recency, "attention_weight": attention_profile.get(segment.segment_type, 1.0), "handoff_priority": handoff_priority})
    if context_strategy.salience_mode == "hybrid":
        ranked_candidates = sorted(segments, key=lambda item: (-scores[item.segment_id].salience_score, _segment_type_priority(item.segment_type), item.segment_id))
        reranked = await rerank_callback(ranked_candidates[: context_strategy.salience_rerank_top_k], context_strategy.salience_rerank_top_k)
        for segment_id, (adjustment, reason) in reranked.items():
            score = scores.get(segment_id)
            if score is None:
                continue
            score.rerank_adjustment = adjustment
            score.keep_reason = reason
            score.salience_score = score.rule_score + score.rerank_adjustment - score.redundancy_penalty

    ranked_segments = sorted(segments, key=lambda item: (-scores[item.segment_id].salience_score, _segment_type_priority(item.segment_type), -item.recency, item.segment_id))
    selected_segments: list[ContextSegment] = []
    dropped_segments: list[ContextSegment] = []
    inhibition_events: list[dict[str, Any]] = []
    decisions: list[CompactionDecision] = []
    min_keep = min(max(1, context_strategy.segment_min_keep), len(ranked_segments))
    selected_group: dict[str, str] = {}
    selected_chars = before_budget["estimated_total_chars"] - (before_budget["conversation_chars"] + before_budget["evidence_chars"] + before_budget["citation_chars"] + before_budget["retrieval_report_chars"] + before_budget["task_packet_chars"] + before_budget["delegation_context_chars"] + before_budget["collective_memory_evidence_chars"] + before_budget["skill_instruction_chars"])
    for segment in ranked_segments:
        selected_content, representation = select_segment_representation(segment, compact=(selected_chars > (char_budget * 0.8)))
        segment_chars = len(_serialize(selected_content))
        if segment.redundancy_group in selected_group:
            dropped_segments.append(segment)
            inhibition_events.append({"segment_id": segment.segment_id, "inhibition_source": selected_group[segment.redundancy_group], "kind": "lateral_inhibition"})
            decisions.append(CompactionDecision(segment_id=segment.segment_id, selected=False, reason="lateral_inhibition", inhibition_source=selected_group[segment.redundancy_group]))
            continue
        if len(selected_segments) < min_keep or selected_chars + segment_chars <= char_budget:
            selected_segments.append(segment)
            selected_group[segment.redundancy_group] = segment.segment_id
            selected_chars += segment_chars
            decisions.append(CompactionDecision(segment_id=segment.segment_id, selected=True, selected_representation=representation, selected_char_count=segment_chars, reason="selected_by_salience"))
        else:
            dropped_segments.append(segment)
            decisions.append(CompactionDecision(segment_id=segment.segment_id, selected=False, reason="over_budget"))

    selected_messages: list[tuple[int, Message]] = []
    selected_evidence: list[tuple[int, dict[str, Any]]] = []
    selected_citations: list[tuple[int, dict[str, Any]]] = []
    selected_collective: list[tuple[int, dict[str, Any]]] = []
    selected_skill_texts: list[tuple[int, str]] = []
    selected_report: dict[str, Any] = {}
    selected_task_packet = None
    selected_delegation_context: dict[str, Any] = {}
    for segment in selected_segments:
        selected_content, _ = select_segment_representation(segment, compact=True)
        if segment.segment_type in {"conversation", "tool_observation"}:
            selected_messages.append((int(segment.metadata.get("index", 0)), Message.model_validate(segment.content)))
        elif segment.segment_type == "retrieval_evidence":
            selected_evidence.append((int(segment.metadata.get("index", 0)), segment.content))
        elif segment.segment_type == "citation":
            selected_citations.append((int(segment.metadata.get("index", 0)), segment.content))
        elif segment.segment_type == "retrieval_report" and isinstance(segment.content, dict):
            selected_report.update(segment.content)
        elif segment.segment_type == "collective_memory":
            selected_collective.append((int(segment.metadata.get("index", 0)), segment.content))
        elif segment.segment_type == "skill":
            selected_skill_texts.append((int(segment.metadata.get("index", 0)), _serialize(selected_content)))
        elif segment.segment_type == "task_packet":
            selected_task_packet = selected_content
        elif segment.segment_type == "delegation_context" and isinstance(selected_content, dict):
            selected_delegation_context.update(selected_content)
    truncated_sections = set(before_budget.get("truncated_sections", []))
    for segment in dropped_segments:
        if segment.segment_type == "citation":
            truncated_sections.add("citations")
        elif segment.segment_type == "retrieval_report":
            truncated_sections.add("retrieval_report")
        elif segment.segment_type == "skill":
            truncated_sections.add("skill_instructions")
        elif segment.segment_type == "collective_memory":
            truncated_sections.add("collective_memory")
        elif segment.segment_type == "delegation_context":
            truncated_sections.add("delegation_context")
        elif segment.segment_type in {"conversation", "tool_observation"}:
            truncated_sections.add("conversation")
    rebuilt = prompt_context.model_copy(
        update={
            "conversation": [item for _, item in sorted(selected_messages, key=lambda row: row[0])],
            "retrieved_evidence": [item for _, item in sorted(selected_evidence, key=lambda row: row[0])],
            "citations": [item for _, item in sorted(selected_citations, key=lambda row: row[0])],
            "retrieval_report": selected_report or None,
            "retrieval_coverage": prompt_context.retrieval_coverage if selected_report else None,
            "collective_memory_evidence": [item for _, item in sorted(selected_collective, key=lambda row: row[0])],
            "collective_memory_context": (
                "\n".join(
                    f"- [{item.get('kind', 'memory')}] {item.get('content', '')}"
                    for _, item in sorted(selected_collective, key=lambda row: row[0])
                )
                if selected_collective
                else ""
            ),
            "collective_memory_citations": [
                {"record_id": item.get("id"), "kind": item.get("kind")}
                for _, item in sorted(selected_collective, key=lambda row: row[0])
                if item.get("id") is not None
            ],
            "skill_instructions": [item for _, item in sorted(selected_skill_texts, key=lambda row: row[0])],
            "task_packet": selected_task_packet,
            "delegation_context": selected_delegation_context,
        }
    )
    after_budget = estimate_prompt_context_budget(rebuilt, truncated_sections=sorted(truncated_sections))
    report = SalienceReport(mode=context_strategy.salience_mode, attention_profile=attention_profile, selected_segments=selected_segments, dropped_segments=dropped_segments, segment_scores=list(scores.values()), decisions=decisions, inhibition_events=inhibition_events, compression_reason="over_budget", estimated_total_chars_before=before_budget["estimated_total_chars"], estimated_total_chars_after=after_budget["estimated_total_chars"])
    after_budget.update({"estimated_total_chars_before": before_budget["estimated_total_chars"], "estimated_total_chars_after": after_budget["estimated_total_chars"], "selected_segment_count": len(selected_segments), "dropped_segment_count": len(dropped_segments), "segment_scores": [item.model_dump() for item in scores.values()], "inhibition_events": inhibition_events, "compression_reason": "over_budget", "compaction_applied": True, "selected_context_segments": [{"segment_id": item.segment_id, "segment_type": item.segment_type, "char_count": item.char_count} for item in selected_segments], "dropped_context_segments": [{"segment_id": item.segment_id, "segment_type": item.segment_type, "char_count": item.char_count} for item in dropped_segments], "salience_report": report.model_dump(), "attention_profile": attention_profile, "compaction_trace": [item.model_dump() for item in decisions]})
    return rebuilt, after_budget
