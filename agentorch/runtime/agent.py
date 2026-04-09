from __future__ import annotations

import asyncio
from typing import Any

from agentorch.core import RunResult
from agentorch.workflow import Workflow

from .runtime import Runtime


class Agent:
    def __init__(self, *, runtime: Runtime, workflow: Workflow | None = None) -> None:
        self.runtime = runtime
        self.workflow = workflow

    async def run(self, user_input: str, *, thread_id: str, metadata: dict[str, Any] | None = None) -> RunResult:
        return await self.runtime.run(user_input, thread_id=thread_id, workflow=self.workflow, metadata=metadata)

    def run_sync(self, user_input: str, *, thread_id: str, metadata: dict[str, Any] | None = None) -> RunResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(user_input, thread_id=thread_id, metadata=metadata))
        raise RuntimeError(
            "Agent.run_sync() cannot be used inside a running event loop such as Jupyter. "
            "Use 'await agent.run(...)' in notebooks and async applications."
        )
