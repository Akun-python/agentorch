import asyncio

from agentorch import Agent, OpenAIModel, Runtime, create_reasoning_framework


async def main() -> None:
    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        policy=create_reasoning_framework(
            "plan_execute",
            max_planning_steps=4,
            max_execution_steps=6,
            allow_replan=True,
        ),
    )
    result = await Agent(runtime=runtime).run("设计一个带工具调用的智能体执行流程。", thread_id="reasoning-plan")
    print(result.output_text)
    print(result.reasoning_trace)


if __name__ == "__main__":
    asyncio.run(main())
