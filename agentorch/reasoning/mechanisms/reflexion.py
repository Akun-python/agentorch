from __future__ import annotations

from typing import Any

from agentorch.prompts import ReasoningPromptProfile

from ..base import BaseReasoningFramework, ReasoningResult, ReasoningStep, ReflexionConfig


class ReflexionReasoning(BaseReasoningFramework):
    def __init__(self, config: ReflexionConfig | None = None) -> None:
        super().__init__(config or ReflexionConfig())

    async def execute(self, runtime: Any, context) -> ReasoningResult:
        session = self.initialize(context)
        best_output = ""
        for attempt in range(1, self.config.max_attempts + 1):
            attempt_response = await runtime._model_round(
                context,
                reasoning_kind=self.config.kind.value,
                stage="attempt",
                output_instruction=f"Attempt {attempt}: solve the task. If uncertain, say what failed.",
                prompt_profile=ReasoningPromptProfile(kind=self.config.kind.value, instruction="Produce a direct attempt before reflecting."),
            )
            session.trace.steps.append(ReasoningStep(index=len(session.trace.steps) + 1, kind="attempt", content=attempt_response.content, metadata={"attempt": attempt}))
            best_output = attempt_response.content or best_output
            failed = any(token in (attempt_response.content or "").lower() for token in ["fail", "error", "retry"])
            if not failed:
                break
            if attempt >= self.config.max_attempts or not self.config.enable_self_reflection:
                continue
            reflection = await runtime._model_round(
                context,
                reasoning_kind=self.config.kind.value,
                stage="reflection",
                output_instruction=f"Reflect on why attempt {attempt} failed and how to improve it.",
                prompt_profile=ReasoningPromptProfile(kind=self.config.kind.value, instruction="Analyze the failure and propose a better next attempt."),
            )
            session.trace.steps.append(ReasoningStep(index=len(session.trace.steps) + 1, kind="reflection", content=reflection.content, metadata={"attempt": attempt}))
        session.state["final_output"] = best_output
        return self.finalize(session)
