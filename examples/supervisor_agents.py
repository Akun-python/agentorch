import asyncio

from pydantic import BaseModel

from agentorch import Agent, AgentCapability, OpenAIModel, ToolRegistry, create_agent, create_multi_agent, tool


class EchoInput(BaseModel):
    text: str


@tool(description="Echo a message as structured data.")
async def echo(input: EchoInput):
    return {"echo": input.text}


async def build_specialist(name: str, description: str) -> Agent:
    tools = ToolRegistry()
    tools.register(echo)
    return create_agent(
        model=OpenAIModel(model="gpt-4.1"),
        tools=tools,
        name=name,
        description=description,
    )


async def main() -> None:
    planner = await build_specialist("planner", "Planning specialist for decomposition tasks")
    agent = create_multi_agent(
        model=OpenAIModel(model="gpt-4.1"),
        agents=[
            {
                "agent": planner,
                "name": "planner",
                "role": "planner",
                "description": "Planning specialist",
                "capabilities": [AgentCapability.PLAN, AgentCapability.TOOL_USE],
                "knowledge_scope": ["planning"],
            }
        ],
        system_prompt="You are a supervisor that delegates planning tasks to the best specialist.",
    )
    result = await agent.run("Please plan the implementation steps for a Python agent framework.", thread_id="supervisor-demo")
    print(result.output_text)


if __name__ == "__main__":
    asyncio.run(main())
