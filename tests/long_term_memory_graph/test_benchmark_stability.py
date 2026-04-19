from __future__ import annotations

from experiments.long_term_memory_graph.tools.benchmark_baseline_stability import run_baseline_stability_benchmark
from experiments.long_term_memory_graph.tools.benchmark_baselines import BASELINE_ORDER
from experiments.long_term_memory_graph.tools.demo_fixtures import HashedDemoEmbeddingProvider, SCENARIOS, build_demo_candidates, build_demo_request


def test_hashed_demo_embedding_provider_salt_changes_vectors():
    text = "service alpha deployment rollout"
    default_provider = HashedDemoEmbeddingProvider(dimensions=16, salt="seed-a")
    variant_provider = HashedDemoEmbeddingProvider(dimensions=16, salt="seed-b")

    assert default_provider._embed_text(text) != variant_provider._embed_text(text)


def test_build_demo_candidates_scale_multiplier_expands_graph():
    single_scale = build_demo_candidates("scale-test-")
    triple_scale = build_demo_candidates("scale-test-", scale_multiplier=3)

    assert len(single_scale) == len(SCENARIOS) * 30
    assert len(triple_scale) == len(single_scale) * 3
    assert any("__cohort_02" in item.capsule_id for item in triple_scale)


def test_build_demo_request_targets_scaled_cohort():
    request = build_demo_request("scale-test-", SCENARIOS[0], replica_index=1, scale_multiplier=3)

    assert request.task_family.endswith("__cohort_02")
    assert "cohort_02" in request.tags
    assert "cohort_02" in request.entities


def test_run_baseline_stability_benchmark_emits_aggregate_reports(tmp_path):
    report = run_baseline_stability_benchmark(
        output_dir=tmp_path,
        seeds=3,
        case_limit=2,
        prefix="stability-test-",
        bootstrap_samples=100,
    )

    assert report["seed_values"] == [0, 1, 2]
    assert [row["baseline"] for row in report["baseline_stability"]] == list(BASELINE_ORDER)
    assert len(report["seed_reports"]) == 3
    assert report["bootstrap_samples"] == 100
    assert report["confidence_level"] == 0.95

    clarks_row = next(row for row in report["baseline_stability"] if row["baseline"] == "clarks_nutcracker_graph")
    no_memory_row = next(row for row in report["baseline_stability"] if row["baseline"] == "no_long_term_memory")
    assert clarks_row["capsule_recall@k_mean"] >= no_memory_row["capsule_recall@k_mean"]
    assert "capsule_recall@k_ci95_low" in clarks_row
    assert "capsule_recall@k_ci95_high" in clarks_row
    assert clarks_row["capsule_recall@k_ci95_low"] <= clarks_row["capsule_recall@k_ci95_high"]

    for filename in (
        "baseline_stability_report.json",
        "baseline_stability_report.md",
        "baseline_stability_seed_rows.csv",
        "baseline_stability_aggregates.csv",
    ):
        assert (tmp_path / filename).exists()
