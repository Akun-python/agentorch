from __future__ import annotations

from experiments.long_term_memory_graph import GraphMemoryConfig
from experiments.long_term_memory_graph.storage.neo4j import Neo4jGraphStore


class _FakeDriver:
    def close(self) -> None:
        return None


def test_neo4j_store_omits_auth_when_credentials_are_blank(monkeypatch):
    captured = {}

    class _FakeGraphDatabase:
        @staticmethod
        def driver(uri, **kwargs):
            captured["uri"] = uri
            captured["kwargs"] = kwargs
            return _FakeDriver()

    monkeypatch.setattr(
        "experiments.long_term_memory_graph.storage.neo4j._load_graph_database",
        lambda: _FakeGraphDatabase,
    )

    store = Neo4jGraphStore(GraphMemoryConfig(neo4j_uri="bolt://127.0.0.1:7797", neo4j_username="", neo4j_password=""))
    store.close()

    assert captured["uri"] == "bolt://127.0.0.1:7797"
    assert captured["kwargs"] == {}


def test_neo4j_store_uses_auth_when_credentials_are_present(monkeypatch):
    captured = {}

    class _FakeGraphDatabase:
        @staticmethod
        def driver(uri, **kwargs):
            captured["uri"] = uri
            captured["kwargs"] = kwargs
            return _FakeDriver()

    monkeypatch.setattr(
        "experiments.long_term_memory_graph.storage.neo4j._load_graph_database",
        lambda: _FakeGraphDatabase,
    )

    store = Neo4jGraphStore(
        GraphMemoryConfig(
            neo4j_uri="bolt://127.0.0.1:7787",
            neo4j_username="neo4j",
            neo4j_password="123456",
        )
    )
    store.close()

    assert captured["uri"] == "bolt://127.0.0.1:7787"
    assert captured["kwargs"] == {"auth": ("neo4j", "123456")}
