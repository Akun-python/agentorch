from pydantic import BaseModel

from agentorch import Agent, OpenAIModel, Runtime, ToolRegistry, tool


class EchoInput(BaseModel):
    text: str


@tool(description="Echo the input text back as structured output.")
async def echo(input: EchoInput):
    return {"echo": input.text}


async def main() -> None:
    model = OpenAIModel(model="gpt-4.1-mini", api_key="YOUR_API_KEY")
    tools = ToolRegistry()
    tools.register(echo)
    runtime = Runtime(model=model, tools=tools)
    agent = Agent(runtime=runtime)
    result = await agent.run("Say hello and use the echo tool if helpful.", thread_id="example-thread")
    print(result.output_text)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
