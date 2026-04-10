from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from agentorch.core import RunResult, RunStreamEvent
from agentorch.parsing import OutputParser, ParsedRunResult, TextParser
from agentorch.workflow import Workflow

from .runtime import Runtime


class Agent:
    @classmethod
    async def acreate(cls, *, workflow: Workflow | None = None, **runtime_kwargs: Any) -> "Agent":
        runtime = await Runtime.acreate(**runtime_kwargs)
        return cls(runtime=runtime, workflow=workflow)

    @classmethod
    def create(cls, *, workflow: Workflow | None = None, **runtime_kwargs: Any) -> "Agent":
        runtime = Runtime.create(**runtime_kwargs)
        return cls(runtime=runtime, workflow=workflow)

    def __init__(self, *, runtime: Runtime, workflow: Workflow | None = None) -> None:
        self.runtime = runtime
        self.workflow = workflow

    def run(
        self,
        user_input: str,
        *,
        thread_id: str,
        metadata: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> Any:
        return self.runtime.run(
            user_input,
            thread_id=thread_id,
            workflow=self.workflow,
            metadata=metadata,
            stream=stream,
        )

    def run_sync(
        self,
        user_input: str,
        *,
        thread_id: str,
        metadata: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> RunResult:
        if stream:
            raise RuntimeError("Agent.run_sync() does not support stream=True. Use 'async for event in agent.run(..., stream=True)' instead.")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(user_input, thread_id=thread_id, metadata=metadata, stream=False))
        raise RuntimeError(
            "Agent.run_sync() cannot be used inside a running event loop such as Jupyter. "
            "Use 'await agent.run(...)' in notebooks and async applications."
        )

    async def run_parsed(
        self,
        user_input: str,
        *,
        thread_id: str,
        parser: OutputParser[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedRunResult[Any]:
        selected_parser = parser or TextParser()
        prompt = selected_parser.with_prompt(user_input)
        raw = await self.run(prompt, thread_id=thread_id, metadata=metadata, stream=False)
        parsed = await selected_parser.parse(raw.output_text)
        return ParsedRunResult(raw=raw, parsed=parsed, parser_name=selected_parser.__class__.__name__)

    def run_parsed_sync(
        self,
        user_input: str,
        *,
        thread_id: str,
        parser: OutputParser[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedRunResult[Any]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_parsed(user_input, thread_id=thread_id, parser=parser, metadata=metadata))
        raise RuntimeError(
            "Agent.run_parsed_sync() cannot be used inside a running event loop such as Jupyter. "
            "Use 'await agent.run_parsed(...)' in notebooks and async applications."
        )
