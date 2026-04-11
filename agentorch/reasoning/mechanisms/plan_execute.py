from __future__ import annotations

from typing import Any

from agentorch.prompts import ReasoningPromptProfile

from ..base import BaseReasoningFramework, PlanExecuteConfig, ReasoningResult, ReasoningStep
from ..parsers import extract_plan_steps


class PlanExecuteReasoning(BaseReasoningFramework):
    def __init__(self, config: PlanExecuteConfig | None = None) -> None:
        super().__init__(config or PlanExecuteConfig())

    async def execute(self, runtime: Any, context) -> ReasoningResult:
        session = self.initialize(context)
        plan_response = await runtime._model_round(
            context,
            reasoning_kind=self.config.kind.value,
            stage="plan",
            output_instruction="Create a concise numbered execution plan. One step per line.",
            prompt_profile=ReasoningPromptProfile(
                kind=self.config.kind.value,
                instruction="First produce a step-by-step plan before attempting execution.",
            ),
        )
        plan_steps = extract_plan_steps(plan_response.content)
        session.trace.steps.append(ReasoningStep(index=1, kind="plan", content=plan_response.content, metadata={"steps": plan_steps}))
        final_outputs: list[str] = []
        for idx, plan_step in enumerate(plan_steps[: self.config.max_execution_steps], start=1):
            exec_response = await runtime._model_round(
                context,
                reasoning_kind=self.config.kind.value,
                stage=f"execute_{idx}",
                output_instruction=f"Execute this plan step and report the result: {plan_step}",
                prompt_profile=ReasoningPromptProfile(
                    kind=self.config.kind.value,
                    instruction=f"You are executing plan step {idx}: {plan_step}",
                ),
            )
            session.trace.steps.append(
                ReasoningStep(index=len(session.trace.steps) + 1, kind="execute_step", content=exec_response.content, metadata={"plan_step": plan_step})
            )
            if exec_response.tool_calls:
                for tool_call in exec_response.tool_calls:
                    tool_result = await runtime._execute_tool(tool_call.name, tool_call.arguments, context.envelope)
                    await runtime._append_tool_observation(context, tool_call, tool_result)
                    observation_text, _ = runtime._tool_message_content(tool_result.data, max_chars=1000)
                    session.trace.steps.append(
                        ReasoningStep(index=len(session.trace.steps) + 1, kind="observation", content=observation_text, metadata={"plan_step": plan_step})
                    )
                    final_outputs.append(observation_text)
            if exec_response.content:
                final_outputs.append(exec_response.content)
        if not final_outputs and self.config.allow_replan:
            replan = await runtime._model_round(
                context,
                reasoning_kind=self.config.kind.value,
                stage="replan",
                output_instruction="The original plan failed. Produce a revised plan and answer.",
                prompt_profile=ReasoningPromptProfile(kind=self.config.kind.value, instruction="Reflect on the failed execution and provide a revised answer."),
            )
            session.trace.steps.append(ReasoningStep(index=len(session.trace.steps) + 1, kind="replan", content=replan.content))
            final_outputs.append(replan.content)
        session.state["final_output"] = "\n".join(item for item in final_outputs if item)
        return self.finalize(session)
