import asyncio

from agentorch import InMemoryKnowledgeBase
from agentorch.knowledge import Document, RAGContextBuilder, RetrievalQuery


def test_knowledge_objects_and_retrieval():
    asyncio.run(_test_knowledge_objects_and_retrieval())


async def _test_knowledge_objects_and_retrieval():
    kb = InMemoryKnowledgeBase()
    await kb.ingest(
        [
            Document(id="doc-1", text="agentorch supports workflows and tools"),
            Document(id="doc-2", text="retrieval systems augment prompts with knowledge"),
        ]
    )
    retriever = kb.get_retriever()
    chunks = await retriever.retrieve(RetrievalQuery(query="agentorch tools", top_k=2))
    assert chunks
    context = RAGContextBuilder().build(chunks)
    assert "agentorch supports workflows and tools" in context
