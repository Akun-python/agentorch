from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

RegistrationT = TypeVar("RegistrationT")
ImplementationT = TypeVar("ImplementationT")
RegistryFactory = Callable[..., Any]
RegistryCreator = Callable[[RegistrationT, ImplementationT, dict[str, Any]], Any]


class ComponentRegistry(Generic[RegistrationT, ImplementationT]):
    """Shared registry kernel for pluggable framework components."""

    def __init__(
        self,
        registration_cls: type[RegistrationT],
        *,
        implementation_attr: str,
        register_error: str,
        unsupported_error: str,
        missing_implementation_error: str,
        factory_attr: str = "factory",
        creator: RegistryCreator[RegistrationT, ImplementationT] | None = None,
    ) -> None:
        self._registration_cls = registration_cls
        self._implementation_attr = implementation_attr
        self._factory_attr = factory_attr
        self._register_error = register_error
        self._unsupported_error = unsupported_error
        self._missing_implementation_error = missing_implementation_error
        self._creator = creator
        self._items: dict[str, RegistrationT] = {}

    def register(
        self,
        kind: str,
        implementation: ImplementationT | None = None,
        *,
        factory: RegistryFactory | None = None,
        **extra: Any,
    ) -> None:
        normalized = str(kind)
        if implementation is None and factory is None:
            raise ValueError(self._register_error)
        payload = {
            "kind": normalized,
            self._implementation_attr: implementation,
            self._factory_attr: factory,
            **extra,
        }
        self._items[normalized] = self._registration_cls(**payload)

    def get(self, kind: str) -> RegistrationT:
        normalized = str(kind)
        try:
            return self._items[normalized]
        except KeyError as exc:
            raise ValueError(self._unsupported_error.format(kind=kind)) from exc

    def list(self) -> list[str]:
        return sorted(self._items.keys())

    def create(self, kind: str, **kwargs: Any) -> Any:
        registration = self.get(kind)
        factory = getattr(registration, self._factory_attr)
        if factory is not None:
            return factory(**kwargs)
        implementation = getattr(registration, self._implementation_attr)
        if implementation is None:
            raise ValueError(self._missing_implementation_error.format(kind=kind))
        if self._creator is not None:
            return self._creator(registration, implementation, dict(kwargs))
        return implementation(**kwargs)
