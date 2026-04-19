from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from random import Random
from statistics import mean, pstdev

from .benchmark_baselines import BASELINE_ORDER, run_baseline_benchmark

STABILITY_METRICS = (
    "capsule_recall@k",
    "subgraph_relevance",
    "relation_hit_rate",
    "returned_memory_usefulness",
    "stale_node_injection_rate",
    "conflict_resolution_success",
    "latency_ms",
    "avg_returned_nodes",
    "avg_raw_returned_nodes",
    "avg_returned_edges",
)


def _metric_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": round(mean(values), 4),
        "std": round(pstdev(values), 4) if len(values) > 1 else 0.0,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def _bootstrap_ci(
    values: list[float],
    *,
    rng: Random,
    samples: int,
    confidence_level: float,
) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        single = round(values[0], 4)
        return single, single
    sample_means: list[float] = []
    for _ in range(samples):
        resample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        sample_means.append(mean(resample))
    alpha = max(0.0, min(1.0, 1.0 - confidence_level))
    lower = _percentile(sample_means, alpha / 2.0)
    upper = _percentile(sample_means, 1.0 - alpha / 2.0)
    return round(lower, 4), round(upper, 4)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_baseline_stability_benchmark(
    *,
    prefix: str = "benchmark-stability-",
    output_dir: Path,
    seeds: int = 5,
    start_seed: int = 0,
    case_limit: int | None = None,
    bootstrap_samples: int = 1000,
    confidence_level: float = 0.95,
) -> dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive.")
    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive.")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1.")

    output_dir.mkdir(parents=True, exist_ok=True)
    seed_rows: list[dict[str, object]] = []
    seed_reports: list[dict[str, object]] = []
    seed_values = list(range(start_seed, start_seed + seeds))
    rng = Random(20260419)

    for seed in seed_values:
        seed_dir = output_dir / f"seed_{seed:02d}"
        seed_prefix = f"{prefix}seed{seed:02d}-"
        report = run_baseline_benchmark(
            prefix=seed_prefix,
            output_dir=seed_dir,
            case_limit=case_limit,
            embedding_salt=f"seed-{seed}",
        )
        seed_reports.append(
            {
                "seed": seed,
                "prefix": seed_prefix,
                "output_dir": str(seed_dir),
                "case_count": report["case_count"],
                "baseline_aggregates": report["baseline_aggregates"],
            }
        )
        for baseline_row in report["baseline_aggregates"]:
            seed_rows.append({"seed": seed, **baseline_row})

    aggregate_rows: list[dict[str, object]] = []
    for baseline_name in BASELINE_ORDER:
        baseline_seed_rows = [row for row in seed_rows if row["baseline"] == baseline_name]
        aggregate_row: dict[str, object] = {
            "baseline": baseline_name,
            "seed_count": len(baseline_seed_rows),
        }
        for metric in STABILITY_METRICS:
            values = [float(row[metric]) for row in baseline_seed_rows]
            stats = _metric_stats(values)
            ci_low, ci_high = _bootstrap_ci(
                values,
                rng=rng,
                samples=bootstrap_samples,
                confidence_level=confidence_level,
            )
            aggregate_row[f"{metric}_mean"] = stats["mean"]
            aggregate_row[f"{metric}_std"] = stats["std"]
            aggregate_row[f"{metric}_min"] = stats["min"]
            aggregate_row[f"{metric}_max"] = stats["max"]
            aggregate_row[f"{metric}_ci95_low"] = ci_low
            aggregate_row[f"{metric}_ci95_high"] = ci_high
        aggregate_rows.append(aggregate_row)

    report = {
        "prefix": prefix,
        "seed_values": seed_values,
        "case_limit": case_limit,
        "bootstrap_samples": bootstrap_samples,
        "confidence_level": confidence_level,
        "metrics": list(STABILITY_METRICS),
        "seed_reports": seed_reports,
        "baseline_stability": aggregate_rows,
    }

    (output_dir / "baseline_stability_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(output_dir / "baseline_stability_seed_rows.csv", seed_rows)
    _write_csv(output_dir / "baseline_stability_aggregates.csv", aggregate_rows)

    markdown_lines = [
        "# Long-Term Memory Graph Baseline Stability Benchmark",
        "",
        f"- Prefix: `{prefix}`",
        f"- Seeds: `{', '.join(str(seed) for seed in seed_values)}`",
        f"- Case limit: `{case_limit if case_limit is not None else 'all'}`",
        f"- Bootstrap samples: `{bootstrap_samples}`",
        f"- Confidence level: `{confidence_level}`",
        "",
        "## Aggregate Stability",
        "",
        "| Baseline | recall mean [95% CI] | relevance mean [95% CI] | relation mean [95% CI] | usefulness mean [95% CI] | stale mean [95% CI] | conflict mean [95% CI] | latency mean [95% CI] |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in aggregate_rows:
        markdown_lines.append(
            f"| `{row['baseline']}` | "
            f"`{row['capsule_recall@k_mean']} [{row['capsule_recall@k_ci95_low']}, {row['capsule_recall@k_ci95_high']}]` | "
            f"`{row['subgraph_relevance_mean']} [{row['subgraph_relevance_ci95_low']}, {row['subgraph_relevance_ci95_high']}]` | "
            f"`{row['relation_hit_rate_mean']} [{row['relation_hit_rate_ci95_low']}, {row['relation_hit_rate_ci95_high']}]` | "
            f"`{row['returned_memory_usefulness_mean']} [{row['returned_memory_usefulness_ci95_low']}, {row['returned_memory_usefulness_ci95_high']}]` | "
            f"`{row['stale_node_injection_rate_mean']} [{row['stale_node_injection_rate_ci95_low']}, {row['stale_node_injection_rate_ci95_high']}]` | "
            f"`{row['conflict_resolution_success_mean']} [{row['conflict_resolution_success_ci95_low']}, {row['conflict_resolution_success_ci95_high']}]` | "
            f"`{row['latency_ms_mean']} [{row['latency_ms_ci95_low']}, {row['latency_ms_ci95_high']}]` |"
        )
    markdown_lines.extend(["", "## Per Seed", ""])
    for seed in seed_values:
        markdown_lines.append(f"### seed {seed}")
        for row in [item for item in seed_rows if int(item["seed"]) == seed]:
            markdown_lines.append(
                f"- `{row['baseline']}`: recall `{row['capsule_recall@k']}`, relevance `{row['subgraph_relevance']}`, "
                f"relation `{row['relation_hit_rate']}`, usefulness `{row['returned_memory_usefulness']}`, "
                f"stale `{row['stale_node_injection_rate']}`, conflict `{row['conflict_resolution_success']}`, "
                f"latency `{row['latency_ms']}` ms"
            )
        markdown_lines.append("")
    (output_dir / "baseline_stability_report.md").write_text("\n".join(markdown_lines).strip() + "\n", encoding="utf-8")
    return report


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "benchmark-baseline-stability",
        help="Run the baseline benchmark across multiple deterministic embedding seeds.",
    )
    parser.add_argument("--prefix", default="benchmark-stability-")
    parser.add_argument("--output-dir", default=str(Path("artifacts") / "long_term_memory_graph_stability"))
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--start-seed", type=int, default=0)
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--confidence-level", type=float, default=0.95)
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    return run_baseline_stability_benchmark(
        prefix=args.prefix,
        output_dir=Path(args.output_dir),
        seeds=args.seeds,
        start_seed=args.start_seed,
        case_limit=args.case_limit,
        bootstrap_samples=args.bootstrap_samples,
        confidence_level=args.confidence_level,
    )


__all__ = ["build_parser", "run_baseline_stability_benchmark", "run_from_args"]
