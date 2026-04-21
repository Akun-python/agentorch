from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ExperimentConfig, RunRecord


def _safe_component(value: str) -> str:
    return value.replace(":", "_").replace("/", "_").replace("\\", "_")


def prepare_output_dir(config: ExperimentConfig) -> Path:
    if config.use_stable_output_dir:
        tag = config.output_tag or config.execution_tier
        output_dir = config.output_dir / config.experiment_name / _safe_component(tag) / _safe_component(config.variant_name) / _safe_component(config.model_name) / f"seed-{config.seed}"
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = config.output_dir / config.experiment_name / timestamp / config.variant_name
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "plots").mkdir(exist_ok=True)
    (output_dir / "config.json").write_text(
        json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_dir


def write_results(output_dir: Path, records: list[RunRecord]) -> None:
    results_path = output_dir / "results.jsonl"
    results_path.write_text(
        "\n".join(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) for item in records) + ("\n" if records else ""),
        encoding="utf-8",
    )

    summary_rows = summarize_records(records)
    with (output_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows.keys()))
        writer.writeheader()
        writer.writerow(summary_rows)

    with (output_dir / "trace_index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "benchmark_id",
                "benchmark_name",
                "model_name",
                "seed",
                "run_id",
                "thread_id",
                "sqlite_path",
                "status",
            ],
        )
        writer.writeheader()
        for item in records:
            writer.writerow(
                {
                    "task_id": item.task_id,
                    "benchmark_id": item.benchmark_id or "",
                    "benchmark_name": item.benchmark_name or "",
                    "model_name": item.model_name,
                    "seed": item.seed,
                    "run_id": item.run_id,
                    "thread_id": item.thread_id,
                    "sqlite_path": item.sqlite_path or "",
                    "status": item.status,
                }
            )

    write_run_status(output_dir, records)


def load_existing_records(output_dir: Path) -> list[RunRecord]:
    results_path = output_dir / "results.jsonl"
    if not results_path.exists():
        return []
    return [RunRecord.model_validate(json.loads(line)) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_record_key(record: RunRecord) -> tuple[str, str | None, str, int, int]:
    return (
        record.task_id,
        record.benchmark_sample_id,
        record.model_name,
        record.seed,
        record.repeat_index,
    )


def write_run_status(output_dir: Path, records: list[RunRecord]) -> None:
    counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "retry": 0, "skipped": 0}
    for item in records:
        counts[item.status] = counts.get(item.status, 0) + 1
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "counts": counts,
        "total_records": len(records),
    }
    (output_dir / "run_status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_records(records: list[RunRecord]) -> dict[str, Any]:
    if not records:
        return {
            "total_runs": 0,
            "success_rate": 0.0,
            "avg_quality_score": 0.0,
            "avg_token_usage": 0.0,
            "avg_latency_ms": 0.0,
        }
    total = len(records)
    return {
        "total_runs": total,
        "success_rate": round(sum(1 for item in records if item.success) / total, 4),
        "avg_quality_score": round(sum(item.quality_score for item in records) / total, 4),
        "avg_token_usage": round(sum(item.token_usage for item in records) / total, 4),
        "avg_latency_ms": round(sum(item.latency_ms for item in records) / total, 4),
    }
