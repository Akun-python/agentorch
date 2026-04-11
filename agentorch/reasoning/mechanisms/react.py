from __future__ import annotations

from typing import Any

from agentorch.prompts import ReasoningPromptProfile

from ..base import BaseReasoningFramework, ReactConfig, ReasoningResult, ReasoningStep


class ReactReasoning(BaseReasoningFramework):
    def __init__(self, config: ReactConfig | None = None) -> None:
        super().__init__(config or ReactConfig())

    async def execute(self, runtime: Any, context) -> ReasoningResult:
        session = self.initialize(context)
        for _ in range(self.config.max_steps):
            response = await runtime._model_round(
                context,
                reasoning_kind=self.config.kind.value,
                stage="react",
                output_instruction="Follow a Thought, Action, Observation pattern when tools are useful. Give the final answer when ready.",
                prompt_profile=ReasoningPromptProfile(
                    kind=self.config.kind.value,
                    instruction="Alternate reasoning and actions. If no action is needed, answer directly.",
                ),
            )
            session.trace.steps.append(ReasoningStep(index=len(session.trace.steps) + 1, kind="thought", content=response.content or ""))
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    session.trace.steps.append(
                        ReasoningStep(index=len(session.trace.steps) + 1, kind="action", content=f"{tool_call.name}({tool_call.arguments})")
                    )
                    tool_result = await runtime._execute_tool(tool_call.name, tool_call.arguments, context.envelope)
                    await runtime._append_tool_observation(context, tool_call, tool_result)
                    observation_text, _ = runtime._tool_message_content(tool_result.data, max_chars=1000)
                    session.trace.steps.append(
                        ReasoningStep(index=len(session.trace.steps) + 1, kind="observation", content=observation_text)
                    )
                continue
            session.state["final_output"] = response.content
            break
        return self.finalize(session)
