import asyncio

from agentorch import Agent, OpenAIModel, Runtime, create_reasoning_framework


async def main() -> None:
    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        policy=create_reasoning_framework("reflexion", max_attempts=3, enable_self_reflection=True),
    )
    result = await Agent(runtime=runtime).run("先给出一个方案，再自我检查并改进。", thread_id="reasoning-reflexion")
    print(result.output_text)
    print(result.reasoning_trace)


if __name__ == "__main__":
    asyncio.run(main())
