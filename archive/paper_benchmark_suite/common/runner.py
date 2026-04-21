from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Callable

from agentorch.runtime import Agent

from .config import ExperimentConfig, RunRecord, TaskSpec
from .io import build_record_key, load_existing_records, prepare_output_dir, write_results
from .judge import score_output
from .runtime_variants import build_runtime_variant
from .tasks import load_tasks


async def run_experiment(
    *,
    config: ExperimentConfig,
    tasks_path: Path | None = None,
    tasks: list[TaskSpec] | None = None,
    annotate_record: Callable[[RunRecord, TaskSpec, Any], None] | None = None,
) -> tuple[Path, list[RunRecord]]:
    output_dir = prepare_output_dir(config)
    existing_records = load_existing_records(output_dir)
    existing_keys = {build_record_key(item) for item in existing_records if item.status in {"completed", "skipped"}}
    runtime, runtime_meta = build_runtime_variant(config, workspace_root=Path.cwd(), output_dir=output_dir)
    agent = Agent(runtime=runtime)
    records: list[RunRecord] = list(existing_records)
    loaded_tasks = tasks if tasks is not None else load_tasks(tasks_path) if tasks_path is not None else []
    if config.task_limit is not None:
        loaded_tasks = loaded_tasks[: config.task_limit]

    for task in loaded_tasks:
        for repeat_index in range(config.repeat_count):
            identity = (task.task_id, task.benchmark_sample_id, config.model_name, config.seed, repeat_index)
            if identity in existing_keys:
                continue
            attempt = 0
            while True:
                record = await _run_single_task(
                    agent=agent,
                    task=task,
                    config=config,
                    runtime_meta=runtime_meta,
                    repeat_index=repeat_index,
                    annotate_record=annotate_record,
                )
                records = [item for item in records if build_record_key(item) != build_record_key(record)]
                records.append(record)
                if record.status != "failed" or attempt >= config.retry_failed:
                    break
                attempt += 1
            existing_keys.add(identity)
    write_results(output_dir, records)
    return output_dir, records


async def _run_single_task(
    *,
    agent: Agent,
    task: TaskSpec,
    config: ExperimentConfig,
    runtime_meta: dict[str, Any],
    repeat_index: int,
    annotate_record: Callable[[RunRecord, TaskSpec, Any], None] | None,
) -> RunRecord:
    thread_id = f"{config.experiment_name}-{task.task_id}-rep-{repeat_index}"
    if task.live_web_required and not runtime_meta.get("live_web_available"):
        return RunRecord(
            experiment_name=config.experiment_name,
            variant_name=config.variant_name,
            model_name=config.model_name,
            seed=config.seed,
            repeat_index=repeat_index,
            results_schema_version=config.results_schema_version,
            task_id=task.task_id,
            benchmark_id=task.benchmark_id,
            benchmark_name=task.benchmark_name,
            benchmark_split=task.benchmark_split,
            benchmark_sample_id=task.benchmark_sample_id,
            run_id="",
            thread_id=thread_id,
            status="skipped",
            success=False,
            final_text="",
            quality_score=0.0,
            token_usage=0,
            latency_ms=0,
            tool_call_count=0,
            delegation_depth=0,
            memory_hit_count=0,
            budget_overflow=False,
            sqlite_path=runtime_meta.get("sqlite_path"),
            live_web_available=False,
            skip_reason="live_web_unavailable",
            metadata={
                "registered_tools": runtime_meta.get("registered_tools", []),
                "output_tag": config.output_tag,
                "execution_tier": config.execution_tier,
                "history_length": config.history_length,
            },
        )

    started = time.perf_counter()
    try:
        result = await agent.run(task.instruction, thread_id=thread_id, metadata={"experiment_task": task.model_dump()})
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return RunRecord(
            experiment_name=config.experiment_name,
            variant_name=config.variant_name,
            model_name=config.model_name,
            seed=config.seed,
            repeat_index=repeat_index,
            results_schema_version=config.results_schema_version,
            task_id=task.task_id,
            benchmark_id=task.benchmark_id,
            benchmark_name=task.benchmark_name,
            benchmark_split=task.benchmark_split,
            benchmark_sample_id=task.benchmark_sample_id,
            run_id="",
            thread_id=thread_id,
            status="failed",
            success=False,
            final_text="",
            quality_score=0.0,
            token_usage=0,
            latency_ms=latency_ms,
            tool_call_count=0,
            delegation_depth=0,
            memory_hit_count=0,
            budget_overflow=False,
            sqlite_path=runtime_meta.get("sqlite_path"),
            live_web_available=bool(runtime_meta.get("live_web_available")),
            skip_reason=str(exc),
            metadata={
                "error": str(exc),
                "method_flags": runtime_meta.get("method_flags", {}),
                "prompt_budget": config.prompt_budget,
                "output_tag": config.output_tag,
                "execution_tier": config.execution_tier,
                "history_length": config.history_length,
                "benchmark": {
                    "benchmark_id": task.benchmark_id,
                    "benchmark_name": task.benchmark_name,
                    "benchmark_split": task.benchmark_split,
                    "benchmark_sample_id": task.benchmark_sample_id,
                },
            },
        )
    latency_ms = int((time.perf_counter() - started) * 1000)
    quality_score, judge_reason = score_output(task=task, output_text=result.output_text)
    todo_summary = result.reasoning_metadata.get("todo_summary", {}) if isinstance(result.reasoning_metadata, dict) else {}
    budget_report = result.reasoning_metadata.get("context_budget_report", {}) if isinstance(result.reasoning_metadata, dict) else {}

    record = RunRecord(
        experiment_name=config.experiment_name,
        variant_name=config.variant_name,
        model_name=config.model_name,
        seed=config.seed,
        repeat_index=repeat_index,
        results_schema_version=config.results_schema_version,
        task_id=task.task_id,
        benchmark_id=task.benchmark_id,
        benchmark_name=task.benchmark_name,
        benchmark_split=task.benchmark_split,
        benchmark_sample_id=task.benchmark_sample_id,
        run_id=result.run_id,
        thread_id=result.thread_id,
        status=result.status,
        success=result.status == "completed" and bool(result.output_text.strip()),
        final_text=result.output_text,
        quality_score=quality_score,
        token_usage=result.usage.total_tokens,
        latency_ms=latency_ms,
        tool_call_count=len(result.tool_results),
        delegation_depth=int(result.reasoning_metadata.get("delegation_depth", 0) or 0),
        memory_hit_count=int(result.reasoning_metadata.get("memory_recall_report", {}).get("selected_count", 0) or 0),
        budget_overflow=bool(budget_report.get("compaction_applied")),
        todo_summary=todo_summary,
        sqlite_path=runtime_meta.get("sqlite_path"),
        live_web_available=bool(runtime_meta.get("live_web_available")),
        metadata={
            "judge_reason": judge_reason,
            "context_budget_report": budget_report,
            "selected_context_segments": budget_report.get("selected_context_segments", []),
            "dropped_context_segments": budget_report.get("dropped_context_segments", []),
            "segment_scores": budget_report.get("segment_scores", []),
            "method_flags": runtime_meta.get("method_flags", {}),
            "prompt_budget": config.prompt_budget,
            "output_tag": config.output_tag,
            "execution_tier": config.execution_tier,
            "history_length": config.history_length,
            "benchmark": {
                "benchmark_id": task.benchmark_id,
                "benchmark_name": task.benchmark_name,
                "benchmark_split": task.benchmark_split,
                "benchmark_sample_id": task.benchmark_sample_id,
            },
        },
    )
    if annotate_record is not None:
        annotate_record(record, task, result)
    return record


def run_experiment_sync(
    *,
    config: ExperimentConfig,
    tasks_path: Path | None = None,
    tasks: list[TaskSpec] | None = None,
    annotate_record: Callable[[RunRecord, TaskSpec, Any], None] | None = None,
) -> tuple[Path, list[RunRecord]]:
    return asyncio.run(run_experiment(config=config, tasks_path=tasks_path, tasks=tasks, annotate_record=annotate_record))
