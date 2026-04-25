from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any

from .. import GraphMemoryConfig, LongTermMemoryGraphPlugin
from .demo_fixtures import HashedDemoEmbeddingProvider, SCENARIOS, build_demo_request


def _load_graph_database() -> Any:
    from neo4j import GraphDatabase

    return GraphDatabase


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def _summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "count": float(len(ordered)),
        "mean_ms": round(mean(ordered), 3) if ordered else 0.0,
        "median_ms": round(median(ordered), 3) if ordered else 0.0,
        "p95_ms": round(_percentile(ordered, 0.95), 3) if ordered else 0.0,
        "min_ms": round(ordered[0], 3) if ordered else 0.0,
        "max_ms": round(ordered[-1], 3) if ordered else 0.0,
    }


def _load_graph_snapshot(uri: str, username: str, password: str, prefix: str) -> dict[str, object]:
    graph_database = _load_graph_database()
    with graph_database.driver(uri, auth=(username, password)) as driver:
        with driver.session() as session:
            component = session.run(
                "CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] AS version, edition LIMIT 1"
            ).single()
            counts = session.run(
                """
                MATCH (n:MemoryCapsule)
                WHERE n.capsule_id STARTS WITH $prefix
                OPTIONAL MATCH (n)-[r]->(m:MemoryCapsule)
                WHERE m.capsule_id STARTS WITH $prefix
                RETURN count(DISTINCT n) AS node_count, count(DISTINCT r) AS edge_count
                """,
                prefix=prefix,
            ).single()
    if component is None or counts is None:
        raise RuntimeError("Failed to inspect the current Neo4j graph snapshot.")
    return {
        "neo4j_component": component["name"],
        "neo4j_version": component["version"],
        "neo4j_edition": component["edition"],
        "node_count": int(counts["node_count"]),
        "edge_count": int(counts["edge_count"]),
    }


def run_latency_benchmark(
    *,
    uri: str,
    username: str,
    password: str,
    prefix: str,
    repeats: int,
    warmup_rounds: int,
    detail_limit: int,
    output_dir: Path,
    scale_multiplier: int = 1,
    embedding_salt: str | int = 0,
) -> dict[str, object]:
    graph_snapshot = _load_graph_snapshot(uri=uri, username=username, password=password, prefix=prefix)
    if graph_snapshot["node_count"] <= 0:
        raise RuntimeError(
            f"No demo graph nodes were found for prefix '{prefix}'. Seed the demo graph before running the latency benchmark."
        )

    provider = HashedDemoEmbeddingProvider(dimensions=3, salt=embedding_salt)
    config = GraphMemoryConfig(
        neo4j_uri=uri,
        neo4j_username=username,
        neo4j_password=password,
        embedding_provider=provider,
        embedding_dimensions=3,
    )
    plugin = LongTermMemoryGraphPlugin(config=config)
    output_dir.mkdir(parents=True, exist_ok=True)

    recall_latencies: list[float] = []
    detail_latencies: list[float] = []
    per_scenario: dict[str, dict[str, list[float] | list[int]]] = {
        spec.code: {"recall_ms": [], "detail_ms": [], "returned_nodes": [], "returned_edges": []}
        for spec in SCENARIOS
    }

    try:
        for _ in range(warmup_rounds):
            for spec in SCENARIOS:
                response = plugin.recall(build_demo_request(prefix, spec, scale_multiplier=scale_multiplier))
                detail_ids = [entry.capsule_id for entry in response.node_index[:detail_limit]]
                plugin.fetch_capsule_details(detail_ids)

        for _ in range(repeats):
            for spec in SCENARIOS:
                request = build_demo_request(prefix, spec, scale_multiplier=scale_multiplier)
                recall_start = perf_counter()
                response = plugin.recall(request)
                recall_ms = (perf_counter() - recall_start) * 1000.0
                detail_ids = [entry.capsule_id for entry in response.node_index[:detail_limit]]
                detail_start = perf_counter()
                plugin.fetch_capsule_details(detail_ids)
                detail_ms = (perf_counter() - detail_start) * 1000.0
                recall_latencies.append(recall_ms)
                detail_latencies.append(detail_ms)
                per_scenario[spec.code]["recall_ms"].append(recall_ms)
                per_scenario[spec.code]["detail_ms"].append(detail_ms)
                per_scenario[spec.code]["returned_nodes"].append(len(response.node_index))
                per_scenario[spec.code]["returned_edges"].append(len(response.edges))
    finally:
        plugin.close()

    scenario_rows: list[dict[str, object]] = []
    for spec in SCENARIOS:
        bucket = per_scenario[spec.code]
        scenario_rows.append(
            {
                "scenario": spec.code,
                "recall": _summarize([float(item) for item in bucket["recall_ms"]]),
                "detail": _summarize([float(item) for item in bucket["detail_ms"]]),
                "avg_returned_nodes": round(mean(bucket["returned_nodes"]), 3) if bucket["returned_nodes"] else 0.0,
                "avg_returned_edges": round(mean(bucket["returned_edges"]), 3) if bucket["returned_edges"] else 0.0,
            }
        )

    recall_summary = _summarize(recall_latencies)
    detail_summary = _summarize(detail_latencies)
    report = {
        "prefix": prefix,
        "environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            **graph_snapshot,
        },
        "benchmark_config": {
            "scenario_count": len(SCENARIOS),
            "warmup_rounds": warmup_rounds,
            "measured_rounds": repeats,
            "measured_recalls": len(recall_latencies),
            "detail_limit": detail_limit,
            "scale_multiplier": scale_multiplier,
            "embedding_salt": str(embedding_salt),
            "top_candidates": config.top_candidates,
            "top_seeds": config.top_seeds,
            "max_nodes": config.max_nodes,
            "max_edges": config.max_edges,
        },
        "recall_summary": {
            **recall_summary,
            "throughput_qps": round(1000.0 / recall_summary["mean_ms"], 3) if recall_summary["mean_ms"] else 0.0,
        },
        "detail_summary": {
            **detail_summary,
            "throughput_qps": round(1000.0 / detail_summary["mean_ms"], 3) if detail_summary["mean_ms"] else 0.0,
        },
        "scenario_rows": scenario_rows,
    }

    (output_dir / "recall_latency_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_lines = [
        "# Long-Term Memory Graph Recall Latency Report",
        "",
        f"- Prefix: `{prefix}`",
        f"- Neo4j: `{graph_snapshot['neo4j_component']} {graph_snapshot['neo4j_version']} ({graph_snapshot['neo4j_edition']})`",
        f"- Graph size: `{graph_snapshot['node_count']}` nodes / `{graph_snapshot['edge_count']}` edges",
        f"- Warmup rounds: `{warmup_rounds}`",
        f"- Measured recalls: `{len(recall_latencies)}`",
        "",
        "## Overall",
        "",
        f"- `recall()` mean / median / p95: `{report['recall_summary']['mean_ms']}` / `{report['recall_summary']['median_ms']}` / `{report['recall_summary']['p95_ms']}` ms",
        f"- `recall()` throughput: `{report['recall_summary']['throughput_qps']}` qps",
        f"- `fetch_capsule_details()` mean / median / p95: `{report['detail_summary']['mean_ms']}` / `{report['detail_summary']['median_ms']}` / `{report['detail_summary']['p95_ms']}` ms",
        f"- `fetch_capsule_details()` throughput: `{report['detail_summary']['throughput_qps']}` qps",
        "",
        "## Per Scenario",
        "",
    ]
    for row in scenario_rows:
        markdown_lines.append(
            f"- `{row['scenario']}`: recall mean `{row['recall']['mean_ms']}` ms, detail mean `{row['detail']['mean_ms']}` ms, avg nodes `{row['avg_returned_nodes']}`, avg edges `{row['avg_returned_edges']}`"
        )
    (output_dir / "recall_latency_report.md").write_text("\n".join(markdown_lines).strip() + "\n", encoding="utf-8")
    return report


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("benchmark-latency", help="Benchmark Neo4j-backed recall latency.")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7787"))
    parser.add_argument("--username", default=os.getenv("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--prefix", default="viz-demo-")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--warmup-rounds", type=int, default=2)
    parser.add_argument("--detail-limit", type=int, default=3)
    parser.add_argument("--scale-multiplier", type=int, default=1)
    parser.add_argument("--embedding-salt", default="0")
    parser.add_argument("--output-dir", default="artifacts/long_term_memory_graph_demo")
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    if bool(args.username) != bool(args.password):
        raise SystemExit("Provide both Neo4j username and password, or leave both empty for an auth-disabled sandbox.")
    return run_latency_benchmark(
        uri=args.uri,
        username=args.username,
        password=args.password,
        prefix=args.prefix,
        repeats=args.repeats,
        warmup_rounds=args.warmup_rounds,
        detail_limit=args.detail_limit,
        output_dir=Path(args.output_dir),
        scale_multiplier=args.scale_multiplier,
        embedding_salt=args.embedding_salt,
    )


__all__ = ["build_parser", "run_from_args", "run_latency_benchmark"]
