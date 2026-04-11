from pydantic import BaseModel

from agentorch import OpenAIModel, ToolRegistry, create_agent, tool


class EchoInput(BaseModel):
    text: str


@tool(description="Echo the input text back as structured output.")
async def echo(input: EchoInput):
    return {"echo": input.text}


async def main() -> None:
    tools = ToolRegistry()
    tools.register(echo)
    agent = create_agent(
        model=OpenAIModel(model="gpt-4.1-mini", api_key="YOUR_API_KEY"),
        tools=tools,
        system_prompt="You are a careful assistant.",
        name="basic-agent",
    )
    result = await agent.run("Say hello and use the echo tool if helpful.", thread_id="example-thread")
    print(result.output_text)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
