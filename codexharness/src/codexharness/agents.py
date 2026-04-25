from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from .bootstrap import ensure_repo_root_on_path
from .config import HarnessConfig
from .routing import HarnessSupervisorPolicy
from .schemas import (
    HarnessRunState,
    HarnessTask,
    IntegrationSummary,
    ReviewDecision,
    ReviewDecisionKind,
    TaskArtifactBundle,
    TaskStatus,
)

ensure_repo_root_on_path()

from agentorch import HumanFeedbackManager, OpenAIModel, create_agent, create_multi_agent
from agentorch.memory import MemoryManager


class PlannedTaskList(BaseModel):
    tasks: list[HarnessTask] = Field(default_factory=list)


class HarnessAgents:
    def __init__(self, *, planner, operator, reviewer, integrator, orchestrator) -> None:
        self.planner = planner
        self.operator = operator
        self.reviewer = reviewer
        self.integrator = integrator
        self.orchestrator = orchestrator

    async def plan(self, *, user_request: str, thread_id: str, max_tasks: int) -> list[HarnessTask]:
        prompt = (
            "Break the user request into executable subtasks and return JSON only.\n"
            "The output schema must be:\n"
            '{"tasks":[{"goal":"...","acceptance_criteria":["..."],"constraints":["..."],"expected_output":"...","write_scope":["..."],"depends_on":[]}]}'
            "\n"
            f"Return at most {max_tasks} tasks.\n"
            "Each task must be verifiable, actionable, and tightly scoped.\n"
            f"User request:\n{user_request}"
        )
        try:
            result = await self.planner.run(prompt, thread_id=thread_id)
        except Exception as exc:
            task = HarnessTask(
                goal=user_request,
                acceptance_criteria=["Provide a concrete result and list remaining risks."],
            )
            task.metadata["planner_fallback_reason"] = _format_exception(exc)
            return [task]
        payload = _parse_json_payload(result.output_text)
        if payload is None:
            task = HarnessTask(
                goal=user_request,
                acceptance_criteria=["Provide a concrete result and list remaining risks."],
                review_summary="Planner did not return valid JSON; using a single-task fallback.",
            )
            task.metadata["planner_fallback_reason"] = "invalid_json"
            return [task]
        tasks = PlannedTaskList.model_validate(payload).tasks[:max_tasks]
        if not tasks:
            tasks = [HarnessTask(goal=user_request)]
        return tasks

    async def review(self, *, task: HarnessTask, artifact: TaskArtifactBundle, thread_id: str) -> ReviewDecision:
        prompt = (
            "You are the task reviewer. Judge the task strictly using the goal, acceptance criteria, "
            "and execution evidence. Return JSON only.\n"
            'Output schema: {"decision":"completed|needs_followup|redo|blocked|ask_human","score":0.0,"gap_list":["..."],"evidence":["..."],"next_prompt":"...","needs_human":false,"summary":"..."}\n'
            f"Task goal: {task.goal}\n"
            f"Acceptance criteria: {json.dumps(task.acceptance_criteria, ensure_ascii=False)}\n"
            f"Constraints: {json.dumps(task.constraints, ensure_ascii=False)}\n"
            f"Execution evidence: {artifact.model_dump_json(indent=2)}"
        )
        try:
            result = await self.reviewer.run(prompt, thread_id=thread_id)
        except Exception as exc:
            message = f"Reviewer unavailable; automatic review was skipped. {_format_exception(exc)}"
            return ReviewDecision(
                task_id=task.task_id,
                decision=ReviewDecisionKind.BLOCKED,
                score=0.0,
                gap_list=[message],
                summary=message,
            )
        payload = _parse_json_payload(result.output_text)
        if payload is None:
            return ReviewDecision(
                task_id=task.task_id,
                decision=ReviewDecisionKind.BLOCKED,
                score=0.0,
                gap_list=["Reviewer did not return valid JSON; task cannot be auto-approved safely."],
                evidence=[artifact.last_agent_message] if artifact.last_agent_message else [],
                summary=result.output_text.strip() or "Reviewer did not return valid JSON.",
            )
        payload.setdefault("task_id", task.task_id)
        return ReviewDecision.model_validate(payload)

    async def integrate(self, *, state: HarnessRunState, thread_id: str) -> IntegrationSummary:
        compact = [
            {
                "task_id": task.task_id,
                "goal": task.goal,
                "status": task.status.value,
                "retry_count": task.retry_count,
                "review_summary": task.review_summary,
            }
            for task in state.tasks
        ]
        prompt = (
            "You are the integrator. Decide whether the current round is done and return JSON only.\n"
            'Output schema: {"all_done":false,"summary":"...","next_actions":["..."]}\n'
            f"Current task states: {json.dumps(compact, ensure_ascii=False, indent=2)}"
        )
        try:
            result = await self.integrator.run(prompt, thread_id=thread_id)
        except Exception:
            result = None
        payload = _parse_json_payload(result.output_text) if result is not None else None
        if payload is None:
            return IntegrationSummary(
                all_done=all(task.status == TaskStatus.COMPLETED for task in state.tasks),
                summary=result.output_text.strip() if result is not None else "Integrator unavailable; used status-based fallback.",
            )
        return IntegrationSummary.model_validate(payload)


def build_harness_agents(
    *,
    config: HarnessConfig,
    tools,
    memory: MemoryManager,
    feedback: HumanFeedbackManager | None,
) -> HarnessAgents:
    def new_model() -> OpenAIModel:
        return OpenAIModel(
            model=config.model_name,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.model_timeout,
            max_retries=config.model_max_retries,
        )

    planner = create_agent(
        model=new_model(),
        tools=tools,
        memory=memory,
        human_feedback=feedback,
        name="planner",
        description="Decomposes long-horizon work into executable subtasks.",
        reasoning="plan_execute",
        system_prompt=(
            "You are the planner for codexharness. Break large requests into a small number of "
            "clear, executable, and reviewable subtasks."
        ),
    )
    operator = create_agent(
        model=new_model(),
        tools=tools,
        memory=memory,
        human_feedback=feedback,
        name="codex_operator",
        description="Controls Codex child tasks through structured tools.",
        reasoning="react",
        system_prompt=(
            "You are the codex operator. Start, poll, and follow up on Codex child tasks using tools. "
            "Do not invent execution results."
        ),
    )
    reviewer = create_agent(
        model=new_model(),
        tools=tools,
        memory=memory,
        human_feedback=feedback,
        name="reviewer",
        description="Reviews Codex task outputs against acceptance criteria.",
        reasoning="reflexion",
        system_prompt=(
            "You are the reviewer. Approve tasks only when the evidence clearly satisfies the goal "
            "and acceptance criteria."
        ),
    )
    integrator = create_agent(
        model=new_model(),
        tools=tools,
        memory=memory,
        human_feedback=feedback,
        name="integrator",
        description="Summarizes the round and decides whether to continue.",
        reasoning="plan_execute",
        system_prompt=(
            "You are the integrator. Summarize the round, decide whether another round is needed, "
            "and keep the next step minimal."
        ),
    )
    orchestrator = create_multi_agent(
        model=new_model(),
        agents=[
            {"agent": planner, "name": "planner", "role": "planner", "description": "Task decomposition specialist"},
            {"agent": operator, "name": "codex_operator", "role": "execute", "description": "Codex execution specialist"},
            {"agent": reviewer, "name": "reviewer", "role": "review", "description": "Task review specialist"},
            {"agent": integrator, "name": "integrator", "role": "integrate", "description": "Round integration specialist"},
        ],
        shared_memory=memory,
        human_feedback=feedback,
        routing_policy=HarnessSupervisorPolicy(),
        system_prompt=(
            "You coordinate the planner, codex operator, reviewer, and integrator to complete "
            "codexharness supervisory loops."
        ),
        name="codexharness_orchestrator",
        description="Phase 1 multi-agent orchestrator for Codex supervisory loops.",
    )
    return HarnessAgents(
        planner=planner,
        operator=operator,
        reviewer=reviewer,
        integrator=integrator,
        orchestrator=orchestrator,
    )


def _parse_json_payload(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    candidates = [text]
    if "```json" in text:
        start = text.find("```json") + len("```json")
        end = text.find("```", start)
        if end != -1:
            candidates.append(text[start:end].strip())
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                candidates.append(stripped)
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _format_exception(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {exc}"
