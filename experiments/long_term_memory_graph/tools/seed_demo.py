from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .. import GraphMemoryConfig, LongTermMemoryGraphPlugin
from ..assets import read_demo_browser_queries
from .demo_fixtures import DEFAULT_BROWSER_URL, HashedDemoEmbeddingProvider, SCENARIOS, build_demo_candidates, build_demo_request


def _load_graph_database() -> Any:
    from neo4j import GraphDatabase

    return GraphDatabase


def _build_session_kwargs(driver: Any, database: str | None) -> dict[str, str]:
    database_name = (database or "").strip()
    if not database_name:
        return {}
    try:
        protocol_version = driver.get_server_info().protocol_version
    except Exception:
        return {"database": database_name}
    if tuple(protocol_version) >= (4, 0):
        return {"database": database_name}
    return {}


def _guess_browser_url(uri: str, explicit_http_url: str | None = None) -> str:
    if explicit_http_url:
        return explicit_http_url
    parsed = urlparse(uri)
    host = parsed.hostname or "127.0.0.1"
    port_map = {
        7687: 7474,
        7787: 7574,
        7797: 7594,
    }
    http_port = port_map.get(parsed.port)
    if http_port is None:
        return DEFAULT_BROWSER_URL
    return f"http://{host}:{http_port}/browser/"


def seed_demo_dataset(
    *,
    uri: str,
    username: str,
    password: str,
    prefix: str,
    output_dir: Path,
    clear_prefix: bool,
    http_url: str | None = None,
    scale_multiplier: int = 1,
    embedding_salt: str | int = 0,
) -> dict[str, object]:
    graph_database = _load_graph_database()
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

    if clear_prefix:
        with graph_database.driver(uri, auth=(username, password)) as driver:
            with driver.session(**_build_session_kwargs(driver, config.neo4j_database)) as session:
                session.run(
                    "MATCH (n:MemoryCapsule) WHERE n.capsule_id STARTS WITH $prefix DETACH DELETE n",
                    prefix=prefix,
                ).consume()

    browser_url = _guess_browser_url(uri, explicit_http_url=http_url)
    try:
        candidates = build_demo_candidates(prefix, scale_multiplier=scale_multiplier)
        stored_ids = plugin.store_capsules(candidates)
        with graph_database.driver(uri, auth=(username, password)) as driver:
            with driver.session(**_build_session_kwargs(driver, config.neo4j_database)) as session:
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
                relation_counts = session.run(
                    """
                    MATCH (a:MemoryCapsule)-[r]->(b:MemoryCapsule)
                    WHERE a.capsule_id STARTS WITH $prefix AND b.capsule_id STARTS WITH $prefix
                    RETURN type(r) AS relation_type, count(*) AS relation_count
                    ORDER BY relation_count DESC, relation_type
                    """,
                    prefix=prefix,
                ).data()
                scenario_counts = session.run(
                    """
                    MATCH (n:MemoryCapsule)
                    WHERE n.capsule_id STARTS WITH $prefix
                    RETURN n.task_family AS task_family, count(*) AS node_count
                    ORDER BY task_family
                    """,
                    prefix=prefix,
                ).data()

        recall_samples: list[dict[str, object]] = []
        for spec in SCENARIOS[:6]:
            response = plugin.recall(build_demo_request(prefix, spec, scale_multiplier=scale_multiplier))
            recall_samples.append(
                {
                    "scenario": spec.code,
                    "query": spec.query,
                    "returned_capsules": [entry.capsule_id for entry in response.node_index],
                    "returned_titles": [entry.title for entry in response.node_index],
                    "returned_edge_count": len(response.edges),
                    "suppressed_stale_nodes": response.retrieval_report.suppressed_stale_nodes,
                    "suppressed_conflict_nodes": response.retrieval_report.suppressed_conflict_nodes,
                    "prompt_summary_head": response.prompt_summary.splitlines()[0] if response.prompt_summary else "",
                }
            )

        report = {
            "prefix": prefix,
            "browser_url": browser_url,
            "browser_queries_asset": "experiments/long_term_memory_graph/assets/demo_browser_queries.cypher",
            "stored_capsule_count": len(stored_ids),
            "scenario_count": len(SCENARIOS),
            "scale_multiplier": scale_multiplier,
            "embedding_salt": str(embedding_salt),
            "node_count": int(counts["node_count"]) if counts is not None else 0,
            "edge_count": int(counts["edge_count"]) if counts is not None else 0,
            "relation_counts": relation_counts,
            "scenario_counts": scenario_counts,
            "recall_results": recall_samples,
        }

        (output_dir / "seed_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "demo_browser_queries.cypher").write_text(read_demo_browser_queries(), encoding="utf-8")

        markdown_lines = [
            "# Long-Term Memory Graph Demo Report",
            "",
            f"- Browser URL: {browser_url}",
            f"- Prefix: `{prefix}`",
            f"- Stored capsules: `{report['stored_capsule_count']}`",
            f"- Graph nodes: `{report['node_count']}`",
            f"- Graph edges: `{report['edge_count']}`",
            "",
            "## Relation Counts",
            "",
        ]
        for item in relation_counts:
            markdown_lines.append(f"- `{item['relation_type']}`: {item['relation_count']}")
        markdown_lines.extend(["", "## Recall Samples", ""])
        for item in recall_samples:
            markdown_lines.append(f"### {item['scenario']}")
            markdown_lines.append(f"- Query: `{item['query']}`")
            markdown_lines.append(f"- Returned capsules: `{len(item['returned_capsules'])}`")
            markdown_lines.append(f"- Returned edges: `{item['returned_edge_count']}`")
            markdown_lines.append(f"- Summary head: `{item['prompt_summary_head']}`")
            markdown_lines.append(f"- Suppressed stale nodes: {', '.join(item['suppressed_stale_nodes']) or 'none'}")
            markdown_lines.append(f"- Suppressed conflict nodes: {', '.join(item['suppressed_conflict_nodes']) or 'none'}")
            markdown_lines.append("")
        (output_dir / "seed_report.md").write_text("\n".join(markdown_lines).strip() + "\n", encoding="utf-8")
        return report
    finally:
        plugin.close()


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("seed-demo", help="Seed a few hundred demo capsules into Neo4j.")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7787"))
    parser.add_argument("--username", default=os.getenv("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--http-url", default=os.getenv("NEO4J_HTTP_URL"))
    parser.add_argument("--prefix", default="viz-demo-")
    parser.add_argument("--output-dir", default=str(Path("artifacts") / "long_term_memory_graph_demo"))
    parser.add_argument("--scale-multiplier", type=int, default=1)
    parser.add_argument("--embedding-salt", default="0")
    parser.add_argument(
        "--no-clear-prefix",
        action="store_true",
        help="Keep existing demo nodes with the same prefix instead of recreating them.",
    )
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    if bool(args.username) != bool(args.password):
        raise SystemExit("Provide both Neo4j username and password, or leave both empty for an auth-disabled sandbox.")
    return seed_demo_dataset(
        uri=args.uri,
        username=args.username,
        password=args.password,
        prefix=args.prefix,
        output_dir=Path(args.output_dir),
        clear_prefix=not args.no_clear_prefix,
        http_url=args.http_url,
        scale_multiplier=args.scale_multiplier,
        embedding_salt=args.embedding_salt,
    )


__all__ = ["build_parser", "run_from_args", "seed_demo_dataset"]
