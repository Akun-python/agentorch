from __future__ import annotations

import inspect
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel

from agentorch.runtime import Agent
from agentorch.runtime.agent import _safe_export, _workflow_summary
from agentorch.workflow import Workflow

from .manager import EvolutionManager
from .types import EvolutionResult, Genome

CandidateT = TypeVar("CandidateT")
CandidateSummarizer = Callable[[CandidateT], Any]


def summarize_evolution_candidate(candidate: Any) -> Any:
    if isinstance(candidate, Agent):
        return candidate.export_blueprint()
    if isinstance(candidate, Workflow):
        return _workflow_summary(candidate)
    if isinstance(candidate, BaseModel):
        return candidate.model_dump()
    if isinstance(candidate, dict):
        return _safe_export(candidate)
    if isinstance(candidate, (list, tuple)):
        return _safe_export(list(candidate))
    if isinstance(candidate, (str, int, float, bool)) or candidate is None:
        return candidate
    return {"type": candidate.__class__.__name__, "repr": repr(candidate)}


class EvolutionSession(Generic[CandidateT]):
    def __init__(
        self,
        *,
        manager: EvolutionManager,
        tasks: list[Any] | None = None,
        candidate_kind: str = "candidate",
        candidate_summarizer: CandidateSummarizer[CandidateT] | None = None,
    ) -> None:
        self.manager = manager
        self.tasks = list(tasks or [])
        self.candidate_kind = candidate_kind
        self.candidate_summarizer = candidate_summarizer or summarize_evolution_candidate

    async def evolve(
        self,
        *,
        tasks: list[Any] | None = None,
        initial_population: list[Genome] | None = None,
    ) -> EvolutionResult:
        resolved_tasks = self.tasks if tasks is None else tasks
        return await self.manager.evolve(tasks=list(resolved_tasks or []), initial_population=initial_population)

    async def build_candidate(self, genome: Genome) -> CandidateT:
        return await self.manager.build_candidate(genome)

    async def build_best_candidate(self, result: EvolutionResult) -> CandidateT:
        return await self.manager.build_best_candidate(result)

    async def summarize_candidate(self, candidate: CandidateT) -> Any:
        value = self.candidate_summarizer(candidate)
        if inspect.isawaitable(value):
            return await value
        return value

    async def summarize_best_candidate(self, result: EvolutionResult) -> Any:
        candidate = await self.build_best_candidate(result)
        return await self.summarize_candidate(candidate)
