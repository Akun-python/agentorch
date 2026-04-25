from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from .benchmark_latency import run_latency_benchmark
from .seed_demo import seed_demo_dataset


def _parse_scale_factors(text: str) -> list[int]:
    values: list[int] = []
    seen: set[int] = set()
    for chunk in text.split(","):
        item = chunk.strip()
        if not item:
            continue
        value = int(item)
        if value <= 0:
            raise ValueError("scale factors must be positive integers.")
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
    if not values:
        raise ValueError("Provide at least one positive scale factor.")
    return values


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_graph_scale_latency_benchmark(
    *,
    uri: str,
    username: str,
    password: str,
    prefix: str,
    scale_factors: list[int],
    repeats: int,
    warmup_rounds: int,
    detail_limit: int,
    output_dir: Path,
    clear_prefix: bool,
    http_url: str | None = None,
    embedding_salt: str | int = 0,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scale_rows: list[dict[str, object]] = []
    per_scale_reports: list[dict[str, object]] = []

    for scale_factor in scale_factors:
        scale_prefix = f"{prefix}s{scale_factor:02d}-"
        scale_dir = output_dir / f"scale_{scale_factor:02d}"
        seed_output_dir = scale_dir / "seed"
        latency_output_dir = scale_dir / "latency"

        seed_report = seed_demo_dataset(
            uri=uri,
            username=username,
            password=password,
            prefix=scale_prefix,
            output_dir=seed_output_dir,
            clear_prefix=clear_prefix,
            http_url=http_url,
            scale_multiplier=scale_factor,
            embedding_salt=embedding_salt,
        )
        latency_report = run_latency_benchmark(
            uri=uri,
            username=username,
            password=password,
            prefix=scale_prefix,
            repeats=repeats,
            warmup_rounds=warmup_rounds,
            detail_limit=detail_limit,
            output_dir=latency_output_dir,
            scale_multiplier=scale_factor,
            embedding_salt=embedding_salt,
        )

        row = {
            "scale_factor": scale_factor,
            "prefix": scale_prefix,
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
        scale_rows.append(row)
        per_scale_reports.append(
            {
                "scale_factor": scale_factor,
                "prefix": scale_prefix,
                "seed_report_path": str(seed_output_dir / "seed_report.json"),
                "latency_report_path": str(latency_output_dir / "recall_latency_report.json"),
                "node_count": row["node_count"],
                "edge_count": row["edge_count"],
            }
        )

    report = {
        "prefix": prefix,
        "scale_factors": scale_factors,
        "repeats": repeats,
        "warmup_rounds": warmup_rounds,
        "detail_limit": detail_limit,
        "embedding_salt": str(embedding_salt),
        "rows": scale_rows,
        "per_scale_reports": per_scale_reports,
    }

    (output_dir / "graph_scale_latency_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(output_dir / "graph_scale_latency_rows.csv", scale_rows)
    markdown_lines = [
        "# Long-Term Memory Graph Scale-Latency Benchmark",
        "",
        f"- Prefix: `{prefix}`",
        f"- Scale factors: `{', '.join(str(item) for item in scale_factors)}`",
        f"- Repeats: `{repeats}`",
        f"- Warmup rounds: `{warmup_rounds}`",
        "",
        "| Scale | Nodes | Edges | Recall mean ms | Recall p95 ms | Recall qps | Detail mean ms | Detail p95 ms | Detail qps |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in scale_rows:
        markdown_lines.append(
            f"| `{row['scale_factor']}` | `{row['node_count']}` | `{row['edge_count']}` | "
            f"`{row['recall_mean_ms']}` | `{row['recall_p95_ms']}` | `{row['recall_qps']}` | "
            f"`{row['detail_mean_ms']}` | `{row['detail_p95_ms']}` | `{row['detail_qps']}` |"
        )
    (output_dir / "graph_scale_latency_report.md").write_text("\n".join(markdown_lines).strip() + "\n", encoding="utf-8")
    return report


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "benchmark-graph-scale-latency",
        help="Seed progressively larger Neo4j graphs and benchmark recall/detail latency.",
    )
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7787"))
    parser.add_argument("--username", default=os.getenv("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--http-url", default=os.getenv("NEO4J_HTTP_URL"))
    parser.add_argument("--prefix", default="graph-scale-")
    parser.add_argument("--scale-factors", default="1,2,4,8")
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--warmup-rounds", type=int, default=2)
    parser.add_argument("--detail-limit", type=int, default=3)
    parser.add_argument("--embedding-salt", default="0")
    parser.add_argument("--output-dir", default=str(Path("artifacts") / "long_term_memory_graph_scale_latency"))
    parser.add_argument(
        "--no-clear-prefix",
        action="store_true",
        help="Keep existing graph data for each generated scale prefix instead of recreating it.",
    )
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    if bool(args.username) != bool(args.password):
        raise SystemExit("Provide both Neo4j username and password, or leave both empty for an auth-disabled sandbox.")
    return run_graph_scale_latency_benchmark(
        uri=args.uri,
        username=args.username,
        password=args.password,
        prefix=args.prefix,
        scale_factors=_parse_scale_factors(args.scale_factors),
        repeats=args.repeats,
        warmup_rounds=args.warmup_rounds,
        detail_limit=args.detail_limit,
        output_dir=Path(args.output_dir),
        clear_prefix=not args.no_clear_prefix,
        http_url=args.http_url,
        embedding_salt=args.embedding_salt,
    )


__all__ = ["build_parser", "run_from_args", "run_graph_scale_latency_benchmark"]
