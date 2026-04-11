import asyncio
from pathlib import Path

from agentorch.knowledge import IndexedKnowledgeBase


def test_ingest_paths_detects_formats_and_skips_ocrless_pdf(tmp_path: Path):
    asyncio.run(_test_ingest_paths_detects_formats_and_skips_ocrless_pdf(tmp_path))


async def _test_ingest_paths_detects_formats_and_skips_ocrless_pdf(tmp_path: Path):
    txt_path = tmp_path / "note.txt"
    txt_path.write_text("agent orchestration note", encoding="utf-8")
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF")

    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([txt_path, pdf_path], scopes=["ops"])

    assets = kb.list_assets()
    assert len(assets) == 2
    assert any(asset.metadata.get("suffix") == ".txt" for asset in assets)
    pdf_doc = kb.get_document(pdf_path.as_posix())
    assert pdf_doc.metadata["extraction_status"] == "needs_ocr"
