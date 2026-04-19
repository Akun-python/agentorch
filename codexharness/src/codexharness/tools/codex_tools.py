from __future__ import annotations

from pydantic import BaseModel

from ..bootstrap import ensure_repo_root_on_path
from ..schemas import StartCodexTaskRequest

ensure_repo_root_on_path()

from agentorch import tool


class StartCodexTaskInput(BaseModel):
    task_id: str
    cwd: str
    prompt: str
    sandbox_mode: str = "workspace-write"
    approval_policy: str = "never"
    skip_git_repo_check: bool = False


class PollCodexSessionInput(BaseModel):
    session_id: str
    after_event_index: int = 0


class StopCodexSessionInput(BaseModel):
    session_id: str


class RestoreCodexSessionInput(BaseModel):
    session_id: str


class SendCodexFollowupInput(BaseModel):
    previous_session_id: str
    prompt: str


class RequestCodexSelfCheckInput(BaseModel):
    session_id: str
    acceptance_criteria: list[str]
    launch: bool = False


def build_codex_tools(session_manager) -> list:
    @tool(description="Start a Codex child task via the exec-json backend.")
    async def start_codex_task(input: StartCodexTaskInput):
        session = await session_manager.start_task(
            StartCodexTaskRequest(
                task_id=input.task_id,
                cwd=input.cwd,
                prompt=input.prompt,
                sandbox_mode=input.sandbox_mode,
                approval_policy=input.approval_policy,
                skip_git_repo_check=input.skip_git_repo_check,
            )
        )
        return session.model_dump(mode="json")

    @tool(description="Poll a Codex child task and retrieve any new structured events.")
    async def poll_codex_session(input: PollCodexSessionInput):
        result = await session_manager.poll_session(input.session_id, after_event_index=input.after_event_index)
        return result.model_dump(mode="json")

    @tool(description="Stop a running Codex child task.")
    async def stop_codex_session(input: StopCodexSessionInput):
        session = await session_manager.stop_session(input.session_id)
        return session.model_dump(mode="json")

    @tool(description="Load the persisted state of a Codex child session.")
    async def restore_codex_session(input: RestoreCodexSessionInput):
        session = await session_manager.restore_session(input.session_id)
        return {
            **session.model_dump(mode="json"),
            "restored": True,
            "resume_strategy": "codex_exec_resume" if session.codex_thread_id else "fresh_followup",
        }

    @tool(description="Start a follow-up Codex task using the previous session's task and workspace.")
    async def send_codex_followup(input: SendCodexFollowupInput):
        session = await session_manager.start_followup(previous_session_id=input.previous_session_id, prompt=input.prompt)
        return session.model_dump(mode="json")

    @tool(description="Generate a self-check prompt for a Codex session and optionally launch it as a follow-up.")
    async def request_codex_self_check(input: RequestCodexSelfCheckInput):
        criteria = "\n".join(f"- {item}" for item in input.acceptance_criteria)
        prompt = (
            "请根据以下验收标准对你刚才完成的任务做自检，并指出未完成项、风险和建议修复步骤：\n"
            f"{criteria}"
        )
        if not input.launch:
            return {"session_id": input.session_id, "launch": False, "self_check_prompt": prompt}
        session = await session_manager.start_followup(previous_session_id=input.session_id, prompt=prompt)
        return {"session_id": session.session_id, "launch": True, "self_check_prompt": prompt}

    return [
        start_codex_task,
        poll_codex_session,
        stop_codex_session,
        restore_codex_session,
        send_codex_followup,
        request_codex_self_check,
    ]
