from pathlib import Path

from agentorch import Agent, OpenAIModel, Runtime, SandboxManager, ToolRegistry, create_python_interpreter_tool
from agentorch.sandbox import SandboxPolicy


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

    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        tools=tools,
        sandbox=sandbox,
    )
    agent = Agent(runtime=runtime)

    result = await agent.run(
        "Use python_interpreter to calculate the first 10 Fibonacci numbers and explain the result briefly.",
        thread_id="code-interpreter-demo",
    )
    print(result.output_text)
    for tool_result in result.tool_results:
        print(tool_result.model_dump())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
