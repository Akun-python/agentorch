from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from agentorch._component_registry import ComponentRegistry


@dataclass
class KnowledgeRegistration:
    kind: str
    component_cls: type | None = None
    factory: Callable[..., Any] | None = None


class _KnowledgeRegistry(ComponentRegistry[KnowledgeRegistration, type]):
    def __init__(self) -> None:
        super().__init__(
            KnowledgeRegistration,
            implementation_attr="component_cls",
            register_error="A component class or factory is required.",
            unsupported_error="Unsupported knowledge component kind: {kind}",
            missing_implementation_error="Knowledge component '{kind}' has no implementation class.",
        )

    def register(self, kind: str, component_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
        super().register(kind, component_cls, factory=factory)


chunking_registry = _KnowledgeRegistry()
embedding_registry = _KnowledgeRegistry()
reranker_registry = _KnowledgeRegistry()
retriever_registry = _KnowledgeRegistry()
document_adapter_registry = _KnowledgeRegistry()


def register_chunking_strategy(kind: str, strategy_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    chunking_registry.register(kind, strategy_cls, factory=factory)


def create_chunking_strategy(kind: str, **kwargs: Any) -> Any:
    return chunking_registry.create(kind, **kwargs)


def list_chunking_strategies() -> list[str]:
    return chunking_registry.list()


def register_embedding_provider(kind: str, provider_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    embedding_registry.register(kind, provider_cls, factory=factory)


def create_embedding_provider(kind: str, **kwargs: Any) -> Any:
    return embedding_registry.create(kind, **kwargs)


def list_embedding_providers() -> list[str]:
    return embedding_registry.list()


def register_reranker(kind: str, reranker_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    reranker_registry.register(kind, reranker_cls, factory=factory)


def create_reranker(kind: str, **kwargs: Any) -> Any:
    return reranker_registry.create(kind, **kwargs)


def list_rerankers() -> list[str]:
    return reranker_registry.list()


def register_retriever(kind: str, retriever_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    retriever_registry.register(kind, retriever_cls, factory=factory)


def create_retriever(kind: str, **kwargs: Any) -> Any:
    return retriever_registry.create(kind, **kwargs)


def list_retrievers() -> list[str]:
    return retriever_registry.list()


def register_document_adapter(kind: str, adapter_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    document_adapter_registry.register(kind, adapter_cls, factory=factory)


def create_document_adapter(kind: str, **kwargs: Any) -> Any:
    return document_adapter_registry.create(kind, **kwargs)


def list_document_adapters() -> list[str]:
    return document_adapter_registry.list()
