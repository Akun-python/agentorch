from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_graph_scale_rows(graph_scale_report: Path | None, graph_scale_root: Path | None) -> list[dict[str, object]]:
    if graph_scale_report is not None and graph_scale_report.exists():
        payload = _load_json(graph_scale_report)
        return [dict(item) for item in payload.get("rows", [])]

    rows: list[dict[str, object]] = []
    if graph_scale_root is None or not graph_scale_root.exists():
        return rows

    for scale_dir in sorted(graph_scale_root.glob("scale_*")):
        seed_report_path = scale_dir / "seed" / "seed_report.json"
        latency_report_path = scale_dir / "latency" / "recall_latency_report.json"
        if not seed_report_path.exists() or not latency_report_path.exists():
            continue
        seed_report = _load_json(seed_report_path)
        latency_report = _load_json(latency_report_path)
        scale_token = scale_dir.name.split("_", 1)[-1]
        scale_factor = int(scale_token)
        rows.append(
            {
                "scale_factor": scale_factor,
                "prefix": seed_report.get("prefix", ""),
                "node_count": latency_report["environment"]["node_count"],
                "edge_count": latency_report["environment"]["edge_count"],
                "stored_capsule_count": seed_report["stored_capsule_count"],
                "recall_mean_ms": latency_report["recall_summary"]["mean_ms"],
                "recall_p95_ms": latency_report["recall_summary"]["p95_ms"],
                "recall_qps": latency_report["recall_summary"]["throughput_qps"],
                "detail_mean_ms": latency_report["detail_summary"]["mean_ms"],
                "detail_p95_ms": latency_report["detail_summary"]["p95_ms"],
                "detail_qps": latency_report["detail_summary"]["throughput_qps"],
            }
        )
    return rows


def _latex_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "_": r"\_",
        "#": r"\#",
        "{": r"\{",
        "}": r"\}",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _format_float(value: object, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}"


def _baseline_markdown(rows: list[dict[str, object]]) -> list[str]:
    lines = [
        "## Baseline Aggregate",
        "",
        "| Baseline | recall@k | relevance | relation_hit | usefulness | stale_injection | conflict_success | latency_ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['baseline']}` | `{_format_float(row['capsule_recall@k'])}` | `{_format_float(row['subgraph_relevance'])}` | "
            f"`{_format_float(row['relation_hit_rate'])}` | `{_format_float(row['returned_memory_usefulness'])}` | "
            f"`{_format_float(row['stale_node_injection_rate'])}` | `{_format_float(row['conflict_resolution_success'])}` | "
            f"`{_format_float(row['latency_ms'])}` |"
        )
    lines.append("")
    return lines


def _stability_markdown(rows: list[dict[str, object]]) -> list[str]:
    lines = [
        "## Stability Aggregate",
        "",
        "| Baseline | recall mean [95% CI] | relevance mean [95% CI] | relation mean [95% CI] | usefulness mean [95% CI] | stale mean [95% CI] | conflict mean [95% CI] | latency mean [95% CI] |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['baseline']}` | "
            f"`{_format_float(row['capsule_recall@k_mean'])} [{_format_float(row['capsule_recall@k_ci95_low'])}, {_format_float(row['capsule_recall@k_ci95_high'])}]` | "
            f"`{_format_float(row['subgraph_relevance_mean'])} [{_format_float(row['subgraph_relevance_ci95_low'])}, {_format_float(row['subgraph_relevance_ci95_high'])}]` | "
            f"`{_format_float(row['relation_hit_rate_mean'])} [{_format_float(row['relation_hit_rate_ci95_low'])}, {_format_float(row['relation_hit_rate_ci95_high'])}]` | "
            f"`{_format_float(row['returned_memory_usefulness_mean'])} [{_format_float(row['returned_memory_usefulness_ci95_low'])}, {_format_float(row['returned_memory_usefulness_ci95_high'])}]` | "
            f"`{_format_float(row['stale_node_injection_rate_mean'])} [{_format_float(row['stale_node_injection_rate_ci95_low'])}, {_format_float(row['stale_node_injection_rate_ci95_high'])}]` | "
            f"`{_format_float(row['conflict_resolution_success_mean'])} [{_format_float(row['conflict_resolution_success_ci95_low'])}, {_format_float(row['conflict_resolution_success_ci95_high'])}]` | "
            f"`{_format_float(row['latency_ms_mean'])} [{_format_float(row['latency_ms_ci95_low'])}, {_format_float(row['latency_ms_ci95_high'])}]` |"
        )
    lines.append("")
    return lines


def _graph_scale_markdown(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["## Graph Scale Latency", "", "_No verified graph-scale latency rows were available._", ""]
    lines = [
        "## Graph Scale Latency",
        "",
        "| Scale | Nodes | Edges | Recall mean ms | Recall p95 ms | Recall qps | Detail mean ms | Detail p95 ms | Detail qps |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['scale_factor']}` | `{row['node_count']}` | `{row['edge_count']}` | "
            f"`{_format_float(row['recall_mean_ms'], 3)}` | `{_format_float(row['recall_p95_ms'], 3)}` | `{_format_float(row['recall_qps'], 3)}` | "
            f"`{_format_float(row['detail_mean_ms'], 3)}` | `{_format_float(row['detail_p95_ms'], 3)}` | `{_format_float(row['detail_qps'], 3)}` |"
        )
    lines.append("")
    return lines


def _latex_table_from_rows(caption: str, label: str, headers: list[str], rows: list[list[str]]) -> str:
    cols = "l" + "r" * (len(headers) - 1)
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        rf"\caption{{{_latex_escape(caption)}}}",
        rf"\label{{{_latex_escape(label)}}}",
        rf"\begin{{tabular}}{{{cols}}}",
        r"\hline",
        " & ".join(_latex_escape(item) for item in headers) + r" \\",
        r"\hline",
    ]
    for row in rows:
        lines.append(" & ".join(_latex_escape(item) for item in row) + r" \\")
    lines.extend([r"\hline", r"\end{tabular}", r"\end{table}", ""])
    return "\n".join(lines)


def generate_paper_tables(
    *,
    baseline_report: Path,
    stability_report: Path,
    output_dir: Path,
    graph_scale_report: Path | None = None,
    graph_scale_root: Path | None = None,
) -> dict[str, object]:
    baseline_payload = _load_json(baseline_report)
    stability_payload = _load_json(stability_report)
    graph_rows = _find_graph_scale_rows(graph_scale_report, graph_scale_root)

    baseline_rows = [dict(item) for item in baseline_payload.get("baseline_aggregates", [])]
    stability_rows = [dict(item) for item in stability_payload.get("baseline_stability", [])]
    output_dir.mkdir(parents=True, exist_ok=True)

    markdown_lines = ["# Long-Term Memory Graph Paper Tables", ""]
    markdown_lines.extend(_baseline_markdown(baseline_rows))
    markdown_lines.extend(_stability_markdown(stability_rows))
    markdown_lines.extend(_graph_scale_markdown(graph_rows))
    (output_dir / "paper_tables.md").write_text("\n".join(markdown_lines).strip() + "\n", encoding="utf-8")

    latex_sections: list[str] = []
    latex_sections.append(
        _latex_table_from_rows(
            "Long-term memory graph baseline benchmark aggregates.",
            "tab:ltmg-baseline-aggregate",
            ["Baseline", "Recall", "Relevance", "Relation", "Usefulness", "Stale", "Conflict", "Latency"],
            [
                [
                    str(row["baseline"]),
                    _format_float(row["capsule_recall@k"]),
                    _format_float(row["subgraph_relevance"]),
                    _format_float(row["relation_hit_rate"]),
                    _format_float(row["returned_memory_usefulness"]),
                    _format_float(row["stale_node_injection_rate"]),
                    _format_float(row["conflict_resolution_success"]),
                    _format_float(row["latency_ms"]),
                ]
                for row in baseline_rows
            ],
        )
    )
    latex_sections.append(
        _latex_table_from_rows(
            "Baseline stability aggregates with bootstrap 95 percent confidence intervals.",
            "tab:ltmg-stability-aggregate",
            ["Baseline", "Recall", "Relevance", "Relation", "Usefulness", "Stale", "Conflict", "Latency"],
            [
                [
                    str(row["baseline"]),
                    f"{_format_float(row['capsule_recall@k_mean'])} [{_format_float(row['capsule_recall@k_ci95_low'])}, {_format_float(row['capsule_recall@k_ci95_high'])}]",
                    f"{_format_float(row['subgraph_relevance_mean'])} [{_format_float(row['subgraph_relevance_ci95_low'])}, {_format_float(row['subgraph_relevance_ci95_high'])}]",
                    f"{_format_float(row['relation_hit_rate_mean'])} [{_format_float(row['relation_hit_rate_ci95_low'])}, {_format_float(row['relation_hit_rate_ci95_high'])}]",
                    f"{_format_float(row['returned_memory_usefulness_mean'])} [{_format_float(row['returned_memory_usefulness_ci95_low'])}, {_format_float(row['returned_memory_usefulness_ci95_high'])}]",
                    f"{_format_float(row['stale_node_injection_rate_mean'])} [{_format_float(row['stale_node_injection_rate_ci95_low'])}, {_format_float(row['stale_node_injection_rate_ci95_high'])}]",
                    f"{_format_float(row['conflict_resolution_success_mean'])} [{_format_float(row['conflict_resolution_success_ci95_low'])}, {_format_float(row['conflict_resolution_success_ci95_high'])}]",
                    f"{_format_float(row['latency_ms_mean'])} [{_format_float(row['latency_ms_ci95_low'])}, {_format_float(row['latency_ms_ci95_high'])}]",
                ]
                for row in stability_rows
            ],
        )
    )
    if graph_rows:
        latex_sections.append(
            _latex_table_from_rows(
                "Neo4j graph-scale latency summary.",
                "tab:ltmg-graph-scale-latency",
                ["Scale", "Nodes", "Edges", "RecallMean", "RecallP95", "RecallQPS", "DetailMean", "DetailP95", "DetailQPS"],
                [
                    [
                        str(row["scale_factor"]),
                        str(row["node_count"]),
                        str(row["edge_count"]),
                        _format_float(row["recall_mean_ms"], 3),
                        _format_float(row["recall_p95_ms"], 3),
                        _format_float(row["recall_qps"], 3),
                        _format_float(row["detail_mean_ms"], 3),
                        _format_float(row["detail_p95_ms"], 3),
                        _format_float(row["detail_qps"], 3),
                    ]
                    for row in graph_rows
                ],
            )
        )
    (output_dir / "paper_tables.tex").write_text("\n\n".join(latex_sections).strip() + "\n", encoding="utf-8")

    manifest = {
        "baseline_report": str(baseline_report),
        "stability_report": str(stability_report),
        "graph_scale_report": str(graph_scale_report) if graph_scale_report is not None else None,
        "graph_scale_root": str(graph_scale_root) if graph_scale_root is not None else None,
        "graph_scale_rows": len(graph_rows),
        "output_dir": str(output_dir),
        "outputs": [
            str(output_dir / "paper_tables.md"),
            str(output_dir / "paper_tables.tex"),
        ],
    }
    (output_dir / "paper_tables_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "generate-paper-tables",
        help="Generate Markdown and LaTeX paper tables from benchmark outputs.",
    )
    parser.add_argument(
        "--baseline-report",
        default=str(Path("artifacts") / "long_term_memory_graph_benchmark" / "baseline_benchmark_report.json"),
    )
    parser.add_argument(
        "--stability-report",
        default=str(Path("artifacts") / "long_term_memory_graph_stability_ci_smoke" / "baseline_stability_report.json"),
    )
    parser.add_argument(
        "--graph-scale-report",
        default=None,
    )
    parser.add_argument(
        "--graph-scale-root",
        default=str(Path("artifacts") / "long_term_memory_graph_scale_latency"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("artifacts") / "long_term_memory_graph_paper_tables"),
    )
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    graph_scale_report = Path(args.graph_scale_report) if args.graph_scale_report else None
    graph_scale_root = Path(args.graph_scale_root) if args.graph_scale_root else None
    return generate_paper_tables(
        baseline_report=Path(args.baseline_report),
        stability_report=Path(args.stability_report),
        graph_scale_report=graph_scale_report,
        graph_scale_root=graph_scale_root,
        output_dir=Path(args.output_dir),
    )


__all__ = ["build_parser", "generate_paper_tables", "run_from_args"]
