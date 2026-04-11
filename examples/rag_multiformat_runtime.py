import asyncio
from pathlib import Path

from agentorch import Agent, IndexedKnowledgeBase, OpenAIModel, Runtime
from agentorch.config import RuntimeConfig
from agentorch.knowledge import RetrievalMode


async def main() -> None:
    resources = Path("examples") / "resources"
    resources.mkdir(exist_ok=True)
    markdown = resources / "deployment_notes.md"
    markdown.write_text("# Deployment\nOwner approval is required before external rollout.\n", encoding="utf-8")
    code = resources / "deploy_guard.py"
    code.write_text("def require_owner_approval():\n    return 'owner approval required'\n", encoding="utf-8")

    knowledge_base = IndexedKnowledgeBase()
    await knowledge_base.ingest_paths([markdown, code], scopes=["ops", "deployment"])

    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        knowledge_base=knowledge_base,
        config=RuntimeConfig(
            enable_retrieval=True,
            retrieval_mode=RetrievalMode.INLINE,
            retrieval_allowed_file_types=[".md", ".py"],
            default_knowledge_scope=["ops", "deployment"],
        ),
    )
    agent = Agent(runtime=runtime)
    result = await agent.run("Find the deployment restriction and summarize the evidence.", thread_id="rag-multiformat-runtime")
    print(result.output_text)


if __name__ == "__main__":
    asyncio.run(main())
