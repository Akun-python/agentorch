from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable

from agentorch._component_registry import ComponentRegistry

from .base import BaseReasoningFramework, ReasoningConfig

ReasoningFactoryFn = Callable[..., BaseReasoningFramework]


@dataclass
class ReasoningRegistration:
    kind: str
    framework_cls: type[BaseReasoningFramework] | None = None
    config_cls: type[ReasoningConfig] | None = None
    factory: ReasoningFactoryFn | None = None


def _create_reasoning_from_registration(
    registration: ReasoningRegistration,
    framework_cls: type[BaseReasoningFramework],
    kwargs: dict[str, Any],
) -> BaseReasoningFramework:
    if registration.config_cls is not None:
        return framework_cls(registration.config_cls(**kwargs))
    return framework_cls(**kwargs)


class ReasoningRegistry(ComponentRegistry[ReasoningRegistration, type[BaseReasoningFramework]]):
    def __init__(self) -> None:
        super().__init__(
            ReasoningRegistration,
            implementation_attr="framework_cls",
            register_error="register_reasoning_framework requires a framework class or factory.",
            unsupported_error="Unsupported reasoning kind: {kind}",
            missing_implementation_error="Reasoning kind '{kind}' has no framework class.",
            creator=_create_reasoning_from_registration,
        )

    def register(
        self,
        kind: str,
        framework_cls: type[BaseReasoningFramework] | None = None,
        *,
        config_cls: type[ReasoningConfig] | None = None,
        factory: ReasoningFactoryFn | None = None,
    ) -> None:
        super().register(kind, framework_cls, factory=factory, config_cls=config_cls)


def _ensure_reasoning_defaults_registered() -> None:
    bootstrap_module = import_module(f"{__package__}.bootstrap")
    bootstrap_module.bootstrap_reasoning_defaults()


default_reasoning_registry = ReasoningRegistry()


def register_reasoning_framework(
    kind: str,
    framework_cls: type[BaseReasoningFramework] | None,
    config_cls: type[ReasoningConfig] | None = None,
    *,
    factory: ReasoningFactoryFn | None = None,
) -> None:
    default_reasoning_registry.register(kind, framework_cls, config_cls=config_cls, factory=factory)


def get_reasoning_framework_registration(kind: str) -> ReasoningRegistration:
    _ensure_reasoning_defaults_registered()
    return default_reasoning_registry.get(kind)


def list_reasoning_frameworks() -> list[str]:
    _ensure_reasoning_defaults_registered()
    return default_reasoning_registry.list()
