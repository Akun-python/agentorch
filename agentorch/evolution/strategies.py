"""Compatibility bridge for legacy evolution strategy imports.

Real strategy implementations live in `agentorch.evolution.algorithms.genetic`.
Do not add new strategy implementations here.
"""

from .algorithms.genetic import MutationOperator, TopKSelection

__all__ = ["MutationOperator", "TopKSelection"]
