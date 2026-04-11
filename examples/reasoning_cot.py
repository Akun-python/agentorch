import asyncio

from agentorch import Agent, OpenAIModel, Runtime, create_reasoning_framework


async def main() -> None:
    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        policy=create_reasoning_framework("cot", max_steps=6),
    )
    result = await Agent(runtime=runtime).run("逐步解释 agentorch 的作用。", thread_id="reasoning-cot")
    print(result.output_text)
    print(result.reasoning_trace)


if __name__ == "__main__":
    asyncio.run(main())
