from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.sandbox import SandboxManager, SandboxPolicy

from .base import FunctionTool


class PythonInterpreterInput(BaseModel):
    code: str = Field(description="Python code to execute inside the sandbox.")
    workdir: str | None = Field(default=None, description="Optional working directory inside the allowed sandbox paths.")


def create_python_interpreter_tool(
    sandbox: SandboxManager,
    *,
    policy: SandboxPolicy | None = None,
    name: str = "python_interpreter",
    description: str = (
        "Execute Python code in a sandbox and return stdout, stderr, exit code, and duration. "
        "Use this for calculations, data processing, and short scripts."
    ),
) -> FunctionTool:
    async def run_python(input: PythonInterpreterInput):
        result = await sandbox.execute(
            "python",
            input.code,
            workdir=Path(input.workdir) if input.workdir else None,
            policy=policy,
        )
        return result.model_dump()

    return FunctionTool(
        name=name,
        description=description,
        input_model=PythonInterpreterInput,
        func=run_python,
        risk_level="high",
        timeout=policy.timeout if policy is not None else sandbox.policy.timeout,
        retryable=False,
        needs_sandbox=False,
    )
