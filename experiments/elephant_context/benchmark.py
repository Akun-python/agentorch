from __future__ import annotations

import asyncio
import csv
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from agentorch import Agent, AgentCapability, AgentRegistry, AgentSpec, InMemoryKnowledgeBase, MemoryManager, RagStrategyConfig, ReasoningStrategyConfig, Runtime, Supervisor
from agentorch.agents.types import Handoff, TaskPacket
from agentorch.config import MemoryConfig
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.observability import EventBus, Tracer

from .benchmark_cases import get_elephant_benchmark_case, list_elephant_benchmark_cases
from .models import BenchmarkCollectiveMemory, BenchmarkKnowledgeDocument, BenchmarkMessageSeed, ElephantBenchmarkCase
from .plugin import build_elephant_runtime_config
from .probe_model import ChapterProbeModel
from .variants import get_elephant_variant, list_elephant_variants


ARTIFACT_ROOT = Path("artifacts") / "elephant_context_benchmark"
DEFAULT_BUDGETS = (6000, 12000, 18000)
DEFAULT_VARIANTS = tuple(spec.name for spec in list_elephant_variants())
QUICK_VARIANTS = ("elephant_full", "multi_agent_default_context")
METRIC_FIELDS = (
    "task_success",
    "context_precision",
    "context_recall",
    "key_evidence_retention_rate",
    "stage_focus_hit_rate",
    "redundancy_ratio",
    "budget_utilization",
    "compaction_gain",
)
_CONTROL_TASK_CONTEXT_KEYS = {"handoff_anchor"}


class _UnusedSupervisorModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        content = "supervisor_placeholder"
        return ModelResponse(
            message=Message(role="assistant", content=content),
            content=content,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class BenchmarkRunRecord(BaseModel):
    status: str = "completed"
    error_message: str | None = None
    case_id: str
    family: str
    variant: str
    category: str
    multi_agent: bool
    budget: int
    task_success: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    key_evidence_retention_rate: float = 0.0
    stage_focus_hit_rate: float = 0.0
    redundancy_ratio: float = 0.0
    budget_utilization: float = 0.0
    compaction_gain: float = 0.0
    expected_answer_fields: dict[str, str] = Field(default_factory=dict)
    observed_answer_fields: dict[str, str] = Field(default_factory=dict)
    output_text: str = ""
    planned_agents: list[str] = Field(default_factory=list)
    plan_reason: str | None = None
    selected_context_segments: list[dict[str, Any]] = Field(default_factory=list)
    dropped_context_segments: list[dict[str, Any]] = Field(default_factory=list)
    context_budget_reports: list[dict[str, Any]] = Field(default_factory=list)
    attention_profiles: list[dict[str, float]] = Field(default_factory=list)

    def summary_row(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "category": self.category,
            "budget": self.budget,
            "case_id": self.case_id,
            "family": self.family,
            "multi_agent": self.multi_agent,
            **{metric: getattr(self, metric) for metric in METRIC_FIELDS},
            "status": self.status,
        }


@dataclass
class _ExecutionPayload:
    output_text: str
    reasoning_payloads: list[dict[str, Any]]
    planned_agents: list[str]
    plan_reason: str | None


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _record_prefix(case: ElephantBenchmarkCase, variant: str, budget: int) -> str:
    return f"{case.case_id}__{variant}__{budget}"


def _artifact_dir(output_dir: str | Path | None = None) -> Path:
    if output_dir is not None:
        return Path(output_dir)
    return ARTIFACT_ROOT / _timestamp()


def _quick_case_ids() -> list[str]:
    seen: set[str] = set()
    selected: list[str] = []
    for case in list_elephant_benchmark_cases():
        if case.family in seen:
            continue
        seen.add(case.family)
        selected.append(case.case_id)
    return selected


def _ordered_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 6)


def _build_reasoning_strategy() -> ReasoningStrategyConfig:
    return ReasoningStrategyConfig.plan_execute(config={"max_execution_steps": 1, "allow_replan": False})


def _build_rag_strategy(knowledge_scope: list[str]) -> RagStrategyConfig:
    return RagStrategyConfig.for_classic(
        knowledge_scope=list(knowledge_scope),
        mount="inline",
        injection_policy="full_report",
        top_k=4,
    )


def _build_memory_config(runtime_dir: Path, prefix: str) -> MemoryConfig:
    return MemoryConfig(
        checkpoint_path=runtime_dir / f"{prefix}_checkpoints.db",
        record_path=runtime_dir / f"{prefix}_records.db",
    )


async def _seed_messages(memory: MemoryManager, thread_id: str, messages: list[BenchmarkMessageSeed]) -> None:
    for item in messages:
        await memory.append_message(
            thread_id,
            Message(
                role=item.role,
                content=item.content,
                name=item.name,
                tool_call_id=item.tool_call_id,
                metadata=dict(item.metadata),
            ),
        )


async def _seed_collective_memory(memory: MemoryManager, thread_id: str, items: list[BenchmarkCollectiveMemory]) -> dict[str, int]:
    keyed_records: dict[str, int] = {}
    for item in items:
        record_id = await memory.promote_collective_memory(
            thread_id=thread_id,
            kind=item.kind,
            content=item.content,
            tags=list(item.tags),
            source_agents=list(item.source_agents),
            confidence=item.confidence,
            scope=item.scope,
            status=item.status,
        )
        if item.record_key:
            keyed_records[item.record_key] = record_id
        if item.reuse_count or item.last_validated_at or item.metadata or item.status != "validated":
            matches = await memory.record_store.search(metadata_filters={"memory_role": "matriarch"})
            target = next((row for row in matches if row["id"] == record_id), None)
            if target is not None:
                metadata = dict(target.get("metadata") or {})
                metadata.update(dict(item.metadata))
                metadata["status"] = item.status
                metadata["reuse_count"] = int(item.reuse_count)
                if item.last_validated_at:
                    metadata["last_validated_at"] = item.last_validated_at
                await memory.record_store.update_record_metadata(record_id, metadata)
    return keyed_records


async def _seed_knowledge_base(knowledge_base: InMemoryKnowledgeBase, documents: list[BenchmarkKnowledgeDocument]) -> None:
    from agentorch import Document

    if not documents:
        return
    await knowledge_base.ingest(
        [
            Document(
                id=item.document_id,
                text=item.text,
                metadata={
                    "source_type": item.source_type,
                    "locator": dict(item.locator),
                    "scopes": list(item.scopes),
                    **dict(item.metadata),
                },
            )
            for item in documents
        ]
    )


def _task_context_for_prompt(case: ElephantBenchmarkCase) -> dict[str, Any]:
    return {
        key: value
        for key, value in case.task_context.items()
        if key not in _CONTROL_TASK_CONTEXT_KEYS
    }


def _build_task_packet(case: ElephantBenchmarkCase, *, task_id: str, origin_agent: str) -> TaskPacket:
    return TaskPacket(
        task_id=task_id,
        goal=case.user_input,
        context=_task_context_for_prompt(case),
        origin_agent=origin_agent,
        knowledge_scope=list(case.knowledge_scope),
        metadata={"thread_id": task_id, "delegation_depth": 0},
    )


def _handoff_reason(case: ElephantBenchmarkCase, base_reason: str | None) -> str | None:
    anchor = case.task_context.get("handoff_anchor")
    if anchor is None:
        return base_reason
    if not base_reason:
        return str(anchor)
    return f"{base_reason}|{anchor}"


def _make_child_runtime_config(case: ElephantBenchmarkCase, variant: str, budget: int):
    return build_elephant_runtime_config(
        variant=variant,
        char_budget=budget,
        reasoning=_build_reasoning_strategy(),
        rag=_build_rag_strategy(case.knowledge_scope),
        default_knowledge_scope=list(case.knowledge_scope),
    )


def _build_registry(case: ElephantBenchmarkCase, variant: str, budget: int) -> AgentRegistry:
    registry = AgentRegistry()
    agent_specs = [
        (
            "planner",
            "Planning specialist for checkpoint synthesis",
            ["plan", "checkpoint"],
            [AgentCapability.PLAN],
        ),
        (
            "evidence_scout",
            "Evidence scout for retrieved context competition",
            ["retrieve", "evidence"],
            [AgentCapability.RETRIEVE],
        ),
        (
            "reviewer",
            "Reviewer for delegated outputs and consistency",
            ["review", "consistency"],
            [AgentCapability.REVIEW],
        ),
    ]
    for name, description, tags, capabilities in agent_specs:
        child_runtime = Runtime(
            model=ChapterProbeModel(case),
            tracer=Tracer(EventBus()),
            config=_make_child_runtime_config(case, variant, budget),
        )
        registry.register(
            AgentSpec(
                name=name,
                description=description,
                tags=tags,
                capabilities=capabilities,
                allowed_knowledge_scopes=list(case.knowledge_scope),
            ),
            Agent(runtime=child_runtime),
        )
    return registry


def _extract_observed_fields(output_text: str) -> dict[str, str]:
    observed: dict[str, str] = {}
    for raw_line in output_text.splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in observed:
            observed[key] = value
    return observed


def _extract_reasoning_payloads(payload: _ExecutionPayload) -> list[dict[str, Any]]:
    return payload.reasoning_payloads


def _evaluate_run(case: ElephantBenchmarkCase, spec_name: str, category: str, multi_agent: bool, budget: int, payload: _ExecutionPayload) -> BenchmarkRunRecord:
    reasoning_payloads = _extract_reasoning_payloads(payload)
    observed = _extract_observed_fields(payload.output_text)
    task_success = 1.0 if all(observed.get(key) == value for key, value in case.expected_answer_fields.items()) else 0.0

    selected_segments: list[dict[str, Any]] = []
    dropped_segments: list[dict[str, Any]] = []
    budget_reports: list[dict[str, Any]] = []
    attention_profiles: list[dict[str, float]] = []
    redundancy_groups: list[str] = []
    for reasoning in reasoning_payloads:
        budget_report = dict(reasoning.get("context_budget_report") or {})
        if budget_report:
            budget_reports.append(budget_report)
        selected_segments.extend(list(reasoning.get("selected_context_segments") or budget_report.get("selected_context_segments") or []))
        dropped_segments.extend(list(reasoning.get("dropped_context_segments") or budget_report.get("dropped_context_segments") or []))
        salience_report = dict(reasoning.get("salience_report") or {})
        attention_profile = dict(reasoning.get("attention_profile") or salience_report.get("attention_profile") or {})
        if attention_profile:
            attention_profiles.append(attention_profile)
        redundancy_groups.extend(
            segment.get("redundancy_group", "")
            for segment in salience_report.get("selected_segments", [])
            if segment.get("redundancy_group")
        )

    selected_ids = set(segment.get("segment_id") for segment in selected_segments if segment.get("segment_id"))
    relevant_ids = set(case.gold_key_segment_ids) | set(case.gold_support_segment_ids)
    relevant_hits = selected_ids & relevant_ids
    key_hits = selected_ids & set(case.gold_key_segment_ids)
    stage_hits = selected_ids & set(case.stage_focus_segment_ids)
    context_precision = len(relevant_hits) / max(1, len(selected_ids))
    context_recall = len(relevant_hits) / max(1, len(relevant_ids))
    key_retention = len(key_hits) / max(1, len(case.gold_key_segment_ids))
    stage_focus_hit_rate = len(stage_hits) / max(1, len(case.stage_focus_segment_ids))
    redundancy_ratio = max(0, len(redundancy_groups) - len(set(redundancy_groups))) / max(1, len(redundancy_groups))

    utilizations: list[float] = []
    gains: list[float] = []
    for report in budget_reports:
        after = float(report.get("estimated_total_chars_after") or 0.0)
        before = float(report.get("estimated_total_chars_before") or 0.0)
        utilizations.append(after / max(1.0, float(budget)))
        gains.append(max(0.0, before - after) / max(1.0, before))

    return BenchmarkRunRecord(
        case_id=case.case_id,
        family=case.family,
        variant=spec_name,
        category=category,
        multi_agent=multi_agent,
        budget=budget,
        task_success=round(task_success, 6),
        context_precision=round(context_precision, 6),
        context_recall=round(context_recall, 6),
        key_evidence_retention_rate=round(key_retention, 6),
        stage_focus_hit_rate=round(stage_focus_hit_rate, 6),
        redundancy_ratio=round(redundancy_ratio, 6),
        budget_utilization=round(_average(utilizations), 6),
        compaction_gain=round(_average(gains), 6),
        expected_answer_fields=dict(case.expected_answer_fields),
        observed_answer_fields=observed,
        output_text=payload.output_text,
        planned_agents=list(payload.planned_agents),
        plan_reason=payload.plan_reason,
        selected_context_segments=selected_segments,
        dropped_context_segments=dropped_segments,
        context_budget_reports=budget_reports,
        attention_profiles=attention_profiles,
    )


async def _run_single_agent_case(case: ElephantBenchmarkCase, variant: str, budget: int, runtime_dir: Path) -> _ExecutionPayload:
    prefix = _record_prefix(case, variant, budget)
    thread_id = f"{prefix}:thread"
    task_id = f"{prefix}:task"
    memory = MemoryManager(config=_build_memory_config(runtime_dir, prefix))
    knowledge_base = InMemoryKnowledgeBase()
    await _seed_knowledge_base(knowledge_base, case.knowledge_documents)
    await _seed_messages(memory, thread_id, case.thread_messages)
    await _seed_collective_memory(memory, thread_id, case.collective_memories)

    runtime = Runtime(
        model=ChapterProbeModel(case),
        memory=memory,
        knowledge_base=knowledge_base,
        tracer=Tracer(EventBus()),
        config=_make_child_runtime_config(case, variant, budget),
    )
    agent = Agent(runtime=runtime)
    task_packet = _build_task_packet(case, task_id=task_id, origin_agent="single_agent")
    handoff = Handoff(
        from_agent="benchmark_supervisor",
        to_agent="single_agent",
        task=task_packet,
        reason=_handoff_reason(case, "single_agent_entry"),
        metadata={"case_id": case.case_id},
    )
    result = await agent.run(
        case.user_input,
        thread_id=thread_id,
        metadata={
            "task_packet": task_packet.model_dump(),
            "handoff": handoff.model_dump(),
            "knowledge_scope": list(case.knowledge_scope),
            "agent_role": "single_agent",
        },
    )
    await runtime.aclose()
    return _ExecutionPayload(
        output_text=result.output_text,
        reasoning_payloads=[dict(result.reasoning_metadata)],
        planned_agents=["single_agent"],
        plan_reason=handoff.reason,
    )


async def _run_multi_agent_case(case: ElephantBenchmarkCase, variant: str, budget: int, runtime_dir: Path) -> _ExecutionPayload:
    prefix = _record_prefix(case, variant, budget)
    parent_thread_id = f"{prefix}:parent"
    memory = MemoryManager(config=_build_memory_config(runtime_dir, prefix))
    knowledge_base = InMemoryKnowledgeBase()
    await _seed_knowledge_base(knowledge_base, case.knowledge_documents)
    await _seed_collective_memory(memory, parent_thread_id, case.collective_memories)

    registry = _build_registry(case, variant, budget)
    supervisor = Supervisor(registry=registry)
    runtime = Runtime(
        model=_UnusedSupervisorModel(),
        memory=memory,
        knowledge_base=knowledge_base,
        agent_registry=registry,
        supervisor=supervisor,
        tracer=Tracer(EventBus()),
        config=_make_child_runtime_config(case, variant, budget),
    )
    runtime._facade_explicit_shared_memory = True
    runtime._facade_explicit_shared_knowledge = True

    envelope = runtime._create_context_envelope(thread_id=parent_thread_id, metadata={})
    coordination_policy = runtime._resolve_coordination_policy()
    memory_policy = runtime._resolve_memory_policy()
    collective_payload, collective_records = await runtime.context_kernel.prepare_supervisor_task_context(
        user_input=case.user_input,
        thread_id=parent_thread_id,
        coordination_policy=coordination_policy,
        memory_policy=memory_policy,
    )
    task_context = dict(collective_payload)
    task_context.update(case.task_context)
    task = TaskPacket(
        task_id=envelope.run_id,
        goal=case.user_input,
        context=task_context,
        origin_agent="supervisor",
        knowledge_scope=list(case.knowledge_scope),
        metadata={
            "thread_id": parent_thread_id,
            "delegation_depth": 0,
            "collective_memory_refs": [item["id"] for item in collective_records],
            "coordination_policy": coordination_policy.model_dump(),
        },
    )
    plan = await runtime.context_kernel.route_planner.plan(
        supervisor=runtime.supervisor,
        task=task,
        registry=runtime.agent_registry,
        coordination_policy=coordination_policy,
    )
    plan_reason = _handoff_reason(case, plan.reason)
    if plan_reason != plan.reason:
        plan = plan.model_copy(update={"reason": plan_reason})

    delegated_results = []
    for invocation in plan.invocations:
        await _seed_messages(memory, invocation.task.task_id, case.thread_messages)
        delegated_results.append(
            await runtime._run_supervisor_invocation(
                invocation=invocation,
                plan=plan,
                task=task,
                envelope=envelope,
                collective_payload=collective_payload,
                coordination_policy=coordination_policy,
                memory_policy=memory_policy,
            )
        )

    aggregated = runtime.coordinator.aggregate_results(delegated_results)
    aggregation_metadata = dict(aggregated.metadata)
    aggregation_metadata["plan"] = {
        "reason": plan.reason,
        "selected_agents": [invocation.agent_name for invocation in plan.invocations],
    }
    reasoning_payloads = [
        dict(result.metadata.get("reasoning_metadata") or {})
        for result in delegated_results
    ]
    await runtime.aclose()
    return _ExecutionPayload(
        output_text=aggregated.summary,
        reasoning_payloads=reasoning_payloads,
        planned_agents=[invocation.agent_name for invocation in plan.invocations],
        plan_reason=plan.reason,
    )


async def _run_case(case: ElephantBenchmarkCase, variant: str, budget: int, runtime_dir: Path) -> BenchmarkRunRecord:
    spec = get_elephant_variant(variant)
    try:
        if spec.multi_agent:
            payload = await _run_multi_agent_case(case, variant, budget, runtime_dir)
        else:
            payload = await _run_single_agent_case(case, variant, budget, runtime_dir)
        return _evaluate_run(case, spec.name, spec.category, spec.multi_agent, budget, payload)
    except Exception as exc:  # pragma: no cover - kept for artifact completeness
        return BenchmarkRunRecord(
            status="failed",
            error_message=str(exc),
            case_id=case.case_id,
            family=case.family,
            variant=spec.name,
            category=spec.category,
            multi_agent=spec.multi_agent,
            budget=budget,
            expected_answer_fields=dict(case.expected_answer_fields),
        )


def _group_rows(records: list[BenchmarkRunRecord], *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[BenchmarkRunRecord]] = defaultdict(list)
    for record in records:
        if record.status != "completed":
            continue
        grouped[tuple(getattr(record, key) for key in keys)].append(record)
    rows: list[dict[str, Any]] = []
    for group_key, items in sorted(grouped.items()):
        row = {key: value for key, value in zip(keys, group_key)}
        row["run_count"] = len(items)
        for metric in METRIC_FIELDS:
            row[metric] = round(sum(getattr(item, metric) for item in items) / len(items), 6)
        rows.append(row)
    return rows


def _paired_delta_rows(records: list[BenchmarkRunRecord]) -> list[dict[str, Any]]:
    baseline_index = {
        (record.case_id, record.budget): record
        for record in records
        if record.variant == "elephant_full" and record.status == "completed"
    }
    rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, int], list[BenchmarkRunRecord]] = defaultdict(list)
    for record in records:
        if record.variant == "elephant_full" or record.status != "completed":
            continue
        grouped[(record.variant, record.budget)].append(record)
    for (variant, budget), items in sorted(grouped.items()):
        deltas: dict[str, list[float]] = {metric: [] for metric in METRIC_FIELDS}
        for item in items:
            baseline = baseline_index.get((item.case_id, item.budget))
            if baseline is None:
                continue
            for metric in METRIC_FIELDS:
                deltas[metric].append(getattr(item, metric) - getattr(baseline, metric))
        for metric, values in deltas.items():
            if not values:
                continue
            rows.append(
                {
                    "variant": variant,
                    "budget": budget,
                    "metric": metric,
                    "pair_count": len(values),
                    "mean_delta_vs_elephant_full": round(sum(values) / len(values), 6),
                }
            )
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, records: list[BenchmarkRunRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(rows: list[dict[str, Any]], headers: list[str]) -> str:
    if not rows:
        return "_No rows generated._"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def _build_summary_markdown(
    *,
    run_id: str,
    records: list[BenchmarkRunRecord],
    baseline_rows: list[dict[str, Any]],
    ablation_rows: list[dict[str, Any]],
    delta_rows: list[dict[str, Any]],
) -> str:
    failure_records = [
        record
        for record in records
        if record.status == "completed" and record.task_success < 1.0
    ][:8]
    lines = [
        "# Elephant Context Benchmark Summary",
        "",
        f"- Run ID: `{run_id}`",
        f"- Completed runs: `{sum(1 for record in records if record.status == 'completed')}`",
        f"- Failed runs: `{sum(1 for record in records if record.status != 'completed')}`",
        "",
        "## Baseline Comparison",
        "",
        _markdown_table(
            baseline_rows,
            ["variant", "budget", "run_count", "task_success", "context_recall", "key_evidence_retention_rate", "stage_focus_hit_rate", "budget_utilization"],
        ),
        "",
        "## Ablation Comparison",
        "",
        _markdown_table(
            ablation_rows,
            ["variant", "budget", "run_count", "task_success", "context_recall", "key_evidence_retention_rate", "stage_focus_hit_rate", "budget_utilization"],
        ),
        "",
        "## Paired Deltas Versus Elephant Full",
        "",
        _markdown_table(
            delta_rows,
            ["variant", "budget", "metric", "pair_count", "mean_delta_vs_elephant_full"],
        ),
        "",
        "## Failure Modes",
        "",
    ]
    if not failure_records:
        lines.append("- No failure records in this run.")
    else:
        for record in failure_records:
            first_answer = next(iter(record.observed_answer_fields.items()), ("none", "none"))
            lines.append(
                f"- `{record.variant}` / `{record.case_id}` / budget `{record.budget}`: "
                f"first observed field `{first_answer[0]}={first_answer[1]}`, planned agents `{','.join(record.planned_agents) or 'single_agent'}`."
            )
    lines.append("")
    return "\n".join(lines)


async def run_elephant_benchmark(
    *,
    quick: bool = False,
    output_dir: str | Path | None = None,
    variants: list[str] | None = None,
    budgets: list[int] | None = None,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    run_dir = _artifact_dir(output_dir)
    runtime_dir = run_dir / "runtime_state"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    selected_variants = list(variants or (QUICK_VARIANTS if quick else DEFAULT_VARIANTS))
    selected_budgets = list(budgets or ([12000] if quick else list(DEFAULT_BUDGETS)))
    selected_case_ids = list(case_ids or (_quick_case_ids() if quick else [case.case_id for case in list_elephant_benchmark_cases()]))
    cases = [get_elephant_benchmark_case(case_id) for case_id in selected_case_ids]

    records: list[BenchmarkRunRecord] = []
    for case in cases:
        for variant in selected_variants:
            for budget in selected_budgets:
                records.append(await _run_case(case, variant, budget, runtime_dir))

    baseline_rows = _group_rows([record for record in records if record.category == "baseline"], keys=("variant", "budget"))
    ablation_rows = _group_rows([record for record in records if record.category == "ablation"], keys=("variant", "budget"))
    scenario_rows = _group_rows(records, keys=("family", "variant", "budget"))
    delta_rows = _paired_delta_rows(records)

    manifest = {
        "run_id": run_dir.name,
        "quick": quick,
        "variants": selected_variants,
        "budgets": selected_budgets,
        "case_ids": selected_case_ids,
        "record_count": len(records),
        "generated_at": datetime.now().isoformat(),
        "output_dir": str(run_dir.resolve()),
    }
    _write_json(run_dir / "manifest.json", manifest)
    _write_jsonl(run_dir / "runs.jsonl", records)
    _write_csv(run_dir / "baseline_summary.csv", baseline_rows)
    _write_csv(run_dir / "ablation_summary.csv", ablation_rows)
    _write_csv(run_dir / "scenario_breakdown.csv", scenario_rows)
    _write_csv(run_dir / "paired_deltas.csv", delta_rows)
    summary_md = _build_summary_markdown(
        run_id=run_dir.name,
        records=records,
        baseline_rows=baseline_rows,
        ablation_rows=ablation_rows,
        delta_rows=delta_rows,
    )
    (run_dir / "summary.md").write_text(summary_md, encoding="utf-8")
    return manifest


def run_elephant_benchmark_sync(
    *,
    quick: bool = False,
    output_dir: str | Path | None = None,
    variants: list[str] | None = None,
    budgets: list[int] | None = None,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        run_elephant_benchmark(
            quick=quick,
            output_dir=output_dir,
            variants=variants,
            budgets=budgets,
            case_ids=case_ids,
        )
    )


async def inspect_elephant_case(
    *,
    case_id: str,
    variant: str = "elephant_full",
    budget: int = 12000,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    run_dir = _artifact_dir(output_dir)
    runtime_dir = run_dir / "runtime_state"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    case = get_elephant_benchmark_case(case_id)
    record = await _run_case(case, variant, budget, runtime_dir)
    payload = {
        "run_id": run_dir.name,
        "output_dir": str(run_dir.resolve()),
        "record": record.model_dump(),
    }
    _write_json(run_dir / "inspection.json", payload)
    return payload


def inspect_elephant_case_sync(
    *,
    case_id: str,
    variant: str = "elephant_full",
    budget: int = 12000,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        inspect_elephant_case(
            case_id=case_id,
            variant=variant,
            budget=budget,
            output_dir=output_dir,
        )
    )


__all__ = [
    "BenchmarkRunRecord",
    "inspect_elephant_case",
    "inspect_elephant_context_case",
    "inspect_elephant_case_sync",
    "inspect_elephant_context_case_sync",
    "run_elephant_benchmark",
    "run_elephant_context_benchmark",
    "run_elephant_benchmark_sync",
    "run_elephant_context_benchmark_sync",
]

run_elephant_context_benchmark = run_elephant_benchmark
run_elephant_context_benchmark_sync = run_elephant_benchmark_sync
inspect_elephant_context_case = inspect_elephant_case
inspect_elephant_context_case_sync = inspect_elephant_case_sync
