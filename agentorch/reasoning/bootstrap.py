from __future__ import annotations

from .base import CotConfig, PlanExecuteConfig, ReactConfig, ReasoningKind, ReflexionConfig, TotConfig
from .mechanisms import CotReasoning, LegacyPolicyAdapter, PlanExecuteReasoning, ReactReasoning, ReflexionReasoning, TotReasoning
from .registry import register_reasoning_framework

_BOOTSTRAPPED = False


def bootstrap_reasoning_defaults(*, force: bool = False) -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED and not force:
        return
    register_reasoning_framework(ReasoningKind.COT.value, CotReasoning, CotConfig)
    register_reasoning_framework(ReasoningKind.REACT.value, ReactReasoning, ReactConfig)
    register_reasoning_framework(ReasoningKind.PLAN_EXECUTE.value, PlanExecuteReasoning, PlanExecuteConfig)
    register_reasoning_framework(ReasoningKind.TOT.value, TotReasoning, TotConfig)
    register_reasoning_framework(ReasoningKind.REFLEXION.value, ReflexionReasoning, ReflexionConfig)
    register_reasoning_framework("legacy_policy", LegacyPolicyAdapter, factory=lambda policy: LegacyPolicyAdapter(policy))
    _BOOTSTRAPPED = True
