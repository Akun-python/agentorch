from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.sandbox import SandboxManager, SandboxPolicy

from .base import FunctionTool


class PythonInterpreterInput(BaseModel):
    code: str | None = Field(default=None, description="Python code to execute inside the sandbox.")
    workdir: str | None = Field(default=None, description="Optional working directory inside the allowed sandbox paths.")
    session_id: str | None = Field(default=None, description="Optional persistent Python session id for multi-step execution.")
    create_session: bool = Field(default=False, description="Create a persistent Python session and return its session id.")
    close_session: bool = Field(default=False, description="Close an existing persistent Python session.")
    reset_session: bool = Field(default=False, description="Reset an existing persistent Python session while keeping the same session id.")


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
        workdir = Path(input.workdir) if input.workdir else None
        if input.close_session:
            if not input.session_id:
                raise ValueError("python_interpreter requires 'session_id' when 'close_session=True'.")
            await sandbox.close_session(input.session_id)
            return {"session_id": input.session_id, "persistent": True, "closed": True}
        if input.reset_session:
            if not input.session_id:
                raise ValueError("python_interpreter requires 'session_id' when 'reset_session=True'.")
            session = await sandbox.reset_session(input.session_id)
            return {"session_id": session.session_id, "persistent": True, "reset": True, "workdir": session.workdir}

        session_id = input.session_id
        created_session = None
        if input.create_session and session_id is None:
            created_session = await sandbox.create_session(policy=policy, mode="python", workdir=workdir)
            session_id = created_session.session_id
            if input.code is None:
                return {
                    "session_id": created_session.session_id,
                    "persistent": True,
                    "created": True,
                    "workdir": created_session.workdir,
                }

        if input.code is None:
            raise ValueError("python_interpreter requires 'code' unless creating, resetting, or closing a session.")

        result = await sandbox.execute(
            "python",
            input.code,
            workdir=workdir,
            policy=policy,
            session_id=session_id,
        )
        payload = result.model_dump()
        if created_session is not None and payload.get("session_id") is None:
            payload["session_id"] = created_session.session_id
            payload["persistent"] = True
        return payload

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
