from __future__ import annotations

from typing import Any

from agentorch.prompts import ReasoningPromptProfile

from ..base import BaseReasoningFramework, CotConfig, ReasoningResult, ReasoningStep


class CotReasoning(BaseReasoningFramework):
    def __init__(self, config: CotConfig | None = None) -> None:
        super().__init__(config or CotConfig())

    async def execute(self, runtime: Any, context) -> ReasoningResult:
        session = self.initialize(context)
        response = await runtime._model_round(
            context,
            reasoning_kind=self.config.kind.value,
            stage="cot",
            output_instruction="Think step by step. Return your full reasoning followed by the final answer.",
            prompt_profile=ReasoningPromptProfile(
                kind=self.config.kind.value,
                instruction="Use an explicit chain of thought with numbered steps before the answer.",
            ),
        )
        session.trace.steps.append(ReasoningStep(index=1, kind="cot", content=response.content or ""))
        if response.tool_calls and not self.config.allow_tool_calls:
            raise RuntimeError("CoT reasoning does not allow tool calls by default.")
        session.state["final_output"] = response.content
        return self.finalize(session)
