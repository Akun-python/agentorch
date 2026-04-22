from __future__ import annotations

from pathlib import Path

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
        context_dir / "summary.md",
        lifecycle_dir / "manifest.json",
        lifecycle_dir / "runs.jsonl",
        lifecycle_dir / "baseline_summary.csv",
        lifecycle_dir / "ablation_summary.csv",
        lifecycle_dir / "scenario_breakdown.csv",
        lifecycle_dir / "paired_deltas.csv",
        lifecycle_dir / "summary.md",
    ):
        assert required.exists(), required
