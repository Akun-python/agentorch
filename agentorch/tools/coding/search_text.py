from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError

from .common import resolve_workspace_path


class SearchTextInput(BaseModel):
    pattern: str = Field(description="Regex or plain-text pattern to search for.")
    path: str | None = Field(default=None, description="Optional directory path relative to the workspace root.")
    glob: str = Field(default="*", description="File glob filter applied during the search.")
    case_sensitive: bool = Field(default=False, description="Whether the search should be case sensitive.")
    regex: bool = Field(default=False, description="Whether pattern is treated as a regular expression.")
    max_results: int = Field(default=100, ge=1, le=2000, description="Maximum number of matches to return.")
    encoding: str = Field(default="utf-8", description="Text encoding used to read candidate files.")


def create_search_text_tool(workspace_root: str | Path, *, name: str = "search_text") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def search_text(input: SearchTextInput):
        base = resolve_workspace_path(root, input.path, tool_name=name)
        if not base.exists():
            raise ToolError(f"Search path '{base}' does not exist.", tool_name=name)
        if base.is_file():
            candidates = [base]
        else:
            candidates = [item for item in base.rglob(input.glob) if item.is_file()]

        flags = 0 if input.case_sensitive else re.IGNORECASE
        needle = re.compile(input.pattern if input.regex else re.escape(input.pattern), flags)
        results = []
        for file_path in candidates:
            try:
                lines = file_path.read_text(encoding=input.encoding).splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if needle.search(line):
                    results.append(
                        {
                            "path": file_path.relative_to(root).as_posix(),
                            "line": line_number,
                            "text": line,
                        }
                    )
                    if len(results) >= input.max_results:
                        return {"matches": results}
        return {"matches": results}

    return FunctionTool(
        name=name,
        description="Search for text or regex matches across workspace files.",
        input_model=SearchTextInput,
        func=search_text,
        risk_level="low",
    )
