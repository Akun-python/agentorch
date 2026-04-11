"""Reasoning policies and reasoning frameworks.

This package includes both legacy single-decision policies and newer
multi-step reasoning frameworks such as CoT, ReAct, Plan-and-Execute,
ToT, and Reflexion.
"""

from agentorch.agents.supervisor import KeywordSupervisorPolicy, SupervisorPolicy

from .base import (
    AggregationPolicy,
    BasePolicy,
    BaseReasoningFramework,
    CotConfig,
    DelegationPolicy,
    PlanExecuteConfig,
    ReactConfig,
    ReasoningConfig,
    ReasoningKind,
    ReasoningResult,
    ReasoningSession,
    ReasoningSessionContext,
    ReasoningStrategyConfig,
    ReasoningStep,
    ReflectionPolicy,
    ReflexionConfig,
    RetrievalPolicy,
    TotConfig,
)
from .bootstrap import bootstrap_reasoning_defaults
from .factory import ReasoningFactory, create_reasoning_framework
from .mechanisms import CotReasoning, LegacyPolicyAdapter, PlanExecuteReasoning, ReactReasoning, ReflexionReasoning, TotReasoning
from .registry import (
    ReasoningRegistration,
    ReasoningRegistry,
    get_reasoning_framework_registration,
    list_reasoning_frameworks,
    register_reasoning_framework,
)
from .react import ReactPolicy

__all__ = [
    "AggregationPolicy",
    "BasePolicy",
    "BaseReasoningFramework",
    "CotConfig",
    "CotReasoning",
    "DelegationPolicy",
    "KeywordSupervisorPolicy",
    "LegacyPolicyAdapter",
    "PlanExecuteConfig",
    "PlanExecuteReasoning",
    "ReactConfig",
    "ReactPolicy",
    "ReactReasoning",
    "ReasoningConfig",
    "ReasoningFactory",
    "ReasoningRegistration",
    "ReasoningRegistry",
    "ReasoningKind",
    "ReasoningResult",
    "ReasoningSession",
    "ReasoningSessionContext",
    "ReasoningStep",
    "ReasoningStrategyConfig",
    "ReflectionPolicy",
    "ReflexionConfig",
    "ReflexionReasoning",
    "RetrievalPolicy",
    "SupervisorPolicy",
    "TotConfig",
    "TotReasoning",
    "bootstrap_reasoning_defaults",
    "create_reasoning_framework",
    "get_reasoning_framework_registration",
    "list_reasoning_frameworks",
    "register_reasoning_framework",
]
