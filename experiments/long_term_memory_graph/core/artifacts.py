from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .judge import JUDGE_PROMPT
from .schemas import EXTRA_CSV_FIELDS, REQUIRED_CSV_FIELDS, ExperimentRecord


CSV_FIELDS = (*REQUIRED_CSV_FIELDS, *EXTRA_CSV_FIELDS)


def write_artifacts(
    *,
    output_dir: Path,
    suite: str,
    records: list[ExperimentRecord],
    aggregates: list[dict[str, Any]],
    manifest: dict[str, Any],
    manual_review_rows: list[dict[str, Any]] | None = None,
    second_judge_rows: list[dict[str, Any]] | None = None,
    parameter_sweep_rows: list[dict[str, Any]] | None = None,
    efficiency_payload: dict[str, Any] | None = None,
    scale_tier_payload: dict[str, Any] | None = None,
) -> dict[str, str]:
    """一次性写出论文实验需要的全部产物。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "runs_csv": output_dir / "runs.csv",
        "runs_jsonl": output_dir / "runs.jsonl",
        "report_json": output_dir / "report.json",
        "summary_md": output_dir / "summary.md",
        "latex_table": output_dir / "tables.tex",
        "metrics_table": output_dir / "mechanism_metrics.tex",
        "judge_prompt": output_dir / "judge_prompt.md",
        "bootstrap_json": output_dir / "bootstrap_summary.json",
        "manual_review_jsonl": output_dir / "manual_review_sample.jsonl",
        "second_judge_jsonl": output_dir / "second_judge_inputs.jsonl",
        "parameter_sweep_json": output_dir / "parameter_sweep.json",
        "efficiency_json": output_dir / "efficiency_report.json",
        "scale_tiers_json": output_dir / "scale_tiers.json",
        "progress_log": output_dir / "run.log",
        "progress_jsonl": output_dir / "progress.jsonl",
        "manifest": output_dir / "manifest.json",
    }
    _write_csv(paths["runs_csv"], records)
    _write_jsonl(paths["runs_jsonl"], [asdict(record) for record in records])
    _write_json(paths["report_json"], {"suite": suite, "aggregates": aggregates, "records": [asdict(record) for record in records]})
    paths["summary_md"].write_text(_summary_md(suite=suite, aggregates=aggregates, manifest=manifest), encoding="utf-8")
    paths["latex_table"].write_text(_latex_tables(suite=suite, aggregates=aggregates), encoding="utf-8")
    paths["metrics_table"].write_text(_mechanism_metric_tables(aggregates=aggregates), encoding="utf-8")
    paths["judge_prompt"].write_text(JUDGE_PROMPT, encoding="utf-8")
    _write_json(paths["bootstrap_json"], _bootstrap_payload(aggregates))
    _write_jsonl(paths["manual_review_jsonl"], manual_review_rows or [])
    _write_jsonl(paths["second_judge_jsonl"], second_judge_rows or [])
    _write_json(paths["parameter_sweep_json"], {"rows": parameter_sweep_rows or []})
    _write_json(paths["efficiency_json"], efficiency_payload or {})
    _write_json(paths["scale_tiers_json"], scale_tier_payload or {})
    manifest = dict(manifest)
    manifest["artifact_paths"] = {key: str(path.resolve()) for key, path in paths.items() if key != "manifest"}
    _write_json(paths["manifest"], manifest)
    return {key: str(path.resolve()) for key, path in paths.items()}


def _write_csv(path: Path, records: list[ExperimentRecord]) -> None:
    """写主运行 CSV，字段顺序由 schemas 中的常量统一控制。"""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def _write_json(path: Path, payload: Any) -> None:
    """写带缩进的 UTF-8 JSON。"""

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """写 JSONL，每行一条记录，便于增量审计。"""

    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _summary_md(*, suite: str, aggregates: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    """生成 Markdown 摘要，直接服务论文结果核对。"""

    lines = [
        f"# Long-Term Memory Graph Experiment: {suite}",
        "",
        f"- Run ID: `{manifest.get('run_id')}`",
        f"- Model backend: `{manifest.get('model_backend')}`",
        f"- Judge backend: `{manifest.get('judge_backend')}`",
        f"- Runs: `{manifest.get('runs')}`",
        f"- Case count: `{manifest.get('case_count')}`",
        f"- Token reference: `{manifest.get('token_reference_method')}`",
        f"- Bootstrap samples: `{manifest.get('bootstrap_samples')}`",
    ]
    if manifest.get("protocol"):
        protocol = manifest["protocol"]
        lines.extend([f"- Protocol: `{protocol.get('name')}`", f"- Reference: `{protocol.get('reference')}`"])
        layers = protocol.get("comparison_layers")
        if layers:
            lines.extend(
                [
                    f"- Core local methods: `{', '.join(layers.get('core_local', []))}`",
                    f"- Proxy extension methods: `{', '.join(layers.get('proxy_extension', []))}`",
                    f"- Literature-only methods: `{', '.join(layers.get('literature_only', []))}`",
                ]
            )
    lines.extend(_summary_design_section(suite=suite, manifest=manifest))
    lines.extend(
        [
            "",
            "## Main Results",
            "",
            "| Method | Variant | Type | Acc. | 95% CI | Capsule Recall@k | Relation Hit | Evidence | Rel. Tok. | Latency (ms) |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in _overall_rows(aggregates):
        lines.append(_overall_result_line(row))
    if suite == "comparison":
        proxy_rows = [row for row in _overall_rows(aggregates) if row.get("source_boundary") == "proxy"]
        if proxy_rows:
            lines.extend(
                [
                    "",
                    "## Proxy Extension Results",
                    "",
                    "| Method | Variant | Type | Acc. | 95% CI | Capsule Recall@k | Relation Hit | Evidence | Rel. Tok. | Latency (ms) |",
                    "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for row in proxy_rows:
                lines.append(_overall_result_line(row))
    lines.extend(
        [
            "",
            "## Evidence Boundary",
            "",
            "当前默认后端是确定性 AgentTorch 探针，用于验证实验管线、字段、产物和统计口径。",
            "正式论文数值必须改用真实模型和真实 judge 运行后，从本目录 CSV/JSONL 产物回填。",
        ]
    )
    return "\n".join(lines) + "\n"


def _latex_tables(*, suite: str, aggregates: list[dict[str, Any]]) -> str:
    """生成可粘贴到论文中的 LaTeX 结果表。"""

    caption = {
        "main": "E1 主模型实验结果表",
        "comparison": "E2 强基线对比实验结果表",
        "ablation": "E4 消融与参数敏感性实验结果表",
    }.get(suite, f"{suite} experiment table")
    lines = [
        "% Auto-generated from experiments.long_term_memory_graph artifacts.",
        "\\begin{table}[t]",
        "\\centering",
        f"\\caption{{{caption}}}",
        "\\begin{tabular}{lllrrrrrr}",
        "\\toprule",
        "Method & Variant & Type & N & Acc. & CI Low & CI High & Rel. Tok. & Eff. \\\\",
        "\\midrule",
    ]
    overall_rows = _overall_rows(aggregates)
    for row in overall_rows:
        lines.append(
            f"\\texttt{{{_tex(row['method'])}}} & \\texttt{{{_tex(row['variant'])}}} & {_tex(row['question_type'])} & "
            f"{row['count']} & {row['accuracy_pct']:.2f} & {row['accuracy_ci_low']:.2f} & {row['accuracy_ci_high']:.2f} & "
            f"{row['avg_relative_tokens']:.2f} & {row.get('token_efficiency_score', 0.0):.2f} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    return "\n".join(lines) + _design_tables_tex(suite=suite, aggregates=aggregates)


def _mechanism_metric_tables(*, aggregates: list[dict[str, Any]]) -> str:
    """生成机制指标表，突出胶囊、关系、证据和冲突治理。"""

    lines = [
        "% Auto-generated mechanism metrics table.",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{E3 结构化机制指标表}",
        "\\begin{tabular}{lllrrrrrr}",
        "\\toprule",
        "Method & Variant & Type & Capsule & Relation & Evidence & Usefulness & Stale & Conflict \\\\",
        "\\midrule",
    ]
    for row in aggregates:
        if row["question_type"] != "Overall":
            continue
        lines.append(
            f"\\texttt{{{_tex(row['method'])}}} & \\texttt{{{_tex(row['variant'])}}} & {_tex(row['question_type'])} & "
            f"{row['capsule_recall_at_k']:.2f} & {row['relation_hit_rate']:.2f} & {row['evidence_completeness']:.2f} & "
            f"{row['returned_memory_usefulness']:.2f} & {row['stale_injection_rate']:.2f} & {row['conflict_success_rate']:.2f} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    return "\n".join(lines)


def _bootstrap_payload(aggregates: list[dict[str, Any]]) -> dict[str, Any]:
    """抽出 bootstrap 置信区间，方便单独复核。"""

    return {
        "rows": [
            {
                "method": row["method"],
                "variant": row["variant"],
                "question_type": row["question_type"],
                "accuracy_ci_low": row["accuracy_ci_low"],
                "accuracy_ci_high": row["accuracy_ci_high"],
            }
            for row in aggregates
        ]
    }


def _tex(value: Any) -> str:
    """转义 LaTeX 表格中的少量特殊字符。"""

    return str(value).replace("_", "\\_").replace("%", "\\%")


def _summary_design_section(*, suite: str, manifest: dict[str, Any]) -> list[str]:
    """根据实验类型补充设计说明段。"""

    protocol = manifest.get("protocol") or {}
    lines: list[str] = []
    if suite == "comparison" and protocol:
        catalog = protocol.get("available_method_catalog") or {}
        lines.extend(["", "## Comparison Design", ""])
        lines.append(f"- Default execution methods: `{', '.join(protocol.get('default_execution_methods', []))}`")
        lines.append(f"- Selected methods: `{', '.join(protocol.get('selected_methods', []))}`")
        lines.append(f"- Available proxy extension methods: `{', '.join(protocol.get('available_proxy_extension_methods', []))}`")
        lines.append(f"- Literature reference methods: `{', '.join(protocol.get('literature_reference_methods', []))}`")
        lines.extend(
            [
                "",
                "| Method | Selected | Boundary | Official Adapter | Has Literature Ref | References |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for method, meta in catalog.items():
            if meta.get("is_core_local"):
                boundary = "core_local"
            elif meta.get("has_official_adapter"):
                boundary = "official_adapter"
            elif meta.get("is_proxy_extension"):
                boundary = "proxy_extension"
            else:
                boundary = "other"
            refs = ", ".join(meta.get("references", []))
            lines.append(
                f"| `{method}` | {'yes' if meta.get('selected') else 'no'} | `{boundary}` | "
                f"{'yes' if meta.get('has_official_adapter') else 'no'} | "
                f"{'yes' if meta.get('has_literature_reference') else 'no'} | `{refs}` |"
            )
    if suite == "ablation" and protocol:
        lines.extend(["", "## Ablation Design", ""])
        lines.append(f"- Selected variants: `{', '.join(protocol.get('selected_variants', []))}`")
        lines.append(f"- All fixed variants: `{', '.join(protocol.get('all_variants', []))}`")
        lines.extend(["", "| Variant | Description |", "| --- | --- |"])
        for variant in protocol.get("selected_variants", []):
            desc = (protocol.get("variant_descriptions") or {}).get(variant, "")
            lines.append(f"| `{variant}` | {desc} |")
        sweep_parameters = protocol.get("sweep_parameters") or {}
        if sweep_parameters:
            lines.extend(["", "## Parameter Sweep Design", "", "| Parameter | Values | Description |", "| --- | --- | --- |"])
            descriptions = protocol.get("sweep_parameter_descriptions") or {}
            for name, values in sweep_parameters.items():
                lines.append(f"| `{name}` | `{', '.join(str(value) for value in values)}` | {descriptions.get(name, '')} |")
    return lines


def _overall_rows(aggregates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只取 Overall 聚合行。"""

    return [row for row in aggregates if row["question_type"] == "Overall"]


def _overall_result_line(row: dict[str, Any]) -> str:
    """把 Overall 聚合行转成 Markdown 表格行。"""

    return (
        f"| `{row['method']}` | `{row['variant']}` | {row['question_type']} | {row['accuracy_pct']:.2f} | "
        f"[{row['accuracy_ci_low']:.2f}, {row['accuracy_ci_high']:.2f}] | {row['capsule_recall_at_k']:.2f} | "
        f"{row['relation_hit_rate']:.2f} | {row['evidence_completeness']:.2f} | {row['avg_relative_tokens']:.2f} | {row['avg_latency_ms']:.2f} |"
    )


def _design_tables_tex(*, suite: str, aggregates: list[dict[str, Any]]) -> str:
    """生成补充设计表，目前主要用于 comparison 的代理扩展结果。"""

    if suite == "comparison":
        proxy_rows = [row for row in _overall_rows(aggregates) if row.get("source_boundary") == "proxy"]
        if not proxy_rows:
            return ""
        lines = [
            "",
            "% Auto-generated proxy extension result table.",
            "\\begin{table}[t]",
            "\\centering",
            "\\caption{E2 proxy 扩展结果表}",
            "\\begin{tabular}{lllrrrrrr}",
            "\\toprule",
            "Method & Variant & Type & N & Acc. & CI Low & CI High & Rel. Tok. & Eff. \\\\",
            "\\midrule",
        ]
        for row in proxy_rows:
            lines.append(
                f"\\texttt{{{_tex(row['method'])}}} & \\texttt{{{_tex(row['variant'])}}} & {_tex(row['question_type'])} & "
                f"{row['count']} & {row['accuracy_pct']:.2f} & {row['accuracy_ci_low']:.2f} & {row['accuracy_ci_high']:.2f} & "
                f"{row['avg_relative_tokens']:.2f} & {row.get('token_efficiency_score', 0.0):.2f} \\\\"
            )
        lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
        return "\n".join(lines)
    return ""
