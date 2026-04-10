import asyncio
import zipfile
from pathlib import Path

from agentorch import InMemoryKnowledgeBase
from agentorch.knowledge import (
    ClassicRetriever,
    Document,
    HybridRetriever,
    IndexedKnowledgeBase,
    KnowledgeAsset,
    RAGContextBuilder,
    RagStrategyConfig,
    RetrievalIntent,
    RetrievalMode,
    RetrievalPlan,
    RetrievalQuery,
    create_rag_retriever,
)


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
    evidence = RAGContextBuilder().build_evidence(chunks)
    assert "agentorch supports workflows and tools" in context
    assert evidence[0].citation.document_id == "doc-1"


def test_knowledge_scope_filtering_and_retrieval_plan():
    asyncio.run(_test_knowledge_scope_filtering_and_retrieval_plan())


async def _test_knowledge_scope_filtering_and_retrieval_plan():
    kb = InMemoryKnowledgeBase()
    await kb.ingest(
        [
            Document(id="doc-1", text="agentorch supports workflows and tools", metadata={"scopes": ["engineering"]}),
            Document(id="doc-2", text="finance report and budget review", metadata={"scopes": ["finance"]}),
        ]
    )
    retriever = kb.get_retriever()
    chunks = await retriever.retrieve(RetrievalQuery(query="budget review", top_k=2, scopes=["finance"]))
    assert len(chunks) == 1
    assert chunks[0].chunk.document_id == "doc-2"
    plan = RetrievalPlan(query="budget review", top_k=2, scopes=["finance"], strategy=RetrievalMode.INLINE.value)
    assert plan.scopes == ["finance"]


def test_multiformat_ingest_paths_and_deliberative_report(tmp_path: Path):
    asyncio.run(_test_multiformat_ingest_paths_and_deliberative_report(tmp_path))


async def _test_multiformat_ingest_paths_and_deliberative_report(tmp_path: Path):
    markdown_path = tmp_path / "design.md"
    markdown_path.write_text("# Workflow\nretrieve node routes evidence\n", encoding="utf-8")
    code_path = tmp_path / "runtime.py"
    code_path.write_text("def retrieve_node():\n    return 'workflow retrieve node'\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([markdown_path, code_path], scopes=["engineering"])
    report = await kb.get_retriever().retrieve_report(
        RetrievalIntent(
            question="where is the workflow retrieve node defined",
            must_cover=["retrieve node"],
            knowledge_scope=["engineering"],
            max_documents=4,
        )
    )
    assert report.evidence
    assert any(item.locator.get("heading_path") or item.locator.get("start_line") for item in report.evidence)
    assert "retrieve node" in report.retrieval_context.lower()
    assert not report.coverage.missing


def test_pdf_and_docx_assets_produce_structured_locators(tmp_path: Path):
    asyncio.run(_test_pdf_and_docx_assets_produce_structured_locators(tmp_path))


async def _test_pdf_and_docx_assets_produce_structured_locators(tmp_path: Path):
    pdf_path = tmp_path / "contract.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
        b"2 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 720 Td (Delivery obligations and liability) Tj ET\nendstream\nendobj\n%%EOF"
    )
    docx_path = tmp_path / "minutes.docx"
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        "<w:p><w:r><w:t>Deployment restrictions for production rollout</w:t></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Owner approval required</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    kb = IndexedKnowledgeBase()
    await kb.ingest_assets(
        [
            KnowledgeAsset(asset_id="contract", source_type="filesystem", path=str(pdf_path), scope_tags=["legal"]),
            KnowledgeAsset(asset_id="minutes", source_type="filesystem", path=str(docx_path), scope_tags=["legal"]),
        ]
    )
    report = await kb.get_retriever().retrieve_report(
        RetrievalIntent(
            question="delivery liability deployment restrictions owner approval",
            must_cover=["delivery", "owner approval"],
            knowledge_scope=["legal"],
            max_documents=6,
        )
    )
    assert any(item.locator.get("page") for item in report.evidence)
    assert any(item.locator.get("paragraph_index") is not None or item.locator.get("table_index") is not None for item in report.evidence)


def test_classic_and_hybrid_retrievers_return_reports(tmp_path: Path):
    asyncio.run(_test_classic_and_hybrid_retrievers_return_reports(tmp_path))


async def _test_classic_and_hybrid_retrievers_return_reports(tmp_path: Path):
    md_path = tmp_path / "guide.md"
    md_path.write_text("# Deploy\nowner approval required before release\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([md_path], scopes=["ops"])
    classic = ClassicRetriever(kb)
    hybrid = HybridRetriever(kb)
    classic_report = await classic.retrieve_report(RetrievalIntent(question="owner approval release", max_documents=3, rag_mode="classic"))
    hybrid_report = await hybrid.retrieve_report(RetrievalIntent(question="owner approval release", must_cover=["owner approval"], max_documents=3, rag_mode="hybrid"))
    assert classic_report.evidence
    assert classic_report.plan[0].step_type == "classic_retrieve"
    assert hybrid_report.evidence
    assert any(step.step_type == "deliberative_refine" for step in hybrid_report.plan)


def test_create_rag_retriever_selects_mode_specific_backend():
    kb = IndexedKnowledgeBase()

    classic = create_rag_retriever(kb, RagStrategyConfig(mode="classic"))
    hybrid = create_rag_retriever(kb, RagStrategyConfig(mode="hybrid"))
    deliberative = create_rag_retriever(kb, RagStrategyConfig(mode="deliberative"))
    default_mode = create_rag_retriever(kb)

    assert isinstance(classic, ClassicRetriever)
    assert isinstance(hybrid, HybridRetriever)
    assert type(deliberative).__name__ == "DeliberativeRetriever"
    assert type(default_mode).__name__ == "DeliberativeRetriever"
