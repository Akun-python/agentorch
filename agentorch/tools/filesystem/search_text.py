from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import is_hidden_path, is_probably_binary, resolve_workspace_path


class SearchTextInput(BaseModel):
    pattern: str = Field(description="Regex or plain-text pattern to search for.")
    path: str | None = Field(default=None, description="Optional directory path relative to the workspace root.")
    glob: str = Field(default="*", description="File glob filter applied during the search.")
    case_sensitive: bool = Field(default=False, description="Whether the search should be case sensitive.")
    regex: bool = Field(default=False, description="Whether pattern is treated as a regular expression.")
    max_results: int = Field(default=100, ge=1, le=2000, description="Maximum number of matches to return.")
    encoding: str = Field(default="utf-8", description="Text encoding used to read candidate files.")
    include_hidden: bool = Field(default=False, description="Whether hidden files and directories should be searched.")
    context_lines: int = Field(default=0, ge=0, le=5, description="How many surrounding lines to include for each match.")


def create_search_text_tool(workspace_root: str | Path, *, name: str = "search_text") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def search_text(input: SearchTextInput):
        base = resolve_workspace_path(root, input.path, tool_name=name)
        if not base.exists():
            raise ToolError(f"Search path '{base}' does not exist.", tool_name=name)
        candidates = [base] if base.is_file() else [item for item in base.rglob(input.glob) if item.is_file()]
        flags = 0 if input.case_sensitive else re.IGNORECASE
        try:
            needle = re.compile(input.pattern if input.regex else re.escape(input.pattern), flags)
        except re.error as exc:
            raise ToolError(f"Invalid search pattern: {exc}", tool_name=name) from exc
        results = []
        files_scanned = 0
        for file_path in candidates:
            relative_path = file_path.relative_to(root)
            if not input.include_hidden and is_hidden_path(relative_path):
                continue
            if is_probably_binary(file_path):
                continue
            try:
                lines = file_path.read_text(encoding=input.encoding).splitlines()
            except UnicodeDecodeError:
                continue
            files_scanned += 1
            for line_number, line in enumerate(lines, start=1):
                if needle.search(line):
                    context_start = max(0, line_number - 1 - input.context_lines)
                    context_end = min(len(lines), line_number + input.context_lines)
                    results.append(
                        {
                            "path": relative_path.as_posix(),
                            "line": line_number,
                            "text": line,
                            "context": lines[context_start:context_end],
                        }
                    )
                    if len(results) >= input.max_results:
                        return {
                            "matches": results,
                            "files_scanned": files_scanned,
                            "summary": f"Found {len(results)} matches after scanning {files_scanned} file(s).",
                            "truncated": True,
                        }
        return {
            "matches": results,
            "files_scanned": files_scanned,
            "summary": f"Found {len(results)} matches after scanning {files_scanned} file(s).",
            "truncated": False,
        }

    return FunctionTool(
        name=name,
        description="Search for text or regex matches across workspace files.",
        input_model=SearchTextInput,
        func=search_text,
        risk_level="low",
    )
