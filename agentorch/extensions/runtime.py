from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class RunHookContext:
    runtime: Any
    thread_id: str
    user_input: str
    metadata: dict[str, Any] = field(default_factory=dict)
    workflow: Any | None = None
    envelope: Any | None = None
    result: Any | None = None
    error: Exception | None = None


@dataclass
class SupervisorPlanHookContext:
    runtime: Any
    task: Any
    coordination_policy: Any
    plan: Any | None = None


@dataclass
class HandoffHookContext:
    runtime: Any
    envelope: Any
    invocation: Any
    handoff: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    result: Any | None = None


class RuntimeExtension:
    """Runtime lifecycle extension point.

    Subclasses may override any hook they need. Hooks are intentionally narrow:
    they expose runtime lifecycle boundaries without coupling extensions to
    internal helper methods.
    """

    name: str | None = None

    @property
    def extension_name(self) -> str:
        return self.name or self.__class__.__name__

    async def before_run(self, context: RunHookContext) -> None:
        return None

    async def after_run(self, context: RunHookContext) -> None:
        return None

    async def on_run_error(self, context: RunHookContext) -> None:
        return None

    async def before_supervisor_plan(self, context: SupervisorPlanHookContext) -> None:
        return None

    async def after_supervisor_plan(self, context: SupervisorPlanHookContext) -> None:
        return None

    async def before_handoff(self, context: HandoffHookContext) -> None:
        return None

    async def after_handoff(self, context: HandoffHookContext) -> None:
        return None


class ExtensionManager:
    def __init__(self, extensions: Iterable[RuntimeExtension] | None = None) -> None:
        self._extensions: list[RuntimeExtension] = list(extensions or [])

    @classmethod
    def from_any(cls, value: "ExtensionManager | Iterable[RuntimeExtension] | None") -> "ExtensionManager":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        return cls(value)

    def register(self, extension: RuntimeExtension) -> None:
        self._extensions.append(extension)

    def names(self) -> list[str]:
        return [extension.extension_name for extension in self._extensions]

    async def before_run(self, context: RunHookContext) -> None:
        await self._dispatch("before_run", context)

    async def after_run(self, context: RunHookContext) -> None:
        await self._dispatch("after_run", context)

    async def on_run_error(self, context: RunHookContext) -> None:
        await self._dispatch("on_run_error", context)

    async def before_supervisor_plan(self, context: SupervisorPlanHookContext) -> None:
        await self._dispatch("before_supervisor_plan", context)

    async def after_supervisor_plan(self, context: SupervisorPlanHookContext) -> None:
        await self._dispatch("after_supervisor_plan", context)

    async def before_handoff(self, context: HandoffHookContext) -> None:
        await self._dispatch("before_handoff", context)

    async def after_handoff(self, context: HandoffHookContext) -> None:
        await self._dispatch("after_handoff", context)

    async def aclose(self) -> None:
        for extension in self._extensions:
            close_async = getattr(extension, "aclose", None)
            if callable(close_async):
                outcome = close_async()
                if inspect.isawaitable(outcome):
                    await outcome
                continue
            close = getattr(extension, "close", None)
            if callable(close):
                close()

    async def _dispatch(self, hook_name: str, context: Any) -> None:
        for extension in self._extensions:
            hook = getattr(extension, hook_name, None)
            if not callable(hook):
                continue
            outcome = hook(context)
            if inspect.isawaitable(outcome):
                await outcome
