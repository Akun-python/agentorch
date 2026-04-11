import asyncio
from pathlib import Path

from pydantic import BaseModel

from agentorch import Agent, IndexedKnowledgeBase, OpenAIModel, Runtime, ToolRegistry, tool
from agentorch.config import RuntimeConfig
from agentorch.knowledge import RetrievalMode


class AskRetrieverInput(BaseModel):
    question: str


async def main() -> None:
    resources = Path("examples") / "resources"
    resources.mkdir(exist_ok=True)
    notes = resources / "restrictions.md"
    notes.write_text("# Restrictions\nOwner approval is required before public deployment.\n", encoding="utf-8")

    knowledge_base = IndexedKnowledgeBase()
    await knowledge_base.ingest_paths([notes], scopes=["ops"])

    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        knowledge_base=knowledge_base,
        config=RuntimeConfig(enable_retrieval=True, retrieval_mode=RetrievalMode.POLICY_DRIVEN),
    )

    @tool(description="Ask the deliberative retriever explicitly for evidence.")
    async def ask_retriever(input: AskRetrieverInput):
        return await runtime.tools.execute(
            "deliberative_retrieve",
            {"question": input.question, "knowledge_scope": ["ops"], "file_types": [".md"], "must_cover": ["owner approval"]},
        )

    tools = ToolRegistry()
    tools.register(ask_retriever)
    runtime.tools.register(ask_retriever)
    agent = Agent(runtime=runtime)
    result = await agent.run(
        "Use ask_retriever to inspect the deployment restriction and then summarize it.",
        thread_id="rag-agent-tool",
    )
    print(result.output_text)


if __name__ == "__main__":
    asyncio.run(main())
