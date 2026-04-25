import json
from pathlib import Path

from experiments.rq2_elephant_attention.run import run_cli as run_rq2
from experiments.run_all import main as run_all_main


def _latest_variant_dir(root: Path, experiment_name: str, variant_name: str) -> Path:
    experiment_root = root / experiment_name
    latest = sorted(experiment_root.iterdir())[-1]
    return latest / variant_name


def test_rq2_records_selected_context_segments(tmp_path):
    run_rq2(
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
    variant_dir = _latest_variant_dir(tmp_path, "rq2_elephant_attention", "full_framework")
    line = json.loads((variant_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert line["metadata"]["selected_context_segments"]
    assert "context_precision" in line["metadata"]


def test_run_all_batches_experiments(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_all.py",
            "--variant",
            "full_framework",
            "--model",
            "mock:tool",
            "--task-limit",
            "1",
            "--output-dir",
            str(tmp_path),
        ],
    )
    run_all_main()
    assert (tmp_path / "rq1_long_horizon_tasks").exists()
    assert (tmp_path / "rq5_observability").exists()
