from __future__ import annotations

from typing import Any

from agentorch.core import ActionType

from ..base import BasePolicy, BaseReasoningFramework, ReactConfig, ReasoningResult, ReasoningStep


class LegacyPolicyAdapter(BaseReasoningFramework):
    def __init__(self, policy: BasePolicy) -> None:
        super().__init__(ReactConfig())
        self.policy = policy

    async def execute(self, runtime: Any, context) -> ReasoningResult:
        session = self.initialize(context)
        for _ in range(self.config.max_steps):
            response = await runtime._model_round(context, reasoning_kind="legacy_policy", stage="legacy")
            session.trace.steps.append(ReasoningStep(index=len(session.trace.steps) + 1, kind="response", content=response.content or ""))
            decision = await self.policy.decide(response)
            if decision.action == ActionType.CALL_TOOL:
                for tool_call in decision.tool_calls:
                    tool_result = await runtime._execute_tool(tool_call.name, tool_call.arguments, context.envelope)
                    await runtime._append_tool_observation(context, tool_call, tool_result)
                    observation_text, _ = runtime._tool_message_content(tool_result.data, max_chars=1000)
                    session.trace.steps.append(ReasoningStep(index=len(session.trace.steps) + 1, kind="observation", content=observation_text))
                continue
            session.state["final_output"] = decision.content or response.content
            break
        return self.finalize(session)
