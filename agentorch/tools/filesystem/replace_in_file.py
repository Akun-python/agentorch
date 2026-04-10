from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentorch.tools.base import FunctionTool, ToolError
from agentorch.tools.common import atomic_write_text, create_backup_file, read_text_file, resolve_workspace_path


class ReplaceInFileInput(BaseModel):
    path: str = Field(description="File path relative to the workspace root.")
    old_text: str = Field(description="Text to replace.")
    new_text: str = Field(description="Replacement text.")
    encoding: str = Field(default="utf-8", description="Text encoding used to read and write the file.")
    replace_all: bool = Field(default=False, description="Whether to replace all matches instead of only the first match.")
    expected_replacements: int | None = Field(
        default=None,
        ge=0,
        description="Optional guard that requires the number of matches to equal this value before writing.",
    )
    create_backup: bool = Field(default=False, description="Whether to create a .bak backup before modifying the file.")
    dry_run: bool = Field(default=False, description="Whether to preview the replacement result without writing the file.")


def create_replace_in_file_tool(workspace_root: str | Path, *, name: str = "replace_in_file") -> FunctionTool:
    root = Path(workspace_root).resolve()

    async def replace_in_file(input: ReplaceInFileInput):
        target = resolve_workspace_path(root, input.path, tool_name=name)
        if not input.old_text:
            raise ToolError("old_text must not be empty.", tool_name=name)
        content = read_text_file(target, encoding=input.encoding, tool_name=name)
        if input.old_text not in content:
            raise ToolError(f"Target text was not found in '{target}'.", tool_name=name)
        available_replacements = content.count(input.old_text)
        if input.expected_replacements is not None and available_replacements != input.expected_replacements:
            raise ToolError(
                f"Expected {input.expected_replacements} matches in '{target}', but found {available_replacements}.",
                tool_name=name,
            )
        if input.replace_all:
            updated = content.replace(input.old_text, input.new_text)
            replacements = available_replacements
        else:
            updated = content.replace(input.old_text, input.new_text, 1)
            replacements = 1
        backup_path = None
        if not input.dry_run:
            backup_path = create_backup_file(target, root=root, tool_name=name) if input.create_backup else None
            atomic_write_text(target, updated, encoding=input.encoding)
        return {
            "path": target.relative_to(root).as_posix(),
            "replacement_count": replacements,
            "match_count": available_replacements,
            "changed": updated != content,
            "backup_path": backup_path,
            "dry_run": input.dry_run,
        }

    return FunctionTool(
        name=name,
        description="Replace text in a workspace file.",
        input_model=ReplaceInFileInput,
        func=replace_in_file,
        risk_level="medium",
    )
