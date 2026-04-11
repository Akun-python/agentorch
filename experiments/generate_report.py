from __future__ import annotations

import csv
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.common.analysis import collect_records
from experiments.common.benchmarks import load_benchmark_registry
from experiments.common.config import RunRecord
from experiments.common.model_presets import CHEAP_FORMAL_MODELS, REFERENCE_FORMAL_MODEL
from experiments.common.stats import ci95, safe_mean, safe_std


RESULT_ROOT = Path("experiments/results_formal")
ASSET_ROOT = Path("experiments/report_assets")
PALETTE = ["#34dba1", "#34dbcb", "#34c2db", "#3498db", "#346edb", "#3445db", "#4d34db"]
KEY_BASELINE = {
    "rq1_long_horizon_tasks": "single_agent_basic",
    "rq2_elephant_attention": "multi_agent_no_elephant",
    "rq3_seagull_memory": "multi_agent_no_seagull",
    "rq4_budget_robustness": "multi_agent_no_long_horizon",
    "rq5_observability": "multi_agent_plain_logs",
}
TRACKED_REAL_MODELS = set(CHEAP_FORMAL_MODELS + [REFERENCE_FORMAL_MODEL])


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.edgecolor": "black",
            "axes.linewidth": 1.2,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "xtick.color": "black",
            "ytick.color": "black",
            "legend.frameon": True,
            "legend.edgecolor": "black",
            "legend.fancybox": False,
            "legend.framealpha": 1.0,
        }
    )


def _style_axis(ax) -> None:
    ax.grid(axis="y", alpha=0.28, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color("black")
        spine.set_linewidth(1.2)


def _wrap_label(value: str, width: int = 16) -> str:
    return "\n".join(textwrap.wrap(value.replace("_", " "), width=width, break_long_words=False))


def _annotate_bars(ax, bars, fmt: str = "{:.2f}", max_annotations: int = 18) -> None:
    if len(bars) > max_annotations:
        return
    top = ax.get_ylim()[1]
    for bar in bars:
        value = float(bar.get_height())
        if value <= 0:
            continue
        headroom = top - value
        offset = min(0.025, max(0.01, headroom * 0.18))
        y = value + offset
        va = "bottom"
        if y >= top * 0.985:
            y = max(0.03, value - offset * 1.6)
            va = "top"
        ax.text(bar.get_x() + bar.get_width() / 2.0, y, fmt.format(value), ha="center", va=va, fontsize=8)


def _legend_outside_top(ax, ncol: int = 3) -> None:
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.08), ncol=ncol, borderaxespad=0.2)


def _write_csv(name: str, rows: list[dict]) -> None:
    if not rows:
        return
    with (ASSET_ROOT / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _is_mock_model(model_name: str) -> bool:
    return model_name.startswith("mock:")


def _formal_records() -> list[RunRecord]:
    return [record for record in collect_records(RESULT_ROOT) if record.metadata.get("execution_tier") == "official_benchmark"]


def _benchmark_records(records: list[RunRecord]) -> list[RunRecord]:
    return [record for record in records if not str(record.metadata.get("output_tag", "")).startswith("scaling_agents_")]


def _scaling_records(records: list[RunRecord]) -> list[RunRecord]:
    return [record for record in records if str(record.metadata.get("output_tag", "")).startswith("scaling_agents_")]


def _preferred_records(records: list[RunRecord]) -> list[RunRecord]:
    real_records = [record for record in records if not _is_mock_model(record.model_name) and record.model_name in TRACKED_REAL_MODELS]
    return real_records if real_records else records


def _summary_for(records: list[RunRecord], getter) -> tuple[float, float, float, float]:
    values = [float(getter(item)) for item in records]
    low, high = ci95(values)
    return round(safe_mean(values), 4), round(safe_std(values), 4), round(low, 4), round(high, 4)


def _primary_metric_name(experiment_name: str) -> str:
    return {
        "rq1_long_horizon_tasks": "quality_score",
        "rq2_elephant_attention": "context_precision",
        "rq3_seagull_memory": "memory_reuse_hit_rate",
        "rq4_budget_robustness": "quality_score",
        "rq5_observability": "diagnostic_accuracy",
    }.get(experiment_name, "quality_score")


def _metric_value(record: RunRecord, metric_name: str) -> float:
    if metric_name == "quality_score":
        return float(record.quality_score)
    return float(record.metadata.get(metric_name, 0.0))


def _build_setup_tables(records: list[RunRecord]) -> tuple[list[dict], list[dict]]:
    registry = load_benchmark_registry()
    benchmark_rows: list[dict] = []
    for experiment_name, benchmark_ids in registry.get("rq_mapping", {}).items():
        for benchmark_id in benchmark_ids:
            meta = registry["benchmarks"][benchmark_id]
            matching = [item for item in records if item.experiment_name == experiment_name and item.benchmark_id == benchmark_id]
            if not matching:
                continue
            benchmark_rows.append(
                {
                    "experiment": experiment_name,
                    "benchmark_name": meta["name"],
                    "category": meta["category"],
                    "samples": len({item.benchmark_sample_id for item in matching}),
                    "models": len({item.model_name for item in matching}),
                    "seeds": len({item.seed for item in matching}),
                }
            )

    model_rows: list[dict] = []
    for model_name in sorted({item.model_name for item in records}):
        subset = [item for item in records if item.model_name == model_name]
        model_rows.append(
            {
                "model_name": model_name,
                "runs": len(subset),
                "avg_tokens": round(safe_mean(item.token_usage for item in subset), 4),
                "avg_latency_ms": round(safe_mean(item.latency_ms for item in subset), 4),
            }
        )
    return benchmark_rows, model_rows


def _build_main_results(records: list[RunRecord]) -> list[dict]:
    rows: list[dict] = []
    grouped: dict[tuple[str, str, str], list[RunRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.experiment_name, record.variant_name, record.model_name)].append(record)
    for (experiment_name, variant_name, model_name), bucket in sorted(grouped.items()):
        primary_metric = _primary_metric_name(experiment_name)
        success_mean, success_std, success_low, success_high = _summary_for(bucket, lambda item: 1.0 if item.success else 0.0)
        primary_mean, primary_std, primary_low, primary_high = _summary_for(bucket, lambda item: _metric_value(item, primary_metric))
        token_mean, token_std, token_low, token_high = _summary_for(bucket, lambda item: item.token_usage)
        rows.append(
            {
                "experiment": experiment_name,
                "variant": variant_name,
                "model_name": model_name,
                "primary_metric": primary_metric,
                "n": len(bucket),
                "success_mean": success_mean,
                "success_std": success_std,
                "success_ci95_low": success_low,
                "success_ci95_high": success_high,
                "primary_mean": primary_mean,
                "primary_std": primary_std,
                "primary_ci95_low": primary_low,
                "primary_ci95_high": primary_high,
                "token_mean": token_mean,
                "token_std": token_std,
                "token_ci95_low": token_low,
                "token_ci95_high": token_high,
            }
        )
    return rows


def _build_reference_results(main_rows: list[dict]) -> list[dict]:
    return [row for row in main_rows if row["model_name"] == REFERENCE_FORMAL_MODEL]


def _build_cheap_aggregate(records: list[RunRecord]) -> list[dict]:
    rows: list[dict] = []
    grouped: dict[tuple[str, str], list[RunRecord]] = defaultdict(list)
    for record in records:
        if record.model_name in CHEAP_FORMAL_MODELS:
            grouped[(record.experiment_name, record.variant_name)].append(record)
    for (experiment_name, variant_name), bucket in sorted(grouped.items()):
        primary_metric = _primary_metric_name(experiment_name)
        rows.append(
            {
                "experiment": experiment_name,
                "variant": variant_name,
                "models": ",".join(sorted({item.model_name for item in bucket})),
                "n": len(bucket),
                "success_mean": round(safe_mean(1.0 if item.success else 0.0 for item in bucket), 4),
                "primary_metric": primary_metric,
                "primary_mean": round(safe_mean(_metric_value(item, primary_metric) for item in bucket), 4),
                "primary_std": round(safe_std(_metric_value(item, primary_metric) for item in bucket), 4),
                "token_mean": round(safe_mean(item.token_usage for item in bucket), 4),
            }
        )
    return rows


def _build_cross_model_consistency(records: list[RunRecord]) -> list[dict]:
    rows: list[dict] = []
    models = sorted({item.model_name for item in records if not _is_mock_model(item.model_name)})
    for experiment_name, baseline_variant in KEY_BASELINE.items():
        consistent_models = 0
        total_models = 0
        gaps: list[float] = []
        for model_name in models:
            full_bucket = [item for item in records if item.experiment_name == experiment_name and item.model_name == model_name and item.variant_name == "full_framework"]
            baseline_bucket = [item for item in records if item.experiment_name == experiment_name and item.model_name == model_name and item.variant_name == baseline_variant]
            if not full_bucket or not baseline_bucket:
                continue
            primary_metric = _primary_metric_name(experiment_name)
            gap = safe_mean(_metric_value(item, primary_metric) for item in full_bucket) - safe_mean(_metric_value(item, primary_metric) for item in baseline_bucket)
            gaps.append(gap)
            total_models += 1
            if gap > 0:
                consistent_models += 1
        if total_models:
            rows.append(
                {
                    "experiment": experiment_name,
                    "reference_variant": "full_framework",
                    "baseline_variant": baseline_variant,
                    "consistent_models": consistent_models,
                    "total_models": total_models,
                    "consistency_ratio": round(consistent_models / total_models, 4),
                    "avg_primary_gap": round(safe_mean(gaps), 4),
                }
            )
    return rows


def _build_multiturn_results(records: list[RunRecord]) -> list[dict]:
    multiturn = [item for item in records if item.benchmark_id == "agentorch_multiturn_suite"]
    rows: list[dict] = []
    grouped: dict[tuple[str, str], list[RunRecord]] = defaultdict(list)
    for record in multiturn:
        grouped[(record.variant_name, record.model_name)].append(record)
    for (variant_name, model_name), bucket in sorted(grouped.items()):
        rows.append(
            {
                "variant": variant_name,
                "model_name": model_name,
                "n": len(bucket),
                "quality_mean": round(safe_mean(item.quality_score for item in bucket), 4),
                "multi_turn_consistency_mean": round(safe_mean(item.metadata.get("multi_turn_consistency", 0.0) for item in bucket), 4),
                "cross_round_constraint_retention_mean": round(safe_mean(item.metadata.get("cross_round_constraint_retention", 0.0) for item in bucket), 4),
                "delegation_continuity_mean": round(safe_mean(item.metadata.get("delegation_continuity", 0.0) for item in bucket), 4),
                "conversation_recovery_rate_mean": round(safe_mean(item.metadata.get("conversation_recovery_rate", 0.0) for item in bucket), 4),
            }
        )
    return rows


def _build_budget_results(records: list[RunRecord]) -> list[dict]:
    rows: list[dict] = []
    grouped: dict[tuple[str, int], list[RunRecord]] = defaultdict(list)
    for record in records:
        if record.experiment_name != "rq4_budget_robustness":
            continue
        grouped[(record.variant_name, int(record.metadata.get("prompt_budget", 0)))].append(record)
    for (variant_name, budget), bucket in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        quality_mean, quality_std, quality_low, quality_high = _summary_for(bucket, lambda item: item.quality_score)
        retained_mean, _, _, _ = _summary_for(bucket, lambda item: item.metadata.get("retained_context_ratio", 0.0))
        rows.append(
            {
                "variant": variant_name,
                "budget": budget,
                "quality_mean": quality_mean,
                "quality_std": quality_std,
                "quality_ci95_low": quality_low,
                "quality_ci95_high": quality_high,
                "retained_context_ratio_mean": retained_mean,
            }
        )
    return rows


def _build_scaling_results(records: list[RunRecord]) -> list[dict]:
    rows: list[dict] = []
    grouped: dict[int, list[RunRecord]] = defaultdict(list)
    for record in records:
        tag = str(record.metadata.get("output_tag", ""))
        if not tag.startswith("scaling_agents_"):
            continue
        agent_count = int(tag.rsplit("_", 1)[-1])
        grouped[agent_count].append(record)
    for agent_count, bucket in sorted(grouped.items()):
        quality_mean, quality_std, quality_low, quality_high = _summary_for(bucket, lambda item: item.quality_score)
        rows.append(
            {
                "agent_count": agent_count,
                "quality_mean": quality_mean,
                "quality_std": quality_std,
                "quality_ci95_low": quality_low,
                "quality_ci95_high": quality_high,
                "avg_latency_ms": round(safe_mean(item.latency_ms for item in bucket), 4),
            }
        )
    return rows


def _build_failure_breakdown(records: list[RunRecord]) -> list[dict]:
    rows: list[dict] = []
    for variant_name in ("full_framework", "multi_agent_plain_logs"):
        subset = [item for item in records if item.experiment_name == "rq5_observability" and item.variant_name == variant_name]
        if not subset:
            continue
        rows.append(
            {
                "variant": variant_name,
                "trace_coverage_mean": round(safe_mean(item.metadata.get("trace_coverage", 0.0) for item in subset), 4),
                "todo_consistency_mean": round(safe_mean(item.metadata.get("todo_consistency", 0.0) for item in subset), 4),
                "diagnostic_accuracy_mean": round(safe_mean(item.metadata.get("diagnostic_accuracy", 0.0) for item in subset), 4),
                "diagnostic_time_seconds_mean": round(safe_mean(item.metadata.get("diagnostic_time_seconds", 0.0) for item in subset), 4),
            }
        )
    return rows


def _plot_reference_results(rows: list[dict]) -> None:
    target = [row for row in rows if row["variant"] == "full_framework"]
    if not target:
        return
    fig, ax = plt.subplots(figsize=(10.8, 5.4), constrained_layout=True)
    labels = [_wrap_label(row["experiment"], 14) for row in target]
    values = [row["primary_mean"] for row in target]
    bars = ax.bar(labels, values, color=PALETTE[: len(target)], edgecolor="black", linewidth=1.2)
    ax.set_title(f"Reference Model Results ({REFERENCE_FORMAL_MODEL})", pad=18)
    ax.set_ylabel("Primary metric mean")
    ax.set_ylim(0, max(1.02, max(values) + 0.1))
    _annotate_bars(ax, bars)
    _style_axis(ax)
    fig.savefig(ASSET_ROOT / "formal_main_results.png", dpi=360, bbox_inches="tight")
    plt.close(fig)


def _plot_cheap_aggregate(rows: list[dict]) -> None:
    target = [row for row in rows if row["variant"] == "full_framework"]
    if not target:
        return
    fig, ax = plt.subplots(figsize=(10.8, 5.4), constrained_layout=True)
    labels = [_wrap_label(row["experiment"], 14) for row in target]
    values = [row["primary_mean"] for row in target]
    bars = ax.bar(labels, values, color=PALETTE[1 : 1 + len(target)], edgecolor="black", linewidth=1.2)
    ax.set_title("Cheap-Model Aggregate Results", pad=18)
    ax.set_ylabel("Primary metric mean")
    ax.set_ylim(0, max(1.02, max(values) + 0.1))
    _annotate_bars(ax, bars)
    _style_axis(ax)
    fig.savefig(ASSET_ROOT / "formal_cheap_model_results.png", dpi=360, bbox_inches="tight")
    plt.close(fig)


def _plot_budget_results(rows: list[dict]) -> None:
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(9.4, 5.6), constrained_layout=True)
    color_map = {"full_framework": PALETTE[3], "multi_agent_no_long_horizon": PALETTE[5], "multi_agent_no_compression": PALETTE[1]}
    for variant in ("full_framework", "multi_agent_no_long_horizon", "multi_agent_no_compression"):
        subset = [row for row in rows if row["variant"] == variant]
        if not subset:
            continue
        budgets = [row["budget"] for row in subset]
        means = [row["quality_mean"] for row in subset]
        lows = [row["quality_ci95_low"] for row in subset]
        highs = [row["quality_ci95_high"] for row in subset]
        line = ax.plot(budgets, means, color=color_map[variant], linewidth=2.4, marker="o", markersize=7, label=_wrap_label(variant, 22))[0]
        line.set_markeredgecolor("black")
        line.set_markeredgewidth(1.0)
        ax.fill_between(budgets, lows, highs, color=color_map[variant], alpha=0.12)
    ax.set_title("RQ4 Budget Robustness with 95% Confidence Intervals", pad=16)
    ax.set_xlabel("Prompt budget")
    ax.set_ylabel("Quality mean")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower right")
    _style_axis(ax)
    fig.savefig(ASSET_ROOT / "formal_rq4_robustness.png", dpi=360, bbox_inches="tight")
    plt.close(fig)


def _plot_scaling(rows: list[dict]) -> None:
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(8.1, 4.9), constrained_layout=True)
    counts = [row["agent_count"] for row in rows]
    means = [row["quality_mean"] for row in rows]
    lows = [row["quality_ci95_low"] for row in rows]
    highs = [row["quality_ci95_high"] for row in rows]
    line = ax.plot(counts, means, color=PALETTE[4], linewidth=2.6, marker="o", markersize=8)[0]
    line.set_markeredgecolor("black")
    line.set_markeredgewidth(1.0)
    ax.fill_between(counts, lows, highs, color=PALETTE[4], alpha=0.15)
    ax.set_title("Scaling with Agent Count", pad=16)
    ax.set_xlabel("Agent count")
    ax.set_ylabel("Quality mean")
    ax.set_xticks(counts)
    ax.set_ylim(0, 1.05)
    _style_axis(ax)
    fig.savefig(ASSET_ROOT / "formal_scaling_curve.png", dpi=360, bbox_inches="tight")
    plt.close(fig)


def _plot_failure_breakdown(rows: list[dict]) -> None:
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(9.6, 5.8), constrained_layout=True)
    labels = [_wrap_label(row["variant"], 16) for row in rows]
    x = list(range(len(rows)))
    bars1 = ax.bar([item - 0.26 for item in x], [row["trace_coverage_mean"] for row in rows], width=0.24, color=PALETTE[2], edgecolor="black", linewidth=1.1, label="Trace coverage")
    bars2 = ax.bar(x, [row["todo_consistency_mean"] for row in rows], width=0.24, color=PALETTE[4], edgecolor="black", linewidth=1.1, label="Todo consistency")
    bars3 = ax.bar([item + 0.26 for item in x], [row["diagnostic_accuracy_mean"] for row in rows], width=0.24, color=PALETTE[6], edgecolor="black", linewidth=1.1, label="Diagnostic accuracy")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.1)
    ax.set_title("RQ5 Diagnostic Breakdown", pad=20)
    _legend_outside_top(ax, ncol=3)
    _annotate_bars(ax, bars1)
    _annotate_bars(ax, bars2)
    _annotate_bars(ax, bars3)
    _style_axis(ax)
    fig.savefig(ASSET_ROOT / "formal_failure_breakdown.png", dpi=360, bbox_inches="tight")
    plt.close(fig)


def _plot_memory_results(records: list[RunRecord]) -> None:
    rows = []
    for variant_name in ("full_framework", "multi_agent_no_seagull", "multi_agent_naive_memory"):
        subset = [item for item in records if item.experiment_name == "rq3_seagull_memory" and item.variant_name == variant_name]
        if not subset:
            continue
        rows.append(
            {
                "variant": variant_name,
                "hit": round(safe_mean(item.metadata.get("memory_reuse_hit_rate", 0.0) for item in subset), 4),
                "precision": round(safe_mean(item.metadata.get("long_term_recall_precision", 0.0) for item in subset), 4),
                "inv_stale": round(1.0 - safe_mean(item.metadata.get("stale_memory_injection_rate", 0.0) for item in subset), 4),
            }
        )
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(9.8, 5.8), constrained_layout=True)
    labels = [_wrap_label(row["variant"], 16) for row in rows]
    x = list(range(len(rows)))
    bars1 = ax.bar([item - 0.26 for item in x], [row["hit"] for row in rows], width=0.24, color=PALETTE[0], edgecolor="black", linewidth=1.1, label="Reuse hit rate")
    bars2 = ax.bar(x, [row["precision"] for row in rows], width=0.24, color=PALETTE[1], edgecolor="black", linewidth=1.1, label="Recall precision")
    bars3 = ax.bar([item + 0.26 for item in x], [row["inv_stale"] for row in rows], width=0.24, color=PALETTE[5], edgecolor="black", linewidth=1.1, label="1 - stale rate")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.1)
    ax.set_title("RQ3 Memory Lifecycle Metrics", pad=20)
    _legend_outside_top(ax, ncol=3)
    _annotate_bars(ax, bars1)
    _annotate_bars(ax, bars2)
    _annotate_bars(ax, bars3)
    _style_axis(ax)
    fig.savefig(ASSET_ROOT / "formal_rq3_memory.png", dpi=360, bbox_inches="tight")
    plt.close(fig)


def _plot_multiturn_results(rows: list[dict]) -> None:
    if not rows:
        return
    priority_variants = ["full_framework", "single_agent_basic", "multi_agent_no_elephant"]
    selected = [row for row in rows if row["model_name"] == REFERENCE_FORMAL_MODEL and row["variant"] in priority_variants]
    if not selected:
        selected = [row for row in rows if row["variant"] in priority_variants][:3]
    if not selected:
        return
    fig, ax = plt.subplots(figsize=(10.2, 5.9), constrained_layout=True)
    labels = [_wrap_label(row["variant"], 18) for row in selected]
    x = list(range(len(selected)))
    bars1 = ax.bar([item - 0.24 for item in x], [row["multi_turn_consistency_mean"] for row in selected], width=0.22, color=PALETTE[0], edgecolor="black", linewidth=1.1, label="Consistency")
    bars2 = ax.bar(x, [row["cross_round_constraint_retention_mean"] for row in selected], width=0.22, color=PALETTE[3], edgecolor="black", linewidth=1.1, label="Constraint retention")
    bars3 = ax.bar([item + 0.24 for item in x], [row["delegation_continuity_mean"] for row in selected], width=0.22, color=PALETTE[5], edgecolor="black", linewidth=1.1, label="Delegation continuity")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.1)
    ax.set_title("Multi-Agent Multi-Turn Dialogue Results", pad=20)
    _legend_outside_top(ax, ncol=3)
    _annotate_bars(ax, bars1)
    _annotate_bars(ax, bars2)
    _annotate_bars(ax, bars3)
    _style_axis(ax)
    fig.savefig(ASSET_ROOT / "formal_multiturn_results.png", dpi=360, bbox_inches="tight")
    plt.close(fig)


def _write_latex_tables(
    benchmark_rows: list[dict],
    model_rows: list[dict],
    reference_rows: list[dict],
    cheap_rows: list[dict],
    cross_model_rows: list[dict],
    multiturn_rows: list[dict],
    failure_rows: list[dict],
) -> None:
    multiturn_focus = [row for row in multiturn_rows if row["model_name"] == REFERENCE_FORMAL_MODEL]
    cheap_focus = [row for row in cheap_rows if row["variant"] == "full_framework"]

    tex = """
% Auto-generated by experiments/generate_report.py
\\begin{table*}[t]
\\centering
\\caption{Formal benchmark setup used by the AgentOrch experiment layer. Counts refer to currently collected official-benchmark records aggregated under stable benchmark and split identifiers.}
\\begin{tabular}{lccccc}
\\toprule
Experiment & Benchmark & Category & Samples & Models & Seeds \\\\
\\midrule
""" + "\n".join(
        f"{row['experiment'].replace('_', ' ')} & {row['benchmark_name']} & {row['category'].replace('_', ' ')} & {row['samples']} & {row['models']} & {row['seeds']} \\\\"
        for row in benchmark_rows
    ) + """
\\bottomrule
\\end{tabular}
\\end{table*}

\\begin{table}[t]
\\centering
\\caption{Controlled real-model setup for the current formal runs.}
\\begin{tabular}{lccc}
\\toprule
Model & Runs & Avg. tokens & Avg. latency (ms) \\\\
\\midrule
""" + "\n".join(
        f"{row['model_name']} & {row['runs']} & {row['avg_tokens']:.1f} & {row['avg_latency_ms']:.1f} \\\\"
        for row in model_rows
    ) + """
\\bottomrule
\\end{tabular}
\\end{table}

\\begin{table*}[t]
\\centering
\\caption{Reference-model formal results. The table emphasizes the strongest reference model while keeping the evaluation protocol identical across variants.}
\\begin{tabular}{lcccc}
\\toprule
Experiment & Variant & Success & Primary metric & Tokens \\\\
\\midrule
""" + "\n".join(
        f"{row['experiment'].replace('_', ' ')} & {row['variant'].replace('_', ' ')} & "
        f"{row['success_mean']:.2f}$\\pm${row['success_std']:.2f} & "
        f"{row['primary_mean']:.2f}$\\pm${row['primary_std']:.2f} & "
        f"{row['token_mean']:.1f}$\\pm${row['token_std']:.1f} \\\\"
        for row in reference_rows
    ) + """
\\bottomrule
\\end{tabular}
\\end{table*}

\\begin{table*}[t]
\\centering
\\caption{Cheap-model aggregate results. Values average over the lower-cost real-model set to test whether the directional behavior is preserved beyond the reference model.}
\\begin{tabular}{lccc}
\\toprule
Experiment & Variant & Success & Primary metric \\\\
\\midrule
""" + "\n".join(
        f"{row['experiment'].replace('_', ' ')} & {row['variant'].replace('_', ' ')} & {row['success_mean']:.2f} & {row['primary_mean']:.2f} \\\\"
        for row in cheap_focus
    ) + """
\\bottomrule
\\end{tabular}
\\end{table*}

\\begin{table}[t]
\\centering
\\caption{Cross-model consistency of the full framework relative to the key baseline for each research question.}
\\begin{tabular}{lccc}
\\toprule
Experiment & Baseline & Consistency & Avg. gap \\\\
\\midrule
""" + "\n".join(
        f"{row['experiment'].replace('_', ' ')} & {row['baseline_variant'].replace('_', ' ')} & "
        f"{row['consistent_models']}/{row['total_models']} & {row['avg_primary_gap']:.2f} \\\\"
        for row in cross_model_rows
    ) + """
\\bottomrule
\\end{tabular}
\\end{table}

\\begin{table*}[t]
\\centering
\\caption{Multi-agent multi-turn dialogue results for the reference model. The metrics capture cross-round continuity rather than one-shot answer quality alone.}
\\begin{tabular}{lcccc}
\\toprule
Variant & Quality & Consistency & Constraint retention & Delegation continuity \\\\
\\midrule
""" + "\n".join(
        f"{row['variant'].replace('_', ' ')} & {row['quality_mean']:.2f} & {row['multi_turn_consistency_mean']:.2f} & "
        f"{row['cross_round_constraint_retention_mean']:.2f} & {row['delegation_continuity_mean']:.2f} \\\\"
        for row in multiturn_focus
    ) + """
\\bottomrule
\\end{tabular}
\\end{table*}

\\begin{table}[t]
\\centering
\\caption{RQ5 diagnostic metrics for the formal diagnostic benchmark.}
\\begin{tabular}{lcccc}
\\toprule
Variant & Trace & Todo & Accuracy & Time (s) \\\\
\\midrule
""" + "\n".join(
        f"{row['variant'].replace('_', ' ')} & {row['trace_coverage_mean']:.2f} & {row['todo_consistency_mean']:.2f} & {row['diagnostic_accuracy_mean']:.2f} & {row['diagnostic_time_seconds_mean']:.2f} \\\\"
        for row in failure_rows
    ) + """
\\bottomrule
\\end{tabular}
\\end{table}
"""
    (ASSET_ROOT / "paper_tables.tex").write_text(tex.strip() + "\n", encoding="utf-8")


def main() -> None:
    _apply_style()
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)

    all_records = _formal_records()
    benchmark_records = _benchmark_records(all_records)
    scaling_records = _scaling_records(all_records)
    preferred_benchmark_records = _preferred_records(benchmark_records)
    preferred_scaling_records = _preferred_records(scaling_records)

    benchmark_rows, model_rows = _build_setup_tables(preferred_benchmark_records)
    main_rows = _build_main_results(preferred_benchmark_records)
    reference_rows = _build_reference_results(main_rows)
    cheap_rows = _build_cheap_aggregate(preferred_benchmark_records)
    cross_model_rows = _build_cross_model_consistency(preferred_benchmark_records)
    multiturn_rows = _build_multiturn_results(preferred_benchmark_records)
    budget_rows = _build_budget_results(preferred_benchmark_records)
    scaling_rows = _build_scaling_results(preferred_scaling_records)
    failure_rows = _build_failure_breakdown(preferred_benchmark_records)

    _write_csv("formal_benchmark_setup", benchmark_rows)
    _write_csv("formal_model_setup", model_rows)
    _write_csv("formal_main_results", main_rows)
    _write_csv("formal_reference_results", reference_rows)
    _write_csv("formal_cheap_model_results", cheap_rows)
    _write_csv("formal_cross_model_consistency", cross_model_rows)
    _write_csv("formal_multiturn_results", multiturn_rows)
    _write_csv("formal_budget_results", budget_rows)
    _write_csv("formal_scaling_results", scaling_rows)
    _write_csv("formal_failure_breakdown", failure_rows)

    _plot_reference_results(reference_rows)
    _plot_cheap_aggregate(cheap_rows)
    _plot_budget_results(budget_rows)
    _plot_scaling(scaling_rows)
    _plot_failure_breakdown(failure_rows)
    _plot_memory_results(preferred_benchmark_records)
    _plot_multiturn_results(multiturn_rows)
    _write_latex_tables(benchmark_rows, model_rows, reference_rows, cheap_rows, cross_model_rows, multiturn_rows, failure_rows)


if __name__ == "__main__":
    main()
