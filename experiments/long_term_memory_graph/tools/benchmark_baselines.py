from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter

from .. import GraphMemoryConfig, LongTermMemoryGraphPlugin, RecallRequest
from ..domain.entities import GraphEdgeCandidate, MemoryCapsuleDetail, SearchHit, SubgraphEdge
from ..domain.rules import build_pairwise_edges, build_temporal_edges, deduplicate_edges
from ..domain.scoring import build_fulltext_query
from ..storage.in_memory import InMemoryGraphStore
from .demo_fixtures import HashedDemoEmbeddingProvider, SCENARIOS, ScenarioSpec, build_demo_candidates

BENCHMARK_EMBEDDING_DIMENSIONS = 32
FIRST_SCREEN_NODE_LIMIT = 6
FIRST_SCREEN_EDGE_LIMIT = 12
SUMMARY_TASK_LIMIT = 2
BASELINE_ORDER = (
    "no_long_term_memory",
    "vector_memory",
    "flat_summary_memory",
    "naive_graph_memory",
    "clarks_nutcracker_graph",
)
INFORMATIVE_RELATION_TYPES = frozenset(
    {
        "TEMPORAL_NEXT",
        "EVIDENCE_SUPPORTS",
        "SCOPE_OVERLAP",
        "REVISES",
        "CONFLICTS_WITH",
    }
)
STATUS_RANK = {
    "validated": 3,
    "active": 2,
    "candidate": 1,
    "deprecated": 0,
}


@dataclass(frozen=True)
class BenchmarkCase:
    scenario_code: str
    task_family: str
    query_request: RecallRequest
    relevant_capsule_ids: set[str]
    useful_capsule_ids: set[str]
    stale_capsule_ids: set[str]
    conflict_loser_ids: set[str]
    preferred_winner_ids: set[str]
    gold_edge_keys: set[tuple[str, str, str]]
    usefulness_weights: dict[str, float]
    metric_node_limit: int
    metric_edge_limit: int


@dataclass
class BaselineRetrievalResult:
    returned_capsule_ids: list[str]
    edge_keys: set[tuple[str, str, str]]
    latency_ms: float
    prompt_summary: str


def _stage_number(node: MemoryCapsuleDetail) -> int:
    for tag in node.tags:
        if tag.startswith("stage_"):
            return int(tag.split("_", 1)[1])
    return 0


def _round_number(node: MemoryCapsuleDetail) -> int:
    for tag in node.tags:
        if tag.startswith("round_"):
            return int(tag.split("_", 1)[1])
    return 0


def _edge_key(source_id: str, relation_type: str, target_id: str) -> tuple[str, str, str]:
    return (source_id, relation_type, target_id)


def _score_hits(hits: Iterable[SearchHit]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for item in hits:
        scores[item.node.capsule_id] = max(scores.get(item.node.capsule_id, 0.0), float(item.score))
    return scores


def _summary_node_sort_key(node: MemoryCapsuleDetail) -> tuple[float, ...]:
    return (
        float(STATUS_RANK.get(node.status, 1)),
        float(_round_number(node)),
        float(_stage_number(node)),
        float(node.salience_score),
        float(node.confidence),
        node.created_at.timestamp(),
    )


def _task_summary_text(nodes: list[MemoryCapsuleDetail]) -> str:
    ranked = sorted([node for node in nodes if node.status != "deprecated"] or nodes, key=_summary_node_sort_key, reverse=True)[:8]
    sections: list[str] = []
    for node in ranked:
        sections.append(node.goal)
        sections.append(node.summary)
        sections.append(node.outcome)
        sections.extend(node.tags[-3:])
        sections.extend(node.entities[:3])
    return " ".join(item for item in sections if item)


def _similarity(left: list[float], right: list[float] | None) -> float:
    if not right:
        return 0.0
    return sum(min(a, b) for a, b in zip(left, right))


def _build_request(spec: ScenarioSpec) -> RecallRequest:
    return RecallRequest(
        query=f"{spec.query} latest stable validated reusable outcome evidence lesson learned",
        knowledge_scope=[*spec.knowledge_scope, spec.scope, "validated", "stable", "reuse"],
        tags=[*spec.tags, "latest", "stable", "reuse"],
        entities=[*spec.entities[:2], spec.owner],
    )


def _build_gold_edge_keys(nodes: list[MemoryCapsuleDetail], *, config: GraphMemoryConfig) -> set[tuple[str, str, str]]:
    ordered = sorted(nodes, key=lambda item: item.created_at)
    candidate_edges: list[GraphEdgeCandidate] = []
    for idx, node in enumerate(ordered):
        previous = ordered[idx - 1] if idx > 0 else None
        following = ordered[idx + 1] if idx + 1 < len(ordered) else None
        candidate_edges.extend(build_temporal_edges(node, previous_capsule=previous, next_capsule=following))
    for idx, node in enumerate(ordered):
        for other in ordered[idx + 1 :]:
            candidate_edges.extend(build_pairwise_edges(node, other, scope_overlap_threshold=config.scope_overlap_threshold))
    return {
        _edge_key(edge.source_capsule_id, edge.relation_type, edge.target_capsule_id)
        for edge in deduplicate_edges(candidate_edges)
        if edge.relation_type in INFORMATIVE_RELATION_TYPES
    }


def _build_benchmark_environment(
    *,
    prefix: str,
    embedding_salt: str | int = 0,
    scale_multiplier: int = 1,
) -> tuple[
    LongTermMemoryGraphPlugin,
    InMemoryGraphStore,
    HashedDemoEmbeddingProvider,
    dict[str, BenchmarkCase],
    dict[str, list[MemoryCapsuleDetail]],
    dict[str, list[float]],
]:
    provider = HashedDemoEmbeddingProvider(dimensions=BENCHMARK_EMBEDDING_DIMENSIONS, salt=embedding_salt)
    config = GraphMemoryConfig(embedding_provider=provider, embedding_dimensions=BENCHMARK_EMBEDDING_DIMENSIONS)
    store = InMemoryGraphStore()
    plugin = LongTermMemoryGraphPlugin(config=config, store=store)
    plugin.store_capsules(build_demo_candidates(prefix, scale_multiplier=scale_multiplier))

    nodes_by_task: dict[str, list[MemoryCapsuleDetail]] = defaultdict(list)
    for node in store.nodes.values():
        if node.task_family:
            nodes_by_task[node.task_family].append(node)

    task_summary_embeddings: dict[str, list[float]] = {}
    for task_family, nodes in nodes_by_task.items():
        task_summary_embeddings[task_family] = provider._embed_text(_task_summary_text(nodes))

    cases: dict[str, BenchmarkCase] = {}
    for spec in SCENARIOS:
        task_family = f"{prefix}{spec.code}"
        task_nodes = nodes_by_task[task_family]
        final_round = max(_round_number(node) for node in task_nodes)
        relevant_nodes = [
            node
            for node in task_nodes
            if _round_number(node) == final_round and _stage_number(node) in {6, 7, 8, 9, 10} and node.status != "deprecated"
        ]
        useful_nodes = [node for node in relevant_nodes if _stage_number(node) in {7, 8, 9, 10}]
        stale = {
            node.capsule_id
            for node in task_nodes
            if _round_number(node) == 1 or node.status == "deprecated"
        }
        conflict_losers = {
            node.capsule_id
            for node in task_nodes
            if _round_number(node) >= 2 and _stage_number(node) == 3
        }
        preferred_winners = {
            node.capsule_id
            for node in useful_nodes
            if _stage_number(node) in {8, 9, 10}
        }
        usefulness_weights: dict[str, float] = {}
        for node in relevant_nodes:
            stage = _stage_number(node)
            if stage == 6:
                usefulness_weights[node.capsule_id] = 0.7
            elif stage == 7:
                usefulness_weights[node.capsule_id] = 0.85
            elif stage == 8:
                usefulness_weights[node.capsule_id] = 0.95
            elif stage in {9, 10}:
                usefulness_weights[node.capsule_id] = 1.0

        cases[spec.code] = BenchmarkCase(
            scenario_code=spec.code,
            task_family=task_family,
            query_request=_build_request(spec),
            relevant_capsule_ids={node.capsule_id for node in relevant_nodes},
            useful_capsule_ids={node.capsule_id for node in useful_nodes},
            stale_capsule_ids=stale,
            conflict_loser_ids=conflict_losers,
            preferred_winner_ids=preferred_winners,
            gold_edge_keys=_build_gold_edge_keys(relevant_nodes, config=config),
            usefulness_weights=usefulness_weights,
            metric_node_limit=min(FIRST_SCREEN_NODE_LIMIT, config.max_nodes),
            metric_edge_limit=min(FIRST_SCREEN_EDGE_LIMIT, config.max_edges),
        )
    return plugin, store, provider, cases, nodes_by_task, task_summary_embeddings


def _run_no_memory(case: BenchmarkCase) -> BaselineRetrievalResult:
    start = perf_counter()
    latency_ms = (perf_counter() - start) * 1000.0
    return BaselineRetrievalResult([], set(), latency_ms, "No long-term memory returned.")


def _run_vector_memory(
    case: BenchmarkCase,
    *,
    store: InMemoryGraphStore,
    provider: HashedDemoEmbeddingProvider,
    max_nodes: int,
) -> BaselineRetrievalResult:
    start = perf_counter()
    query_text = build_fulltext_query(case.query_request) or case.query_request.query
    query_embedding = provider._embed_text(query_text)
    hits = store.query_vector(query_embedding, limit=max_nodes)
    returned_ids = [item.node.capsule_id for item in hits[:max_nodes]]
    latency_ms = (perf_counter() - start) * 1000.0
    return BaselineRetrievalResult(returned_ids, set(), latency_ms, "Vector-only memory retrieval.")


def _run_flat_summary_memory(
    case: BenchmarkCase,
    *,
    task_nodes: dict[str, list[MemoryCapsuleDetail]],
    task_summary_embeddings: dict[str, list[float]],
    provider: HashedDemoEmbeddingProvider,
    max_nodes: int,
) -> BaselineRetrievalResult:
    start = perf_counter()
    query_text = build_fulltext_query(case.query_request) or case.query_request.query
    query_embedding = provider._embed_text(query_text)
    lexical_tokens = set(query_text.lower().split())
    summary_scores: list[tuple[str, float]] = []
    for task_family, embedding in task_summary_embeddings.items():
        text = _task_summary_text(task_nodes[task_family]).lower()
        lexical_score = float(sum(1 for token in lexical_tokens if token and token in text))
        semantic_score = _similarity(query_embedding, embedding)
        summary_scores.append((task_family, semantic_score + lexical_score))
    summary_scores.sort(key=lambda item: item[1], reverse=True)

    selected: list[tuple[str, float]] = []
    for task_family, task_score in summary_scores[:SUMMARY_TASK_LIMIT]:
        for node in task_nodes[task_family]:
            if node.status == "deprecated":
                continue
            node_score = (
                task_score * 100.0
                + float(STATUS_RANK.get(node.status, 1)) * 6.0
                + float(_round_number(node)) * 3.0
                + float(_stage_number(node)) * 0.8
                + float(node.salience_score)
                + float(node.confidence)
            )
            selected.append((node.capsule_id, node_score))
    selected_ids = [capsule_id for capsule_id, _ in sorted(selected, key=lambda item: item[1], reverse=True)[:max_nodes]]
    latency_ms = (perf_counter() - start) * 1000.0
    return BaselineRetrievalResult(selected_ids, set(), latency_ms, "Flat summary memory retrieval.")


def _run_naive_graph_memory(
    case: BenchmarkCase,
    *,
    store: InMemoryGraphStore,
    provider: HashedDemoEmbeddingProvider,
    top_candidates: int,
    top_seeds: int,
    max_nodes: int,
) -> BaselineRetrievalResult:
    start = perf_counter()
    lexical_query = build_fulltext_query(case.query_request)
    query_embedding = provider._embed_text(lexical_query or case.query_request.query)
    semantic_scores = _score_hits(store.query_vector(query_embedding, limit=top_candidates))
    lexical_scores = _score_hits(store.query_fulltext(lexical_query, limit=top_candidates))
    merged_ids = set(semantic_scores) | set(lexical_scores)
    rank_scores = {
        capsule_id: semantic_scores.get(capsule_id, 0.0) + lexical_scores.get(capsule_id, 0.0)
        for capsule_id in merged_ids
    }
    ranked_ids = [capsule_id for capsule_id, _ in sorted(rank_scores.items(), key=lambda item: item[1], reverse=True)[:top_candidates]]
    seed_ids = ranked_ids[:top_seeds]
    expanded_nodes, expanded_edges = store.fetch_one_hop_subgraph(seed_ids, edge_limit=case.metric_edge_limit * 3)
    expanded_lookup = {node.capsule_id: node for node in expanded_nodes}
    score_map = dict(rank_scores)
    for edge in expanded_edges:
        propagation_weight = 0.75 if edge.relation_type in INFORMATIVE_RELATION_TYPES else 0.55
        if edge.source_capsule_id in score_map:
            propagated = score_map[edge.source_capsule_id] * propagation_weight + edge.score
            score_map[edge.target_capsule_id] = max(score_map.get(edge.target_capsule_id, 0.0), propagated)
        if edge.target_capsule_id in score_map:
            propagated = score_map[edge.target_capsule_id] * propagation_weight + edge.score
            score_map[edge.source_capsule_id] = max(score_map.get(edge.source_capsule_id, 0.0), propagated)
    final_nodes = sorted(expanded_lookup.values(), key=lambda item: score_map.get(item.capsule_id, 0.0), reverse=True)[:max_nodes]
    final_ids = {node.capsule_id for node in final_nodes}
    selected_edge_keys: list[tuple[str, str, str]] = []
    for edge in sorted(expanded_edges, key=lambda item: float(item.score), reverse=True):
        if edge.source_capsule_id in final_ids and edge.target_capsule_id in final_ids:
            selected_edge_keys.append(_edge_key(edge.source_capsule_id, edge.relation_type, edge.target_capsule_id))
        if len(selected_edge_keys) >= case.metric_edge_limit:
            break
    latency_ms = (perf_counter() - start) * 1000.0
    return BaselineRetrievalResult([node.capsule_id for node in final_nodes], set(selected_edge_keys), latency_ms, "Naive graph memory retrieval.")


def _run_nutcracker_graph(case: BenchmarkCase, *, plugin: LongTermMemoryGraphPlugin) -> BaselineRetrievalResult:
    start = perf_counter()
    response = plugin.recall(case.query_request)
    latency_ms = (perf_counter() - start) * 1000.0
    id_by_index = {entry.index: entry.capsule_id for entry in response.node_index}
    ordered_edge_keys: list[tuple[str, str, str]] = []
    for edge in response.edges[: case.metric_edge_limit]:
        source_id = id_by_index.get(edge.source_index)
        target_id = id_by_index.get(edge.target_index)
        if source_id and target_id:
            ordered_edge_keys.append(_edge_key(source_id, edge.relation_type, target_id))
    return BaselineRetrievalResult(
        [entry.capsule_id for entry in response.node_index],
        set(ordered_edge_keys),
        latency_ms,
        response.prompt_summary.splitlines()[0] if response.prompt_summary else "",
    )


def _metric_average(values: list[float]) -> float:
    return round(mean(values), 4) if values else 0.0


def _evaluate_case(case: BenchmarkCase, result: BaselineRetrievalResult) -> dict[str, float | int | str]:
    visible_nodes = result.returned_capsule_ids[: case.metric_node_limit]
    visible_set = set(visible_nodes)
    useful_hits = visible_set.intersection(case.useful_capsule_ids)
    relevant_hits = visible_set.intersection(case.relevant_capsule_ids)
    stale_hits = visible_set.intersection(case.stale_capsule_ids)
    loser_hits = visible_set.intersection(case.conflict_loser_ids)
    winner_hits = visible_set.intersection(case.preferred_winner_ids)

    usefulness_total = sum(case.usefulness_weights.get(capsule_id, 0.0) for capsule_id in visible_nodes)
    usefulness_denominator = max(1, len(visible_nodes))
    relation_hits = len(result.edge_keys.intersection(case.gold_edge_keys))
    relation_denominator = len(case.gold_edge_keys) or 1
    conflict_success = 1.0 if (winner_hits and not loser_hits) else 0.0

    return {
        "scenario": case.scenario_code,
        "evaluation_top_k": case.metric_node_limit,
        "evaluation_edge_k": case.metric_edge_limit,
        "raw_returned_nodes": len(result.returned_capsule_ids),
        "returned_nodes": len(visible_nodes),
        "returned_edges": len(result.edge_keys),
        "capsule_recall@k": round(len(useful_hits) / max(1, len(case.useful_capsule_ids)), 4),
        "subgraph_relevance": round(len(relevant_hits) / max(1, len(visible_nodes)), 4) if visible_nodes else 0.0,
        "relation_hit_rate": round(relation_hits / relation_denominator, 4),
        "returned_memory_usefulness": round(usefulness_total / usefulness_denominator, 4) if visible_nodes else 0.0,
        "stale_node_injection_rate": round(len(stale_hits) / max(1, len(visible_nodes)), 4) if visible_nodes else 0.0,
        "conflict_resolution_success": conflict_success,
        "latency_ms": round(result.latency_ms, 4),
        "summary_head": result.prompt_summary,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_baseline_benchmark(
    *,
    prefix: str = "benchmark-",
    output_dir: Path,
    case_limit: int | None = None,
    embedding_salt: str | int = 0,
    scale_multiplier: int = 1,
) -> dict[str, object]:
    plugin, store, provider, cases, task_nodes, task_summary_embeddings = _build_benchmark_environment(
        prefix=prefix,
        embedding_salt=embedding_salt,
        scale_multiplier=scale_multiplier,
    )
    try:
        ordered_cases = list(cases.values())[:case_limit] if case_limit is not None else list(cases.values())
        baseline_runs: dict[str, list[dict[str, float | int | str]]] = defaultdict(list)
        for case in ordered_cases:
            runs = {
                "no_long_term_memory": _run_no_memory(case),
                "vector_memory": _run_vector_memory(case, store=store, provider=provider, max_nodes=plugin.config.max_nodes),
                "flat_summary_memory": _run_flat_summary_memory(
                    case,
                    task_nodes=task_nodes,
                    task_summary_embeddings=task_summary_embeddings,
                    provider=provider,
                    max_nodes=plugin.config.max_nodes,
                ),
                "naive_graph_memory": _run_naive_graph_memory(
                    case,
                    store=store,
                    provider=provider,
                    top_candidates=plugin.config.top_candidates,
                    top_seeds=plugin.config.top_seeds,
                    max_nodes=plugin.config.max_nodes,
                ),
                "clarks_nutcracker_graph": _run_nutcracker_graph(case, plugin=plugin),
            }
            for baseline_name in BASELINE_ORDER:
                baseline_runs[baseline_name].append(_evaluate_case(case, runs[baseline_name]))

        metric_names = [
            "capsule_recall@k",
            "subgraph_relevance",
            "relation_hit_rate",
            "returned_memory_usefulness",
            "stale_node_injection_rate",
            "conflict_resolution_success",
            "latency_ms",
        ]
        aggregates: list[dict[str, object]] = []
        for baseline_name in BASELINE_ORDER:
            rows = baseline_runs[baseline_name]
            aggregates.append(
                {
                    "baseline": baseline_name,
                    **{
                        metric: _metric_average([float(row[metric]) for row in rows])
                        for metric in metric_names
                    },
                    "avg_returned_nodes": round(mean(int(row["returned_nodes"]) for row in rows), 4) if rows else 0.0,
                    "avg_raw_returned_nodes": round(mean(int(row["raw_returned_nodes"]) for row in rows), 4) if rows else 0.0,
                    "avg_returned_edges": round(mean(int(row["returned_edges"]) for row in rows), 4) if rows else 0.0,
                }
            )

        case_rows = [
            {"baseline": baseline_name, **row}
            for baseline_name in BASELINE_ORDER
            for row in baseline_runs[baseline_name]
        ]
        report = {
            "prefix": prefix,
            "case_count": len(ordered_cases),
            "metrics": metric_names,
            "evaluation_config": {
                "embedding_dimensions": BENCHMARK_EMBEDDING_DIMENSIONS,
                "embedding_salt": str(embedding_salt),
                "scale_multiplier": scale_multiplier,
                "node_top_k": ordered_cases[0].metric_node_limit if ordered_cases else FIRST_SCREEN_NODE_LIMIT,
                "edge_top_k": ordered_cases[0].metric_edge_limit if ordered_cases else FIRST_SCREEN_EDGE_LIMIT,
                "summary_task_limit": SUMMARY_TASK_LIMIT,
                "top_candidates": plugin.config.top_candidates,
                "top_seeds": plugin.config.top_seeds,
                "max_nodes": plugin.config.max_nodes,
                "max_edges": plugin.config.max_edges,
            },
            "baseline_aggregates": aggregates,
            "case_rows": case_rows,
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "baseline_benchmark_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_csv(output_dir / "baseline_benchmark_aggregates.csv", aggregates)
        _write_csv(output_dir / "baseline_benchmark_case_rows.csv", case_rows)

        markdown_lines = [
            "# Long-Term Memory Graph Baseline Benchmark",
            "",
            f"- Prefix: `{prefix}`",
            f"- Cases: `{len(ordered_cases)}`",
            f"- First-screen node budget: `{report['evaluation_config']['node_top_k']}`",
            f"- First-screen edge budget: `{report['evaluation_config']['edge_top_k']}`",
            "",
            "## Aggregate Comparison",
            "",
            "| Baseline | recall@k | relevance | relation_hit | usefulness | stale_injection | conflict_success | latency_ms |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in aggregates:
            markdown_lines.append(
                f"| `{row['baseline']}` | `{row['capsule_recall@k']}` | `{row['subgraph_relevance']}` | "
                f"`{row['relation_hit_rate']}` | `{row['returned_memory_usefulness']}` | "
                f"`{row['stale_node_injection_rate']}` | `{row['conflict_resolution_success']}` | `{row['latency_ms']}` |"
            )
        markdown_lines.extend(["", "## Case Rows", ""])
        for baseline_name in BASELINE_ORDER:
            markdown_lines.append(f"### {baseline_name}")
            for row in baseline_runs[baseline_name]:
                markdown_lines.append(
                    f"- `{row['scenario']}`: recall@k `{row['capsule_recall@k']}`, relevance `{row['subgraph_relevance']}`, "
                    f"relation_hit `{row['relation_hit_rate']}`, usefulness `{row['returned_memory_usefulness']}`, "
                    f"stale `{row['stale_node_injection_rate']}`, conflict `{row['conflict_resolution_success']}`, "
                    f"latency `{row['latency_ms']}` ms"
                )
            markdown_lines.append("")
        (output_dir / "baseline_benchmark_report.md").write_text("\n".join(markdown_lines).strip() + "\n", encoding="utf-8")
        return report
    finally:
        plugin.close()


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("benchmark-baselines", help="Run long-term memory quality benchmark against strong baselines.")
    parser.add_argument("--prefix", default="benchmark-")
    parser.add_argument("--output-dir", default=str(Path("artifacts") / "long_term_memory_graph_benchmark"))
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--embedding-salt", default="0")
    parser.add_argument("--scale-multiplier", type=int, default=1)
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    return run_baseline_benchmark(
        prefix=args.prefix,
        output_dir=Path(args.output_dir),
        case_limit=args.case_limit,
        embedding_salt=args.embedding_salt,
        scale_multiplier=args.scale_multiplier,
    )


__all__ = ["build_parser", "run_baseline_benchmark", "run_from_args"]
