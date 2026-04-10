from __future__ import annotations

from agentorch.sandbox import SandboxManager, SandboxPolicy

from .run_command import create_run_command_tool


def register_execution_tools(registry, sandbox: SandboxManager, *, policy: SandboxPolicy | None = None) -> None:
    registry.register(create_run_command_tool(sandbox, policy=policy))
