from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from experiments.elephant_context.chapter_benchmark import inspect_elephant_case_sync, run_elephant_benchmark_sync


def test_context_inspect_case_emits_real_runtime_metadata(tmp_path: Path):
    payload = inspect_elephant_case_sync(
        suite="context",
        case_id="rule_preservation_01",
        variant="elephant_full",
        budget=12000,
        output_dir=tmp_path / "context_inspect",
    )

    record = payload["record"]
    assert record["status"] == "completed"
    assert record["selected_context_segments"]
    assert record["context_budget_reports"]
    assert record["attention_profiles"]


def test_lifecycle_inspect_case_emits_mechanism_result(tmp_path: Path):
    payload = inspect_elephant_case_sync(
        suite="lifecycle",
        case_id="succession_01",
        variant="mgcm_full",
        output_dir=tmp_path / "lifecycle_inspect",
    )

    record = payload["record"]
    assert record["status"] == "completed"
    assert record["mechanism_success"] == 1.0
    assert "SUCCESSION_ALPHA_01" in record["observed_markers"]


def test_lifecycle_thread_local_succession_does_not_count_hidden_primary_rows(tmp_path: Path):
    payload = inspect_elephant_case_sync(
        suite="lifecycle",
        case_id="succession_01",
        variant="mgcm_thread_local_memory",
        output_dir=tmp_path / "lifecycle_thread_local",
    )
    record = payload["record"]
    assert record["status"] == "completed"
    assert record["retrieval_success"] == 0.0
    assert "SUCCESSION_ALPHA_01" not in record["observed_markers"]


def test_full_quick_benchmark_writes_context_and_lifecycle_artifacts(tmp_path: Path):
    output_dir = tmp_path / "chapter_benchmark"
    manifest = run_elephant_benchmark_sync(
        suite="full",
        quick=True,
        output_dir=output_dir,
    )

    assert manifest["suite"] == "full"
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "summary.md").exists()
    assert (output_dir / "runs.jsonl").exists()

    context_dir = output_dir / "context"
    lifecycle_dir = output_dir / "lifecycle"
    for required in (
        context_dir / "manifest.json",
        context_dir / "runs.jsonl",
        context_dir / "baseline_summary.csv",
        context_dir / "ablation_summary.csv",
        context_dir / "scenario_breakdown.csv",
        context_dir / "paired_deltas.csv",
        context_dir / "paired_significance.csv",
        context_dir / "summary.md",
        lifecycle_dir / "manifest.json",
        lifecycle_dir / "runs.jsonl",
        lifecycle_dir / "baseline_summary.csv",
        lifecycle_dir / "ablation_summary.csv",
        lifecycle_dir / "scenario_breakdown.csv",
        lifecycle_dir / "paired_deltas.csv",
        lifecycle_dir / "paired_significance.csv",
        lifecycle_dir / "summary.md",
    ):
        assert required.exists(), required
    assert (context_dir / "metric_stats.csv").exists()
    assert (lifecycle_dir / "metric_stats.csv").exists()


def test_context_real_task_dataset_and_seeded_run(tmp_path: Path):
    output_dir = tmp_path / "context_real_task"
    manifest = run_elephant_benchmark_sync(
        suite="context",
        quick=True,
        output_dir=output_dir,
        dataset="real_task_x",
        model_backend="probe",
        seeds=[0, 1],
        report_level="brief",
    )
    assert manifest["suite"] == "context"
    assert manifest["context"]["dataset"] == "real_task_x"
    assert manifest["context"]["seeds"] == [0, 1]
    runs_path = output_dir / "context" / "runs.jsonl"
    first = json.loads(runs_path.read_text(encoding="utf-8").splitlines()[0])
    assert "cost_metrics" in first
    assert "latency_ms" in first["cost_metrics"]
    assert "total_tokens" in first["cost_metrics"]
    assert "retrieval_trace" in first
    assert "rejection_trace" in first


def test_full_real_task_dataset_runs_context_and_lifecycle(tmp_path: Path):
    output_dir = tmp_path / "full_real_task"
    manifest = run_elephant_benchmark_sync(
        suite="full",
        quick=True,
        output_dir=output_dir,
        dataset="real_task_x",
        model_backend="probe",
        seeds=[0],
    )
    assert "context" in manifest
    assert "lifecycle" in manifest
    assert manifest["context"]["dataset"] == "real_task_x"
    assert manifest["lifecycle"]["dataset"] == "real_task_x"
    assert "cross_thread_real_01" in manifest["lifecycle"]["case_ids"]


def test_lifecycle_cross_thread_regains_signal_when_cross_thread_enabled(tmp_path: Path):
    output_dir = tmp_path / "lifecycle_cross_thread_signal"
    manifest = run_elephant_benchmark_sync(
        suite="lifecycle",
        quick=False,
        output_dir=output_dir,
        variants=["mgcm_full", "mgcm_no_cross_thread"],
        case_ids=["cross_thread_01"],
        seeds=[0],
    )
    assert manifest["suite"] == "lifecycle"
    with (output_dir / "lifecycle" / "scenario_breakdown.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_variant = {
        row["variant"]: row
        for row in rows
        if row["family"] == "cross_thread"
    }
    assert float(by_variant["mgcm_full"]["task_success"]) == 1.0
    assert float(by_variant["mgcm_no_cross_thread"]["task_success"]) == 0.0
    inspection = inspect_elephant_case_sync(
        suite="lifecycle",
        case_id="cross_thread_01",
        variant="mgcm_full",
        output_dir=tmp_path / "cross_thread_diag",
    )
    diagnostics = inspection["record"]["detail"]["diagnostics"]
    assert "candidate_count_collective_memory" in diagnostics
    assert "candidate_count_record_store" in diagnostics


def test_lifecycle_temporal_decay_differs_by_recency_weight(tmp_path: Path):
    output_dir = tmp_path / "lifecycle_temporal_signal"
    run_elephant_benchmark_sync(
        suite="lifecycle",
        quick=False,
        output_dir=output_dir,
        variants=["mgcm_full", "mgcm_no_temporal_decay"],
        case_ids=["temporal_decay_01"],
        seeds=[0],
    )
    with (output_dir / "lifecycle" / "scenario_breakdown.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_variant = {
        row["variant"]: row
        for row in rows
        if row["family"] == "temporal_decay"
    }
    assert float(by_variant["mgcm_full"]["ordering_success"]) == 1.0
    assert float(by_variant["mgcm_no_temporal_decay"]["ordering_success"]) == 0.0


def test_full_suite_variant_filter_does_not_fall_back_to_other_suite_defaults(tmp_path: Path):
    output_dir = tmp_path / "context_only_benchmark"
    manifest = run_elephant_benchmark_sync(
        suite="full",
        quick=True,
        output_dir=output_dir,
        variants=["elephant_full"],
    )

    assert "context" in manifest
    assert "lifecycle" not in manifest
    assert (output_dir / "context" / "summary.md").exists()
    assert not (output_dir / "lifecycle").exists()


def test_full_suite_case_filter_can_run_lifecycle_only(tmp_path: Path):
    output_dir = tmp_path / "lifecycle_only_benchmark"
    manifest = run_elephant_benchmark_sync(
        suite="full",
        quick=True,
        output_dir=output_dir,
        case_ids=["succession_01"],
    )

    assert "context" not in manifest
    assert "lifecycle" in manifest
    assert (output_dir / "lifecycle" / "summary.md").exists()
    assert not (output_dir / "context").exists()


def test_full_suite_raises_when_filters_match_no_subsuite(tmp_path: Path):
    with pytest.raises(ValueError, match="No benchmark suites matched"):
        run_elephant_benchmark_sync(
            suite="full",
            quick=True,
            output_dir=tmp_path / "invalid_filters",
            variants=["unknown_variant"],
        )


def test_significance_rows_include_tie_aware_columns(tmp_path: Path):
    output_dir = tmp_path / "significance_columns"
    run_elephant_benchmark_sync(
        suite="full",
        quick=True,
        output_dir=output_dir,
        seeds=[0, 1],
    )
    for path in (
        output_dir / "context" / "paired_significance.csv",
        output_dir / "lifecycle" / "paired_significance.csv",
    ):
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows
        sample = rows[0]
        assert "effective_pair_count" in sample
        assert "positive_count" in sample
        assert "negative_count" in sample
        assert "tie_count" in sample
