from __future__ import annotations

from agentorch.sandbox import SandboxManager, SandboxPolicy

from ..code_interpreter import create_python_interpreter_tool
from .run_command import create_run_command_tool


def register_execution_tools(registry, sandbox: SandboxManager, *, policy: SandboxPolicy | None = None) -> None:
    registry.register(create_run_command_tool(sandbox, policy=policy))
    registry.register(create_python_interpreter_tool(sandbox, policy=policy))
