from __future__ import annotations

from types import SimpleNamespace

from experiments.long_term_memory_graph import GraphMemoryConfig
from experiments.long_term_memory_graph.storage.neo4j import Neo4jGraphStore


class _FakeSessionContext:
    def __init__(self, driver: "_FakeDriver", kwargs: dict[str, object]) -> None:
        self._driver = driver
        self._kwargs = kwargs

    def __enter__(self) -> object:
        self._driver.session_calls.append(self._kwargs)
        return object()

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeDriver:
    def __init__(self, protocol_version: tuple[int, int]) -> None:
        self._protocol_version = protocol_version
        self.session_calls: list[dict[str, object]] = []

    def get_server_info(self) -> object:
        return SimpleNamespace(protocol_version=self._protocol_version)

    def session(self, **kwargs: object) -> _FakeSessionContext:
        return _FakeSessionContext(self, kwargs)

    def close(self) -> None:
        return None


def _build_store(protocol_version: tuple[int, int], *, database: str = "neo4j") -> Neo4jGraphStore:
    store = Neo4jGraphStore.__new__(Neo4jGraphStore)
    store.config = GraphMemoryConfig(neo4j_database=database)
    store._driver = _FakeDriver(protocol_version)
    store._session_kwargs = store._build_session_kwargs()
    return store


def test_legacy_bolt_protocol_omits_database_name() -> None:
    store = _build_store((3, 0))

    with store._session():
        pass

    assert store._driver.session_calls == [{}]


def test_modern_bolt_protocol_passes_database_name() -> None:
    store = _build_store((5, 8))

    with store._session():
        pass

    assert store._driver.session_calls == [{"database": "neo4j"}]
