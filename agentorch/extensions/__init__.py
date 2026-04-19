"""Runtime extension hooks for integrating framework behavior cleanly."""

from .runtime import ExtensionManager, HandoffHookContext, RunHookContext, RuntimeExtension, SupervisorPlanHookContext

__all__ = [
    "ExtensionManager",
    "HandoffHookContext",
    "RunHookContext",
    "RuntimeExtension",
    "SupervisorPlanHookContext",
]
