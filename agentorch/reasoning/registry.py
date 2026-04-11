from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .base import BaseReasoningFramework, ReasoningConfig

ReasoningFactoryFn = Callable[..., BaseReasoningFramework]


@dataclass
class ReasoningRegistration:
    kind: str
    framework_cls: type[BaseReasoningFramework] | None = None
    config_cls: type[ReasoningConfig] | None = None
    factory: ReasoningFactoryFn | None = None


class ReasoningRegistry:
    def __init__(self) -> None:
        self._frameworks: dict[str, ReasoningRegistration] = {}

    def register(
        self,
        kind: str,
        framework_cls: type[BaseReasoningFramework] | None = None,
        *,
        config_cls: type[ReasoningConfig] | None = None,
        factory: ReasoningFactoryFn | None = None,
    ) -> None:
        normalized = str(kind)
        if framework_cls is None and factory is None:
            raise ValueError("register_reasoning_framework requires a framework class or factory.")
        self._frameworks[normalized] = ReasoningRegistration(
            kind=normalized,
            framework_cls=framework_cls,
            config_cls=config_cls,
            factory=factory,
        )

    def get(self, kind: str) -> ReasoningRegistration:
        try:
            return self._frameworks[str(kind)]
        except KeyError as exc:
            raise ValueError(f"Unsupported reasoning kind: {kind}") from exc

    def list(self) -> list[str]:
        return sorted(self._frameworks.keys())

    def create(self, kind: str, **kwargs: Any) -> BaseReasoningFramework:
        registration = self.get(kind)
        if registration.factory is not None:
            return registration.factory(**kwargs)
        if registration.framework_cls is None:
            raise ValueError(f"Reasoning kind '{kind}' has no framework class.")
        if registration.config_cls is not None:
            return registration.framework_cls(registration.config_cls(**kwargs))
        return registration.framework_cls(**kwargs)


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
    return default_reasoning_registry.get(kind)


def list_reasoning_frameworks() -> list[str]:
    return default_reasoning_registry.list()
