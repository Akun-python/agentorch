from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class SkillManifest(BaseModel):
    name: str
    description: str = ""
    triggers: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    manifest: SkillManifest
    root_path: Path
    markdown: str
    references_path: Path | None = None
    scripts_path: Path | None = None
    assets_path: Path | None = None

    def matches(self, text: str) -> bool:
        lowered = text.lower()
        return any(trigger.lower() in lowered for trigger in self.manifest.triggers)

    @property
    def instructions(self) -> str:
        return self.markdown
