import asyncio

from agentorch import Agent, OpenAIModel, Runtime, create_reasoning_framework


async def main() -> None:
    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        policy=create_reasoning_framework("tot", branch_factor=3, max_depth=3, top_k=2),
    )
    result = await Agent(runtime=runtime).run("比较三种多智能体架构思路并择优。", thread_id="reasoning-tot")
    print(result.output_text)
    print(result.reasoning_trace)


if __name__ == "__main__":
    asyncio.run(main())
