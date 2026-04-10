from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class MemoryBackendRegistration:
    kind: str
    component_cls: type | None = None
    factory: Callable[..., Any] | None = None


@dataclass
class MemoryGovernanceRegistration:
    kind: str
    component_cls: type | None = None
    factory: Callable[..., Any] | None = None


@dataclass
class MemoryMechanismRegistration:
    kind: str
    component_cls: type | None = None
    factory: Callable[..., Any] | None = None


@dataclass
class MemoryPolicyRegistration:
    kind: str
    component_cls: type | None = None
    factory: Callable[..., Any] | None = None


class MemoryBackendRegistry:
    def __init__(self) -> None:
        self._items: dict[str, MemoryBackendRegistration] = {}

    def register(self, kind: str, component_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
        if component_cls is None and factory is None:
            raise ValueError("A component class or factory is required.")
        self._items[kind] = MemoryBackendRegistration(kind=kind, component_cls=component_cls, factory=factory)

    def create(self, kind: str, **kwargs: Any) -> Any:
        try:
            registration = self._items[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported memory component kind: {kind}") from exc
        if registration.factory is not None:
            return registration.factory(**kwargs)
        if registration.component_cls is None:
            raise ValueError(f"Memory component '{kind}' has no implementation class.")
        return registration.component_cls(**kwargs)

    def get(self, kind: str) -> MemoryBackendRegistration:
        try:
            return self._items[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported memory component kind: {kind}") from exc

    def list(self) -> list[str]:
        return sorted(self._items.keys())


class MemoryGovernanceRegistry:
    def __init__(self) -> None:
        self._items: dict[str, MemoryGovernanceRegistration] = {}

    def register(self, kind: str, component_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
        if component_cls is None and factory is None:
            raise ValueError("A component class or factory is required.")
        self._items[kind] = MemoryGovernanceRegistration(kind=kind, component_cls=component_cls, factory=factory)

    def create(self, kind: str, **kwargs: Any) -> Any:
        try:
            registration = self._items[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported memory component kind: {kind}") from exc
        if registration.factory is not None:
            return registration.factory(**kwargs)
        if registration.component_cls is None:
            raise ValueError(f"Memory component '{kind}' has no implementation class.")
        return registration.component_cls(**kwargs)

    def get(self, kind: str) -> MemoryGovernanceRegistration:
        try:
            return self._items[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported memory component kind: {kind}") from exc

    def list(self) -> list[str]:
        return sorted(self._items.keys())


class MemoryMechanismRegistry:
    def __init__(self) -> None:
        self._items: dict[str, MemoryMechanismRegistration] = {}

    def register(self, kind: str, component_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
        if component_cls is None and factory is None:
            raise ValueError("A component class or factory is required.")
        self._items[kind] = MemoryMechanismRegistration(kind=kind, component_cls=component_cls, factory=factory)

    def create(self, kind: str, **kwargs: Any) -> Any:
        try:
            registration = self._items[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported memory component kind: {kind}") from exc
        if registration.factory is not None:
            return registration.factory(**kwargs)
        if registration.component_cls is None:
            raise ValueError(f"Memory component '{kind}' has no implementation class.")
        return registration.component_cls(**kwargs)

    def get(self, kind: str) -> MemoryMechanismRegistration:
        try:
            return self._items[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported memory component kind: {kind}") from exc

    def list(self) -> list[str]:
        return sorted(self._items.keys())


memory_backend_registry = MemoryBackendRegistry()
memory_governance_registry = MemoryGovernanceRegistry()
memory_mechanism_registry = MemoryMechanismRegistry()
memory_promotion_policy_registry = MemoryMechanismRegistry()
memory_index_policy_registry = MemoryMechanismRegistry()
memory_recall_policy_registry = MemoryMechanismRegistry()
memory_decay_policy_registry = MemoryMechanismRegistry()


def register_memory_backend(kind: str, backend_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_backend_registry.register(kind, backend_cls, factory=factory)


def create_memory_backend(kind: str, **kwargs: Any) -> Any:
    return memory_backend_registry.create(kind, **kwargs)


def list_memory_backends() -> list[str]:
    return memory_backend_registry.list()


def register_memory_governance(kind: str, governance_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_governance_registry.register(kind, governance_cls, factory=factory)


def create_memory_governance(kind: str, **kwargs: Any) -> Any:
    return memory_governance_registry.create(kind, **kwargs)


def list_memory_governance() -> list[str]:
    return memory_governance_registry.list()


def register_memory_mechanism(kind: str, mechanism_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_mechanism_registry.register(kind, mechanism_cls, factory=factory)


def create_memory_mechanism(kind: str, **kwargs: Any) -> Any:
    return memory_mechanism_registry.create(kind, **kwargs)


def list_memory_mechanisms() -> list[str]:
    return memory_mechanism_registry.list()


def register_memory_promotion_policy(kind: str, policy_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_promotion_policy_registry.register(kind, policy_cls, factory=factory)


def create_memory_promotion_policy(kind: str, **kwargs: Any) -> Any:
    return memory_promotion_policy_registry.create(kind, **kwargs)


def list_memory_promotion_policies() -> list[str]:
    return memory_promotion_policy_registry.list()


def register_memory_index_policy(kind: str, policy_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_index_policy_registry.register(kind, policy_cls, factory=factory)


def create_memory_index_policy(kind: str, **kwargs: Any) -> Any:
    return memory_index_policy_registry.create(kind, **kwargs)


def list_memory_index_policies() -> list[str]:
    return memory_index_policy_registry.list()


def register_memory_recall_policy(kind: str, policy_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_recall_policy_registry.register(kind, policy_cls, factory=factory)


def create_memory_recall_policy(kind: str, **kwargs: Any) -> Any:
    return memory_recall_policy_registry.create(kind, **kwargs)


def list_memory_recall_policies() -> list[str]:
    return memory_recall_policy_registry.list()


def register_memory_decay_policy(kind: str, policy_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_decay_policy_registry.register(kind, policy_cls, factory=factory)


def create_memory_decay_policy(kind: str, **kwargs: Any) -> Any:
    return memory_decay_policy_registry.create(kind, **kwargs)


def list_memory_decay_policies() -> list[str]:
    return memory_decay_policy_registry.list()
