from __future__ import annotations

import asyncio

from .agents import HarnessAgents
from .config import HarnessConfig
from .progress import NullProgressReporter, ProgressReporter, shorten_text
from .review_tools import ReviewCollector
from .schemas import (
    CodexSessionEvent,
    HarnessRunState,
    HarnessTask,
    PollSessionResult,
    ReviewDecision,
    ReviewDecisionKind,
    SessionStatus,
    StartCodexTaskRequest,
    TaskStatus,
)
from .session_manager import SessionManager
from .state_store import StateStore
from .workspace_manager import WorkspaceManager


class HarnessLoop:
    def __init__(
        self,
        *,
        config: HarnessConfig,
        agents: HarnessAgents,
        state_store: StateStore,
        session_manager: SessionManager,
        workspace_manager: WorkspaceManager,
        review_collector: ReviewCollector,
        progress: ProgressReporter | None = None,
    ) -> None:
        self.config = config
        self.agents = agents
        self.state_store = state_store
        self.session_manager = session_manager
        self.workspace_manager = workspace_manager
        self.review_collector = review_collector
        self.progress = progress or NullProgressReporter()

    async def run(self, *, user_request: str) -> HarnessRunState:
        state = HarnessRunState(user_request=user_request, project_root=str(self.config.project_root))
        self.progress.emit("run.start", f"Starting run for project root {self.config.project_root}", task_id=None, session_id=None)
        return await self._run_from_state(state)

    async def resume(self, *, run_id: str | None = None) -> HarnessRunState:
        target_run_id = run_id or self.state_store.latest_run_id()
        if target_run_id is None:
            raise ValueError("No previous codexharness run was found to resume.")
        state = self.state_store.load_latest_checkpoint(target_run_id) or self.state_store.load_run_state(target_run_id)
        self.progress.emit("run.resume", f"Resuming run {state.run_id}", task_id=None, session_id=None)
        await self._recover_state(state)
        return await self._run_from_state(state)

    async def _run_from_state(self, state: HarnessRunState) -> HarnessRunState:
        self.state_store.save_run_state(state)
        start_round = max(1, state.round_index or 1)
        for round_index in range(start_round, self.config.max_rounds + 1):
            state.round_index = round_index
            self.progress.emit("round.start", f"Round {round_index}/{self.config.max_rounds} started.")
            if not state.tasks:
                self.progress.emit("plan.start", "Requesting task plan from planner.")
                planned = await self.agents.plan(
                    user_request=state.user_request,
                    thread_id=state.thread_id,
                    max_tasks=self.config.planner_max_tasks,
                )
                state.tasks.extend(planned)
                self.progress.emit("plan.done", f"Planner produced {len(planned)} task(s).")
                for task in planned:
                    fallback = task.metadata.get("planner_fallback_reason")
                    details = task.goal
                    if isinstance(fallback, str) and fallback:
                        details += f" | fallback={shorten_text(fallback, limit=120)}"
                    self.progress.emit("task.planned", details, task_id=task.task_id)
                self.state_store.save_run_state(state)

            reviewable = [task for task in state.tasks if task.status == TaskStatus.WAITING_REVIEW]
            if reviewable:
                await self._review_tasks(state, reviewable)

            runnable = await self._prepare_runnable_tasks(state)
            if not runnable:
                self.progress.emit("integrate.start", "No runnable tasks remain; integrating current state.")
                integration = await self.agents.integrate(state=state, thread_id=state.thread_id)
                state.summary = integration.summary
                state.overall_status = "completed" if integration.all_done else "idle"
                self.progress.emit(
                    "integrate.done",
                    f"Integration finished with overall_status={state.overall_status}. {shorten_text(state.summary)}",
                )
                self.state_store.write_checkpoint(state)
                break

            await self._execute_tasks(state, runnable)
            await self._review_tasks(state, runnable)
            self.progress.emit("integrate.start", "Review complete; integrating round result.")
            integration = await self.agents.integrate(state=state, thread_id=state.thread_id)
            state.summary = integration.summary
            self.progress.emit("integrate.done", shorten_text(state.summary) or "Integration completed.")
            if integration.all_done or all(task.status == TaskStatus.COMPLETED for task in state.tasks):
                state.overall_status = "completed"
                self.state_store.write_checkpoint(state)
                break
            self.state_store.write_checkpoint(state)
            self.state_store.save_run_state(state)

        if state.overall_status == "running":
            done = all(task.status == TaskStatus.COMPLETED for task in state.tasks)
            state.overall_status = "completed" if done else "partial"
        self.state_store.save_run_state(state)
        self.progress.emit("run.done", f"Run {state.run_id} finished with overall_status={state.overall_status}.")
        return state

    async def _recover_state(self, state: HarnessRunState) -> None:
        state.overall_status = "running"
        for task in state.tasks:
            if task.status == TaskStatus.PREPARED:
                task.status = TaskStatus.PENDING
                continue
            if task.status == TaskStatus.RUNNING:
                await self._recover_running_task(task, state)
                continue
            if task.status == TaskStatus.WAITING_REVIEW:
                continue
            if task.status == TaskStatus.NEEDS_FOLLOWUP and not task.followup_prompt:
                task.followup_prompt = self._build_resume_prompt(task, "")
        self.state_store.save_run_state(state)

    async def _recover_running_task(self, task: HarnessTask, state: HarnessRunState) -> None:
        if not task.assigned_session_id:
            task.status = TaskStatus.PENDING
            return
        try:
            session = await self.session_manager.restore_session(task.assigned_session_id)
        except FileNotFoundError:
            task.last_error = "Recovered from checkpoint but the previous session state file is missing."
            task.followup_prompt = self._build_resume_prompt(task, "")
            task.status = TaskStatus.NEEDS_FOLLOWUP if task.retry_count < self.config.max_task_retries else TaskStatus.FAILED
            return
        state.sessions[session.session_id] = session
        if session.status in {SessionStatus.FINISHED, SessionStatus.ERRORED, SessionStatus.STOPPED}:
            task.status = TaskStatus.WAITING_REVIEW
            return
        session.status = SessionStatus.LOST
        session.error_message = session.error_message or "Previous Codex child session cannot be reattached after resume."
        self.state_store.save_session_state(session)
        task.last_error = "Recovered from checkpoint; previous Codex child session was marked lost."
        task.followup_prompt = self._build_resume_prompt(task, session.last_message or "")
        task.status = TaskStatus.NEEDS_FOLLOWUP if task.retry_count < self.config.max_task_retries else TaskStatus.FAILED

    async def _prepare_runnable_tasks(self, state: HarnessRunState) -> list[HarnessTask]:
        runnable: list[HarnessTask] = []
        completed = {task.task_id for task in state.tasks if task.status == TaskStatus.COMPLETED}
        for task in state.tasks:
            if task.status not in {TaskStatus.PENDING, TaskStatus.NEEDS_FOLLOWUP}:
                continue
            if any(dep not in completed for dep in task.depends_on):
                continue
            allocation = await self.workspace_manager.prepare(
                task_id=task.task_id,
                mode=self.config.workspace_mode,
                write_scope=task.write_scope,
            )
            task.workspace_path = allocation.workspace_path
            if allocation.branch_name:
                task.metadata["branch_name"] = allocation.branch_name
            task.metadata["workspace_kind"] = allocation.workspace_kind.value
            task.metadata["workspace_baseline"] = await self.review_collector.capture_baseline(task.workspace_path)
            task.status = TaskStatus.PREPARED
            self.progress.emit(
                "task.prepared",
                f"Prepared workspace={task.workspace_path} mode={allocation.workspace_kind.value}",
                task_id=task.task_id,
            )
            runnable.append(task)
        return runnable[: self.config.max_parallel_tasks]

    async def _execute_tasks(self, state: HarnessRunState, tasks: list[HarnessTask]) -> None:
        for task in tasks:
            self.progress.emit("task.start", shorten_text(task.goal), task_id=task.task_id)
            prompt = self._build_task_prompt(task)
            task.latest_prompt = prompt
            if task.followup_prompt and task.assigned_session_id:
                try:
                    session = await self.session_manager.start_followup(
                        previous_session_id=task.assigned_session_id,
                        prompt=prompt,
                    )
                except FileNotFoundError:
                    session = await self.session_manager.start_task(
                        StartCodexTaskRequest(
                            task_id=task.task_id,
                            cwd=task.workspace_path or str(self.config.project_root),
                            prompt=prompt,
                            sandbox_mode=self.config.codex_sandbox,
                            approval_policy=self.config.codex_approval,
                            skip_git_repo_check=self.config.codex_skip_git_repo_check,
                        )
                    )
            else:
                session = await self.session_manager.start_task(
                    StartCodexTaskRequest(
                        task_id=task.task_id,
                        cwd=task.workspace_path or str(self.config.project_root),
                        prompt=prompt,
                        sandbox_mode=self.config.codex_sandbox,
                        approval_policy=self.config.codex_approval,
                        skip_git_repo_check=self.config.codex_skip_git_repo_check,
                    )
                    )
            task.assigned_session_id = session.session_id
            task.status = TaskStatus.RUNNING
            state.sessions[session.session_id] = session
            self.progress.emit(
                "session.start",
                f"Started child Codex session in {task.workspace_path or self.config.project_root}",
                task_id=task.task_id,
                session_id=session.session_id,
            )
        self.state_store.save_run_state(state)

        active = {task.assigned_session_id: 0 for task in tasks if task.assigned_session_id}
        while active:
            finished: list[str] = []
            for session_id, offset in list(active.items()):
                poll = await self.session_manager.poll_session(session_id, after_event_index=offset)
                active[session_id] = poll.next_offset
                state.sessions[session_id] = poll.session
                self._emit_session_progress(state, poll)
                self._sync_task_from_session(state, poll)
                if poll.session.status in {SessionStatus.FINISHED, SessionStatus.ERRORED, SessionStatus.STOPPED}:
                    task = self._find_task_by_session_id(state, session_id)
                    self.progress.emit(
                        "session.done",
                        f"Child Codex session finished with status={poll.session.status.value}",
                        task_id=task.task_id if task is not None else None,
                        session_id=session_id,
                    )
                    finished.append(session_id)
            for session_id in finished:
                active.pop(session_id, None)
            if active:
                await asyncio.sleep(self.config.poll_interval_seconds)
            self.state_store.save_run_state(state)

    async def _review_tasks(self, state: HarnessRunState, tasks: list[HarnessTask]) -> None:
        for task in tasks:
            self.progress.emit("review.start", "Collecting artifacts and reviewing task output.", task_id=task.task_id)
            artifact = await self.review_collector.collect(task)
            decision = self._heuristic_review(task, artifact)
            if decision is None:
                decision = await self.agents.review(task=task, artifact=artifact, thread_id=state.thread_id)
            task.review_summary = decision.summary
            if decision.decision == ReviewDecisionKind.COMPLETED:
                task.status = TaskStatus.COMPLETED
                self.progress.emit("review.done", "Task completed.", task_id=task.task_id)
                continue
            if decision.decision == ReviewDecisionKind.ASK_HUMAN:
                task.status = TaskStatus.BLOCKED
                task.last_error = decision.summary or "Human input required."
                self.progress.emit("review.done", shorten_text(task.last_error), task_id=task.task_id)
                continue
            if task.retry_count < self.config.max_task_retries and decision.next_prompt:
                task.retry_count += 1
                task.followup_prompt = decision.next_prompt
                task.status = TaskStatus.NEEDS_FOLLOWUP
                self.progress.emit(
                    "review.done",
                    f"Task needs follow-up retry #{task.retry_count}. {shorten_text(decision.summary)}",
                    task_id=task.task_id,
                )
                continue
            task.status = TaskStatus.BLOCKED if decision.decision == ReviewDecisionKind.BLOCKED else TaskStatus.FAILED
            task.last_error = "; ".join(decision.gap_list) or decision.summary
            self.progress.emit("review.done", shorten_text(task.last_error), task_id=task.task_id)
        self.state_store.save_run_state(state)

    def _heuristic_review(self, task: HarnessTask, artifact) -> ReviewDecision | None:
        if artifact.changed_files or artifact.output_files:
            return None
        message = "\n".join(part for part in (artifact.last_agent_message, artifact.log_excerpt) if part).lower()
        if not message:
            return None
        readiness_patterns = (
            "ready for the assigned subtask",
            "send the concrete task",
            "please provide the specific task",
            "send the concrete task, target files or paths",
            "请发送具体任务",
            "请直接下发具体任务",
            "把具体子任务发给我",
        )
        if not any(pattern in message for pattern in readiness_patterns):
            return None
        return ReviewDecision(
            task_id=task.task_id,
            decision=ReviewDecisionKind.BLOCKED,
            score=0.0,
            gap_list=["Child Codex only acknowledged the task and produced no concrete changes or artifacts."],
            summary="Child Codex only acknowledged the task; no concrete execution evidence was produced.",
        )

    def _sync_task_from_session(self, state: HarnessRunState, poll: PollSessionResult) -> None:
        for task in state.tasks:
            if task.assigned_session_id != poll.session.session_id:
                continue
            if poll.session.status == SessionStatus.RUNNING:
                task.status = TaskStatus.RUNNING
            elif poll.session.status in {SessionStatus.FINISHED, SessionStatus.ERRORED, SessionStatus.STOPPED}:
                task.status = TaskStatus.WAITING_REVIEW
                if poll.session.status == SessionStatus.ERRORED and poll.session.error_message:
                    task.last_error = poll.session.error_message
            break

    def _emit_session_progress(self, state: HarnessRunState, poll: PollSessionResult) -> None:
        task = self._find_task_by_session_id(state, poll.session.session_id)
        task_id = task.task_id if task is not None else None
        for event in poll.events:
            message = self._describe_session_event(event)
            if not message:
                continue
            self.progress.emit("session.update", message, task_id=task_id, session_id=poll.session.session_id)

    def _describe_session_event(self, event: CodexSessionEvent) -> str | None:
        parsed = event.parsed
        if event.stream == "system":
            if parsed.get("event") == "session_started":
                return "Child Codex process launched."
            if parsed.get("event") == "session_finished":
                return f"Child Codex process exited with code {parsed.get('exit_code')}."
            return None
        if event.stream == "stdout":
            if parsed.get("type") == "thread.started":
                thread_id = parsed.get("thread_id")
                return f"Codex thread started: {thread_id}" if isinstance(thread_id, str) else "Codex thread started."
            if parsed.get("type") == "turn.started":
                return "Codex turn started."
            if parsed.get("type") == "turn.completed":
                usage = parsed.get("usage")
                if isinstance(usage, dict):
                    output_tokens = usage.get("output_tokens")
                    return f"Codex turn completed. output_tokens={output_tokens}"
                return "Codex turn completed."
            if parsed.get("type") == "item.completed":
                item = parsed.get("item")
                if isinstance(item, dict) and item.get("type") == "agent_message":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        return "Agent message: " + shorten_text(text)
            return None
        if event.stream == "stderr":
            raw = (event.raw_text or "").strip()
            if not raw:
                return None
            lower = raw.lower()
            skip_tokens = (
                "failed to remove legacy logs db file",
                "failed to open state db",
                "state db discrepancy",
                "failed to warm featured plugin ids cache",
                "startup remote plugin sync failed",
                "shell snapshot not supported",
                "state db unavailable for memories startup pipeline",
                "ignoring interface.defaultprompt",
            )
            if any(token in lower for token in skip_tokens):
                return None
            important_tokens = ("error", "exception", "timeout", "429", "rate limit", "timed out")
            if any(token in lower for token in important_tokens):
                return "stderr: " + shorten_text(raw)
        return None

    def _find_task_by_session_id(self, state: HarnessRunState, session_id: str) -> HarnessTask | None:
        for task in state.tasks:
            if task.assigned_session_id == session_id:
                return task
        return None

    def _build_task_prompt(self, task: HarnessTask) -> str:
        if task.followup_prompt:
            return task.followup_prompt
        criteria = "\n".join(f"- {item}" for item in task.acceptance_criteria) or "- Complete the task and explain the result."
        constraints = "\n".join(f"- {item}" for item in task.constraints) or "- Avoid unrelated changes."
        write_scope = "\n".join(f"- {item}" for item in task.write_scope) or "- No explicit write scope was provided."
        expected = task.expected_output or "Return a short execution summary, changed files, verification, and remaining risks."
        return (
            "You are a Codex child task executor managed by codexharness.\n"
            "Start working immediately. Do not reply with acknowledgement only, do not ask for the task again, "
            "and do not stop at a restatement.\n\n"
            f"Task goal:\n{task.goal}\n\n"
            f"Acceptance criteria:\n{criteria}\n\n"
            f"Constraints:\n{constraints}\n\n"
            f"Write scope:\n{write_scope}\n\n"
            f"Expected output:\n{expected}\n"
        )

    def _build_resume_prompt(self, task: HarnessTask, last_message: str) -> str:
        previous = f"Last visible output:\n{last_message}\n\n" if last_message else ""
        return (
            "This is a resumed execution. The previous Codex child session could not be reattached after "
            "the outer harness was interrupted. Continue from the current workspace state.\n"
            "Inspect existing progress first, then finish the remaining work. Do not restart unrelated work.\n\n"
            f"{previous}"
            f"{self._build_task_prompt(task)}"
        )
