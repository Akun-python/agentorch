from __future__ import annotations

import experiments.generate_report as report


def test_extract_primary_metric_uses_experiment_specific_fields():
    rq2_name, rq2_value = report._extract_primary_metric(
        {
            "experiment_name": "rq2_elephant_attention",
            "quality_score": 0.12,
            "metadata": {"context_precision": 0.75},
        }
    )
    rq3_name, rq3_value = report._extract_primary_metric(
        {
            "experiment_name": "rq3_seagull_memory",
            "quality_score": 0.25,
            "metadata": {"memory_reuse_hit_rate": 0.81},
        }
    )
    rq5_name, rq5_value = report._extract_primary_metric(
        {
            "experiment_name": "rq5_observability",
            "quality_score": 0.5,
            "metadata": {"diagnostic_accuracy": 1.0},
        }
    )

    assert (rq2_name, rq2_value) == ("context_precision", 0.75)
    assert (rq3_name, rq3_value) == ("memory_reuse_hit_rate", 0.81)
    assert (rq5_name, rq5_value) == ("diagnostic_accuracy", 1.0)


def test_elephant_rows_and_tables_cover_both_required_baselines(tmp_path, monkeypatch):
    records = [
        {
            "experiment_name": "rq2_elephant_attention",
            "variant_name": "full_framework",
            "model_name": "gpt-4o",
            "seed": 7,
            "sample_id": "hotpot-001",
            "benchmark_id": "hotpotqa",
            "budget": 12000,
            "primary_metric": 1.0,
            "metadata": {
                "context_precision": 1.0,
                "context_recall": 1.0,
                "key_evidence_retention_rate": 1.0,
                "prompt_redundancy_ratio": 0.50,
            },
        },
        {
            "experiment_name": "rq2_elephant_attention",
            "variant_name": "full_framework",
            "model_name": "gpt-4o",
            "seed": 7,
            "sample_id": "musique-001",
            "benchmark_id": "musique",
            "budget": 12000,
            "primary_metric": 1.0,
            "metadata": {
                "context_precision": 1.0,
                "context_recall": 1.0,
                "key_evidence_retention_rate": 1.0,
                "prompt_redundancy_ratio": 0.50,
            },
        },
        {
            "experiment_name": "rq2_elephant_attention",
            "variant_name": "multi_agent_no_elephant",
            "model_name": "gpt-4o",
            "seed": 7,
            "sample_id": "hotpot-001",
            "benchmark_id": "hotpotqa",
            "budget": 12000,
            "primary_metric": 0.6667,
            "metadata": {
                "context_precision": 0.6667,
                "context_recall": 1.0,
                "key_evidence_retention_rate": 1.0,
                "prompt_redundancy_ratio": 0.12,
            },
        },
        {
            "experiment_name": "rq2_elephant_attention",
            "variant_name": "multi_agent_no_elephant",
            "model_name": "gpt-4o",
            "seed": 7,
            "sample_id": "musique-001",
            "benchmark_id": "musique",
            "budget": 12000,
            "primary_metric": 0.6667,
            "metadata": {
                "context_precision": 0.6667,
                "context_recall": 1.0,
                "key_evidence_retention_rate": 1.0,
                "prompt_redundancy_ratio": 0.12,
            },
        },
        {
            "experiment_name": "rq2_elephant_attention",
            "variant_name": "single_agent_long_context",
            "model_name": "gpt-4o",
            "seed": 7,
            "sample_id": "hotpot-001",
            "benchmark_id": "hotpotqa",
            "budget": 12000,
            "primary_metric": 0.50,
            "metadata": {
                "context_precision": 0.50,
                "context_recall": 0.50,
                "key_evidence_retention_rate": 0.50,
                "prompt_redundancy_ratio": 0.42,
            },
        },
        {
            "experiment_name": "rq2_elephant_attention",
            "variant_name": "single_agent_long_context",
            "model_name": "gpt-4o",
            "seed": 7,
            "sample_id": "musique-001",
            "benchmark_id": "musique",
            "budget": 12000,
            "primary_metric": 0.50,
            "metadata": {
                "context_precision": 0.50,
                "context_recall": 0.50,
                "key_evidence_retention_rate": 0.50,
                "prompt_redundancy_ratio": 0.42,
            },
        },
    ]

    elephant_rows = report.elephant_metric_rows(records)
    elephant_gaps = report.elephant_paired_rows(records)

    assert [row["variant"] for row in elephant_rows] == [
        "Full Framework",
        "Multi-Agent No Elephant",
        "Single Agent Long Context",
    ]
    assert [row["baseline"] for row in elephant_gaps] == [
        "Multi-Agent No Elephant",
        "Single Agent Long Context",
    ]
    assert elephant_gaps[0]["context_precision_gap"] == "0.33"
    assert elephant_gaps[1]["context_precision_gap"] == "0.50"

    monkeypatch.setattr(report, "ASSETS_DIR", tmp_path)
    report.write_elephant_tables(elephant_rows, elephant_gaps)

    content = (tmp_path / "elephant_context_tables.tex").read_text(encoding="utf-8")
    assert "RQ2 elephant-context comparison" in content
    assert "Single Agent Long Context" in content
