from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .types import AgentResult, AggregationResult, TaskPacket


class ExecutionPolicy:
    def __init__(self, *, allow_parallel: bool = False, max_parallel_tasks: int = 1) -> None:
        self.allow_parallel = allow_parallel
        self.max_parallel_tasks = max_parallel_tasks


class BudgetManager:
    def check_task_budget(self, task: TaskPacket) -> None:
        if task.budget is None or task.budget.max_steps is None:
            return
        if task.budget.max_steps <= 0:
            raise RuntimeError(f"Task '{task.task_id}' has exhausted its step budget.")

    def consume_step(self, task: TaskPacket) -> None:
        if task.budget is None or task.budget.max_steps is None:
            return
        task.budget = task.budget.model_copy(update={"max_steps": max(task.budget.max_steps - 1, 0)})


class PermissionManager:
    def can_delegate(self, *, current_depth: int, allowed_depth: int) -> bool:
        return current_depth < allowed_depth

    def ensure_knowledge_scope(self, allowed_scopes: list[str], requested_scopes: list[str]) -> None:
        if not requested_scopes or not allowed_scopes:
            return
        if not set(requested_scopes).issubset(set(allowed_scopes)):
            raise PermissionError("Requested knowledge scope exceeds the agent's allowed scopes.")

    def ensure_tools(self, allowed_tools: list[str], requested_tools: Iterable[str]) -> None:
        if not allowed_tools:
            return
        if any(tool_name not in allowed_tools for tool_name in requested_tools):
            raise PermissionError("Requested tool usage exceeds the agent's allowed tool list.")


class EscalationPolicy:
    def should_escalate(self, results: list[AgentResult]) -> bool:
        return any(result.status.value == "failed" for result in results)


class AggregationPolicy:
    def aggregate(self, results: list[AgentResult]) -> AggregationResult:
        return AggregationResult(
            summary="\n\n".join(f"[{result.agent_name}] {result.summary or result.output_text}" for result in results),
            combined_output={result.agent_name: result.structured_output for result in results},
            citations=[citation for result in results for citation in result.citations],
            metadata={"agent_count": len(results)},
        )


@dataclass
class Coordinator:
    execution_policy: ExecutionPolicy
    budget_manager: BudgetManager
    permission_manager: PermissionManager
    escalation_policy: EscalationPolicy
    aggregation_policy: AggregationPolicy

    @classmethod
    def default(cls) -> "Coordinator":
        return cls(
            execution_policy=ExecutionPolicy(),
            budget_manager=BudgetManager(),
            permission_manager=PermissionManager(),
            escalation_policy=EscalationPolicy(),
            aggregation_policy=AggregationPolicy(),
        )

    def validate_task(self, task: TaskPacket) -> None:
        self.budget_manager.check_task_budget(task)

    def aggregate_results(self, results: list[AgentResult]) -> AggregationResult:
        return self.aggregation_policy.aggregate(results)
