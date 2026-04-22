from __future__ import annotations

import asyncio
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentorch import AgentRegistry, MemoryManager, Supervisor
from agentorch.agents.types import SharedNote, TaskPacket
from agentorch.config import MemoryConfig
from agentorch.strategies import DefaultMemoryEvaluator, MemoryPolicy

from .benchmark import _artifact_dir, _markdown_table
from .lifecycle_cases import (
    LifecycleBenchmarkCase,
    LifecycleVariantSpec,
    get_lifecycle_case,
    get_lifecycle_variant,
    list_lifecycle_cases,
    list_lifecycle_variants,
    quick_lifecycle_case_ids,
)
from .models import BenchmarkCollectiveMemory

LIFECYCLE_METRIC_FIELDS = (
    "task_success",
    "mechanism_success",
    "retrieval_success",
    "state_integrity",
    "ordering_success",
)


class LifecycleRunRecord(BaseModel):
    suite: str = "lifecycle"
    status: str = "completed"
    error_message: str | None = None
    case_id: str
    family: str
    variant: str
    category: str
    task_success: float = 0.0
    mechanism_success: float = 0.0
    retrieval_success: float = 0.0
    state_integrity: float = 0.0
    ordering_success: float = 0.0
    output_text: str = ""
    observed_markers: list[str] = Field(default_factory=list)
    observed_rank_markers: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)

    def summary_row(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "category": self.category,
            "case_id": self.case_id,
            "family": self.family,
            **{metric: getattr(self, metric) for metric in LIFECYCLE_METRIC_FIELDS},
            "status": self.status,
        }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, records: list[LifecycleRunRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _memory_config(runtime_dir: Path, prefix: str) -> MemoryConfig:
    return MemoryConfig(
        checkpoint_path=runtime_dir / f"{prefix}_checkpoints.db",
        record_path=runtime_dir / f"{prefix}_records.db",
    )


def _record_prefix(case: LifecycleBenchmarkCase, variant: LifecycleVariantSpec) -> str:
    return f"{case.case_id}__{variant.name}"


def _policy_for_long_memory(variant: LifecycleVariantSpec) -> MemoryPolicy:
    base_thresholds = MemoryPolicy.long_horizon().thresholds_and_weights
    return MemoryPolicy.long_horizon(
        thresholds_and_weights={
            **base_thresholds,
            "allow_cross_thread_recall": variant.allow_cross_thread_recall,
            "recency_weight": variant.recency_weight,
        }
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


async def _collective_rows(memory: MemoryManager, *, thread_id: str | None = None) -> list[dict[str, Any]]:
    return await memory.search_collective_memory(query=None, thread_id=thread_id, status=None, limit=200)


def _markers_in_texts(markers: list[str], texts: list[str]) -> list[str]:
    hits: list[str] = []
    for marker in markers:
        if any(marker in text for text in texts):
            hits.append(marker)
    return hits


def _safe_avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 6)


def _build_observed_output(*, markers: list[str], rows: list[dict[str, Any]], ordered_markers: list[str]) -> str:
    lines = [
        f"markers: {','.join(markers) if markers else 'none'}",
        f"ordered_markers: {','.join(ordered_markers) if ordered_markers else 'none'}",
        f"records: {len(rows)}",
    ]
    return "\n".join(lines)


def _finalize_record(
    case: LifecycleBenchmarkCase,
    variant: LifecycleVariantSpec,
    *,
    retrieved_texts: list[str],
    rows: list[dict[str, Any]],
    state_integrity: float,
    ordering_success: float,
    ordered_markers: list[str],
    detail: dict[str, Any],
) -> LifecycleRunRecord:
    expected_markers = case.expected_present_markers + case.expected_absent_markers
    observed_markers = _markers_in_texts(expected_markers, retrieved_texts + [row.get("content", "") for row in rows])
    present_hits = sum(1 for marker in case.expected_present_markers if marker in observed_markers)
    absent_hits = sum(1 for marker in case.expected_absent_markers if marker not in observed_markers)
    total_expectations = len(case.expected_present_markers) + len(case.expected_absent_markers)
    retrieval_success = (present_hits + absent_hits) / max(1, total_expectations)
    mechanism_success = 1.0 if retrieval_success >= 1.0 and state_integrity >= 1.0 and ordering_success >= 1.0 else 0.0
    return LifecycleRunRecord(
        case_id=case.case_id,
        family=case.family,
        variant=variant.name,
        category=variant.category,
        task_success=round(mechanism_success, 6),
        mechanism_success=round(mechanism_success, 6),
        retrieval_success=round(retrieval_success, 6),
        state_integrity=round(state_integrity, 6),
        ordering_success=round(ordering_success, 6),
        output_text=_build_observed_output(markers=observed_markers, rows=rows, ordered_markers=ordered_markers),
        observed_markers=observed_markers,
        observed_rank_markers=ordered_markers,
        detail=detail,
    )


async def _run_succession_case(case: LifecycleBenchmarkCase, variant: LifecycleVariantSpec, runtime_dir: Path) -> LifecycleRunRecord:
    prefix = _record_prefix(case, variant)
    primary_memory = MemoryManager(config=_memory_config(runtime_dir, prefix))
    keyed_records = await _seed_collective_memory(primary_memory, case.source_thread_id, case.collective_memories)
    successor_memory = primary_memory
    if not variant.persistent_inheritance_enabled:
        successor_memory = MemoryManager(config=_memory_config(runtime_dir, prefix + "_fresh"))
    supervisor = Supervisor(registry=AgentRegistry())
    task = TaskPacket(
        task_id=f"{prefix}:successor",
        goal=case.query,
        knowledge_scope=list(case.knowledge_scope),
        metadata={"thread_id": case.source_thread_id},
    )
    retrieved = await supervisor.retrieve_collective_knowledge(task, successor_memory, limit=20)
    texts = [item.get("content", "") for item in retrieved]
    all_rows = await _collective_rows(primary_memory, thread_id=case.source_thread_id)
    state_integrity = 1.0
    if "deprecated" in keyed_records:
        deprecated_row = next((row for row in all_rows if row["id"] == keyed_records["deprecated"]), None)
        state_integrity = 1.0 if deprecated_row and deprecated_row.get("metadata", {}).get("status") == "deprecated" else 0.0
    detail = {
        "retrieved_record_ids": [item.get("id") for item in retrieved],
        "persistent_inheritance_enabled": variant.persistent_inheritance_enabled,
    }
    return _finalize_record(
        case,
        variant,
        retrieved_texts=texts,
        rows=all_rows,
        state_integrity=state_integrity,
        ordering_success=1.0,
        ordered_markers=[],
        detail=detail,
    )


async def _run_cross_thread_case(case: LifecycleBenchmarkCase, variant: LifecycleVariantSpec, runtime_dir: Path) -> LifecycleRunRecord:
    prefix = _record_prefix(case, variant)
    memory = MemoryManager(config=_memory_config(runtime_dir, prefix))
    evaluator = DefaultMemoryEvaluator()
    policy = _policy_for_long_memory(variant)
    await evaluator.promote_episode(
        memory,
        policy=policy,
        thread_id=case.source_thread_id,
        user_input=case.source_goal or case.query,
        final_output=case.source_output or case.query,
        retrieval_payload={
            "evidence": [
                {"citation": {"document_id": f"{case.case_id}:doc-a"}, "source_type": "benchmark"},
                {"citation": {"document_id": f"{case.case_id}:doc-b"}, "source_type": "benchmark"},
            ]
        },
        task_packet={
            "task_id": f"{prefix}:source",
            "goal": case.source_goal or case.query,
            "knowledge_scope": list(case.knowledge_scope),
        },
        agent_role=case.agent_role,
        knowledge_scope=list(case.knowledge_scope),
    )
    retrieved = await evaluator.search_long_term_memory(
        memory,
        policy=policy,
        thread_id=case.target_thread_id,
        query=case.query,
        knowledge_scope=list(case.knowledge_scope),
        task_packet={
            "task_id": f"{prefix}:target",
            "goal": case.query,
            "knowledge_scope": list(case.knowledge_scope),
        },
        agent_role=case.agent_role,
    )
    texts = [dict(item.get("record") or {}).get("content", "") for item in retrieved]
    detail = {
        "retrieved_record_ids": [dict(item.get("record") or {}).get("id") for item in retrieved],
        "allow_cross_thread_recall": variant.allow_cross_thread_recall,
    }
    return _finalize_record(
        case,
        variant,
        retrieved_texts=texts,
        rows=[],
        state_integrity=1.0,
        ordering_success=1.0,
        ordered_markers=[],
        detail=detail,
    )


async def _run_promotion_validation_case(case: LifecycleBenchmarkCase, variant: LifecycleVariantSpec, runtime_dir: Path) -> LifecycleRunRecord:
    prefix = _record_prefix(case, variant)
    memory = MemoryManager(config=_memory_config(runtime_dir, prefix))
    supervisor = Supervisor(registry=AgentRegistry())
    keyed_records = await _seed_collective_memory(memory, case.source_thread_id, case.collective_memories)
    if case.candidate_notes and variant.collective_governance_enabled:
        notes = [
            SharedNote(
                note_id=f"{prefix}:{index}",
                task_id=item.task_id,
                author_agent=item.author_agent,
                content=item.content,
                metadata=dict(item.metadata),
            )
            for index, item in enumerate(case.candidate_notes, start=1)
        ]
        promoted_ids = await supervisor.govern_collective_memory(
            thread_id=case.source_thread_id,
            candidates=notes,
            memory=memory,
            promotion_threshold=0.7,
        )
        if promoted_ids:
            keyed_records["promoted"] = promoted_ids[0]
    if case.validate_record_key and variant.collective_governance_enabled:
        record_id = keyed_records.get(case.validate_record_key)
        for _ in range(case.validate_rounds):
            if record_id is not None:
                await memory.validate_collective_memory(record_id)
    if case.deprecate_record_key and variant.collective_governance_enabled:
        record_id = keyed_records.get(case.deprecate_record_key)
        if record_id is not None:
            await memory.deprecate_collective_memory(record_id)
    task = TaskPacket(
        task_id=f"{prefix}:promotion",
        goal=case.query,
        knowledge_scope=list(case.knowledge_scope),
        metadata={"thread_id": case.source_thread_id},
    )
    retrieved = await supervisor.retrieve_collective_knowledge(task, memory, limit=20)
    texts = [item.get("content", "") for item in retrieved]
    rows = await _collective_rows(memory, thread_id=case.source_thread_id)
    state_checks: list[bool] = []
    if case.validate_record_key:
        row = next((item for item in rows if item["id"] == keyed_records.get(case.validate_record_key)), None)
        state_checks.append(bool(row and row.get("metadata", {}).get("reuse_count") == case.validate_rounds))
    if case.deprecate_record_key:
        row = next((item for item in rows if item["id"] == keyed_records.get(case.deprecate_record_key)), None)
        state_checks.append(bool(row and row.get("metadata", {}).get("status") == "deprecated"))
    if case.candidate_notes:
        state_checks.append("promoted" in keyed_records if variant.collective_governance_enabled else "promoted" not in keyed_records)
    state_integrity = 1.0 if all(state_checks) else 0.0
    detail = {
        "collective_governance_enabled": variant.collective_governance_enabled,
        "keyed_records": keyed_records,
    }
    return _finalize_record(
        case,
        variant,
        retrieved_texts=texts,
        rows=rows,
        state_integrity=state_integrity,
        ordering_success=1.0,
        ordered_markers=[],
        detail=detail,
    )


async def _run_conflict_case(case: LifecycleBenchmarkCase, variant: LifecycleVariantSpec, runtime_dir: Path) -> LifecycleRunRecord:
    prefix = _record_prefix(case, variant)
    memory = MemoryManager(config=_memory_config(runtime_dir, prefix))
    keyed_records = await _seed_collective_memory(memory, case.source_thread_id, case.collective_memories)
    resolution_result: dict[str, Any] | None = None
    if variant.conflict_resolution_enabled and case.conflict_resolution:
        resolution_result = await memory.resolve_conflict(
            keyed_records[case.conflict_record_keys[0]],
            keyed_records[case.conflict_record_keys[1]],
            case.conflict_resolution,
            reason="lifecycle_benchmark",
        )
    rows = await _collective_rows(memory, thread_id=case.source_thread_id)
    row_by_id = {row["id"]: row for row in rows}
    left = row_by_id.get(keyed_records["left"])
    right = row_by_id.get(keyed_records["right"])
    state_checks: list[bool] = []
    if case.conflict_resolution == "supersede":
        state_checks.append(bool(left and left.get("metadata", {}).get("status") == "deprecated"))
        state_checks.append(bool(left and left.get("metadata", {}).get("superseded_by") == keyed_records["right"]))
        supersedes = list((right or {}).get("metadata", {}).get("supersedes") or [])
        state_checks.append(keyed_records["left"] in supersedes)
    elif case.conflict_resolution == "merge":
        merged_id = int((resolution_result or {}).get("merged_id", 0) or 0)
        merged = row_by_id.get(merged_id)
        state_checks.append(bool(left and left.get("metadata", {}).get("merged_into") == merged_id))
        state_checks.append(bool(right and right.get("metadata", {}).get("merged_into") == merged_id))
        state_checks.append(bool(merged and "CONFLICT_LEFT" in merged.get("content", "") and "CONFLICT_RIGHT" in merged.get("content", "")))
    elif case.conflict_resolution == "keep_both":
        state_checks.append(bool(left and left.get("metadata", {}).get("conflict_reviewed") is True))
        state_checks.append(bool(right and right.get("metadata", {}).get("conflict_reviewed") is True))
        state_checks.append(bool(left and left.get("metadata", {}).get("conflict_with") == keyed_records["right"]))
    state_integrity = 1.0 if all(state_checks) else 0.0
    texts = [row.get("content", "") for row in rows]
    detail = {
        "conflict_resolution_enabled": variant.conflict_resolution_enabled,
        "resolution_result": resolution_result or {},
        "keyed_records": keyed_records,
    }
    return _finalize_record(
        case,
        variant,
        retrieved_texts=texts,
        rows=rows,
        state_integrity=state_integrity,
        ordering_success=1.0,
        ordered_markers=[],
        detail=detail,
    )


async def _run_temporal_decay_case(case: LifecycleBenchmarkCase, variant: LifecycleVariantSpec, runtime_dir: Path) -> LifecycleRunRecord:
    prefix = _record_prefix(case, variant)
    memory = MemoryManager(config=_memory_config(runtime_dir, prefix))
    await _seed_collective_memory(memory, case.source_thread_id, case.collective_memories)
    evaluator = DefaultMemoryEvaluator()
    policy = _policy_for_long_memory(variant)
    retrieved = await evaluator.search_long_term_memory(
        memory,
        policy=policy,
        thread_id=case.source_thread_id,
        query=case.query,
        knowledge_scope=list(case.knowledge_scope),
        task_packet={
            "task_id": f"{prefix}:temporal",
            "goal": case.query,
            "knowledge_scope": list(case.knowledge_scope),
        },
        agent_role=case.agent_role,
    )
    texts = [dict(item.get("record") or {}).get("content", "") for item in retrieved]
    ordered_markers = [
        marker
        for marker in case.temporal_rank_markers
        if any(marker in text for text in texts)
    ]
    expected_rank = list(case.temporal_rank_markers)
    ordering_success = 1.0 if ordered_markers[: len(expected_rank)] == expected_rank else 0.0
    detail = {
        "recency_weight": variant.recency_weight,
        "retrieved_record_ids": [dict(item.get("record") or {}).get("id") for item in retrieved],
    }
    return _finalize_record(
        case,
        variant,
        retrieved_texts=texts,
        rows=[],
        state_integrity=1.0,
        ordering_success=ordering_success,
        ordered_markers=ordered_markers,
        detail=detail,
    )


async def _run_case(case: LifecycleBenchmarkCase, variant_name: str, runtime_dir: Path) -> LifecycleRunRecord:
    variant = get_lifecycle_variant(variant_name)
    try:
        if case.family == "succession":
            return await _run_succession_case(case, variant, runtime_dir)
        if case.family == "cross_thread":
            return await _run_cross_thread_case(case, variant, runtime_dir)
        if case.family == "promotion_validation":
            return await _run_promotion_validation_case(case, variant, runtime_dir)
        if case.family == "conflict":
            return await _run_conflict_case(case, variant, runtime_dir)
        if case.family == "temporal_decay":
            return await _run_temporal_decay_case(case, variant, runtime_dir)
        raise ValueError(f"Unsupported lifecycle family: {case.family}")
    except Exception as exc:  # pragma: no cover - preserve artifact completeness
        return LifecycleRunRecord(
            status="failed",
            error_message=str(exc),
            case_id=case.case_id,
            family=case.family,
            variant=variant.name,
            category=variant.category,
        )


def _group_rows(records: list[LifecycleRunRecord], *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[LifecycleRunRecord]] = defaultdict(list)
    for record in records:
        if record.status != "completed":
            continue
        grouped[tuple(getattr(record, key) for key in keys)].append(record)
    rows: list[dict[str, Any]] = []
    for group_key, items in sorted(grouped.items()):
        row = {key: value for key, value in zip(keys, group_key)}
        row["run_count"] = len(items)
        for metric in LIFECYCLE_METRIC_FIELDS:
            row[metric] = round(sum(getattr(item, metric) for item in items) / len(items), 6)
        rows.append(row)
    return rows


def _paired_delta_rows(records: list[LifecycleRunRecord]) -> list[dict[str, Any]]:
    baseline_index = {
        record.case_id: record
        for record in records
        if record.variant == "mgcm_full" and record.status == "completed"
    }
    rows: list[dict[str, Any]] = []
    grouped: dict[str, list[LifecycleRunRecord]] = defaultdict(list)
    for record in records:
        if record.variant == "mgcm_full" or record.status != "completed":
            continue
        grouped[record.variant].append(record)
    for variant, items in sorted(grouped.items()):
        for metric in LIFECYCLE_METRIC_FIELDS:
            deltas = [
                getattr(item, metric) - getattr(baseline_index[item.case_id], metric)
                for item in items
                if item.case_id in baseline_index
            ]
            if not deltas:
                continue
            rows.append(
                {
                    "variant": variant,
                    "metric": metric,
                    "pair_count": len(deltas),
                    "mean_delta_vs_mgcm_full": round(sum(deltas) / len(deltas), 6),
                }
            )
    return rows


def _build_summary_markdown(
    *,
    run_id: str,
    records: list[LifecycleRunRecord],
    baseline_rows: list[dict[str, Any]],
    ablation_rows: list[dict[str, Any]],
    delta_rows: list[dict[str, Any]],
) -> str:
    failures = [record for record in records if record.status != "completed" or record.task_success < 1.0][:8]
    lines = [
        "# MGCM Lifecycle Benchmark Summary",
        "",
        f"- Run ID: `{run_id}`",
        f"- Completed runs: `{sum(1 for record in records if record.status == 'completed')}`",
        f"- Failed runs: `{sum(1 for record in records if record.status != 'completed')}`",
        "",
        "## Baseline Comparison",
        "",
        _markdown_table(
            baseline_rows,
            ["variant", "run_count", "task_success", "mechanism_success", "retrieval_success", "state_integrity", "ordering_success"],
        ),
        "",
        "## Ablation Comparison",
        "",
        _markdown_table(
            ablation_rows,
            ["variant", "run_count", "task_success", "mechanism_success", "retrieval_success", "state_integrity", "ordering_success"],
        ),
        "",
        "## Paired Deltas Versus MGCM Full",
        "",
        _markdown_table(
            delta_rows,
            ["variant", "metric", "pair_count", "mean_delta_vs_mgcm_full"],
        ),
        "",
        "## Failure Modes",
        "",
    ]
    if not failures:
        lines.append("- No failure records in this run.")
    else:
        for record in failures:
            lines.append(
                f"- `{record.variant}` / `{record.case_id}`: "
                f"markers `{','.join(record.observed_markers) or 'none'}`, "
                f"state_integrity `{record.state_integrity}`."
            )
    lines.append("")
    return "\n".join(lines)


async def run_lifecycle_benchmark(
    *,
    quick: bool = False,
    output_dir: str | Path | None = None,
    variants: list[str] | None = None,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    run_dir = _artifact_dir(output_dir)
    runtime_dir = run_dir / "runtime_state"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    selected_variants = list(variants or (["mgcm_full", "mgcm_thread_local_memory"] if quick else [item.name for item in list_lifecycle_variants()]))
    selected_case_ids = list(case_ids or (quick_lifecycle_case_ids() if quick else [case.case_id for case in list_lifecycle_cases()]))
    cases = [get_lifecycle_case(case_id) for case_id in selected_case_ids]
    records: list[LifecycleRunRecord] = []
    for case in cases:
        for variant in selected_variants:
            records.append(await _run_case(case, variant, runtime_dir))

    baseline_rows = _group_rows([record for record in records if record.category == "baseline"], keys=("variant",))
    ablation_rows = _group_rows([record for record in records if record.category == "ablation"], keys=("variant",))
    scenario_rows = _group_rows(records, keys=("family", "variant"))
    delta_rows = _paired_delta_rows(records)
    manifest = {
        "run_id": run_dir.name,
        "quick": quick,
        "variants": selected_variants,
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


def run_lifecycle_benchmark_sync(
    *,
    quick: bool = False,
    output_dir: str | Path | None = None,
    variants: list[str] | None = None,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        run_lifecycle_benchmark(
            quick=quick,
            output_dir=output_dir,
            variants=variants,
            case_ids=case_ids,
        )
    )


async def inspect_lifecycle_case(
    *,
    case_id: str,
    variant: str = "mgcm_full",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    run_dir = _artifact_dir(output_dir)
    runtime_dir = run_dir / "runtime_state"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    case = get_lifecycle_case(case_id)
    record = await _run_case(case, variant, runtime_dir)
    payload = {
        "run_id": run_dir.name,
        "output_dir": str(run_dir.resolve()),
        "record": record.model_dump(),
    }
    _write_json(run_dir / "inspection.json", payload)
    return payload


def inspect_lifecycle_case_sync(
    *,
    case_id: str,
    variant: str = "mgcm_full",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        inspect_lifecycle_case(
            case_id=case_id,
            variant=variant,
            output_dir=output_dir,
        )
    )


__all__ = [
    "LifecycleRunRecord",
    "inspect_lifecycle_case",
    "inspect_lifecycle_case_sync",
    "run_lifecycle_benchmark",
    "run_lifecycle_benchmark_sync",
]
