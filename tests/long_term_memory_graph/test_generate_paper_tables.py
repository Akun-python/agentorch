from __future__ import annotations

import json

from experiments.long_term_memory_graph.tools.generate_paper_tables import generate_paper_tables


def test_generate_paper_tables_emits_markdown_and_latex(tmp_path):
    baseline_report = tmp_path / "baseline.json"
    baseline_report.write_text(
        json.dumps(
            {
                "baseline_aggregates": [
                    {
                        "baseline": "clarks_nutcracker_graph",
                        "capsule_recall@k": 0.6458,
                        "subgraph_relevance": 0.4305,
                        "relation_hit_rate": 0.0324,
                        "returned_memory_usefulness": 0.4243,
                        "stale_node_injection_rate": 0.0,
                        "conflict_resolution_success": 1.0,
                        "latency_ms": 13.4797,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    stability_report = tmp_path / "stability.json"
    stability_report.write_text(
        json.dumps(
            {
                "baseline_stability": [
                    {
                        "baseline": "clarks_nutcracker_graph",
                        "capsule_recall@k_mean": 0.6945,
                        "capsule_recall@k_ci95_low": 0.6667,
                        "capsule_recall@k_ci95_high": 0.7222,
                        "subgraph_relevance_mean": 0.5,
                        "subgraph_relevance_ci95_low": 0.4444,
                        "subgraph_relevance_ci95_high": 0.5371,
                        "relation_hit_rate_mean": 0.0340,
                        "relation_hit_rate_ci95_low": 0.0278,
                        "relation_hit_rate_ci95_high": 0.0371,
                        "returned_memory_usefulness_mean": 0.4935,
                        "returned_memory_usefulness_ci95_low": 0.4389,
                        "returned_memory_usefulness_ci95_high": 0.55,
                        "stale_node_injection_rate_mean": 0.0,
                        "stale_node_injection_rate_ci95_low": 0.0,
                        "stale_node_injection_rate_ci95_high": 0.0,
                        "conflict_resolution_success_mean": 1.0,
                        "conflict_resolution_success_ci95_low": 1.0,
                        "conflict_resolution_success_ci95_high": 1.0,
                        "latency_ms_mean": 15.1317,
                        "latency_ms_ci95_low": 13.9936,
                        "latency_ms_ci95_high": 17.044,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    graph_scale_root = tmp_path / "graph_scale"
    scale_latency_dir = graph_scale_root / "scale_01" / "latency"
    scale_seed_dir = graph_scale_root / "scale_01" / "seed"
    scale_latency_dir.mkdir(parents=True)
    scale_seed_dir.mkdir(parents=True)
    (scale_seed_dir / "seed_report.json").write_text(
        json.dumps({"prefix": "scale-01-", "stored_capsule_count": 360}, ensure_ascii=False),
        encoding="utf-8",
    )
    (scale_latency_dir / "recall_latency_report.json").write_text(
        json.dumps(
            {
                "environment": {"node_count": 360, "edge_count": 720},
                "recall_summary": {"mean_ms": 24.0, "p95_ms": 30.0, "throughput_qps": 41.667},
                "detail_summary": {"mean_ms": 9.0, "p95_ms": 12.0, "throughput_qps": 111.111},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest = generate_paper_tables(
        baseline_report=baseline_report,
        stability_report=stability_report,
        graph_scale_root=graph_scale_root,
        output_dir=tmp_path / "tables",
    )

    assert manifest["graph_scale_rows"] == 1
    assert (tmp_path / "tables" / "paper_tables.md").exists()
    assert (tmp_path / "tables" / "paper_tables.tex").exists()
    assert (tmp_path / "tables" / "paper_tables_manifest.json").exists()
