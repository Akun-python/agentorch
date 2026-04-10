from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.tools.base import FunctionTool


class RunCommandInput(BaseModel):
    command: str = Field(description="Shell command to execute.")
    workdir: str | None = Field(default=None, description="Optional working directory inside the allowed sandbox paths.")
    timeout_seconds: float | None = Field(default=None, gt=0, le=300, description="Optional per-call timeout override.")
    check_exit_code: bool = Field(default=False, description="Whether a non-zero exit code should raise a tool error.")
    max_output_chars: int = Field(default=20000, ge=200, le=200000, description="Maximum number of characters to keep from stdout and stderr.")


def create_run_command_tool(
    sandbox: SandboxManager,
    *,
    policy: SandboxPolicy | None = None,
    name: str = "run_command",
    description: str = "Execute a shell command inside the sandbox and return stdout, stderr, exit code, and duration.",
) -> FunctionTool:
    async def run_command(input: RunCommandInput):
        effective_policy = policy or sandbox.policy
        if input.timeout_seconds is not None:
            effective_policy = effective_policy.model_copy(update={"timeout": input.timeout_seconds})
        result = await sandbox.execute(
            "shell",
            input.command,
            workdir=Path(input.workdir) if input.workdir else None,
            policy=effective_policy,
        )
        stdout = result.stdout[: input.max_output_chars]
        stderr = result.stderr[: input.max_output_chars]
        payload = {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": result.exit_code,
            "duration": result.duration,
            "stdout_truncated": len(stdout) < len(result.stdout),
            "stderr_truncated": len(stderr) < len(result.stderr),
        }
        if input.check_exit_code and result.exit_code != 0:
            raise RuntimeError(f"Command exited with code {result.exit_code}: {stderr or stdout}".strip())
        return payload

    return FunctionTool(
        name=name,
        description=description,
        input_model=RunCommandInput,
        func=run_command,
        risk_level="high",
        timeout=policy.timeout if policy is not None else sandbox.policy.timeout,
        retryable=False,
        needs_sandbox=False,
    )
