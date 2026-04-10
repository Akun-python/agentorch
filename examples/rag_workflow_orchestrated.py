import asyncio
import json
from pathlib import Path

from agentorch import Agent, Context, Edge, IndexedKnowledgeBase, Node, OpenAIModel, Runtime, Workflow
from agentorch.config import RuntimeConfig
from agentorch.knowledge import RetrievalMode


async def main() -> None:
    resources = Path("examples") / "resources"
    resources.mkdir(exist_ok=True)
    meeting_notes = resources / "meeting_notes.md"
    meeting_notes.write_text("# Meeting Notes\nProduction deployment requires owner approval.\n", encoding="utf-8")

    knowledge_base = IndexedKnowledgeBase()
    await knowledge_base.ingest_paths([meeting_notes], scopes=["ops"])

    runtime = Runtime(
        model=OpenAIModel(model="gpt-4.1"),
        knowledge_base=knowledge_base,
        config=RuntimeConfig(enable_retrieval=True, retrieval_mode=RetrievalMode.EXPLICIT_STEP),
    )
    workflow = Workflow(
        entry_node="retrieve",
        nodes=[
            Node(
                id="retrieve",
                kind="retrieve",
                config={
                    "question": "What is the production deployment restriction?",
                    "must_cover": ["owner approval"],
                    "file_types": [".md"],
                    "output_key": "retrieved",
                },
            ),
            Node(id="aggregate", kind="aggregate", config={"sources": ["retrieved"], "output_key": "combined"}),
        ],
        edges=[Edge(source="retrieve", target="aggregate", kind="success")],
    )
    agent = Agent(runtime=runtime, workflow=workflow)
    result = await agent.run("Orchestrate retrieval first.", thread_id="rag-workflow")
    print(json.dumps(json.loads(result.output_text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
