from __future__ import annotations

import sys
import types
from dataclasses import dataclass

from experiments.long_term_memory_graph.core.datasets import build_default_cases
from experiments.long_term_memory_graph.core.methods import ExperimentMethodRunner
from experiments.long_term_memory_graph.研究对比试验.protocol import build_comparison_protocol_metadata


class _FakeOption:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeMemoryClient:
    def __init__(self, *args, **kwargs):
        self.deleted = []
        self.added = []

    def delete_all(self, options=None, **kwargs):
        self.deleted.append((options, kwargs))
        return {"message": "ok"}

    def add(self, messages, options=None, **kwargs):
        self.added.append((messages, options, kwargs))
        return {"message": "ok"}

    def search(self, query, options=None, **kwargs):
        return {
            "results": [
                {
                    "id": "mem_1",
                    "memory": "Checkout payment retries should use exponential backoff at 2s, 4s, and 8s.",
                    "score": 0.93,
                    "metadata": {
                        "capsule_id": "cap_retry_policy",
                    },
                }
            ]
        }


@dataclass
class _FakeLangMemItem:
    key: str
    value: dict
    score: float | None = None


class _FakeLangMemStore:
    def __init__(self, *args, **kwargs):
        self.rows = {}

    def put(self, namespace, key, value, index=None):
        self.rows[(tuple(namespace), key)] = value

    def search(self, namespace, query=None, filter=None, limit=10, offset=0):
        items = []
        for (row_namespace, key), value in self.rows.items():
            if row_namespace != tuple(namespace):
                continue
            items.append(_FakeLangMemItem(key=key, value=value, score=0.88))
        return items[offset : offset + limit]


class _FakeSearchTool:
    def __init__(self, *, namespace, store, response_format="content", **kwargs):
        self.namespace = tuple(namespace)
        self.store = store
        self.response_format = response_format

    def invoke(self, payload):
        rows = self.store.search(self.namespace, query=payload.get("query"), limit=payload.get("limit", 10))
        return ("[]", rows)


class _FakeZepEpisodeData:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeZepEpisode:
    def __init__(self, *, content, metadata, score=0.79, uuid_="zep_episode_1"):
        self.content = content
        self.metadata = metadata
        self.score = score
        self.uuid_ = uuid_


class _FakeZepSearchResponse:
    def __init__(self, episodes):
        self.episodes = episodes


class _FakeZepGraph:
    def __init__(self):
        self.batches = []

    def add_batch(self, episodes=None, user_id=None, **kwargs):
        self.batches.append((episodes or [], user_id, kwargs))
        return episodes or []

    def search(self, query=None, user_id=None, limit=None, scope=None, **kwargs):
        if not self.batches:
            return _FakeZepSearchResponse([])
        episodes = []
        for item in self.batches[-1][0][: limit or 10]:
            metadata = item.kwargs.get("metadata") or {}
            episodes.append(
                _FakeZepEpisode(
                    content=item.kwargs.get("data", ""),
                    metadata=metadata,
                )
            )
        return _FakeZepSearchResponse(episodes)


class _FakeZepClient:
    def __init__(self, *args, **kwargs):
        self.graph = _FakeZepGraph()


def _install_fake_mem0_modules(monkeypatch):
    fake_mem0 = types.ModuleType("mem0")
    fake_mem0.MemoryClient = _FakeMemoryClient
    fake_types = types.ModuleType("mem0.client.types")
    fake_types.AddMemoryOptions = _FakeOption
    fake_types.DeleteAllMemoryOptions = _FakeOption
    fake_types.SearchMemoryOptions = _FakeOption
    monkeypatch.setitem(sys.modules, "mem0", fake_mem0)
    monkeypatch.setitem(sys.modules, "mem0.client.types", fake_types)


def _install_fake_langmem_modules(monkeypatch):
    fake_langmem = types.ModuleType("langmem")
    fake_langmem.create_search_memory_tool = lambda **kwargs: _FakeSearchTool(**kwargs)
    fake_store_module = types.ModuleType("langgraph.store.memory")
    fake_store_module.InMemoryStore = _FakeLangMemStore
    monkeypatch.setitem(sys.modules, "langmem", fake_langmem)
    monkeypatch.setitem(sys.modules, "langgraph.store.memory", fake_store_module)


def _install_fake_zep_modules(monkeypatch):
    fake_zep = types.ModuleType("zep_cloud")
    fake_zep.Zep = _FakeZepClient
    fake_types = types.ModuleType("zep_cloud.types")
    fake_types.EpisodeData = _FakeZepEpisodeData
    monkeypatch.setitem(sys.modules, "zep_cloud", fake_zep)
    monkeypatch.setitem(sys.modules, "zep_cloud.types", fake_types)


def test_mem0_official_adapter_is_used_when_sdk_and_env_exist(monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "test-key")
    _install_fake_mem0_modules(monkeypatch)
    case = build_default_cases()[0]
    runner = ExperimentMethodRunner(
        top_candidates=6,
        top_seeds=3,
        max_nodes=12,
        max_edges=24,
        seed=7,
    )

    result = runner.run(case, method="mem0_memory")

    assert result.source_boundary == "official_sdk"
    assert result.is_proxy is False
    assert result.returned_capsule_ids == ["cap_retry_policy"]
    assert "Mem0 官方 SDK 检索结果" in result.prompt_summary


def test_mem0_falls_back_to_proxy_when_official_env_is_missing(monkeypatch):
    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    monkeypatch.delitem(sys.modules, "mem0", raising=False)
    monkeypatch.delitem(sys.modules, "mem0.client.types", raising=False)
    case = build_default_cases()[0]
    runner = ExperimentMethodRunner(
        top_candidates=6,
        top_seeds=3,
        max_nodes=12,
        max_edges=24,
        seed=11,
    )

    result = runner.run(case, method="mem0_memory")

    assert result.source_boundary is None
    assert "Mem0-style proxy" in result.prompt_summary


def test_langmem_official_adapter_is_used_when_sdk_and_env_exist(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    _install_fake_langmem_modules(monkeypatch)
    case = build_default_cases()[0]
    runner = ExperimentMethodRunner(
        top_candidates=6,
        top_seeds=3,
        max_nodes=12,
        max_edges=24,
        seed=5,
    )

    result = runner.run(case, method="langmem_memory")

    assert result.source_boundary == "official_sdk"
    assert result.is_proxy is False
    assert result.returned_capsule_ids
    assert "LangMem 官方检索结果" in result.prompt_summary


def test_zep_official_adapter_is_used_when_sdk_and_env_exist(monkeypatch):
    monkeypatch.setenv("ZEP_API_KEY", "test-key")
    _install_fake_zep_modules(monkeypatch)
    case = build_default_cases()[0]
    runner = ExperimentMethodRunner(
        top_candidates=6,
        top_seeds=3,
        max_nodes=12,
        max_edges=24,
        seed=9,
    )

    result = runner.run(case, method="zep_memory")

    assert result.source_boundary == "official_sdk"
    assert result.is_proxy is False
    assert result.returned_capsule_ids
    assert "Zep 官方 SDK 检索结果" in result.prompt_summary


def test_protocol_catalog_marks_mem0_as_having_official_adapter():
    metadata = build_comparison_protocol_metadata(("mem0_memory", "langmem_memory", "zep_memory"))

    assert metadata["available_official_adapter_methods"] == ["langmem_memory", "mem0_memory", "zep_memory"]
    assert "mem0_memory" not in metadata["available_proxy_extension_methods"]
    assert metadata["comparison_layers"]["official_adapter"] == ["langmem_memory", "mem0_memory", "zep_memory"]
    assert metadata["available_method_catalog"]["mem0_memory"]["has_official_adapter"] is True
    assert metadata["available_method_catalog"]["langmem_memory"]["has_official_adapter"] is True
    assert metadata["available_method_catalog"]["zep_memory"]["has_official_adapter"] is True
