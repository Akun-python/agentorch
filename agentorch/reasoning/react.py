from __future__ import annotations

from agentorch.core import ActionType, Decision, ModelResponse

from .base import BasePolicy
from .frameworks import ReactReasoning


class ReactPolicy(BasePolicy):
    async def decide(self, response: ModelResponse) -> Decision:
        if response.tool_calls:
            return Decision(action=ActionType.CALL_TOOL, tool_calls=response.tool_calls)
        if response.finish_reason == "stop" or response.content:
            return Decision(action=ActionType.FINISH, content=response.content)
        return Decision(action=ActionType.RESPOND, content=response.content)


__all__ = ["ReactPolicy", "ReactReasoning"]
