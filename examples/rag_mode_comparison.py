import asyncio
from pathlib import Path

from agentorch import Agent, IndexedKnowledgeBase, OpenAIModel, RagStrategyConfig, Runtime
from agentorch.config import RuntimeConfig


async def main() -> None:
    resources = Path("examples") / "resources"
    resources.mkdir(exist_ok=True)
    note = resources / "rag_mode_notes.md"
    note.write_text("# Release\nOwner approval is required before public rollout.\n", encoding="utf-8")

    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([note], scopes=["ops"])

    for mode in ("classic", "deliberative", "hybrid"):
        runtime = Runtime(
            model=OpenAIModel(model="gpt-4.1"),
            knowledge_base=kb,
            config=RuntimeConfig(enable_retrieval=True, rag_strategy=RagStrategyConfig(mode=mode, file_types=[".md"], knowledge_scope=["ops"])),
        )
        agent = Agent(runtime=runtime)
        result = await agent.run(f"Summarize the release restriction with {mode} rag.", thread_id=f"rag-mode-{mode}")
        print(f"=== {mode} ===")
        print(result.output_text)


if __name__ == "__main__":
    asyncio.run(main())
