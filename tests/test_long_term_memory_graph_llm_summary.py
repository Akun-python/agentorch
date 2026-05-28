from __future__ import annotations

from datetime import datetime, timezone

from agentorch.knowledge.base import EmbeddingProvider

from experiments.long_term_memory_graph.api.config import GraphMemoryConfig
from experiments.long_term_memory_graph.api.models import ClaimSlot, MemoryCapsuleCandidate, RecallRequest
from experiments.long_term_memory_graph.api.plugin import LongTermMemoryGraphPlugin
from experiments.long_term_memory_graph.storage.in_memory import InMemoryGraphStore


class _FakeEmbeddingProvider(EmbeddingProvider):
    dimensions = 8

    async def embed(self, texts):
        return [[0.1] * self.dimensions for _ in texts]


class _FakeLLMSummarizer:
    def __init__(self, *, config, env_file):
        self.config = config
        self.env_file = env_file
        self.calls = []

    def summarize(self, **kwargs):
        self.calls.append(kwargs)
        node = list(kwargs["nodes"])[0]
        return f"保留详情: {node.outcome}"


def test_llm_summary_backend_is_wired_into_plugin(monkeypatch):
    import experiments.long_term_memory_graph.api.plugin as plugin_module

    created = {}

    def _factory(*, config, env_file):
        summarizer = _FakeLLMSummarizer(config=config, env_file=env_file)
        created["instance"] = summarizer
        return summarizer

    monkeypatch.setattr(plugin_module, "LLMSubgraphSummarizer", _factory)
    config = GraphMemoryConfig(
        embedding_provider=_FakeEmbeddingProvider(),
        embedding_dimensions=8,
        auto_create_schema=False,
        summary_backend="llm",
        summary_model_backend="openai_http",
        summary_model="deepseek-v4-flash",
    )
    plugin = LongTermMemoryGraphPlugin(config=config, store=InMemoryGraphStore(), env_file=".env")
    plugin.store_capsules(
        [
            MemoryCapsuleCandidate(
                capsule_id="cap_1",
                thread_id="thread_1",
                task_id="task_1",
                created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                goal="确认客户首选发货时间",
                summary="客户倾向于下周二上午收货",
                outcome="2026-05-01 user: 请安排下周二上午送达；assistant: 已记录优先时间窗口。",
                entities=["customer"],
                claims=[ClaimSlot(slot="delivery_time", value="next tuesday morning", scope="shipping")],
                tags=["Temporal"],
                knowledge_scope=["shipping"],
                status="validated",
            )
        ]
    )

    response = plugin.recall(
        RecallRequest(
            query="客户希望什么时候收货？",
            knowledge_scope=["shipping"],
            tags=["Temporal"],
            entities=["customer"],
        )
    )

    summarizer = created["instance"]
    assert summarizer.env_file == ".env"
    assert summarizer.calls
    assert "下周二上午送达" in response.prompt_summary
