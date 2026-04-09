"""Multi-agent registration, handoff, and supervisor primitives.

This package makes agents first-class orchestration objects that can be
registered, delegated to, and composed inside workflows.
"""

from .registry import AgentRegistry, AgentSpec, RegisteredAgent
from .supervisor import AgentRouteDecision, DelegationPlan, Supervisor, SupervisorPolicy
from .types import AgentInvocation, AgentResult, Handoff, TaskArtifact, TaskConstraint, TaskPacket

__all__ = [
    "AgentInvocation",
    "AgentRegistry",
    "AgentResult",
    "AgentRouteDecision",
    "AgentSpec",
    "DelegationPlan",
    "Handoff",
    "RegisteredAgent",
    "Supervisor",
    "SupervisorPolicy",
    "TaskArtifact",
    "TaskConstraint",
    "TaskPacket",
]
