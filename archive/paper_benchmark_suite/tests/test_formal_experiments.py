import json
from pathlib import Path

from experiments.common.tasks import load_formal_tasks
from experiments.run_formal import main as run_formal_main
from experiments.run_scaling import main as run_scaling_main


def test_load_formal_tasks_from_bundled_cache():
    tasks = load_formal_tasks(["gaia", "hotpotqa"], split="official_subset")
    assert tasks
    assert all(task.benchmark_split == "official_subset" for task in tasks)


def test_run_formal_writes_stable_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_formal.py",
            "--experiment",
            "rq1_long_horizon_tasks",
            "--models",
            "mock:strong",
            "--variants",
            "full_framework",
            "--seeds",
            "7",
            "--task-limit",
            "1",
            "--output-dir",
            str(tmp_path),
        ],
    )
    run_formal_main()

    result_dir = tmp_path / "rq1_long_horizon_tasks" / "formal_benchmark" / "full_framework" / "mock_strong" / "seed-7"
    assert (result_dir / "results.jsonl").exists()
    status = json.loads((result_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["counts"]["completed"] >= 1


def test_run_scaling_emits_agent_count_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_scaling.py",
            "--model",
            "mock:strong",
            "--agent-counts",
            "1,2",
            "--seeds",
            "7",
            "--task-limit",
            "1",
            "--output-dir",
            str(tmp_path),
        ],
    )
    run_scaling_main()
    one_dir = tmp_path / "rq1_long_horizon_tasks" / "scaling_agents_1" / "single_agent_basic" / "mock_strong" / "seed-7"
    two_dir = tmp_path / "rq1_long_horizon_tasks" / "scaling_agents_2" / "full_framework" / "mock_strong" / "seed-7"
    assert (one_dir / "results.jsonl").exists()
    assert (two_dir / "results.jsonl").exists()
