from __future__ import annotations

import asyncio
from pathlib import Path

from agentorch.tools.filesystem import create_find_files_tool, create_list_directory_tool, create_search_text_tool


def _run_tool(tool, **kwargs):
    payload = tool.input_model(**kwargs)
    return asyncio.run(tool.run(payload)).data


def test_list_directory_preserves_sorted_prefix_with_max_entries(tmp_path: Path) -> None:
    (tmp_path / "beta").mkdir()
    (tmp_path / "alpha").mkdir()
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("bb", encoding="utf-8")
    (tmp_path / ".hidden.txt").write_text("hidden", encoding="utf-8")

    tool = create_list_directory_tool(tmp_path)
    result = _run_tool(
        tool,
        recursive=False,
        include_hidden=False,
        include_size=True,
        max_entries=3,
    )

    entries = result["entries"]
    assert [entry["path"] for entry in entries] == ["alpha", "beta", "a.txt"]
    assert [entry["type"] for entry in entries] == ["directory", "directory", "file"]
    assert "size_bytes" not in entries[0]
    assert "size_bytes" not in entries[1]
    assert entries[2]["size_bytes"] == 1
    assert result["count"] == 3


def test_find_files_case_sensitive_uses_exact_matching(tmp_path: Path) -> None:
    docs = tmp_path / "Docs"
    docs.mkdir()
    (docs / "caps.TXT").write_text("caps", encoding="utf-8")
    (docs / "lower.txt").write_text("lower", encoding="utf-8")

    tool = create_find_files_tool(tmp_path)

    insensitive = _run_tool(tool, pattern="*.txt", case_sensitive=False)
    sensitive = _run_tool(tool, pattern="*.txt", case_sensitive=True)

    assert insensitive["matches"] == ["Docs/caps.TXT", "Docs/lower.txt"]
    assert sensitive["matches"] == ["Docs/lower.txt"]


def test_search_text_streams_when_context_disabled(tmp_path: Path) -> None:
    sample = tmp_path / "sample.log"
    sample.write_text("line one\nneedle line\nline three\n", encoding="utf-8")

    tool = create_search_text_tool(tmp_path)
    result = _run_tool(
        tool,
        pattern="needle",
        context_lines=0,
        max_results=1,
        regex=False,
    )

    assert result["files_scanned"] == 1
    assert result["truncated"] is True
    assert len(result["matches"]) == 1
    assert result["matches"][0]["line"] == 2
    assert result["matches"][0]["text"] == "needle line"
    assert result["matches"][0]["context"] == ["needle line"]
