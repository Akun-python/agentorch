from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class SkillRoutingConfig(BaseModel):
    mode: str = "progressive"
    max_candidates: int = 4
    max_active: int = 2
    disclosure_level: str = "progressive"
    include_allowed_tools: bool = True

    @classmethod
    def from_any(cls, value: "SkillRoutingConfig | str | dict[str, object] | None", **overrides: object) -> "SkillRoutingConfig":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        elif isinstance(value, str):
            mapping = {
                "off": cls(mode="off", disclosure_level="descriptor"),
                "descriptor": cls(mode="descriptor", disclosure_level="descriptor"),
                "summary": cls(mode="summary", disclosure_level="summary"),
                "progressive": cls(mode="progressive", disclosure_level="progressive"),
                "full": cls(mode="full", disclosure_level="full"),
            }
            base = mapping.get(value, cls(mode=value, disclosure_level="progressive"))
        else:
            base = cls.model_validate(value)
        if overrides:
            return base.model_copy(update=overrides)
        return base


class SkillManifest(BaseModel):
    name: str
    description: str = ""
    triggers: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None


class SkillDescriptor(BaseModel):
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)


class SkillRoute(BaseModel):
    skill_name: str
    score: float = 0.0
    trigger_matches: list[str] = Field(default_factory=list)
    disclosure_level: str = "summary"
    content: str = ""
    allowed_tools: list[str] = Field(default_factory=list)
    descriptor: SkillDescriptor
    rationale: str = ""


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

    def matched_triggers(self, text: str) -> list[str]:
        lowered = text.lower()
        return [trigger for trigger in self.manifest.triggers if trigger.lower() in lowered]

    def descriptor(self) -> SkillDescriptor:
        return SkillDescriptor(
            name=self.manifest.name,
            description=self.manifest.description,
            tags=list(self.manifest.tags),
            triggers=list(self.manifest.triggers),
            allowed_tools=list(self.manifest.allowed_tools),
        )

    def summary_text(self) -> str:
        summary = (self.manifest.summary or self.manifest.description or "").strip()
        first_line = next((line.strip() for line in self.markdown.splitlines() if line.strip()), "")
        if not summary:
            summary = first_line
        parts = [f"Skill: {self.manifest.name}"]
        if summary:
            parts.append(f"Purpose: {summary}")
        if self.manifest.description and self.manifest.description not in summary:
            parts.append(f"Description: {self.manifest.description}")
        if first_line and first_line not in summary:
            parts.append(f"Guidance: {first_line}")
        if self.manifest.allowed_tools:
            parts.append(f"Recommended Tools: {', '.join(self.manifest.allowed_tools)}")
        return "\n".join(parts)

    def disclosure(self, level: str) -> str:
        if level == "descriptor":
            descriptor = self.descriptor()
            return f"Skill: {descriptor.name}\nPurpose: {descriptor.description or 'No description provided.'}"
        if level == "summary":
            return self.summary_text()
        return self.instructions

    @property
    def instructions(self) -> str:
        return self.markdown
