import json
from pathlib import Path

from experiments.rq1_long_horizon_tasks.run import run_cli as run_rq1
from experiments.rq3_seagull_memory.run import run_cli as run_rq3
from experiments.rq4_budget_robustness.run import run_cli as run_rq4
from experiments.rq5_observability.run import run_cli as run_rq5


def _latest_variant_dir(root: Path, experiment_name: str, variant_name: str) -> Path:
    experiment_root = root / experiment_name
    latest = sorted(experiment_root.iterdir())[-1]
    return latest / variant_name


def test_rq1_smoke_creates_results(tmp_path):
    run_rq1(
        variant="full_framework",
        model="mock:tool",
        judge_model=None,
        task_limit=1,
        repeat=1,
        budget=12000,
        output_dir=tmp_path,
        live_web=False,
        seed=7,
    )
    variant_dir = _latest_variant_dir(tmp_path, "rq1_long_horizon_tasks", "full_framework")
    assert (variant_dir / "results.jsonl").exists()
    assert (variant_dir / "summary.csv").exists()


def test_rq3_records_memory_lifecycle(tmp_path):
    run_rq3(
        variant="full_framework",
        model="mock:tool",
        judge_model=None,
        task_limit=1,
        repeat=1,
        budget=12000,
        output_dir=tmp_path,
        live_web=False,
        seed=7,
    )
    variant_dir = _latest_variant_dir(tmp_path, "rq3_seagull_memory", "full_framework")
    lines = [json.loads(line) for line in (variant_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    assert "memory_lifecycle" in lines[0]["metadata"]


def test_rq4_budget_dimension_present(tmp_path):
    run_rq4(
        variant="full_framework",
        model="mock:tool",
        judge_model=None,
        task_limit=1,
        repeat=1,
        budget=3000,
        output_dir=tmp_path,
        live_web=False,
        seed=7,
    )
    variant_dir = _latest_variant_dir(tmp_path, "rq4_budget_robustness", "full_framework")
    config = json.loads((variant_dir / "config.json").read_text(encoding="utf-8"))
    assert config["prompt_budget"] == 3000


def test_rq5_observability_metrics_present(tmp_path):
    run_rq5(
        variant="full_framework",
        model="mock:tool",
        judge_model=None,
        task_limit=1,
        repeat=1,
        budget=12000,
        output_dir=tmp_path,
        live_web=False,
        seed=7,
    )
    variant_dir = _latest_variant_dir(tmp_path, "rq5_observability", "full_framework")
    lines = [json.loads(line) for line in (variant_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    assert "trace_coverage" in lines[0]["metadata"]
