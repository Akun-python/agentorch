from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ProjectRepository:
    """负责项目产物落盘。"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.artifacts_root = self.project_root / "artifacts" / "drama_projects"

    def ensure_project_layout(self, project_id: str) -> Path:
        project_dir = self.artifacts_root / project_id
        for relative_dir in (
            ".",
            "roles",
            "roles/images",
            "preproduction",
            "script",
            "storyboard",
            "storyboard/images",
            "video",
            "video/shots",
            "video/transitions",
            "logs",
            "exports",
        ):
            (project_dir / relative_dir).mkdir(parents=True, exist_ok=True)
        return project_dir

    def write_json(self, project_id: str, relative_path: str, payload: Any) -> Path:
        target_path = self.artifacts_root / project_id / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target_path

    def role_image_path(self, project_id: str, index: int) -> Path:
        return self.artifacts_root / project_id / "roles" / "images" / f"role_{index:02d}.png"

    def shot_image_path(self, project_id: str, shot_no: int) -> Path:
        return self.artifacts_root / project_id / "storyboard" / "images" / f"shot_{shot_no:02d}.png"

    def shot_video_path(self, project_id: str, shot_no: int) -> Path:
        return self.artifacts_root / project_id / "video" / "shots" / f"shot_{shot_no:02d}.mp4"

    def transition_image_path(self, project_id: str, transition_no: int) -> Path:
        return self.artifacts_root / project_id / "video" / "transitions" / f"transition_{transition_no:02d}.png"

    def preproduction_path(self, project_id: str, filename: str) -> Path:
        return self.artifacts_root / project_id / "preproduction" / filename

    @staticmethod
    def slugify_project_id(raw_name: str) -> str:
        normalized = re.sub(r"[^0-9A-Za-z_-]+", "-", raw_name.strip()).strip("-").lower()
        return normalized or "drama-project"
