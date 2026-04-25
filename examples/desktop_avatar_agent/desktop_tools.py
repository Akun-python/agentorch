from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from agentorch import tool


def _resolve_desktop_item(desktop_root: Path, item_name: str) -> Path:
    target = (desktop_root / item_name).resolve()
    try:
        target.relative_to(desktop_root)
    except ValueError as exc:
        raise ValueError(f"Item '{item_name}' is outside the desktop root.") from exc
    if not target.exists():
        raise FileNotFoundError(f"Desktop item '{item_name}' does not exist.")
    return target


def _scan_desktop(desktop_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in sorted(desktop_root.iterdir(), key=lambda entry: (entry.is_file(), entry.name.lower())):
        if item.name.startswith("."):
            continue
        rows.append(
            {
                "name": item.name,
                "kind": "directory" if item.is_dir() else "file",
                "suffix": item.suffix.lower(),
                "size_bytes": item.stat().st_size if item.is_file() else None,
            }
        )
    return rows


class ListDesktopItemsInput(BaseModel):
    limit: int = Field(default=80, ge=1, le=300, description="Maximum number of desktop items to return.")


class CreateDesktopFolderInput(BaseModel):
    folder_name: str = Field(description="Folder name to create directly on the desktop.")


class MoveDesktopItemsInput(BaseModel):
    item_names: list[str] = Field(description="Desktop item names to move.")
    destination_folder: str = Field(description="Destination folder name on the desktop.")
    create_folder_if_missing: bool = Field(default=True, description="Whether to create the destination folder when it does not exist.")


class PreviewDesktopOrganizationInput(BaseModel):
    limit: int = Field(default=80, ge=1, le=300, description="Maximum number of desktop items to inspect.")


def build_desktop_tools(desktop_root: Path):
    desktop_root = desktop_root.resolve()

    @tool(
        description="List visible files and folders on the Windows desktop. Use this before giving cleanup suggestions.",
        risk_level="low",
    )
    async def list_desktop_items(input: ListDesktopItemsInput):
        items = _scan_desktop(desktop_root)[: input.limit]
        return {
            "desktop_root": str(desktop_root),
            "items": items,
            "count": len(items),
        }

    @tool(
        description="Preview a safe desktop cleanup plan grouped by file type and common categories. Use this before moving multiple items.",
        risk_level="low",
    )
    async def preview_desktop_organization(input: PreviewDesktopOrganizationInput):
        rows = _scan_desktop(desktop_root)[: input.limit]
        categories: dict[str, list[str]] = {
            "documents": [],
            "images": [],
            "archives": [],
            "shortcuts": [],
            "folders": [],
            "other": [],
        }
        for row in rows:
            if row["kind"] == "directory":
                categories["folders"].append(str(row["name"]))
                continue
            suffix = str(row["suffix"])
            if suffix in {".doc", ".docx", ".pdf", ".ppt", ".pptx", ".xls", ".xlsx", ".txt", ".md", ".csv"}:
                categories["documents"].append(str(row["name"]))
            elif suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}:
                categories["images"].append(str(row["name"]))
            elif suffix in {".zip", ".rar", ".7z", ".tar", ".gz"}:
                categories["archives"].append(str(row["name"]))
            elif suffix in {".lnk", ".url"}:
                categories["shortcuts"].append(str(row["name"]))
            else:
                categories["other"].append(str(row["name"]))
        suggestions = []
        for category, names in categories.items():
            if names:
                suggestions.append(
                    {
                        "category": category,
                        "suggested_folder": category.capitalize(),
                        "items": names,
                    }
                )
        return {
            "desktop_root": str(desktop_root),
            "suggestions": suggestions,
            "safety_note": "Preview only. Use move_desktop_items after the user confirms the target folder and selected items.",
        }

    @tool(
        description="Create a folder directly on the Windows desktop.",
        risk_level="medium",
    )
    async def create_desktop_folder(input: CreateDesktopFolderInput):
        folder = (desktop_root / input.folder_name).resolve()
        try:
            folder.relative_to(desktop_root)
        except ValueError as exc:
            raise ValueError("Destination folder must stay inside the desktop root.") from exc
        folder.mkdir(parents=True, exist_ok=True)
        return {
            "created": True,
            "folder": str(folder),
        }

    @tool(
        description="Move selected desktop files or folders into a destination folder on the desktop. Do not use this for bulk moves unless the user has confirmed.",
        risk_level="high",
    )
    async def move_desktop_items(input: MoveDesktopItemsInput):
        destination = (desktop_root / input.destination_folder).resolve()
        try:
            destination.relative_to(desktop_root)
        except ValueError as exc:
            raise ValueError("Destination folder must stay inside the desktop root.") from exc
        if destination.exists() and not destination.is_dir():
            raise ValueError("Destination exists but is not a directory.")
        if not destination.exists():
            if not input.create_folder_if_missing:
                raise FileNotFoundError("Destination folder does not exist.")
            destination.mkdir(parents=True, exist_ok=True)

        moved: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        for item_name in input.item_names:
            source = _resolve_desktop_item(desktop_root, item_name)
            target = destination / source.name
            if target.exists():
                skipped.append({"item": source.name, "reason": "target_already_exists"})
                continue
            shutil.move(str(source), str(target))
            moved.append({"item": source.name, "target": str(target)})

        return {
            "destination": str(destination),
            "moved": moved,
            "skipped": skipped,
            "moved_count": len(moved),
            "skipped_count": len(skipped),
        }

    return [
        list_desktop_items,
        preview_desktop_organization,
        create_desktop_folder,
        move_desktop_items,
    ]
