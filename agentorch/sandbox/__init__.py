"""Sandbox abstractions and the default local execution backend.

This package defines structured sandbox results, policies, sessions, and the
manager used to run higher-risk shell or Python actions in isolation.
"""

from .manager import ExecutionRequest, ExecutionResult, LocalSubprocessSandbox, SandboxManager, SandboxPolicy, SandboxSession

__all__ = [
    "ExecutionRequest",
    "ExecutionResult",
    "LocalSubprocessSandbox",
    "SandboxManager",
    "SandboxPolicy",
    "SandboxSession",
]
