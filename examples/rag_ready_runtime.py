import asyncio

from agentorch import Agent, InMemoryKnowledgeBase, OpenAIModel, Runtime
from agentorch.config import RuntimeConfig
from agentorch.knowledge import Document, RetrievalMode


async def main() -> None:
    knowledge_base = InMemoryKnowledgeBase()
    await knowledge_base.ingest(
        [
            Document(
                id="doc-1",
                text="agentorch is a code-first, async-first agent orchestration framework for Python.",
                metadata={"scopes": ["architecture"]},
            ),
            Document(
                id="doc-2",
                text="agentorch supports supervisor delegation, workflow agent nodes, and structured handoff.",
                metadata={"scopes": ["multi-agent"]},
            )
        ]
    )
    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        knowledge_base=knowledge_base,
        config=RuntimeConfig(
            enable_retrieval=True,
            retrieval_mode=RetrievalMode.INLINE,
            default_knowledge_scope=["architecture", "multi-agent"],
            max_retrieved_chunks=3,
        ),
    )
    agent = Agent(runtime=runtime)
    result = await agent.run("What is agentorch designed for?", thread_id="rag-demo")
    print(result.output_text)


if __name__ == "__main__":
    asyncio.run(main())
