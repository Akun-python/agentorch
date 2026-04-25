from __future__ import annotations

from collections.abc import Callable

from ...api.config import GraphMemoryConfig
from ...api.models import MemoryCapsuleCandidate
from ...storage.base import GraphStore
from ..entities import MemoryCapsuleDetail
from ..rules import build_pairwise_edges, build_temporal_edges, deduplicate_edges
from ..utils import ensure_utc_datetime


class CapsuleIngestionService:
    def __init__(
        self,
        *,
        config: GraphMemoryConfig,
        store: GraphStore,
        embed_texts: Callable[[list[str]], list[list[float]]],
    ) -> None:
        self.config = config
        self.store = store
        self.embed_texts = embed_texts

    def store_capsules(self, candidates: list[MemoryCapsuleCandidate]) -> list[str]:
        if not candidates:
            return []
        ordered = sorted(candidates, key=lambda item: ensure_utc_datetime(item.created_at))
        embeddings = self._embed_capsules(ordered)
        stored_ids: list[str] = []
        for candidate, embedding in zip(ordered, embeddings):
            detail = MemoryCapsuleDetail.model_validate(candidate.model_dump())
            detail.scene_hash = candidate.computed_scene_hash()
            detail.summary_embedding = embedding
            upserted = self.store.upsert_capsule(
                detail,
                summary_embedding=embedding,
                scene_hash=detail.scene_hash or candidate.computed_scene_hash(),
            )
            previous_capsule, next_capsule = self.store.fetch_temporal_neighbors(upserted)
            neighbors = self.store.fetch_rule_neighbors(upserted, limit=self.config.neighborhood_limit)
            edges = build_temporal_edges(
                upserted,
                previous_capsule=previous_capsule,
                next_capsule=next_capsule,
            )
            for neighbor in neighbors:
                edges.extend(
                    build_pairwise_edges(
                        upserted,
                        neighbor,
                        scope_overlap_threshold=self.config.scope_overlap_threshold,
                    )
                )
            deduped = deduplicate_edges(edges)
            if deduped:
                self.store.upsert_edges(deduped)
            stored_ids.append(candidate.capsule_id)
        return stored_ids

    def _embed_capsules(self, candidates: list[MemoryCapsuleCandidate]) -> list[list[float] | None]:
        if self.config.embedding_provider is None:
            return [None] * len(candidates)
        texts = [candidate.summary or candidate.goal or candidate.outcome for candidate in candidates]
        return self.embed_texts(texts)
