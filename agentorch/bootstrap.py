from __future__ import annotations

from .evolution.bootstrap import bootstrap_evolution_defaults
from .memory.bootstrap import bootstrap_memory_defaults
from .models.bootstrap import bootstrap_model_defaults
from .reasoning.bootstrap import bootstrap_reasoning_defaults


def bootstrap_defaults(
    *,
    reasoning: bool = True,
    evolution: bool = True,
    memory: bool = True,
    models: bool = True,
    force: bool = False,
) -> None:
    """Explicitly register built-in framework defaults."""

    if reasoning:
        bootstrap_reasoning_defaults(force=force)
    if evolution:
        bootstrap_evolution_defaults(force=force)
    if memory:
        bootstrap_memory_defaults(force=force)
    if models:
        bootstrap_model_defaults(force=force)
