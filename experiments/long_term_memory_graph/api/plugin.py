from __future__ import annotations

from ..domain.services import CapsuleIngestionService, CapsulePromotionService, DetailQueryService, RecallService
from ..domain.summary import TemplateSubgraphSummarizer
from ..domain.summary_llm import LLMSubgraphSummarizer
from ..domain.utils import run_async
from ..integrations.backfill import SQLiteBackfillImporter
from ..storage.base import GraphStore
from ..storage.neo4j import Neo4jGraphStore
from .config import GraphMemoryConfig
from .models import BackfillReport, CapsuleDetailResponse, ExperienceCandidate, MemoryCapsuleCandidate, PromotionReport, RecallRequest, RecallResponse


class LongTermMemoryGraphPlugin:
    """长期记忆图谱插件门面。

    对外保持 store/promote/recall/detail/backfill 五类操作，内部组合存储层和领域服务。
    """

    def __init__(
        self,
        config: GraphMemoryConfig | None = None,
        *,
        store: GraphStore | None = None,
        env_file: str | None = None,
    ) -> None:
        self.config = config or GraphMemoryConfig()
        self.env_file = env_file
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

        summarizer = self._build_summarizer()
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

    def _build_summarizer(self):
        """按配置选择模板摘要器或 LLM 摘要器。"""

        if self.config.summary_backend == "llm":
            return LLMSubgraphSummarizer(config=self.config, env_file=self.env_file)
        return TemplateSubgraphSummarizer()

    def close(self) -> None:
        """关闭底层图数据库连接。"""

        if self.store is not None:
            self.store.close()

    def store_capsules(self, candidates: list[MemoryCapsuleCandidate]) -> list[str]:
        """直接写入已经整理好的长期记忆胶囊。"""

        self._require_store()
        assert self._ingestion_service is not None
        return self._ingestion_service.store_capsules(candidates)

    def promote_candidates(self, candidates: list[ExperienceCandidate]) -> PromotionReport:
        """把短期经验按规则筛选后晋升为长期记忆。"""

        self._require_store()
        assert self._promotion_service is not None
        return self._promotion_service.promote_candidates(candidates)

    def recall(self, request: RecallRequest) -> RecallResponse:
        """按查询和场景信息召回长期记忆证据。"""

        self._require_store()
        assert self._recall_service is not None
        return self._recall_service.recall(request)

    def fetch_capsule_details(self, capsule_ids: list[str]) -> CapsuleDetailResponse:
        """按 ID 拉取胶囊详情，用于审计或二阶段生成。"""

        self._require_store()
        assert self._detail_service is not None
        return self._detail_service.fetch_capsule_details(capsule_ids)

    def backfill_from_sqlite(self, records_db_path: str) -> BackfillReport:
        """从 AgentTorch 旧 SQLite 记忆库回填历史记忆。"""

        self._require_store()
        assert self._backfill_importer is not None
        return self._backfill_importer.import_from_sqlite(records_db_path)

    def _require_store(self) -> None:
        """在外部调用前确认存储层已经成功初始化。"""

        if self.store is None:
            if self._store_error is None:
                raise RuntimeError("Long-term memory graph store is not available.")
            raise RuntimeError(f"Long-term memory graph store is not available: {self._store_error}") from self._store_error

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """同步服务层与异步 embedding provider 之间的桥接。"""

        if self.config.embedding_provider is None:
            raise RuntimeError("Embedding provider is required for this operation.")
        return run_async(self.config.embedding_provider.embed(texts))
