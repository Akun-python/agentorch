from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any

from ..api.config import GraphMemoryConfig
from ..domain.entities import GraphEdgeCandidate, MemoryCapsuleDetail, SearchHit, SubgraphEdge
from ..domain.utils import now_utc, to_iso8601


def _load_graph_database() -> Any:
    from neo4j import GraphDatabase

    return GraphDatabase


class Neo4jGraphStore:
    NODE_LABEL = "MemoryCapsule"

    def __init__(self, config: GraphMemoryConfig) -> None:
        self.config = config
        graph_database = _load_graph_database()
        username = (config.neo4j_username or "").strip()
        password = config.neo4j_password or ""
        driver_kwargs: dict[str, Any] = {}
        if username or password:
            driver_kwargs["auth"] = (username, password)
        self._driver = graph_database.driver(config.neo4j_uri, **driver_kwargs)
        self._session_kwargs = self._build_session_kwargs()

    def close(self) -> None:
        self._driver.close()

    def _build_session_kwargs(self) -> dict[str, Any]:
        database = (self.config.neo4j_database or "").strip()
        if not database:
            return {}
        try:
            protocol_version = self._driver.get_server_info().protocol_version
        except Exception:
            return {"database": database}
        if tuple(protocol_version) >= (4, 0):
            return {"database": database}
        return {}

    @contextmanager
    def _session(self) -> Any:
        with self._driver.session(**self._session_kwargs) as session:
            yield session

    def ensure_schema(self) -> None:
        statements = [
            f"CREATE CONSTRAINT memory_capsule_id_unique IF NOT EXISTS FOR (n:{self.NODE_LABEL}) REQUIRE n.capsule_id IS UNIQUE",
            (
                f"CREATE FULLTEXT INDEX {self.config.fulltext_index_name} IF NOT EXISTS "
                f"FOR (n:{self.NODE_LABEL}) ON EACH [n.summary, n.goal, n.tags, n.entities]"
            ),
            (
                f"CREATE VECTOR INDEX {self.config.vector_index_name} IF NOT EXISTS "
                f"FOR (n:{self.NODE_LABEL}) ON (n.summary_embedding) "
                f"OPTIONS {{indexConfig: {{`vector.dimensions`: {self.config.embedding_dimensions}, "
                "`vector.similarity_function`: 'cosine'}}"
            ),
            f"CREATE INDEX memory_capsule_thread_family IF NOT EXISTS FOR (n:{self.NODE_LABEL}) ON (n.thread_family)",
            f"CREATE INDEX memory_capsule_task_family IF NOT EXISTS FOR (n:{self.NODE_LABEL}) ON (n.task_family)",
            f"CREATE INDEX memory_capsule_status IF NOT EXISTS FOR (n:{self.NODE_LABEL}) ON (n.status)",
            f"CREATE INDEX memory_capsule_created_at IF NOT EXISTS FOR (n:{self.NODE_LABEL}) ON (n.created_at)",
        ]
        with self._session() as session:
            for statement in statements:
                session.run(statement).consume()

    def upsert_capsule(
        self,
        capsule: MemoryCapsuleDetail,
        *,
        summary_embedding: list[float] | None,
        scene_hash: str,
    ) -> MemoryCapsuleDetail:
        props: dict[str, Any] = {
            "agent_id": capsule.agent_id,
            "run_id": capsule.run_id,
            "thread_id": capsule.thread_id,
            "thread_family": capsule.thread_family,
            "task_id": capsule.task_id,
            "task_family": capsule.task_family,
            "created_at": to_iso8601(capsule.created_at),
            "goal": capsule.goal,
            "summary": capsule.summary,
            "outcome": capsule.outcome,
            "knowledge_scope": capsule.knowledge_scope,
            "tags": capsule.tags,
            "entities": capsule.entities,
            "claims": json.dumps([item.model_dump() for item in capsule.claims], ensure_ascii=True, sort_keys=True),
            "evidence_refs": capsule.evidence_refs,
            "source_memory_refs": capsule.source_memory_refs,
            "scene_hash": scene_hash,
            "salience_score": float(capsule.salience_score),
            "confidence": float(capsule.confidence),
            "status": capsule.status,
            "last_validated_at": to_iso8601(capsule.last_validated_at or capsule.created_at),
        }
        if summary_embedding is not None:
            props["summary_embedding"] = summary_embedding
        query = (
            f"MERGE (n:{self.NODE_LABEL} {{capsule_id: $capsule_id}}) "
            "SET n += $props, n.reuse_count = coalesce(n.reuse_count, 0) "
            "RETURN properties(n) AS node"
        )
        with self._session() as session:
            record = session.run(query, capsule_id=capsule.capsule_id, props=props).single()
        if record is None:
            raise RuntimeError(f"Failed to upsert capsule '{capsule.capsule_id}' into Neo4j.")
        return self._hydrate_node(record["node"])

    def fetch_temporal_neighbors(self, capsule: MemoryCapsuleDetail) -> tuple[MemoryCapsuleDetail | None, MemoryCapsuleDetail | None]:
        if not capsule.thread_family:
            return None, None
        previous_query = (
            f"MATCH (n:{self.NODE_LABEL}) "
            "WHERE n.thread_family = $thread_family AND n.capsule_id <> $capsule_id AND n.created_at < $created_at "
            "RETURN properties(n) AS node ORDER BY n.created_at DESC LIMIT 1"
        )
        next_query = (
            f"MATCH (n:{self.NODE_LABEL}) "
            "WHERE n.thread_family = $thread_family AND n.capsule_id <> $capsule_id AND n.created_at > $created_at "
            "RETURN properties(n) AS node ORDER BY n.created_at ASC LIMIT 1"
        )
        params = {
            "thread_family": capsule.thread_family,
            "capsule_id": capsule.capsule_id,
            "created_at": to_iso8601(capsule.created_at),
        }
        with self._session() as session:
            previous = session.run(previous_query, **params).single()
            following = session.run(next_query, **params).single()
        return (
            self._hydrate_node(previous["node"]) if previous is not None else None,
            self._hydrate_node(following["node"]) if following is not None else None,
        )

    def fetch_rule_neighbors(self, capsule: MemoryCapsuleDetail, *, limit: int) -> list[MemoryCapsuleDetail]:
        query = (
            f"MATCH (n:{self.NODE_LABEL}) "
            "WHERE n.capsule_id <> $capsule_id AND ("
            "($thread_family IS NOT NULL AND n.thread_family = $thread_family) OR "
            "($task_id IS NOT NULL AND n.task_id = $task_id) OR "
            "($task_family IS NOT NULL AND n.task_family = $task_family) OR "
            "ANY(tag IN $tags WHERE tag IN coalesce(n.tags, [])) OR "
            "ANY(entity IN $entities WHERE entity IN coalesce(n.entities, [])) OR "
            "ANY(ref IN $evidence_refs WHERE ref IN coalesce(n.evidence_refs, [])) OR "
            "ANY(ref IN $source_memory_refs WHERE ref IN coalesce(n.source_memory_refs, []))"
            ") "
            "RETURN properties(n) AS node ORDER BY n.created_at DESC LIMIT $limit"
        )
        params = {
            "capsule_id": capsule.capsule_id,
            "thread_family": capsule.thread_family,
            "task_id": capsule.task_id,
            "task_family": capsule.task_family,
            "tags": capsule.tags,
            "entities": capsule.entities,
            "evidence_refs": capsule.evidence_refs,
            "source_memory_refs": capsule.source_memory_refs,
            "limit": int(limit),
        }
        with self._session() as session:
            rows = session.run(query, **params).data()
        return [self._hydrate_node(item["node"]) for item in rows]

    def upsert_edges(self, edges: list[GraphEdgeCandidate]) -> None:
        relation_types = {item.relation_type for item in edges}
        invalid = relation_types.difference(self.config.relation_types)
        if invalid:
            raise ValueError(f"Unsupported relation types: {sorted(invalid)}")
        with self._session() as session:
            for relation_type in sorted(relation_types):
                batch = [
                    {
                        "source_capsule_id": edge.source_capsule_id,
                        "target_capsule_id": edge.target_capsule_id,
                        "score": float(edge.score),
                        "created_at": to_iso8601(edge.created_at),
                        "source_rule": edge.source_rule,
                        "support_count": int(edge.support_count),
                    }
                    for edge in edges
                    if edge.relation_type == relation_type
                ]
                if not batch:
                    continue
                query = (
                    "UNWIND $rows AS row "
                    f"MATCH (a:{self.NODE_LABEL} {{capsule_id: row.source_capsule_id}}) "
                    f"MATCH (b:{self.NODE_LABEL} {{capsule_id: row.target_capsule_id}}) "
                    f"MERGE (a)-[r:{relation_type}]->(b) "
                    "SET r.score = row.score, "
                    "r.created_at = row.created_at, "
                    "r.source_rule = row.source_rule, "
                    "r.support_count = row.support_count"
                )
                session.run(query, rows=batch).consume()

    def query_vector(self, embedding: list[float], *, limit: int) -> list[SearchHit]:
        query = (
            "CALL db.index.vector.queryNodes($index_name, $limit, $embedding) "
            "YIELD node, score "
            "RETURN properties(node) AS node, score"
        )
        with self._session() as session:
            rows = session.run(
                query,
                index_name=self.config.vector_index_name,
                limit=int(limit),
                embedding=embedding,
            ).data()
        return [SearchHit(node=self._hydrate_node(item["node"]), score=float(item["score"])) for item in rows]

    def query_fulltext(self, query_text: str, *, limit: int) -> list[SearchHit]:
        query = (
            "CALL db.index.fulltext.queryNodes($index_name, $query_text, {limit: $limit}) "
            "YIELD node, score "
            "RETURN properties(node) AS node, score"
        )
        with self._session() as session:
            rows = session.run(
                query,
                index_name=self.config.fulltext_index_name,
                query_text=query_text,
                limit=int(limit),
            ).data()
        return [SearchHit(node=self._hydrate_node(item["node"]), score=float(item["score"])) for item in rows]

    def fetch_conflict_counts(self, capsule_ids: list[str]) -> dict[str, int]:
        if not capsule_ids:
            return {}
        query = (
            "UNWIND $capsule_ids AS capsule_id "
            f"MATCH (n:{self.NODE_LABEL} {{capsule_id: capsule_id}}) "
            f"OPTIONAL MATCH (n)-[r:CONFLICTS_WITH]-(:{self.NODE_LABEL}) "
            "RETURN capsule_id, count(r) AS conflict_count"
        )
        with self._session() as session:
            rows = session.run(query, capsule_ids=capsule_ids).data()
        return {item["capsule_id"]: int(item["conflict_count"]) for item in rows}

    def fetch_capsules(self, capsule_ids: list[str]) -> list[MemoryCapsuleDetail]:
        if not capsule_ids:
            return []
        query = (
            "UNWIND $capsule_ids AS capsule_id "
            f"MATCH (n:{self.NODE_LABEL} {{capsule_id: capsule_id}}) "
            "RETURN properties(n) AS node"
        )
        with self._session() as session:
            rows = session.run(query, capsule_ids=capsule_ids).data()
        by_id = {item["node"]["capsule_id"]: self._hydrate_node(item["node"]) for item in rows}
        return [by_id[capsule_id] for capsule_id in capsule_ids if capsule_id in by_id]

    def fetch_one_hop_subgraph(self, seed_ids: list[str], *, edge_limit: int) -> tuple[list[MemoryCapsuleDetail], list[SubgraphEdge]]:
        if not seed_ids:
            return [], []
        seed_nodes = {item.capsule_id: item for item in self.fetch_capsules(seed_ids)}
        query = (
            f"MATCH (seed:{self.NODE_LABEL})-[r]-(neighbor:{self.NODE_LABEL}) "
            "WHERE seed.capsule_id IN $seed_ids "
            "RETURN properties(seed) AS seed, properties(neighbor) AS neighbor, "
            "type(r) AS relation_type, "
            "startNode(r).capsule_id AS source_capsule_id, "
            "endNode(r).capsule_id AS target_capsule_id, "
            "coalesce(r.score, 0.0) AS score, "
            "coalesce(r.source_rule, '') AS source_rule, "
            "coalesce(r.support_count, 1) AS support_count "
            "ORDER BY score DESC "
            "LIMIT $edge_limit"
        )
        with self._session() as session:
            rows = session.run(query, seed_ids=seed_ids, edge_limit=int(edge_limit)).data()
        nodes = dict(seed_nodes)
        edges: list[SubgraphEdge] = []
        seen_edges: set[tuple[str, str, str]] = set()
        for item in rows:
            seed = self._hydrate_node(item["seed"])
            neighbor = self._hydrate_node(item["neighbor"])
            nodes[seed.capsule_id] = seed
            nodes[neighbor.capsule_id] = neighbor
            edge_key = (
                item["source_capsule_id"],
                item["relation_type"],
                item["target_capsule_id"],
            )
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append(
                SubgraphEdge(
                    source_capsule_id=item["source_capsule_id"],
                    target_capsule_id=item["target_capsule_id"],
                    relation_type=item["relation_type"],
                    score=float(item["score"]),
                    source_rule=item["source_rule"],
                    support_count=int(item["support_count"]),
                )
            )
        return list(nodes.values()), edges

    def mark_recalled(self, capsule_ids: list[str]) -> None:
        if not capsule_ids:
            return
        query = (
            "UNWIND $capsule_ids AS capsule_id "
            f"MATCH (n:{self.NODE_LABEL} {{capsule_id: capsule_id}}) "
            "SET n.reuse_count = coalesce(n.reuse_count, 0) + 1, "
            "n.last_validated_at = $timestamp"
        )
        with self._session() as session:
            session.run(query, capsule_ids=capsule_ids, timestamp=to_iso8601(now_utc())).consume()

    def _hydrate_node(self, props: dict[str, Any]) -> MemoryCapsuleDetail:
        claims = props.get("claims")
        if isinstance(claims, str):
            try:
                props = {**props, "claims": json.loads(claims)}
            except json.JSONDecodeError:
                props = {**props, "claims": []}
        return MemoryCapsuleDetail.model_validate(props)
