from __future__ import annotations

from experiments.long_term_memory_graph.tools import cli


def test_cli_seed_demo_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(
        "experiments.long_term_memory_graph.tools.seed_demo.run_from_args",
        lambda args: {"command": "seed-demo", "prefix": args.prefix},
    )
    exit_code = cli.main(["seed-demo", "--password", "secret", "--prefix", "demo-"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"command": "seed-demo"' in captured.out
    assert '"prefix": "demo-"' in captured.out


def test_cli_benchmark_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(
        "experiments.long_term_memory_graph.tools.benchmark_latency.run_from_args",
        lambda args: {"command": "benchmark-latency", "repeats": args.repeats},
    )
    exit_code = cli.main(["benchmark-latency", "--password", "secret", "--repeats", "5"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"command": "benchmark-latency"' in captured.out
    assert '"repeats": 5' in captured.out


def test_cli_baseline_benchmark_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(
        "experiments.long_term_memory_graph.tools.benchmark_baselines.run_from_args",
        lambda args: {"command": "benchmark-baselines", "case_limit": args.case_limit},
    )
    exit_code = cli.main(["benchmark-baselines", "--case-limit", "3"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"command": "benchmark-baselines"' in captured.out
    assert '"case_limit": 3' in captured.out


def test_cli_baseline_stability_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(
        "experiments.long_term_memory_graph.tools.benchmark_baseline_stability.run_from_args",
        lambda args: {"command": "benchmark-baseline-stability", "seeds": args.seeds},
    )
    exit_code = cli.main(["benchmark-baseline-stability", "--seeds", "4"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"command": "benchmark-baseline-stability"' in captured.out
    assert '"seeds": 4' in captured.out


def test_cli_graph_scale_latency_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(
        "experiments.long_term_memory_graph.tools.benchmark_graph_scale_latency.run_from_args",
        lambda args: {"command": "benchmark-graph-scale-latency", "scale_factors": args.scale_factors},
    )
    exit_code = cli.main(["benchmark-graph-scale-latency", "--password", "secret", "--scale-factors", "1,2,4"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"command": "benchmark-graph-scale-latency"' in captured.out
    assert '"scale_factors": "1,2,4"' in captured.out


def test_cli_generate_paper_tables_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(
        "experiments.long_term_memory_graph.tools.generate_paper_tables.run_from_args",
        lambda args: {"command": "generate-paper-tables", "output_dir": args.output_dir},
    )
    exit_code = cli.main(["generate-paper-tables", "--output-dir", "artifacts/output_tables"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"command": "generate-paper-tables"' in captured.out
    assert '"output_dir": "artifacts/output_tables"' in captured.out


def test_cli_backfill_dispatch(monkeypatch, capsys, tmp_path):
    db_path = tmp_path / "records.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "experiments.long_term_memory_graph.tools.backfill_sqlite.run_from_args",
        lambda args: {"command": "backfill-sqlite", "records_db_path": args.records_db_path},
    )
    exit_code = cli.main(["backfill-sqlite", str(db_path), "--password", "secret"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"command": "backfill-sqlite"' in captured.out
    assert "records.db" in captured.out
