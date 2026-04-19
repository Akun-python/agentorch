"""Multi-agent registration, protocol, governance, and supervisor primitives.

This package makes agents first-class orchestration objects that can be
registered, delegated to, governed, and composed inside workflows.
"""

from .coordinator import AggregationPolicy, BudgetManager, Coordinator, EscalationPolicy, ExecutionPolicy, PermissionManager
from .registry import AgentRegistry, AgentSpec, RegisteredAgent
from .supervisor import (
    AdaptiveTaskPlanner,
    AgentRouteDecision,
    CapabilitySupervisorPolicy,
    DelegationPlan,
    KeywordSupervisorPolicy,
    Supervisor,
    SupervisorPolicy,
)
from .types import (
    AgentCapability,
    AgentInvocation,
    AgentPolicyProfile,
    AgentResult,
    AggregationResult,
    ArtifactRef,
    DelegationRule,
    Handoff,
    ReturnMode,
    SharedNote,
    SharedWorkspace,
    TaskArtifact,
    TaskAssignment,
    TaskBudget,
    TaskConstraint,
    TaskPacket,
    TaskPlan,
    TaskStatus,
    TaskStep,
    WorkspaceRecord,
)

__all__ = [
    "AggregationPolicy",
    "AgentCapability",
    "AgentInvocation",
    "AgentPolicyProfile",
    "AgentRegistry",
    "AgentResult",
    "AgentRouteDecision",
    "AgentSpec",
    "AdaptiveTaskPlanner",
    "AggregationResult",
    "ArtifactRef",
    "BudgetManager",
    "Coordinator",
    "DelegationRule",
    "DelegationPlan",
    "EscalationPolicy",
    "ExecutionPolicy",
    "Handoff",
    "KeywordSupervisorPolicy",
    "PermissionManager",
    "RegisteredAgent",
    "ReturnMode",
    "SharedNote",
    "SharedWorkspace",
    "Supervisor",
    "CapabilitySupervisorPolicy",
    "SupervisorPolicy",
    "TaskArtifact",
    "TaskAssignment",
    "TaskBudget",
    "TaskConstraint",
    "TaskPacket",
    "TaskPlan",
    "TaskStatus",
    "TaskStep",
    "WorkspaceRecord",
]
