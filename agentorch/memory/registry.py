from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable

from agentorch._component_registry import ComponentRegistry


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


class _BaseMemoryRegistry(ComponentRegistry[Any, type]):
    def __init__(self, registration_cls: type[Any]) -> None:
        super().__init__(
            registration_cls,
            implementation_attr="component_cls",
            register_error="A component class or factory is required.",
            unsupported_error="Unsupported memory component kind: {kind}",
            missing_implementation_error="Memory component '{kind}' has no implementation class.",
        )

    def register(self, kind: str, component_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
        super().register(kind, component_cls, factory=factory)


class MemoryBackendRegistry(_BaseMemoryRegistry):
    def __init__(self) -> None:
        super().__init__(MemoryBackendRegistration)


class MemoryGovernanceRegistry(_BaseMemoryRegistry):
    def __init__(self) -> None:
        super().__init__(MemoryGovernanceRegistration)


class MemoryMechanismRegistry(_BaseMemoryRegistry):
    def __init__(self) -> None:
        super().__init__(MemoryMechanismRegistration)


def _ensure_memory_defaults_registered() -> None:
    bootstrap_module = import_module(f"{__package__}.bootstrap")
    bootstrap_module.bootstrap_memory_defaults()


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
    _ensure_memory_defaults_registered()
    return memory_backend_registry.create(kind, **kwargs)


def list_memory_backends() -> list[str]:
    _ensure_memory_defaults_registered()
    return memory_backend_registry.list()


def register_memory_governance(kind: str, governance_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_governance_registry.register(kind, governance_cls, factory=factory)


def create_memory_governance(kind: str, **kwargs: Any) -> Any:
    _ensure_memory_defaults_registered()
    return memory_governance_registry.create(kind, **kwargs)


def list_memory_governance() -> list[str]:
    _ensure_memory_defaults_registered()
    return memory_governance_registry.list()


def register_memory_mechanism(kind: str, mechanism_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_mechanism_registry.register(kind, mechanism_cls, factory=factory)


def create_memory_mechanism(kind: str, **kwargs: Any) -> Any:
    _ensure_memory_defaults_registered()
    return memory_mechanism_registry.create(kind, **kwargs)


def list_memory_mechanisms() -> list[str]:
    _ensure_memory_defaults_registered()
    return memory_mechanism_registry.list()


def register_memory_promotion_policy(kind: str, policy_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_promotion_policy_registry.register(kind, policy_cls, factory=factory)


def create_memory_promotion_policy(kind: str, **kwargs: Any) -> Any:
    _ensure_memory_defaults_registered()
    return memory_promotion_policy_registry.create(kind, **kwargs)


def list_memory_promotion_policies() -> list[str]:
    _ensure_memory_defaults_registered()
    return memory_promotion_policy_registry.list()


def register_memory_index_policy(kind: str, policy_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_index_policy_registry.register(kind, policy_cls, factory=factory)


def create_memory_index_policy(kind: str, **kwargs: Any) -> Any:
    _ensure_memory_defaults_registered()
    return memory_index_policy_registry.create(kind, **kwargs)


def list_memory_index_policies() -> list[str]:
    _ensure_memory_defaults_registered()
    return memory_index_policy_registry.list()


def register_memory_recall_policy(kind: str, policy_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_recall_policy_registry.register(kind, policy_cls, factory=factory)


def create_memory_recall_policy(kind: str, **kwargs: Any) -> Any:
    _ensure_memory_defaults_registered()
    return memory_recall_policy_registry.create(kind, **kwargs)


def list_memory_recall_policies() -> list[str]:
    _ensure_memory_defaults_registered()
    return memory_recall_policy_registry.list()


def register_memory_decay_policy(kind: str, policy_cls: type | None = None, *, factory: Callable[..., Any] | None = None) -> None:
    memory_decay_policy_registry.register(kind, policy_cls, factory=factory)


def create_memory_decay_policy(kind: str, **kwargs: Any) -> Any:
    _ensure_memory_defaults_registered()
    return memory_decay_policy_registry.create(kind, **kwargs)


def list_memory_decay_policies() -> list[str]:
    _ensure_memory_defaults_registered()
    return memory_decay_policy_registry.list()
