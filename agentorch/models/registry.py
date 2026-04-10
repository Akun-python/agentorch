from __future__ import annotations

from collections.abc import Callable

from agentorch.config import ModelConfig

from .base import BaseModelAdapter

ModelFactory = Callable[[ModelConfig], BaseModelAdapter]

_MODEL_FACTORIES: dict[str, ModelFactory] = {}


def register_model_provider(name: str, factory: ModelFactory) -> None:
    _MODEL_FACTORIES[name] = factory


def list_model_providers() -> list[str]:
    return sorted(_MODEL_FACTORIES)


def create_model_adapter(config: ModelConfig | dict[str, object] | str | None = None, **overrides: object) -> BaseModelAdapter:
    resolved = ModelConfig.from_any(config, **overrides)
    factory = _MODEL_FACTORIES.get(resolved.provider)
    if factory is None:
        available = ", ".join(list_model_providers()) or "<none>"
        raise KeyError(f"Unknown model provider '{resolved.provider}'. Available providers: {available}")
    return factory(resolved)
