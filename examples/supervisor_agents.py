import asyncio

from pydantic import BaseModel

from agentorch import Agent, AgentCapability, AgentRegistry, AgentSpec, OpenAIModel, Runtime, Supervisor, ToolRegistry, tool
from agentorch.config import RuntimeConfig


class EchoInput(BaseModel):
    text: str


@tool(description="Echo a message as structured data.")
async def echo(input: EchoInput):
    return {"echo": input.text}


async def build_specialist(name: str, description: str) -> Agent:
    tools = ToolRegistry()
    tools.register(echo)
    runtime = Runtime(model=OpenAIModel(model="gpt-4.1"), tools=tools)
    agent = Agent(runtime=runtime)
    return agent


async def main() -> None:
    registry = AgentRegistry()
    planner = await build_specialist("planner", "Planning specialist for decomposition tasks")
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            tags=["plan", "task"],
            capabilities=[AgentCapability.PLAN, AgentCapability.TOOL_USE],
            allowed_knowledge_scopes=["planning"],
        ),
        planner,
    )

    supervisor = Supervisor(registry=registry)
    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        agent_registry=registry,
        supervisor=supervisor,
        config=RuntimeConfig(default_knowledge_scope=["planning"]),
    )
    agent = Agent(runtime=runtime)
    result = await agent.run("Please plan the implementation steps for a Python agent framework.", thread_id="supervisor-demo")
    print(result.output_text)


if __name__ == "__main__":
    asyncio.run(main())
