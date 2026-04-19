from __future__ import annotations

from experiments.long_term_memory_graph.tools.benchmark_graph_scale_latency import run_graph_scale_latency_benchmark


def test_run_graph_scale_latency_benchmark_aggregates_seed_and_latency_reports(tmp_path, monkeypatch):
    def fake_seed_demo_dataset(**kwargs):
        scale_multiplier = kwargs["scale_multiplier"]
        return {
            "stored_capsule_count": 360 * scale_multiplier,
            "node_count": 360 * scale_multiplier,
            "edge_count": 720 * scale_multiplier,
        }

    def fake_run_latency_benchmark(**kwargs):
        scale_multiplier = kwargs["scale_multiplier"]
        return {
            "environment": {
                "node_count": 360 * scale_multiplier,
                "edge_count": 720 * scale_multiplier,
            },
            "recall_summary": {
                "mean_ms": round(12.0 * scale_multiplier, 3),
                "p95_ms": round(18.0 * scale_multiplier, 3),
                "throughput_qps": round(1000.0 / (12.0 * scale_multiplier), 3),
            },
            "detail_summary": {
                "mean_ms": round(4.0 * scale_multiplier, 3),
                "p95_ms": round(6.0 * scale_multiplier, 3),
                "throughput_qps": round(1000.0 / (4.0 * scale_multiplier), 3),
            },
        }

    monkeypatch.setattr(
        "experiments.long_term_memory_graph.tools.benchmark_graph_scale_latency.seed_demo_dataset",
        fake_seed_demo_dataset,
    )
    monkeypatch.setattr(
        "experiments.long_term_memory_graph.tools.benchmark_graph_scale_latency.run_latency_benchmark",
        fake_run_latency_benchmark,
    )

    report = run_graph_scale_latency_benchmark(
        uri="bolt://127.0.0.1:7787",
        username="neo4j",
        password="secret",
        prefix="scale-bench-",
        scale_factors=[1, 2, 4],
        repeats=3,
        warmup_rounds=1,
        detail_limit=2,
        output_dir=tmp_path,
        clear_prefix=True,
        http_url="http://127.0.0.1:7574/browser/",
    )

    assert report["scale_factors"] == [1, 2, 4]
    assert len(report["rows"]) == 3
    assert report["rows"][0]["node_count"] == 360
    assert report["rows"][2]["node_count"] == 1440

    for filename in (
        "graph_scale_latency_report.json",
        "graph_scale_latency_report.md",
        "graph_scale_latency_rows.csv",
    ):
        assert (tmp_path / filename).exists()
