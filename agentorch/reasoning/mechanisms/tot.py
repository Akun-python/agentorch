from __future__ import annotations

from typing import Any

from agentorch.prompts import ReasoningPromptProfile

from ..base import BaseReasoningFramework, ReasoningResult, ReasoningStep, TotConfig
from ..parsers import extract_branches


class TotReasoning(BaseReasoningFramework):
    def __init__(self, config: TotConfig | None = None) -> None:
        super().__init__(config or TotConfig())

    async def execute(self, runtime: Any, context) -> ReasoningResult:
        session = self.initialize(context)
        generated = await runtime._model_round(
            context,
            reasoning_kind=self.config.kind.value,
            stage="branch_generate",
            output_instruction=f"Generate {self.config.branch_factor} candidate solution branches. Return one per line or separated by ||.",
            prompt_profile=ReasoningPromptProfile(kind=self.config.kind.value, instruction="Explore multiple candidate reasoning branches before deciding."),
        )
        branches = extract_branches(generated.content)[: self.config.branch_factor]
        session.trace.steps.append(ReasoningStep(index=1, kind="branch_generate", content=generated.content, metadata={"branches": branches}))
        scored: list[tuple[float, str]] = []
        for branch_id, branch in enumerate(branches, start=1):
            scored_response = await runtime._model_round(
                context,
                reasoning_kind=self.config.kind.value,
                stage="branch_evaluate",
                output_instruction=f"Evaluate this branch from 1 to 10 and explain briefly: {branch}",
                prompt_profile=ReasoningPromptProfile(kind=self.config.kind.value, instruction="Score the branch and briefly justify the score."),
            )
            digits = [token for token in scored_response.content.replace("/", " ").split() if token.isdigit()]
            score = float(digits[0]) if digits else float(max(1, 10 - branch_id))
            scored.append((score, branch))
            session.trace.steps.append(
                ReasoningStep(index=len(session.trace.steps) + 1, kind="branch_score", content=scored_response.content, metadata={"branch_id": branch_id, "branch": branch, "score": score})
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        kept = scored[: self.config.top_k]
        session.trace.steps.append(ReasoningStep(index=len(session.trace.steps) + 1, kind="branch_prune", content=str([branch for _, branch in kept]), metadata={"top_k": self.config.top_k}))
        best_branch = kept[0][1] if kept else context.user_input
        final = await runtime._model_round(
            context,
            reasoning_kind=self.config.kind.value,
            stage="branch_finalize",
            output_instruction=f"Using this best branch, produce the final answer:\n{best_branch}",
            prompt_profile=ReasoningPromptProfile(kind=self.config.kind.value, instruction="Finalize the answer from the strongest branch."),
        )
        session.trace.steps.append(ReasoningStep(index=len(session.trace.steps) + 1, kind="answer", content=final.content, metadata={"best_branch": best_branch}))
        session.state["final_output"] = final.content
        return self.finalize(session)
