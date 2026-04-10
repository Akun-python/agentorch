from __future__ import annotations

from typing import Any

from .bootstrap import bootstrap_reasoning_defaults
from .base import ReasoningKind
from .registry import default_reasoning_registry


class ReasoningFactory:
    @staticmethod
    def create(kind: str | ReasoningKind, **kwargs: Any):
        bootstrap_reasoning_defaults()
        normalized = kind.value if isinstance(kind, ReasoningKind) else str(kind)
        return default_reasoning_registry.create(normalized, **kwargs)


def create_reasoning_framework(kind: str | ReasoningKind, **kwargs: Any):
    return ReasoningFactory.create(kind, **kwargs)
