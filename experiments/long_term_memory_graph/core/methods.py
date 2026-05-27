from __future__ import annotations

import json
from time import perf_counter

from ..api.config import GraphMemoryConfig
from ..api.models import RecallRequest
from ..api.plugin import LongTermMemoryGraphPlugin
from ..domain.scoring import build_fulltext_query
from ..domain.utils import run_async
from ..研究对比试验.对比模型 import OfficialBaselineRegistry
from ..storage.in_memory import InMemoryGraphStore
from .embeddings import DeterministicEmbeddingProvider
from .env_config import resolve_embedding_env
from .live_embeddings import LiveOpenAIEmbeddingProvider
from .schemas import ExperimentCase, RetrievalResult


# 文献基线没有统一官方 SDK 时，用轻量代理策略保持实验矩阵可跑。
PAPER_PROXY_PROFILES: dict[str, tuple[str, str]] = {
    "light_rag_memory": ("light_graph", "LightRAG-style proxy used hybrid lexical-semantic retrieval plus light graph expansion."),
    "hippo_rag2_memory": ("episodic_graph", "HippoRAG 2-style proxy emphasized episodic paths and temporal/revision evidence."),
    "openai_memory": ("recent_high_confidence", "OpenAI-memory proxy returned recent high-confidence memories as session context."),
    "langmem_memory": ("session_namespace", "LangMem-style proxy prioritized task/thread namespaces before answer generation."),
    "zep_memory": ("entity_graph", "Zep-style proxy returned entity-centered graph memories and relation evidence."),
    "amem_memory": ("adaptive_salience", "A-Mem-style proxy emphasized salient active memories selected from the current query."),
    "mem0_memory": ("fact_only", "Mem0-style proxy returned compact fact-like memories without graph governance."),
    "mem0_graph_memory": ("entity_graph", "Mem0g-style proxy expanded retrieved memories through graph relations."),
    "mirix_memory": ("episodic_graph", "MIRIX-style proxy combined episodic state, temporal anchors, and graph relations."),
    "memobase_memory": ("profile_event", "Memobase-style proxy returned profile and event memories with compact summaries."),
    "memu_memory": ("compact_profile", "MemU-style proxy returned a compact personalized memory context."),
    "memos_memory": ("hierarchical_os", "MemOS-style proxy used a hierarchical memory schedule over semantic and episodic candidates."),
}


class ExperimentMethodRunner:
    """把不同记忆方法统一成 RetrievalResult 的执行器。"""

    def __init__(
        self,
        *,
        top_candidates: int,
        top_seeds: int,
        max_nodes: int,
        max_edges: int,
        seed: int = 0,
        embedding_backend: str = "deterministic",
        embedding_model: str | None = None,
        embedding_dimensions: int | None = None,
    ) -> None:
        self.top_candidates = top_candidates
        self.top_seeds = top_seeds
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.seed = seed
        self.embedding_backend = embedding_backend
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.official_registry = OfficialBaselineRegistry(seed=seed)
        self._last_embedding_request_count = 0
        self._last_embedding_text_count = 0
        self._last_embedding_latency_ms = 0.0

    def run(self, case: ExperimentCase, *, method: str, variant: str = "full") -> RetrievalResult:
        """按方法名分发到官方基线、代理基线或本文图谱机制。"""

        return self.run_with_policy(case, method=method, variant=variant, strict_official_baselines=False)

    def run_with_policy(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str = "full",
        strict_official_baselines: bool = False,
    ) -> RetrievalResult:
        """按策略运行方法；严格模式下禁止官方 baseline 回退到 proxy。"""

        self._last_embedding_request_count = 0
        self._last_embedding_text_count = 0
        self._last_embedding_latency_ms = 0.0
        if method == "no_long_term_memory":
            return RetrievalResult(method=method, variant=variant, prompt_summary="No long-term memory was provided.")
        official_result = self.official_registry.maybe_run(
            case,
            method=method,
            variant=variant,
            max_nodes=self.max_nodes,
            strict=strict_official_baselines,
        )
        if official_result is not None:
            return official_result
        plugin, store, provider = self._build_graph(case, variant=variant)
        if method == "rag_chunk_memory":
            return self._rag_chunk_memory(case, method=method, variant=variant, store=store, provider=provider)
        if method == "vector_memory":
            return self._vector_memory(case, method=method, variant=variant, store=store, provider=provider)
        if method == "flat_summary_memory":
            return self._flat_summary_memory(case, method=method, variant=variant, store=store)
        if method == "naive_graph_memory":
            return self._naive_graph_memory(case, method=method, variant=variant, store=store, provider=provider)
        if method == "graph_rag_memory":
            return self._graph_rag_memory(case, method=method, variant=variant, store=store, provider=provider)
        if method == "mem0_zep_memory":
            return self._mem0_zep_memory(case, method=method, variant=variant, store=store)
        if method == "hypergraph_proxy":
            return self._hypergraph_proxy(case, method=method, variant=variant, store=store)
        if method == "hypergraph_rag_memory":
            return self._hypergraph_proxy(case, method=method, variant=variant, store=store)
        if method in PAPER_PROXY_PROFILES:
            return self._paper_proxy_memory(case, method=method, variant=variant, store=store, provider=provider)
        if method == "clarks_nutcracker_graph":
            if variant == "graph_no_policy":
                return self._naive_graph_memory(case, method=method, variant=variant, store=store, provider=provider)
            return self._clarks_graph(case, method=method, variant=variant, plugin=plugin)
        raise ValueError(f"Unsupported long-term memory method: {method}")

    def _config_for_variant(self, variant: str, provider: DeterministicEmbeddingProvider) -> GraphMemoryConfig:
        """根据消融 variant 生成对应的图谱配置。"""

        kwargs = {
            "embedding_provider": provider,
            "embedding_dimensions": provider.dimensions,
            "top_candidates": self.top_candidates,
            "top_seeds": self.top_seeds,
            "max_nodes": self.max_nodes,
            "max_edges": self.max_edges,
            "auto_create_schema": False,
            "stale_after_days": 3650,
        }
        if variant == "wo_scene_match":
            kwargs["scene_match_weight"] = 0.0
        elif variant == "wo_stale_suppression":
            kwargs["blocked_statuses"] = ()
            kwargs["stale_after_days"] = 36500
            kwargs["stale_low_confidence_threshold"] = 0.0
            kwargs["stale_penalty_weight"] = 0.0
            kwargs["enable_stale_filter"] = False
        elif variant == "multi_level_topk":
            kwargs.update({"top_candidates": 10, "top_seeds": 5, "max_nodes": 16, "max_edges": 32})
        elif variant == "scene_weight_0_3":
            kwargs["scene_match_weight"] = 0.3
        elif variant == "scene_weight_1_2":
            kwargs["scene_match_weight"] = 1.2
        elif variant == "topk_small":
            kwargs.update({"top_candidates": 4, "top_seeds": 2, "max_nodes": 6, "max_edges": 10})
        elif variant == "topk_large":
            kwargs.update({"top_candidates": 12, "top_seeds": 6, "max_nodes": 18, "max_edges": 36})
        elif variant == "wo_conflict_suppression":
            kwargs["conflict_penalty_weight"] = 0.0
            kwargs["enable_conflict_filter"] = False
        return GraphMemoryConfig(**kwargs)

    def config_for_variant(self, variant: str) -> GraphMemoryConfig:
        """暴露给消融参数记录使用的配置视图。"""

        provider = self._build_embedding_provider()
        return self._config_for_variant(variant, provider)

    def _build_graph(
        self,
        case: ExperimentCase,
        *,
        variant: str,
    ) -> tuple[LongTermMemoryGraphPlugin, InMemoryGraphStore, DeterministicEmbeddingProvider]:
        """为单个 case 构造隔离的内存图，避免样本之间互相污染。"""

        provider = self._build_embedding_provider()
        store = InMemoryGraphStore()
        config = self._config_for_variant(variant, provider)
        plugin = LongTermMemoryGraphPlugin(config=config, store=store)
        plugin.store_capsules(list(case.capsules))
        if variant == "wo_temporal_edges":
            _remove_edges(store, {"TEMPORAL_NEXT"})
        elif variant == "wo_revision_edges":
            _remove_edges(store, {"REVISES"})
        return plugin, store, provider

    def _request(
        self,
        case: ExperimentCase,
        *,
        top_candidates: int | None = None,
        top_seeds: int | None = None,
        max_nodes: int | None = None,
        max_edges: int | None = None,
    ) -> RecallRequest:
        """把实验 case 转成召回服务请求。"""

        return RecallRequest(
            query=case.query,
            knowledge_scope=list(case.knowledge_scope),
            tags=list(case.tags),
            entities=list(case.entities),
            top_candidates=top_candidates if top_candidates is not None else self.top_candidates,
            top_seeds=top_seeds if top_seeds is not None else self.top_seeds,
            max_nodes=max_nodes if max_nodes is not None else self.max_nodes,
            max_edges=max_edges if max_edges is not None else self.max_edges,
        )

    def _clarks_graph(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        plugin: LongTermMemoryGraphPlugin,
    ) -> RetrievalResult:
        """运行本文长期记忆图谱召回路径。"""

        start = perf_counter()
        response = plugin.recall(
            self._request(
                case,
                top_candidates=plugin.config.top_candidates,
                top_seeds=plugin.config.top_seeds,
                max_nodes=plugin.config.max_nodes,
                max_edges=plugin.config.max_edges,
            )
        )
        elapsed = (perf_counter() - start) * 1000
        index_to_id = {entry.index: entry.capsule_id for entry in response.node_index}
        relation_types = [edge.relation_type for edge in response.edges]
        edge_keys = [
            f"{index_to_id.get(edge.source_index, edge.source_index)}:{edge.relation_type}:{index_to_id.get(edge.target_index, edge.target_index)}"
            for edge in response.edges
        ]
        detail_capsule_ids = list(case.detail_lookup_capsule_ids or tuple(entry.capsule_id for entry in response.node_index[:2]))
        detail_start = perf_counter()
        detail_response = plugin.fetch_capsule_details(detail_capsule_ids) if detail_capsule_ids else None
        detail_latency_ms = (perf_counter() - detail_start) * 1000 if detail_capsule_ids else 0.0
        latency_breakdown = dict(response.retrieval_report.timing_breakdown_ms)
        if detail_capsule_ids:
            latency_breakdown["detail_lookup_ms"] = round(detail_latency_ms, 4)
        return RetrievalResult(
            method=method,
            variant=variant,
            prompt_summary=response.prompt_summary,
            returned_capsule_ids=[entry.capsule_id for entry in response.node_index],
            returned_relation_types=relation_types,
            returned_edge_keys=edge_keys,
            suppressed_stale_nodes=response.retrieval_report.suppressed_stale_nodes,
            suppressed_conflict_nodes=response.retrieval_report.suppressed_conflict_nodes,
            detail_lookup_capsule_ids=detail_capsule_ids,
            detail_lookup_hit_count=len(detail_response.details) if detail_response is not None else 0,
            detail_lookup_missing_count=len(detail_response.missing_capsule_ids) if detail_response is not None else 0,
            detail_lookup_latency_ms=round(detail_latency_ms, 4),
            latency_breakdown=latency_breakdown,
            latency_ms=elapsed,
        )

    def _rag_chunk_memory(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        store: InMemoryGraphStore,
        provider: DeterministicEmbeddingProvider,
    ) -> RetrievalResult:
        """RAG chunk 基线：只按向量语义拿片段，不使用图结构。"""

        start = perf_counter()
        query_vector = run_async(provider.embed([case.query]))[0]
        hits = store.query_vector(query_vector, limit=self.max_nodes)
        elapsed = (perf_counter() - start) * 1000
        nodes = [hit.node for hit in hits]
        return _result_from_nodes(
            method,
            variant,
            nodes,
            [],
            elapsed,
            "RAG chunk proxy returned top semantic chunks without memory structure.",
            embedding_request_count=self._last_embedding_request_count,
            embedding_text_count=self._last_embedding_text_count,
            embedding_latency_ms=self._last_embedding_latency_ms,
        )

    def _vector_memory(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        store: InMemoryGraphStore,
        provider: DeterministicEmbeddingProvider,
    ) -> RetrievalResult:
        """纯向量记忆基线：返回最相似的胶囊文本。"""

        start = perf_counter()
        query_vector = run_async(provider.embed([case.query]))[0]
        hits = store.query_vector(query_vector, limit=self.max_nodes)
        elapsed = (perf_counter() - start) * 1000
        nodes = [hit.node for hit in hits]
        return _result_from_nodes(
            method,
            variant,
            nodes,
            [],
            elapsed,
            "Vector-only memory returned flat capsule texts.",
            embedding_request_count=self._last_embedding_request_count,
            embedding_text_count=self._last_embedding_text_count,
            embedding_latency_ms=self._last_embedding_latency_ms,
        )

    def _flat_summary_memory(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        store: InMemoryGraphStore,
    ) -> RetrievalResult:
        """扁平摘要基线：按关键词重叠选取短摘要。"""

        start = perf_counter()
        tokens = set(_tokens(case.query))
        ranked = sorted(
            store.nodes.values(),
            key=lambda node: (
                len(tokens.intersection(_tokens(" ".join([node.goal, node.summary, node.outcome, " ".join(node.tags)])))),
                node.created_at.timestamp(),
            ),
            reverse=True,
        )[: self.max_nodes]
        elapsed = (perf_counter() - start) * 1000
        active = [node for node in ranked if node.status != "deprecated"]
        return _result_from_nodes(method, variant, active, [], elapsed, "Flat summary memory returned top textual summaries.")

    def _naive_graph_memory(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        store: InMemoryGraphStore,
        provider: DeterministicEmbeddingProvider,
    ) -> RetrievalResult:
        """朴素图基线：扩展一跳邻居，但不做治理策略。"""

        start = perf_counter()
        seed_ids = self._seed_ids(case, store=store, provider=provider)
        nodes, edges = store.fetch_one_hop_subgraph(seed_ids, edge_limit=self.max_edges)
        elapsed = (perf_counter() - start) * 1000
        return _result_from_nodes(
            method,
            variant,
            nodes[: self.max_nodes],
            edges,
            elapsed,
            "Naive graph memory expanded one-hop neighbors without governance policy.",
            embedding_request_count=self._last_embedding_request_count,
            embedding_text_count=self._last_embedding_text_count,
            embedding_latency_ms=self._last_embedding_latency_ms,
        )

    def _graph_rag_memory(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        store: InMemoryGraphStore,
        provider: DeterministicEmbeddingProvider,
    ) -> RetrievalResult:
        """GraphRAG 代理：图邻居召回加简单排序，不处理冲突/过期策略。"""

        start = perf_counter()
        seed_ids = self._seed_ids(case, store=store, provider=provider, lexical_bonus=True)
        nodes, edges = store.fetch_one_hop_subgraph(seed_ids, edge_limit=self.max_edges)
        nodes = sorted(nodes, key=lambda item: (item.status != "deprecated", item.confidence, item.created_at.timestamp()), reverse=True)
        elapsed = (perf_counter() - start) * 1000
        return _result_from_nodes(
            method,
            variant,
            nodes[: self.max_nodes],
            edges,
            elapsed,
            "GraphRAG-style proxy returned graph neighbors but did not apply revision/conflict/stale policy.",
            embedding_request_count=self._last_embedding_request_count,
            embedding_text_count=self._last_embedding_text_count,
            embedding_latency_ms=self._last_embedding_latency_ms,
        )

    def _mem0_zep_memory(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        store: InMemoryGraphStore,
    ) -> RetrievalResult:
        """旧版生产记忆代理：用高置信、近期记忆近似 Mem0/Zep 类路径。"""

        start = perf_counter()
        nodes = sorted(
            [node for node in store.nodes.values() if node.status != "deprecated"],
            key=lambda item: (item.confidence, item.created_at.timestamp()),
            reverse=True,
        )[: self.max_nodes]
        elapsed = (perf_counter() - start) * 1000
        return _result_from_nodes(method, variant, nodes, [], elapsed, "Production memory proxy returned recent high-confidence memories.")

    def _hypergraph_proxy(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        store: InMemoryGraphStore,
    ) -> RetrievalResult:
        """超图代理：以任务簇近似 topic-episode-fact 的多层组织。"""

        start = perf_counter()
        task_scores: dict[str, int] = {}
        query_tokens = set(_tokens(case.query))
        for node in store.nodes.values():
            key = node.task_family or node.task_id or "global"
            task_scores[key] = max(
                task_scores.get(key, 0),
                len(query_tokens.intersection(_tokens(" ".join([node.goal, node.summary, " ".join(node.tags), " ".join(node.entities)])))),
            )
        selected_task = max(task_scores, key=task_scores.get) if task_scores else ""
        nodes = [node for node in store.nodes.values() if (node.task_family or node.task_id or "global") == selected_task]
        nodes = sorted(nodes, key=lambda item: item.created_at, reverse=True)[: self.max_nodes]
        node_ids = {node.capsule_id for node in nodes}
        edges = [
            edge
            for edge in store.edges.values()
            if edge.source_capsule_id in node_ids and edge.target_capsule_id in node_ids
        ][: self.max_edges]
        elapsed = (perf_counter() - start) * 1000
        result = _result_from_nodes(
            method,
            variant,
            nodes,
            edges,
            elapsed,
            "Topic-episode-fact proxy returned the nearest task cluster.",
            embedding_request_count=self._last_embedding_request_count,
            embedding_text_count=self._last_embedding_text_count,
            embedding_latency_ms=self._last_embedding_latency_ms,
        )
        result.returned_relation_types.append("TOPIC_EPISODE_FACT")
        return result

    def _paper_proxy_memory(
        self,
        case: ExperimentCase,
        *,
        method: str,
        variant: str,
        store: InMemoryGraphStore,
        provider: DeterministicEmbeddingProvider,
    ) -> RetrievalResult:
        """按文献画像选择不同代理策略，保证对比矩阵结构稳定。"""

        strategy, summary = PAPER_PROXY_PROFILES[method]
        start = perf_counter()
        edges = []
        nodes = []

        if strategy == "recent_high_confidence":
            nodes = _active_nodes(store.nodes.values())
            nodes = sorted(nodes, key=lambda item: (item.confidence, item.created_at.timestamp()), reverse=True)
        elif strategy == "session_namespace":
            nodes = _rank_by_query_overlap(case, _active_nodes(store.nodes.values()))
            nodes = sorted(nodes, key=lambda item: (item.task_family in case.knowledge_scope, item.created_at.timestamp()), reverse=True)
        elif strategy == "fact_only":
            nodes = _rank_by_query_overlap(case, _active_nodes(store.nodes.values()))
        elif strategy == "compact_profile":
            nodes = _rank_by_query_overlap(case, _active_nodes(store.nodes.values()))[: max(2, min(4, self.max_nodes))]
        elif strategy == "profile_event":
            nodes = _rank_by_query_overlap(case, _active_nodes(store.nodes.values()))
            nodes = sorted(nodes, key=lambda item: (len(set(item.entities).intersection(case.entities)), item.confidence), reverse=True)
        elif strategy in {"entity_graph", "light_graph", "episodic_graph", "hierarchical_os", "adaptive_salience"}:
            lexical_bonus = strategy in {"light_graph", "hierarchical_os", "adaptive_salience"}
            seed_ids = self._seed_ids(case, store=store, provider=provider, lexical_bonus=lexical_bonus)
            nodes, edges = store.fetch_one_hop_subgraph(seed_ids, edge_limit=self.max_edges)
            nodes = _active_nodes(nodes)
            if strategy == "episodic_graph":
                relation_priority = {"TEMPORAL_NEXT": 5, "REVISES": 4, "SAME_TASK": 3, "EVIDENCE_SUPPORTS": 2}
                edges = sorted(edges, key=lambda edge: relation_priority.get(edge.relation_type, 1), reverse=True)
                nodes = sorted(nodes, key=lambda item: (item.task_family in case.knowledge_scope, item.created_at.timestamp()), reverse=True)
            elif strategy == "entity_graph":
                nodes = sorted(nodes, key=lambda item: (len(set(item.entities).intersection(case.entities)), item.confidence), reverse=True)
            elif strategy == "hierarchical_os":
                nodes = sorted(nodes, key=lambda item: (item.status == "validated", item.confidence, item.created_at.timestamp()), reverse=True)
            else:
                nodes = _rank_by_query_overlap(case, nodes)
        else:
            nodes = _rank_by_query_overlap(case, _active_nodes(store.nodes.values()))

        elapsed = (perf_counter() - start) * 1000
        return _result_from_nodes(
            method,
            variant,
            nodes[: self.max_nodes],
            edges[: self.max_edges],
            elapsed,
            summary,
            embedding_request_count=self._last_embedding_request_count,
            embedding_text_count=self._last_embedding_text_count,
            embedding_latency_ms=self._last_embedding_latency_ms,
        )

    def _seed_ids(
        self,
        case: ExperimentCase,
        *,
        store: InMemoryGraphStore,
        provider: DeterministicEmbeddingProvider,
        lexical_bonus: bool = False,
    ) -> list[str]:
        """先向量召回种子，再按需叠加词法召回分数。"""

        query_vector = run_async(provider.embed([case.query]))[0]
        vector_hits = store.query_vector(query_vector, limit=self.top_candidates)
        scores = {hit.node.capsule_id: hit.score for hit in vector_hits}
        lexical_query = build_fulltext_query(self._request(case))
        for hit in store.query_fulltext(lexical_query, limit=self.top_candidates):
            scores[hit.node.capsule_id] = scores.get(hit.node.capsule_id, 0.0) + (hit.score if lexical_bonus else hit.score * 0.5)
        ranked = sorted(scores, key=scores.get, reverse=True)
        return ranked[: self.top_seeds]

    def _build_embedding_provider(self) -> DeterministicEmbeddingProvider:
        """优先使用真实 OpenAI-compatible embedding，否则退回确定性嵌入。"""

        env = resolve_embedding_env()
        api_key = (env.get("embedding_api_key") or "").strip()
        base_url = (env.get("embedding_base_url") or "").strip()
        model = (self.embedding_model or env.get("embedding_model") or "").strip()
        if api_key and base_url and model:
            dimensions = self.embedding_dimensions if self.embedding_dimensions is not None else 1536
            provider = LiveOpenAIEmbeddingProvider(
                model=model,
                api_key=api_key,
                base_url=base_url,
                embedding_model=model,
                embedding_dimensions=dimensions,
            )
            original_embed = provider.embed

            async def instrumented_embed(texts: list[str]) -> list[list[float]]:
                """包装真实 embedding 调用，顺带记录请求数和耗时。"""

                start = perf_counter()
                try:
                    return await original_embed(texts)
                finally:
                    self._last_embedding_request_count += 1
                    self._last_embedding_text_count += len(texts)
                    self._last_embedding_latency_ms += (perf_counter() - start) * 1000

            provider.embed = instrumented_embed  # type: ignore[method-assign]
            return provider
        return DeterministicEmbeddingProvider(dimensions=self.embedding_dimensions or 32, salt=f"ltmg-{self.seed}")


def _remove_edges(store: InMemoryGraphStore, relation_types: set[str]) -> None:
    """消融实验中按关系类型移除边。"""

    for key in list(store.edges):
        if key[1] in relation_types:
            store.edges.pop(key)


def _tokens(text: str) -> list[str]:
    """轻量分词，避免给实验基线引入额外依赖。"""

    return [item.strip(".,;:!?()[]").lower() for item in text.replace("_", " ").split() if item.strip(".,;:!?()[]")]


def _active_nodes(nodes) -> list:
    """过滤已废弃节点。"""

    return [node for node in nodes if node.status != "deprecated"]


def _rank_by_query_overlap(case: ExperimentCase, nodes) -> list:
    """按查询、标签、实体和范围的词面重叠排序。"""

    query_tokens = set(_tokens(" ".join([case.query, " ".join(case.tags), " ".join(case.entities), " ".join(case.knowledge_scope)])))
    return sorted(
        nodes,
        key=lambda node: (
            len(query_tokens.intersection(_tokens(" ".join([node.goal, node.summary, node.outcome, " ".join(node.tags), " ".join(node.entities)])))),
            node.confidence,
            node.created_at.timestamp(),
        ),
        reverse=True,
    )


def _result_from_nodes(
    method: str,
    variant: str,
    nodes: list,
    edges: list,
    latency_ms: float,
    summary_prefix: str,
    *,
    embedding_request_count: int = 0,
    embedding_text_count: int = 0,
    embedding_latency_ms: float = 0.0,
) -> RetrievalResult:
    """把节点和边整理成统一的召回结果结构。"""

    relation_types = [edge.relation_type for edge in edges]
    edge_keys = [f"{edge.source_capsule_id}:{edge.relation_type}:{edge.target_capsule_id}" for edge in edges]
    summary_parts = [summary_prefix]
    for node in nodes[:6]:
        summary_parts.append(f"[{node.capsule_id}] {node.summary}")
    return RetrievalResult(
        method=method,
        variant=variant,
        prompt_summary="\n".join(summary_parts),
        returned_capsule_ids=[node.capsule_id for node in nodes],
        returned_relation_types=relation_types,
        returned_edge_keys=edge_keys,
        suppressed_stale_nodes=[],
        suppressed_conflict_nodes=[],
        detail_lookup_capsule_ids=[],
        detail_lookup_hit_count=0,
        detail_lookup_missing_count=0,
        detail_lookup_latency_ms=0.0,
        latency_breakdown={"total_ms": round(latency_ms, 4)},
        latency_ms=latency_ms,
        embedding_request_count=embedding_request_count,
        embedding_text_count=embedding_text_count,
        embedding_latency_ms=round(embedding_latency_ms, 4),
    )
