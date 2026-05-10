from __future__ import annotations

from ..domain.services import CapsuleIngestionService, CapsulePromotionService, DetailQueryService, RecallService
from ..domain.summary import TemplateSubgraphSummarizer
from ..domain.utils import run_async
from ..integrations.backfill import SQLiteBackfillImporter
from ..storage.base import GraphStore
from ..storage.neo4j import Neo4jGraphStore
from .config import GraphMemoryConfig
from .models import BackfillReport, CapsuleDetailResponse, ExperienceCandidate, MemoryCapsuleCandidate, PromotionReport, RecallRequest, RecallResponse


class LongTermMemoryGraphPlugin:
    def __init__(
        self,
        config: GraphMemoryConfig | None = None,
        *,
        store: GraphStore | None = None,
    ) -> None:
        self.config = config or GraphMemoryConfig()
        self._store_error: Exception | None = None
        if store is not None:
            self.store: GraphStore | None = store
        else:
            try:
                self.store = Neo4jGraphStore(self.config)
            except Exception as exc:  # pragma: no cover - depends on optional dependency/runtime
                self.store = None
                self._store_error = exc
        if self.store is not None and self.config.auto_create_schema:
            self.store.ensure_schema()

        if self.store is None:
            self._ingestion_service = None
            self._promotion_service = None
            self._recall_service = None
            self._detail_service = None
            self._backfill_importer = None
            return

        summarizer = TemplateSubgraphSummarizer()
        self._ingestion_service = CapsuleIngestionService(
            config=self.config,
            store=self.store,
            embed_texts=self._embed_texts,
        )
        self._promotion_service = CapsulePromotionService(
            config=self.config,
            ingestion_service=self._ingestion_service,
        )
        self._recall_service = RecallService(
            config=self.config,
            store=self.store,
            embed_texts=self._embed_texts,
            summarizer=summarizer,
        )
        self._detail_service = DetailQueryService(store=self.store)
        self._backfill_importer = SQLiteBackfillImporter(self._ingestion_service.store_capsules)

    def close(self) -> None:
        if self.store is not None:
            self.store.close()

    def store_capsules(self, candidates: list[MemoryCapsuleCandidate]) -> list[str]:
        self._require_store()
        assert self._ingestion_service is not None
        return self._ingestion_service.store_capsules(candidates)

    def promote_candidates(self, candidates: list[ExperienceCandidate]) -> PromotionReport:
        self._require_store()
        assert self._promotion_service is not None
        return self._promotion_service.promote_candidates(candidates)

    def recall(self, request: RecallRequest) -> RecallResponse:
        self._require_store()
        assert self._recall_service is not None
        return self._recall_service.recall(request)

    def fetch_capsule_details(self, capsule_ids: list[str]) -> CapsuleDetailResponse:
        self._require_store()
        assert self._detail_service is not None
        return self._detail_service.fetch_capsule_details(capsule_ids)

    def backfill_from_sqlite(self, records_db_path: str) -> BackfillReport:
        self._require_store()
        assert self._backfill_importer is not None
        return self._backfill_importer.import_from_sqlite(records_db_path)

    def _require_store(self) -> None:
        if self.store is None:
            if self._store_error is None:
                raise RuntimeError("Long-term memory graph store is not available.")
            raise RuntimeError(f"Long-term memory graph store is not available: {self._store_error}") from self._store_error

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.config.embedding_provider is None:
            raise RuntimeError("Embedding provider is required for this operation.")
        return run_async(self.config.embedding_provider.embed(texts))
