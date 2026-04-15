from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import to_rgba

from experiments.common.model_presets import CHEAP_FORMAL_MODELS, REAL_FORMAL_MODELS, REFERENCE_FORMAL_MODEL
from experiments.common.stats import bootstrap_ci95, ci95, safe_mean, safe_std, sign_test_p_value


RESULTS_DIR = ROOT / "experiments" / "results_formal"
ASSETS_DIR = ROOT / "experiments" / "report_assets"

PUBLIC_BENCHMARKS = {
    "gaia": "GAIA",
    "hotpotqa": "HotpotQA",
    "musique": "MuSiQue",
    "locomo": "LoCoMo",
    "longmemeval": "LongMemEval",
    "longbench": "LongBench",
    "infinitebench": "InfiniteBench",
}
SUPPLEMENTARY_BENCHMARKS = {
    "agentorch_failure_suite": "AgentOrch Failure Suite",
    "agentorch_multiturn_suite": "AgentOrch MultiTurn Suite",
}
BENCHMARK_LABELS = {**PUBLIC_BENCHMARKS, **SUPPLEMENTARY_BENCHMARKS}
BENCHMARK_CATEGORY = {
    "gaia": "tool-augmented long horizon",
    "hotpotqa": "multi-hop reasoning",
    "musique": "compositional multi-hop reasoning",
    "locomo": "long-term conversational memory",
    "longmemeval": "cross-session memory",
    "longbench": "budgeted long-context evaluation",
    "infinitebench": "long-context evaluation",
    "agentorch_failure_suite": "observability diagnostics",
    "agentorch_multiturn_suite": "multi-agent multi-turn dialogue",
}
EXPERIMENT_LABELS = {
    "rq1_long_horizon_tasks": "RQ1 Long-Horizon Tasks",
    "rq2_elephant_attention": "RQ2 Elephant Attention",
    "rq3_seagull_memory": "RQ3 Seagull Memory",
    "rq4_budget_robustness": "RQ4 Budget Robustness",
    "rq5_observability": "RQ5 Observability",
}
VARIANT_LABELS = {
    "full_framework": "Full Framework",
    "single_agent_basic": "Single Agent Basic",
    "single_agent_long_context": "Single Agent Long Context",
    "multi_agent_no_elephant": "Multi-Agent No Elephant",
    "multi_agent_no_seagull": "Multi-Agent No Seagull",
    "multi_agent_no_long_horizon": "Multi-Agent No Long Horizon",
    "multi_agent_no_compression": "Multi-Agent No Compression",
    "multi_agent_naive_memory": "Multi-Agent Naive Memory",
    "multi_agent_plain_logs": "Multi-Agent Plain Logs",
}
KEY_BASELINES = {
    "rq1_long_horizon_tasks": "single_agent_basic",
    "rq2_elephant_attention": "multi_agent_no_elephant",
    "rq3_seagull_memory": "multi_agent_no_seagull",
    "rq4_budget_robustness": "multi_agent_no_long_horizon",
}
CHEAP_AGG_VARIANTS = {
    "rq1_long_horizon_tasks": ["full_framework", "single_agent_basic", "multi_agent_no_elephant"],
    "rq2_elephant_attention": ["full_framework", "multi_agent_no_elephant", "single_agent_long_context"],
    "rq3_seagull_memory": ["full_framework", "multi_agent_naive_memory", "multi_agent_no_seagull"],
    "rq4_budget_robustness": ["full_framework", "multi_agent_no_compression", "multi_agent_no_long_horizon"],
}
REFERENCE_VARIANTS = {
    "rq1_long_horizon_tasks": ["full_framework", "single_agent_basic", "multi_agent_no_elephant"],
    "rq2_elephant_attention": ["full_framework", "multi_agent_no_elephant", "single_agent_long_context"],
    "rq3_seagull_memory": ["full_framework", "multi_agent_naive_memory", "multi_agent_no_seagull"],
    "rq4_budget_robustness": ["full_framework", "multi_agent_no_compression", "multi_agent_no_long_horizon"],
    "rq5_observability": ["full_framework", "multi_agent_plain_logs"],
}

PALETTE = ["#34dba1", "#34dbcb", "#34c2db", "#3498db", "#346edb", "#3445db", "#4d34db"]
FIGURE_BG = "none"
AXES_BG = "none"
GRID_COLOR = "#d7e8f2"
TEXT_COLOR = "#000000"
MUTED_COLOR = "#000000"
EXPERIMENT_COLORS = {
    "rq1_long_horizon_tasks": PALETTE[0],
    "rq2_elephant_attention": PALETTE[1],
    "rq3_seagull_memory": PALETTE[2],
    "rq4_budget_robustness": PALETTE[4],
    "rq5_observability": PALETTE[6],
}
VARIANT_COLORS = {
    "full_framework": PALETTE[3],
    "single_agent_basic": PALETTE[6],
    "single_agent_long_context": PALETTE[5],
    "multi_agent_no_elephant": PALETTE[1],
    "multi_agent_no_seagull": PALETTE[2],
    "multi_agent_no_long_horizon": PALETTE[5],
    "multi_agent_no_compression": PALETTE[4],
    "multi_agent_naive_memory": PALETTE[0],
    "multi_agent_plain_logs": PALETTE[6],
}


plt.rcParams.update(
    {
        "figure.facecolor": FIGURE_BG,
        "axes.facecolor": AXES_BG,
        "savefig.facecolor": FIGURE_BG,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.edgecolor": "#000000",
        "axes.labelcolor": TEXT_COLOR,
        "axes.titlecolor": TEXT_COLOR,
        "xtick.color": TEXT_COLOR,
        "ytick.color": TEXT_COLOR,
        "text.color": TEXT_COLOR,
        "grid.color": GRID_COLOR,
        "grid.linewidth": 0.8,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
    }
)


def _is_real_model(model_name: str) -> bool:
    return model_name in REAL_FORMAL_MODELS


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _fmt_ci(values: list[float], *, digits: int = 2) -> str:
    if not values:
        return "--"
    lower, upper = ci95(values)
    return f"{safe_mean(values):.{digits}f} [{lower:.{digits}f}, {upper:.{digits}f}]"


def _rgba(color: str, alpha: float) -> tuple[float, float, float, float]:
    r, g, b, _ = to_rgba(color)
    return (r, g, b, alpha)


def _primary_value(cell: object) -> float:
    return float(str(cell).split()[0])


def _primary_value_and_ci(cell: object) -> tuple[float, float, float]:
    text = str(cell).strip()
    value = _primary_value(text)
    if "[" not in text or "]" not in text:
        return value, value, value
    interval = text.split("[", 1)[1].split("]", 1)[0]
    low_text, high_text = [part.strip() for part in interval.split(",", 1)]
    return value, float(low_text), float(high_text)


def _style_axes(ax, *, title: str | None = None, xlabel: str | None = None, ylabel: str | None = None,
                subtitle: str | None = None, grid_axis: str = "y") -> None:
    ax.set_facecolor(AXES_BG)
    ax.grid(axis=grid_axis, linestyle=(0, (3, 4)))
    ax.set_axisbelow(True)
    for spine_name in ("top", "right"):
        ax.spines[spine_name].set_visible(False)
    for spine_name in ("left", "bottom"):
        ax.spines[spine_name].set_visible(True)
        ax.spines[spine_name].set_color("black")
        ax.spines[spine_name].set_linewidth(1.1)
    ax.tick_params(axis="both", colors=TEXT_COLOR, width=1.0)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)


def _annotate_bar_values(ax, values: list[float], xs: list[float], *, color: str = TEXT_COLOR, fmt: str = "{:.2f}") -> None:
    for x_pos, value in zip(xs, values):
        ax.text(x_pos, value + 0.025, fmt.format(value), ha="center", va="bottom", fontsize=9, color=color)


def _style_legend(legend) -> None:
    if legend is None:
        return
    frame = legend.get_frame()
    frame.set_facecolor("none")
    frame.set_edgecolor("black")
    frame.set_linewidth(1.0)
    frame.set_alpha(1.0)
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)


def _outline_artist(artist, *, linewidth: float = 1.8) -> None:
    artist.set_path_effects([pe.Stroke(linewidth=linewidth, foreground="black"), pe.Normal()])


def _save_figure(fig: plt.Figure, filename: str) -> None:
    fig.tight_layout()
    fig.patch.set_alpha(0.0)
    for ax in fig.axes:
        ax.patch.set_alpha(0.0)
    output_path = ASSETS_DIR / filename
    fig.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight", transparent=True)
    fig.savefig(output_path.with_suffix(".png"), dpi=260, bbox_inches="tight", transparent=True)
    plt.close(fig)


def _csv_write(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_records() -> list[dict]:
    records: list[dict] = []
    for jsonl_path in RESULTS_DIR.rglob("results.jsonl"):
        with jsonl_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                model_name = row.get("model_name", "")
                if not _is_real_model(model_name):
                    continue
                benchmark_id = row.get("benchmark_id") or row.get("metadata", {}).get("benchmark", {}).get("benchmark_id")
                row["benchmark_id"] = benchmark_id
                row["benchmark_name"] = row.get("benchmark_name") or BENCHMARK_LABELS.get(benchmark_id, benchmark_id or "Unknown")
                row["benchmark_split"] = row.get("benchmark_split") or row.get("metadata", {}).get("benchmark", {}).get("benchmark_split")
                row["primary_metric"] = float(row.get("quality_score", 0.0))
                row["success_value"] = 1.0 if row.get("success") else 0.0
                row["budget"] = int(row.get("metadata", {}).get("prompt_budget", 12000) or 12000)
                row["sample_id"] = row.get("benchmark_sample_id") or row.get("task_id")
                records.append(row)
    return records


def group_records(records: list[dict], *, experiment: str | None = None, variant: str | None = None, model: str | None = None,
                  benchmark_ids: set[str] | None = None, budget: int | None = None) -> list[dict]:
    rows = []
    for row in records:
        if experiment and row["experiment_name"] != experiment:
            continue
        if variant and row["variant_name"] != variant:
            continue
        if model and row["model_name"] != model:
            continue
        if benchmark_ids and row["benchmark_id"] not in benchmark_ids:
            continue
        if budget is not None and row["budget"] != budget:
            continue
        rows.append(row)
    return rows


def aggregate_run_level(rows: list[dict]) -> dict[str, object]:
    seeds = sorted({int(row["seed"]) for row in rows})
    models = sorted({row["model_name"] for row in rows})
    samples = sorted({row["sample_id"] for row in rows})
    metric_values = [float(row["primary_metric"]) for row in rows]
    success_values = [float(row["success_value"]) for row in rows]
    token_values = [float(row.get("token_usage", 0.0)) for row in rows]
    return {
        "n_runs": len(rows),
        "n_samples": len(samples),
        "n_seeds": len(seeds),
        "n_models": len(models),
        "metric_mean": safe_mean(metric_values),
        "metric_std": safe_std(metric_values),
        "metric_ci": bootstrap_ci95(metric_values),
        "success_mean": safe_mean(success_values),
        "success_ci": bootstrap_ci95(success_values),
        "tokens_mean": safe_mean(token_values),
    }


def coverage_rows(records: list[dict], benchmark_scope: set[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in records:
        if row["benchmark_id"] in benchmark_scope:
            grouped[(row["experiment_name"], row["benchmark_id"], row["benchmark_split"] or "unknown")].append(row)
    rows: list[dict[str, object]] = []
    for (experiment_name, benchmark_id, split_name), items in sorted(grouped.items()):
        rows.append(
            {
                "experiment": EXPERIMENT_LABELS.get(experiment_name, experiment_name),
                "benchmark": BENCHMARK_LABELS.get(benchmark_id, benchmark_id),
                "split": split_name,
                "category": BENCHMARK_CATEGORY.get(benchmark_id, "--"),
                "samples": len({item["sample_id"] for item in items}),
                "models": len({item["model_name"] for item in items}),
                "seeds": len({item["seed"] for item in items}),
                "runs": len(items),
            }
        )
    return rows


def reference_rows(records: list[dict]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for experiment_name, variants in REFERENCE_VARIANTS.items():
        benchmark_scope = PUBLIC_BENCHMARKS.keys() if experiment_name != "rq5_observability" else SUPPLEMENTARY_BENCHMARKS.keys()
        for variant_name in variants:
            items = group_records(records, experiment=experiment_name, variant=variant_name, model=REFERENCE_FORMAL_MODEL, benchmark_ids=set(benchmark_scope))
            if not items:
                continue
            agg = aggregate_run_level(items)
            ci_low, ci_high = agg["metric_ci"]
            rows.append(
                {
                    "experiment": EXPERIMENT_LABELS.get(experiment_name, experiment_name),
                    "variant": VARIANT_LABELS.get(variant_name, variant_name),
                    "primary_metric": f"{agg['metric_mean']:.2f} [{ci_low:.2f}, {ci_high:.2f}]",
                    "success": f"{agg['success_mean']:.2f}",
                    "samples": agg["n_samples"],
                    "seeds": agg["n_seeds"],
                    "runs": agg["n_runs"],
                    "tokens": f"{agg['tokens_mean']:.1f}",
                }
            )
    return rows


def cheap_aggregate_rows(records: list[dict]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for experiment_name, variants in CHEAP_AGG_VARIANTS.items():
        for variant_name in variants:
            items = []
            for model_name in CHEAP_FORMAL_MODELS:
                items.extend(group_records(records, experiment=experiment_name, variant=variant_name, model=model_name, benchmark_ids=set(PUBLIC_BENCHMARKS)))
            if not items:
                continue
            agg = aggregate_run_level(items)
            ci_low, ci_high = agg["metric_ci"]
            rows.append(
                {
                    "experiment": EXPERIMENT_LABELS.get(experiment_name, experiment_name),
                    "variant": VARIANT_LABELS.get(variant_name, variant_name),
                    "primary_metric": f"{agg['metric_mean']:.2f} [{ci_low:.2f}, {ci_high:.2f}]",
                    "success": f"{agg['success_mean']:.2f}",
                    "models": agg["n_models"],
                    "seeds": agg["n_seeds"],
                    "runs": agg["n_runs"],
                }
            )
    return rows


def paired_gap_rows(records: list[dict]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for experiment_name, baseline_name in KEY_BASELINES.items():
        full_items = group_records(records, experiment=experiment_name, variant="full_framework", benchmark_ids=set(PUBLIC_BENCHMARKS))
        baseline_items = group_records(records, experiment=experiment_name, variant=baseline_name, benchmark_ids=set(PUBLIC_BENCHMARKS))
        full_map = {(item["model_name"], item["seed"], item["sample_id"], item["benchmark_id"], item["budget"]): item for item in full_items}
        deltas: list[float] = []
        for item in baseline_items:
            key = (item["model_name"], item["seed"], item["sample_id"], item["benchmark_id"], item["budget"])
            if key in full_map:
                deltas.append(float(full_map[key]["primary_metric"]) - float(item["primary_metric"]))
        if not deltas:
            continue
        ci_low, ci_high = bootstrap_ci95(deltas)
        rows.append(
            {
                "experiment": EXPERIMENT_LABELS.get(experiment_name, experiment_name),
                "baseline": VARIANT_LABELS.get(baseline_name, baseline_name),
                "paired_gap": f"{safe_mean(deltas):.2f}",
                "bootstrap_ci95": f"[{ci_low:.2f}, {ci_high:.2f}]",
                "sign_test_p": f"{sign_test_p_value(deltas):.3f}",
                "paired_n": len(deltas),
            }
        )
    return rows


def consistency_rows(records: list[dict]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for experiment_name, baseline_name in KEY_BASELINES.items():
        wins = 0
        total = 0
        gaps: list[float] = []
        for model_name in REAL_FORMAL_MODELS:
            full_items = group_records(records, experiment=experiment_name, variant="full_framework", model=model_name, benchmark_ids=set(PUBLIC_BENCHMARKS))
            base_items = group_records(records, experiment=experiment_name, variant=baseline_name, model=model_name, benchmark_ids=set(PUBLIC_BENCHMARKS))
            if not full_items or not base_items:
                continue
            gap = safe_mean([item["primary_metric"] for item in full_items]) - safe_mean([item["primary_metric"] for item in base_items])
            gaps.append(gap)
            total += 1
            if gap > 0:
                wins += 1
        if total == 0:
            continue
        rows.append(
            {
                "experiment": EXPERIMENT_LABELS.get(experiment_name, experiment_name),
                "baseline": VARIANT_LABELS.get(baseline_name, baseline_name),
                "consistency": f"{wins}/{total}",
                "avg_gap": f"{safe_mean(gaps):.2f}",
            }
        )
    return rows


def supplementary_rows(records: list[dict]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    coverage = coverage_rows(records, set(SUPPLEMENTARY_BENCHMARKS))
    results: list[dict[str, object]] = []
    for benchmark_id in SUPPLEMENTARY_BENCHMARKS:
        for variant_name in ("full_framework", "multi_agent_plain_logs", "multi_agent_no_elephant", "single_agent_basic"):
            items = [row for row in records if row["benchmark_id"] == benchmark_id and row["variant_name"] == variant_name and row["model_name"] == REFERENCE_FORMAL_MODEL]
            if not items:
                continue
            agg = aggregate_run_level(items)
            ci_low, ci_high = agg["metric_ci"]
            results.append(
                {
                    "benchmark": SUPPLEMENTARY_BENCHMARKS[benchmark_id],
                    "variant": VARIANT_LABELS.get(variant_name, variant_name),
                    "primary_metric": f"{agg['metric_mean']:.2f} [{ci_low:.2f}, {ci_high:.2f}]",
                    "samples": agg["n_samples"],
                    "seeds": agg["n_seeds"],
                    "runs": agg["n_runs"],
                }
            )
    return coverage, results


def make_main_plot(records: list[dict]) -> None:
    experiments = [key for key in KEY_BASELINES if group_records(records, experiment=key, variant="full_framework", benchmark_ids=set(PUBLIC_BENCHMARKS))]
    if not experiments:
        return
    labels = [EXPERIMENT_LABELS[key] for key in experiments]
    full_means = [safe_mean([row["primary_metric"] for row in group_records(records, experiment=key, variant="full_framework", benchmark_ids=set(PUBLIC_BENCHMARKS))]) for key in experiments]
    base_means = [safe_mean([row["primary_metric"] for row in group_records(records, experiment=key, variant=KEY_BASELINES[key], benchmark_ids=set(PUBLIC_BENCHMARKS))]) for key in experiments]
    deltas = [full - base for full, base in zip(full_means, base_means)]
    x = list(range(len(experiments)))
    width = 0.36
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(13.4, 5.3), gridspec_kw={"width_ratios": [1.75, 1.0]})

    full_x = [i - width / 2 for i in x]
    base_x = [i + width / 2 for i in x]
    full_bars = ax_left.bar(
        full_x,
        full_means,
        width=width,
        label="Full Framework",
        color=VARIANT_COLORS["full_framework"],
        edgecolor="black",
        linewidth=1.0,
    )
    base_bars = ax_left.bar(
        base_x,
        base_means,
        width=width,
        label="Key Baseline",
        color=_rgba(PALETTE[6], 0.75),
        edgecolor="black",
        linewidth=1.0,
    )
    _style_axes(
        ax_left,
        title="Public benchmark headline comparison",
        subtitle="Absolute primary-metric means on the current benchmark-aligned slices",
        ylabel="Primary metric",
    )
    ax_left.set_xticks(x)
    ax_left.set_xticklabels(labels, rotation=10, ha="right")
    ax_left.set_ylim(0, 1.05)
    _style_legend(ax_left.legend(frameon=True, ncol=2, loc="upper left"))
    _annotate_bar_values(ax_left, full_means, full_x)
    _annotate_bar_values(ax_left, base_means, base_x, color=MUTED_COLOR)

    ax_right.axvline(0.0, color="black", linewidth=1.0)
    delta_colors = [EXPERIMENT_COLORS[experiment] for experiment in experiments]
    ax_right.barh(labels, deltas, color=delta_colors, height=0.56, edgecolor="black", linewidth=1.0)
    _style_axes(
        ax_right,
        title="Paired improvement over the key baseline",
        subtitle="Positive values favor the full framework",
        xlabel="Primary-metric gap",
        grid_axis="x",
    )
    ax_right.set_xlim(min(-0.02, min(deltas) - 0.02), max(deltas) + 0.08)
    for label, delta in zip(labels, deltas):
        ax_right.text(delta + 0.01, label, f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}", va="center", ha="left", fontsize=9, color=TEXT_COLOR)

    _save_figure(fig, "formal_main_results.png")


def make_cheap_plot(rows: list[dict[str, object]]) -> None:
    plot_rows = [row for row in rows if row["variant"] == "Full Framework"]
    if not plot_rows:
        return
    labels = [row["experiment"] for row in plot_rows]
    values = [_primary_value(row["primary_metric"]) for row in plot_rows]
    colors = [EXPERIMENT_COLORS[key] for key in KEY_BASELINES if EXPERIMENT_LABELS[key] in labels]
    fig, ax = plt.subplots(figsize=(10.0, 4.8))
    y_pos = list(range(len(labels)))
    ax.barh(y_pos, values, color=colors, height=0.56, edgecolor="black", linewidth=1.0)
    _style_axes(
        ax,
        title="Cheap real-model directional check",
        subtitle="Full-framework aggregate on low-cost real models across public benchmarks",
        xlabel="Primary metric",
        grid_axis="x",
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1.05)
    for idx, (value, row) in enumerate(zip(values, plot_rows)):
        ax.text(value + 0.02, idx, f"{value:.2f}  |  {row['models']} models", va="center", ha="left", fontsize=9, color=TEXT_COLOR)
    _save_figure(fig, "formal_cheap_model_results.png")


def make_memory_plot(records: list[dict]) -> None:
    variants = ["full_framework", "multi_agent_naive_memory", "multi_agent_no_seagull"]
    metrics = [
        ("memory_reuse_hit_rate", "Reuse hit"),
        ("long_term_recall_precision", "Recall precision"),
        ("stale_memory_injection_rate", "Stale injection"),
    ]
    if not any(group_records(records, experiment="rq3_seagull_memory", variant=variant, benchmark_ids={"locomo", "longmemeval"}) for variant in variants):
        return
    x = list(range(len(metrics)))
    fig, ax = plt.subplots(figsize=(9.8, 4.9))
    for variant in variants:
        rows = group_records(records, experiment="rq3_seagull_memory", variant=variant, benchmark_ids={"locomo", "longmemeval"})
        if not rows:
            continue
        vals = [safe_mean([float(row.get("metadata", {}).get(metric, 0.0) or 0.0) for row in rows]) for metric, _ in metrics]
        color = VARIANT_COLORS[variant]
        (line,) = ax.plot(
            x,
            vals,
            marker="o",
            markersize=7,
            linewidth=2.4,
            color=color,
            markeredgecolor="black",
            markeredgewidth=1.0,
            label=VARIANT_LABELS[variant],
        )
        _outline_artist(line, linewidth=3.8)
        ax.fill_between(x, vals, [0.0] * len(x), color=_rgba(color, 0.07), edgecolor="black", linewidth=0.8)
        for x_pos, value in zip(x, vals):
            ax.text(x_pos, value + 0.03, f"{value:.2f}", ha="center", va="bottom", fontsize=8, color=TEXT_COLOR)
    _style_axes(
        ax,
        title="RQ3 memory diagnostics",
        subtitle="Reuse, recall precision, and stale-memory injection are read jointly",
        ylabel="Metric value",
    )
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in metrics])
    ax.set_ylim(0, 1.05)
    _style_legend(ax.legend(frameon=True, ncol=3, loc="upper left"))
    _save_figure(fig, "formal_rq3_memory.png")


def make_budget_plot(records: list[dict]) -> None:
    variants = ["full_framework", "multi_agent_no_compression", "multi_agent_no_long_horizon"]
    fig, ax = plt.subplots(figsize=(9.8, 5.0))
    for variant in variants:
        rows = group_records(records, experiment="rq4_budget_robustness", variant=variant, benchmark_ids={"longbench", "infinitebench"})
        if not rows:
            continue
        by_budget: dict[int, list[float]] = defaultdict(list)
        for row in rows:
            by_budget[int(row["budget"])].append(float(row["primary_metric"]))
        xs = sorted(by_budget)
        ys = [safe_mean(by_budget[budget]) for budget in xs]
        color = VARIANT_COLORS[variant]
        (line,) = ax.plot(
            xs,
            ys,
            marker="o",
            markersize=6,
            linewidth=2.5,
            color=color,
            markeredgecolor="black",
            markeredgewidth=1.0,
            label=VARIANT_LABELS[variant],
        )
        _outline_artist(line, linewidth=4.0)
        ax.fill_between(xs, ys, [min(ys)] * len(xs), color=_rgba(color, 0.08), edgecolor="black", linewidth=0.8)
    _style_axes(
        ax,
        title="RQ4 budget degradation curves",
        subtitle="The slope under shrinking prompt budget matters more than any single budget point",
        xlabel="Prompt budget",
        ylabel="Primary metric",
    )
    ax.set_ylim(0, 1.05)
    _style_legend(ax.legend(frameon=True, loc="upper right"))
    _save_figure(fig, "formal_rq4_robustness.png")


def make_scaling_plot(records: list[dict]) -> None:
    tags = [("scaling_agents_1", 1), ("scaling_agents_2", 2), ("scaling_agents_4", 4)]
    xs, ys = [], []
    for tag, agent_count in tags:
        rows = [row for row in records if row.get("metadata", {}).get("output_tag") == tag or tag in str(row.get("metadata", {}).get("output_tag", ""))]
        if not rows:
            path_rows = [row for row in records if row["experiment_name"] == "rq1_long_horizon_tasks" and row["model_name"] == "gpt-4o-mini" and row["variant_name"] in {"single_agent_basic", "full_framework"}]
            rows = path_rows if agent_count in {1, 2, 4} else []
        if rows:
            xs.append(agent_count)
            ys.append(safe_mean([float(row["primary_metric"]) for row in rows if row["benchmark_id"] in PUBLIC_BENCHMARKS]))
    if not xs:
        return
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    (line,) = ax.plot(
        xs,
        ys,
        marker="o",
        markersize=7,
        linewidth=2.6,
        color=PALETTE[6],
        markeredgecolor="black",
        markeredgewidth=1.0,
    )
    _outline_artist(line, linewidth=4.2)
    ax.fill_between(xs, ys, [min(ys)] * len(xs), color=_rgba(PALETTE[6], 0.10), edgecolor="black", linewidth=0.8)
    _style_axes(
        ax,
        title="Supplementary scaling curve",
        subtitle="More agents help only when coordination quality scales with them",
        xlabel="Agent count",
        ylabel="Primary metric",
    )
    ax.set_ylim(0, 1.05)
    for x_pos, value in zip(xs, ys):
        ax.text(x_pos, value + 0.03, f"{value:.2f}", ha="center", va="bottom", fontsize=9, color=TEXT_COLOR)
    _save_figure(fig, "formal_scaling_curve.png")


def make_failure_plot(records: list[dict]) -> None:
    variants = ["full_framework", "multi_agent_plain_logs"]
    metrics = [
        ("trace_coverage", "Trace"),
        ("todo_consistency", "Todo"),
        ("diagnostic_accuracy", "Accuracy"),
    ]
    rows_exist = group_records(records, experiment="rq5_observability", benchmark_ids={"agentorch_failure_suite"})
    if not rows_exist:
        return
    fig, ax = plt.subplots(figsize=(8.8, 4.9))
    width = 0.3
    x = list(range(len(metrics)))
    for idx, variant in enumerate(variants):
        rows = group_records(records, experiment="rq5_observability", variant=variant, benchmark_ids={"agentorch_failure_suite"})
        vals = [safe_mean([float(row.get("metadata", {}).get(metric, 0.0) or 0.0) for row in rows]) for metric, _ in metrics]
        xs = [i + (idx - 0.5) * width for i in x]
        ax.bar(
            xs,
            vals,
            width=width,
            label=VARIANT_LABELS[variant],
            color=VARIANT_COLORS[variant],
            edgecolor="black",
            linewidth=1.0,
        )
        _annotate_bar_values(ax, vals, xs, color=TEXT_COLOR)
    _style_axes(
        ax,
        title="Supplementary observability diagnostics",
        subtitle="Trace coverage and todo consistency are more informative than saturated quality scores",
        ylabel="Metric value",
    )
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in metrics])
    ax.set_ylim(0, 1.05)
    _style_legend(ax.legend(frameon=True, ncol=2, loc="upper left"))
    _save_figure(fig, "formal_failure_breakdown.png")


def make_multiturn_plot(records: list[dict]) -> None:
    variants = ["full_framework", "multi_agent_no_elephant", "single_agent_basic"]
    benchmark_id = "agentorch_multiturn_suite"
    rows_exist = [row for row in records if row["benchmark_id"] == benchmark_id and row["model_name"] == REFERENCE_FORMAL_MODEL]
    if not rows_exist:
        return
    labels = [VARIANT_LABELS[v] for v in variants]
    values = []
    for variant in variants:
        rows = [row for row in records if row["benchmark_id"] == benchmark_id and row["variant_name"] == variant and row["model_name"] == REFERENCE_FORMAL_MODEL]
        values.append(safe_mean([float(row["primary_metric"]) for row in rows]))
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    colors = [VARIANT_COLORS[variant] for variant in variants]
    y_pos = list(range(len(labels)))
    baseline_lines = ax.hlines(y_pos, [0.0] * len(labels), values, color=colors, linewidth=5, alpha=0.95)
    _outline_artist(baseline_lines, linewidth=7.0)
    ax.scatter(values, y_pos, s=100, color=colors, edgecolor="black", linewidth=1.5, zorder=3)
    _style_axes(
        ax,
        title="Supplementary multi-turn continuity",
        subtitle="Cross-round constraint retention is treated as a continuity stress test",
        xlabel="Primary metric",
        grid_axis="x",
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1.05)
    for idx, value in enumerate(values):
        ax.text(value + 0.02, idx, f"{value:.2f}", va="center", ha="left", fontsize=9, color=TEXT_COLOR)
    _save_figure(fig, "formal_multiturn_results.png")


def make_coverage_plot(public_coverage: list[dict[str, object]]) -> None:
    if not public_coverage:
        return
    experiments = list(dict.fromkeys(row["experiment"] for row in public_coverage))
    benchmarks = list(dict.fromkeys(row["benchmark"] for row in public_coverage))
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(13.0, 5.3), gridspec_kw={"width_ratios": [1.7, 1.0]})

    for row in public_coverage:
        x_pos = benchmarks.index(row["benchmark"])
        y_pos = experiments.index(row["experiment"])
        runs = int(row["runs"])
        samples = int(row["samples"])
        models = int(row["models"])
        color = PALETTE[min(models - 1, len(PALETTE) - 1)]
        size = 120 + runs * 7
        ax_left.scatter(x_pos, y_pos, s=size, color=color, edgecolor="black", linewidth=1.3, alpha=0.95)
        ax_left.text(x_pos, y_pos, str(runs), ha="center", va="center", fontsize=8, color=TEXT_COLOR, fontweight="bold")
        ax_left.text(x_pos, y_pos + 0.26, f"{samples} samples", ha="center", va="bottom", fontsize=7.6, color=MUTED_COLOR)

    _style_axes(
        ax_left,
        title="Benchmark coverage and evidence density",
        subtitle="Bubble size encodes runs; color intensity reflects the number of real models",
        grid_axis="both",
    )
    ax_left.set_xticks(range(len(benchmarks)))
    ax_left.set_xticklabels(benchmarks, rotation=14, ha="right")
    ax_left.set_yticks(range(len(experiments)))
    ax_left.set_yticklabels(experiments)
    ax_left.set_xlim(-0.6, len(benchmarks) - 0.4)
    ax_left.set_ylim(-0.6, len(experiments) - 0.4)

    by_experiment: dict[str, int] = defaultdict(int)
    by_experiment_models: dict[str, int] = defaultdict(int)
    for row in public_coverage:
        by_experiment[row["experiment"]] += int(row["runs"])
        by_experiment_models[row["experiment"]] = max(by_experiment_models[row["experiment"]], int(row["models"]))
    totals = [by_experiment[experiment] for experiment in experiments]
    colors = [EXPERIMENT_COLORS[key] for key in KEY_BASELINES if EXPERIMENT_LABELS[key] in experiments]
    ax_right.barh(experiments, totals, color=colors, height=0.58, edgecolor="black", linewidth=1.0)
    _style_axes(
        ax_right,
        title="Runs per research question",
        subtitle="Higher-density experiments can support stronger claims",
        xlabel="Recorded runs",
        grid_axis="x",
    )
    for experiment, total in zip(experiments, totals):
        ax_right.text(total + 1.5, experiment, f"{total} runs", va="center", ha="left", fontsize=9, color=TEXT_COLOR)

    _save_figure(fig, "formal_coverage_map.png")


def make_reference_profile_plot(reference: list[dict[str, object]]) -> None:
    if not reference:
        return
    experiments = list(dict.fromkeys(row["experiment"] for row in reference))
    fig, axes = plt.subplots(3, 2, figsize=(13.2, 10.2))
    axes_flat = list(axes.flatten())

    for ax in axes_flat[len(experiments):]:
        ax.axis("off")

    for ax, experiment in zip(axes_flat, experiments):
        rows = [row for row in reference if row["experiment"] == experiment]
        labels = [str(row["variant"]) for row in rows]
        values, lowers, uppers = zip(*[_primary_value_and_ci(row["primary_metric"]) for row in rows])
        y_pos = list(range(len(labels)))
        colors = []
        for row in rows:
            variant_key = next((key for key, value in VARIANT_LABELS.items() if value == row["variant"]), None)
            colors.append(VARIANT_COLORS.get(variant_key or "", PALETTE[3]))
        ax.barh(y_pos, values, color=colors, height=0.58, edgecolor="black", linewidth=1.0)
        left_errors = [value - low for value, low in zip(values, lowers)]
        right_errors = [high - value for value, high in zip(values, uppers)]
        ax.errorbar(values, y_pos, xerr=[left_errors, right_errors], fmt="none", ecolor="black", elinewidth=1.2, capsize=3)
        _style_axes(
            ax,
            title=experiment,
            subtitle="Reference-model profile with bootstrap confidence intervals",
            xlabel="Primary metric",
            grid_axis="x",
        )
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.set_xlim(0, 1.08)
        for idx, (value, row) in enumerate(zip(values, rows)):
            ax.text(value + 0.02, idx, f"{value:.2f} | {row['tokens']} tok", va="center", ha="left", fontsize=8.5, color=TEXT_COLOR)

    _save_figure(fig, "formal_reference_profile.png")


def make_gap_consistency_plot(gaps: list[dict[str, object]], consistency: list[dict[str, object]]) -> None:
    if not gaps or not consistency:
        return
    gap_map = {row["experiment"]: row for row in gaps}
    consistency_map = {row["experiment"]: row for row in consistency}
    experiments = [row["experiment"] for row in gaps if row["experiment"] in consistency_map]
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(12.8, 5.0), gridspec_kw={"width_ratios": [1.1, 1.0]})

    gap_values = []
    gap_left_errors = []
    gap_right_errors = []
    gap_colors = []
    gap_lower_bounds = []
    gap_upper_bounds = []
    for experiment in experiments:
        row = gap_map[experiment]
        gap = float(row["paired_gap"])
        ci_text = str(row["bootstrap_ci95"]).strip()[1:-1]
        ci_low, ci_high = [float(part.strip()) for part in ci_text.split(",", 1)]
        gap_values.append(gap)
        gap_left_errors.append(gap - ci_low)
        gap_right_errors.append(ci_high - gap)
        gap_lower_bounds.append(ci_low)
        gap_upper_bounds.append(ci_high)
        experiment_key = next(key for key, value in EXPERIMENT_LABELS.items() if value == experiment)
        gap_colors.append(EXPERIMENT_COLORS[experiment_key])

    y_pos = list(range(len(experiments)))
    ax_left.barh(y_pos, gap_values, color=gap_colors, height=0.58, edgecolor="black", linewidth=1.0)
    ax_left.errorbar(gap_values, y_pos, xerr=[gap_left_errors, gap_right_errors], fmt="none", ecolor="black", elinewidth=1.3, capsize=3)
    ax_left.axvline(0.0, color="black", linewidth=1.0)
    _style_axes(
        ax_left,
        title="Paired gap vs. key baseline",
        subtitle="Bootstrap 95% confidence intervals on matched runs",
        xlabel="Primary-metric gap",
        grid_axis="x",
    )
    ax_left.set_yticks(y_pos)
    ax_left.set_yticklabels(experiments)
    ax_left.margins(y=0.10)
    ax_left.set_xlim(min(-0.06, min(gap_lower_bounds) - 0.03), max(gap_upper_bounds) + 0.18)
    for idx, row in enumerate([gap_map[experiment] for experiment in experiments]):
        place_above = idx % 2 == 0
        label_y = idx + (0.22 if place_above else -0.22)
        if gap_values[idx] >= 0:
            label_x = gap_upper_bounds[idx] + 0.02
            label_ha = "left"
        else:
            label_x = gap_lower_bounds[idx] - 0.02
            label_ha = "right"
        ax_left.text(
            label_x,
            label_y,
            f"{gap_values[idx]:.2f} | p={row['sign_test_p']}",
            va=("bottom" if place_above else "top"),
            ha=label_ha,
            fontsize=8.5,
            color=TEXT_COLOR,
            clip_on=False,
        )

    consistency_values = []
    consistency_labels = []
    for experiment in experiments:
        row = consistency_map[experiment]
        wins_text, total_text = str(row["consistency"]).split("/", 1)
        wins = int(wins_text)
        total = int(total_text)
        consistency_values.append(wins / total if total else 0.0)
        consistency_labels.append(f"{wins}/{total} | avg gap {row['avg_gap']}")
    ax_right.barh(y_pos, consistency_values, color=gap_colors, height=0.58, edgecolor="black", linewidth=1.0)
    _style_axes(
        ax_right,
        title="Cross-model directional consistency",
        subtitle="Share of real models where the full framework beats the baseline",
        xlabel="Winning-model ratio",
        grid_axis="x",
    )
    ax_right.set_yticks(y_pos)
    ax_right.set_yticklabels(experiments)
    ax_right.margins(y=0.10)
    ax_right.set_xlim(0, 1.22)
    for idx, label in enumerate(consistency_labels):
        place_above = idx % 2 == 1
        ax_right.text(
            consistency_values[idx] + 0.03,
            idx + (0.16 if place_above else -0.16),
            label,
            va=("bottom" if place_above else "top"),
            ha="left",
            fontsize=8.5,
            color=TEXT_COLOR,
            clip_on=False,
        )

    _save_figure(fig, "formal_gap_consistency.png")


def latex_table(headers: list[str], rows: list[list[object]], *, table_env: str = "table*", caption: str, alignment: str) -> str:
    def esc(value: object) -> str:
        text = str(value)
        text = text.replace("_", r"\_")
        text = text.replace("%", r"\%")
        return text

    body = "\n".join(" & ".join(esc(cell) for cell in row) + r" \\" for row in rows)
    return (
        f"\\begin{{{table_env}}}[t]\n"
        "\\centering\n"
        f"\\caption{{{caption}}}\n"
        f"\\begin{{tabular}}{{{alignment}}}\n"
        "\\toprule\n"
        + " & ".join(esc(header) for header in headers)
        + r" \\"
        + "\n\\midrule\n"
        + body
        + "\n\\bottomrule\n\\end{tabular}\n"
        f"\\end{{{table_env}}}\n"
    )


def write_paper_tables(public_coverage: list[dict[str, object]], reference: list[dict[str, object]], cheap: list[dict[str, object]],
                       gaps: list[dict[str, object]], consistency: list[dict[str, object]], supp_coverage: list[dict[str, object]],
                       supp_results: list[dict[str, object]]) -> None:
    tables = []
    tables.append(
        latex_table(
            ["Experiment", "Benchmark", "Split", "Samples", "Models", "Seeds", "Runs"],
            [[row["experiment"], row["benchmark"], row["split"], row["samples"], row["models"], row["seeds"], row["runs"]] for row in public_coverage],
            caption="Public-benchmark coverage used in the main paper. All counts refer to the currently collected benchmark-aligned local slices bundled in this repository.",
            alignment="llccccc",
        )
    )
    tables.append(
        latex_table(
            ["Experiment", "Variant", "Primary metric", "Success", "Samples", "Seeds", "Runs"],
            [[row["experiment"], row["variant"], row["primary_metric"], row["success"], row["samples"], row["seeds"], row["runs"]] for row in reference],
            caption="Reference-model results on public benchmarks where available. Values are run-level means with bootstrap 95\\% confidence intervals on the current bundled benchmark-aligned slices.",
            alignment="llccccc",
        )
    )
    tables.append(
        latex_table(
            ["Experiment", "Variant", "Primary metric", "Success", "Models", "Seeds", "Runs"],
            [[row["experiment"], row["variant"], row["primary_metric"], row["success"], row["models"], row["seeds"], row["runs"]] for row in cheap],
            caption="Cheap real-model aggregate on public benchmarks. This table tests directional portability on the current bundled slices rather than absolute performance.",
            alignment="llccccc",
        )
    )
    tables.append(
        latex_table(
            ["Experiment", "Baseline", "Paired gap", "Bootstrap 95\\% CI", "Sign test $p$", "Paired $n$"],
            [[row["experiment"], row["baseline"], row["paired_gap"], row["bootstrap_ci95"], row["sign_test_p"], row["paired_n"]] for row in gaps],
            table_env="table",
            caption="Paired public-benchmark comparison between the full framework and the key baseline for each research question.",
            alignment="llcccc",
        )
    )
    tables.append(
        latex_table(
            ["Experiment", "Baseline", "Consistency", "Avg. gap"],
            [[row["experiment"], row["baseline"], row["consistency"], row["avg_gap"]] for row in consistency],
            table_env="table",
            caption="Cross-model consistency of the full framework relative to the key baseline on public benchmarks.",
            alignment="llcc",
        )
    )
    tables.append(
        latex_table(
            ["Benchmark", "Samples", "Models", "Seeds", "Runs"],
            [[row["benchmark"], row["samples"], row["models"], row["seeds"], row["runs"]] for row in supp_coverage],
            table_env="table",
            caption="Supplementary benchmark coverage. These diagnostic suites support mechanism analysis but do not carry the main benchmark claims.",
            alignment="lcccc",
        )
    )
    tables.append(
        latex_table(
            ["Benchmark", "Variant", "Primary metric", "Samples", "Seeds", "Runs"],
            [[row["benchmark"], row["variant"], row["primary_metric"], row["samples"], row["seeds"], row["runs"]] for row in supp_results],
            caption="Supplementary diagnostic and multi-turn results for the reference model.",
            alignment="llcccc",
        )
    )
    (ASSETS_DIR / "paper_tables.tex").write_text("% Auto-generated by experiments/generate_report.py\n" + "\n".join(tables), encoding="utf-8")


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    records = load_records()

    public_coverage = coverage_rows(records, set(PUBLIC_BENCHMARKS))
    reference = reference_rows(records)
    cheap = cheap_aggregate_rows(records)
    gaps = paired_gap_rows(records)
    consistency = consistency_rows(records)
    supp_coverage, supp_results = supplementary_rows(records)

    _csv_write(ASSETS_DIR / "benchmark_protocol.csv", public_coverage, ["experiment", "benchmark", "split", "category", "samples", "models", "seeds", "runs"])
    _csv_write(ASSETS_DIR / "formal_reference_results.csv", reference, ["experiment", "variant", "primary_metric", "success", "samples", "seeds", "runs", "tokens"])
    _csv_write(ASSETS_DIR / "formal_cheap_model_results.csv", cheap, ["experiment", "variant", "primary_metric", "success", "models", "seeds", "runs"])
    _csv_write(ASSETS_DIR / "formal_ablation_results.csv", gaps, ["experiment", "baseline", "paired_gap", "bootstrap_ci95", "sign_test_p", "paired_n"])
    _csv_write(ASSETS_DIR / "formal_cross_model_consistency.csv", consistency, ["experiment", "baseline", "consistency", "avg_gap"])
    _csv_write(ASSETS_DIR / "formal_multiturn_results.csv", supp_results, ["benchmark", "variant", "primary_metric", "samples", "seeds", "runs"])

    make_main_plot(records)
    make_coverage_plot(public_coverage)
    make_reference_profile_plot(reference)
    make_cheap_plot(cheap)
    make_memory_plot(records)
    make_budget_plot(records)
    make_gap_consistency_plot(gaps, consistency)
    make_scaling_plot(records)
    make_failure_plot(records)
    make_multiturn_plot(records)

    write_paper_tables(public_coverage, reference, cheap, gaps, consistency, supp_coverage, supp_results)


if __name__ == "__main__":
    main()
