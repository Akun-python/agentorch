import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentorch import Agent, IndexedKnowledgeBase, OpenAIModel, Runtime, Workflow
from agentorch.workflow import Edge, Node
from agentorch.config import RuntimeConfig


async def main() -> None:
    resources = Path("examples") / "resources"
    resources.mkdir(exist_ok=True)
    note = resources / "workflow_rag.md"
    note.write_text("# Workflow\nOwner approval required before deployment.\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([note], scopes=["ops"])
    runtime = Runtime(model=OpenAIModel(model="gpt-4.1"), knowledge_base=kb, config=RuntimeConfig(enable_retrieval=True))
    workflow = Workflow(
        entry_node="retrieve",
        nodes=[
            Node(id="retrieve", kind="retrieve", config={"rag_mode": "hybrid", "must_cover": ["owner approval"], "output_key": "retrieved"}),
            Node(id="mount", kind="rag_mount", config={"from_variable": "retrieved", "mount_result_to": "variable", "target_key": "mounted"}),
            Node(id="score", kind="rag_evaluate", config={"from_variable": "retrieved", "output_key": "scored"}),
        ],
        edges=[
            Edge(source="retrieve", target="mount", kind="success"),
            Edge(source="mount", target="score", kind="success"),
        ],
    )
    agent = Agent(runtime=runtime, workflow=workflow)
    result = await agent.run("Find deployment restriction", thread_id="workflow-selectable-rag")
    print("Example smoke response:")
    print(json.dumps(json.loads(result.output_text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
