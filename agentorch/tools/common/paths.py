from __future__ import annotations

from pathlib import Path

from agentorch.tools.base import ToolError


def resolve_workspace_path(root: Path, path: str | None = None, *, tool_name: str = "filesystem") -> Path:
    candidate = (root / path).resolve() if path else root.resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ToolError(f"Path '{candidate}' is outside the allowed workspace.", tool_name=tool_name) from exc
    return candidate


def is_hidden_path(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)
