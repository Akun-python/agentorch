from __future__ import annotations

from experiments.long_term_memory_graph.tools.benchmark_baselines import BASELINE_ORDER, run_baseline_benchmark


def test_run_baseline_benchmark_emits_expected_reports(tmp_path):
    report = run_baseline_benchmark(output_dir=tmp_path, case_limit=3, prefix="test-benchmark-")

    assert report["case_count"] == 3
    assert [row["baseline"] for row in report["baseline_aggregates"]] == list(BASELINE_ORDER)
    assert report["evaluation_config"]["node_top_k"] > 0
    assert report["evaluation_config"]["edge_top_k"] > 0

    for filename in (
        "baseline_benchmark_report.json",
        "baseline_benchmark_report.md",
        "baseline_benchmark_aggregates.csv",
        "baseline_benchmark_case_rows.csv",
    ):
        assert (tmp_path / filename).exists()


def test_baseline_benchmark_preserves_expected_baseline_behavior(tmp_path):
    report = run_baseline_benchmark(output_dir=tmp_path, case_limit=4, prefix="test-baseline-")
    aggregates = {row["baseline"]: row for row in report["baseline_aggregates"]}

    assert aggregates["no_long_term_memory"]["capsule_recall@k"] == 0.0
    assert aggregates["no_long_term_memory"]["returned_memory_usefulness"] == 0.0
    assert aggregates["flat_summary_memory"]["relation_hit_rate"] == 0.0
    assert aggregates["clarks_nutcracker_graph"]["stale_node_injection_rate"] <= aggregates["naive_graph_memory"]["stale_node_injection_rate"]
    assert aggregates["clarks_nutcracker_graph"]["relation_hit_rate"] >= aggregates["flat_summary_memory"]["relation_hit_rate"]
