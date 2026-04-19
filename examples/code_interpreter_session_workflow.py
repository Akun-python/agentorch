import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentorch import Agent, Runtime, SandboxManager, ToolRegistry, create_python_interpreter_tool
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter
from agentorch.sandbox import SandboxPolicy
from agentorch.workflow import Node, WorkflowBuilder


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="workflow-ok"),
            content="workflow-ok",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


async def main() -> None:
    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[Path.cwd()],
            command_allowlist=["python"],
            timeout=15.0,
        )
    )
    tools = ToolRegistry()
    tools.register(create_python_interpreter_tool(sandbox))

    workflow = (
        WorkflowBuilder(max_steps=8)
        .then(Node.tool("start", "python_interpreter", arguments={"create_session": True, "workdir": str(Path.cwd())}))
        .then(
            Node.tool(
                "seed",
                "python_interpreter",
                arguments={
                    "session_id": {"$from": "start.output.session_id"},
                    "code": "numbers = [1, 1, 2, 3]\nprint(sum(numbers))",
                    "workdir": str(Path.cwd()),
                },
            )
        )
        .then(
            Node.tool(
                "extend",
                "python_interpreter",
                arguments={
                    "session_id": {"$from": "start.output.session_id"},
                    "code": "numbers.append(5)\nprint(sum(numbers))",
                    "workdir": str(Path.cwd()),
                },
            )
        )
        .then(
            Node.tool(
                "close",
                "python_interpreter",
                arguments={"session_id": {"$from": "start.output.session_id"}, "close_session": True},
            )
        )
        .then(Node.aggregate("finalize", sources=["start", "seed", "extend", "close"]))
        .build()
    )

    result = await Agent(runtime=Runtime(model=EchoModel(), tools=tools, sandbox=sandbox), workflow=workflow).run(
        "Run a persistent python session through a workflow.",
        thread_id="code-interpreter-session-demo",
    )
    payload = json.loads(result.output_text)
    combined = payload["combined"]
    summary = {
        "session_id": combined["start"]["output"]["session_id"],
        "seed_stdout": combined["seed"]["output"]["stdout"].strip(),
        "extend_stdout": combined["extend"]["output"]["stdout"].strip(),
        "closed": combined["close"]["output"]["closed"],
    }
    print("=== Code Interpreter Session Workflow ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
