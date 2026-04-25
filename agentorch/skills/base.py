from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr


_DEFAULT_DISCOVERY_ROOTS = [".claude/skills", ".skills"]
_KEBAB_CASE_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_-]{2,}")


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                values.append(text)
        return values
    text = str(value).strip()
    return [text] if text else []


def normalize_skill_name(value: str) -> str:
    return value.strip().replace("_", "-")


def is_kebab_case(value: str) -> bool:
    return bool(_KEBAB_CASE_PATTERN.fullmatch(value.strip()))


def tokenize_skill_text(value: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(value or "")]


class SkillCatalogConfig(BaseModel):
    discovery_roots: list[str] = Field(default_factory=lambda: list(_DEFAULT_DISCOVERY_ROOTS))
    validation_mode: Literal["lenient", "strict"] = "lenient"
    selection_mode: Literal["model", "hybrid", "rule"] = "model"
    activation_cache: Literal["thread", "run", "off"] = "thread"

    @classmethod
    def from_any(
        cls,
        value: "SkillCatalogConfig | dict[str, object] | None",
        **overrides: object,
    ) -> "SkillCatalogConfig":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        return base.model_copy(update=overrides) if overrides else base


class SkillRoutingConfig(BaseModel):
    mode: str = "progressive"
    max_candidates: int = 4
    max_active: int = 2
    disclosure_level: str = "progressive"
    include_allowed_tools: bool = True
    selection_mode: Literal["model", "hybrid", "rule"] = "model"

    @classmethod
    def from_any(
        cls,
        value: "SkillRoutingConfig | str | dict[str, object] | None",
        **overrides: object,
    ) -> "SkillRoutingConfig":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        elif isinstance(value, str):
            mapping = {
                "off": cls(mode="off", disclosure_level="descriptor", selection_mode="rule"),
                "descriptor": cls(mode="descriptor", disclosure_level="descriptor", selection_mode="rule"),
                "summary": cls(mode="summary", disclosure_level="summary", selection_mode="rule"),
                "progressive": cls(mode="progressive", disclosure_level="progressive", selection_mode="model"),
                "full": cls(mode="full", disclosure_level="full", selection_mode="rule"),
            }
            base = mapping.get(value, cls(mode=value, disclosure_level="progressive"))
        else:
            base = cls.model_validate(value)
        if overrides:
            return base.model_copy(update=overrides)
        return base


class SkillArgumentBundle(BaseModel):
    raw: str = ""
    argv: list[str] = Field(default_factory=list)
    input: dict[str, Any] | None = None

    @classmethod
    def from_any(
        cls,
        value: "SkillArgumentBundle | dict[str, Any] | str | list[str] | tuple[str, ...] | None",
    ) -> "SkillArgumentBundle":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value.model_copy(deep=True)
        if isinstance(value, str):
            return cls(raw=value, argv=[item for item in value.split() if item])
        if isinstance(value, (list, tuple)):
            argv = [str(item) for item in value]
            return cls(raw=" ".join(argv), argv=argv)
        payload = dict(value)
        if payload.get("argv") is not None:
            payload["argv"] = [str(item) for item in payload["argv"]]
        return cls.model_validate(payload)


class SkillRequest(BaseModel):
    enabled: list[str] = Field(default_factory=list)
    disabled: list[str] = Field(default_factory=list)
    force_load: list[str] = Field(default_factory=list)
    arguments: dict[str, SkillArgumentBundle] = Field(default_factory=dict)
    selection_mode: Literal["model", "hybrid", "rule"] | None = None
    skill_routing: SkillRoutingConfig | None = None
    allow_auto_select: bool = True

    @classmethod
    def from_any(
        cls,
        value: "SkillRequest | dict[str, Any] | None",
    ) -> "SkillRequest":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value.model_copy(deep=True)
        payload = dict(value)
        payload["enabled"] = normalize_string_list(payload.get("enabled"))
        payload["disabled"] = normalize_string_list(payload.get("disabled"))
        payload["force_load"] = normalize_string_list(payload.get("force_load"))
        raw_arguments = payload.get("arguments") or {}
        payload["arguments"] = {
            str(skill_name): SkillArgumentBundle.from_any(argument_payload)
            for skill_name, argument_payload in raw_arguments.items()
        }
        if payload.get("skill_routing") is not None:
            payload["skill_routing"] = SkillRoutingConfig.from_any(payload["skill_routing"])
        return cls.model_validate(payload)


class SkillDiagnostic(BaseModel):
    level: Literal["warning", "error"]
    code: str
    message: str
    skill_name: str | None = None
    location: str | None = None


class SkillManifest(BaseModel):
    name: str
    description: str
    license: str | None = None
    compatibility: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    summary: str | None = None

    @property
    def search_terms(self) -> list[str]:
        terms = list(self.triggers)
        terms.extend(tokenize_skill_text(self.description))
        return [term for term in terms if term]


class SkillDescriptor(BaseModel):
    name: str
    description: str = ""
    location: str = ""
    tags: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    compatibility: list[str] = Field(default_factory=list)


class SkillRoute(BaseModel):
    skill_name: str
    score: float = 0.0
    trigger_matches: list[str] = Field(default_factory=list)
    disclosure_level: str = "summary"
    content: str = ""
    allowed_tools: list[str] = Field(default_factory=list)
    descriptor: SkillDescriptor
    rationale: str = ""


class SkillActivation(BaseModel):
    skill_name: str
    location: str
    content: str
    argument_bundle: SkillArgumentBundle = Field(default_factory=SkillArgumentBundle)
    structured_input: dict[str, Any] | None = None
    resource_hints: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)

    def prompt_text(self) -> str:
        parts = [f"Skill: {self.skill_name}", f"Location: {self.location}"]
        if self.argument_bundle.raw:
            parts.append(f"Arguments: {self.argument_bundle.raw}")
        if self.structured_input:
            parts.append(f"Structured Input: {self.structured_input}")
        parts.append(self.content)
        return "\n".join(part for part in parts if part)


class SkillResourceLoad(BaseModel):
    skill_name: str
    location: str
    path: str
    content: str

    def prompt_text(self) -> str:
        return "\n".join(
            [
                f"Skill Resource: {self.skill_name}",
                f"Location: {self.location}",
                f"Path: {self.path}",
                self.content,
            ]
        )


class SkillCatalogEntry(BaseModel):
    manifest: SkillManifest
    root_path: Path
    skill_file: Path
    location: str
    references_path: Path | None = None
    scripts_path: Path | None = None
    assets_path: Path | None = None
    resource_files: list[str] = Field(default_factory=list)
    diagnostics: list[SkillDiagnostic] = Field(default_factory=list)

    def descriptor(self) -> SkillDescriptor:
        return SkillDescriptor(
            name=self.manifest.name,
            description=self.manifest.description,
            location=self.location,
            tags=list(self.manifest.tags),
            triggers=list(self.manifest.triggers),
            allowed_tools=list(self.manifest.allowed_tools),
            compatibility=list(self.manifest.compatibility),
        )

    def summary_text(self, *, first_line: str = "") -> str:
        summary = (self.manifest.summary or self.manifest.description or "").strip()
        parts = [f"Skill: {self.manifest.name}", f"Location: {self.location}"]
        if summary:
            parts.append(f"Purpose: {summary}")
        if first_line and first_line not in summary:
            parts.append(f"Guidance: {first_line}")
        if self.manifest.allowed_tools:
            parts.append(f"Recommended Tools: {', '.join(self.manifest.allowed_tools)}")
        return "\n".join(parts)

    def matched_terms(self, text: str) -> list[str]:
        lowered = text.lower()
        matched = [term for term in self.manifest.triggers if term.lower() in lowered]
        if matched:
            return matched
        seen: set[str] = set()
        for token in self.manifest.search_terms:
            lowered_token = token.lower()
            if lowered_token in seen:
                continue
            if lowered_token in lowered:
                matched.append(token)
                seen.add(lowered_token)
        return matched


class SkillCatalog(BaseModel):
    config: SkillCatalogConfig = Field(default_factory=SkillCatalogConfig)
    entries: list[SkillCatalogEntry] = Field(default_factory=list)
    diagnostics: list[SkillDiagnostic] = Field(default_factory=list)

    def by_name(self) -> dict[str, SkillCatalogEntry]:
        return {entry.manifest.name: entry for entry in self.entries}


class SkillPackage(BaseModel):
    entry: SkillCatalogEntry

    _body_cache: str | None = PrivateAttr(default=None)

    @property
    def manifest(self) -> SkillManifest:
        return self.entry.manifest

    @property
    def root_path(self) -> Path:
        return self.entry.root_path

    @property
    def references_path(self) -> Path | None:
        return self.entry.references_path

    @property
    def scripts_path(self) -> Path | None:
        return self.entry.scripts_path

    @property
    def assets_path(self) -> Path | None:
        return self.entry.assets_path

    @property
    def location(self) -> str:
        return self.entry.location

    def matches(self, text: str) -> bool:
        return bool(self.matched_triggers(text))

    def matched_triggers(self, text: str) -> list[str]:
        return self.entry.matched_terms(text)

    def descriptor(self) -> SkillDescriptor:
        return self.entry.descriptor()

    def summary_text(self) -> str:
        first_line = next((line.strip() for line in self.instructions.splitlines() if line.strip()), "")
        return self.entry.summary_text(first_line=first_line)

    def disclosure(self, level: str) -> str:
        if level == "descriptor":
            descriptor = self.descriptor()
            return "\n".join(
                [
                    f"Skill: {descriptor.name}",
                    f"Location: {descriptor.location}",
                    f"Purpose: {descriptor.description or 'No description provided.'}",
                ]
            )
        if level == "summary":
            return self.summary_text()
        return self.instructions

    @property
    def instructions(self) -> str:
        if self._body_cache is None:
            raw = self.entry.skill_file.read_text(encoding="utf-8")
            parts = raw.split("---", 2)
            self._body_cache = parts[2].strip() if raw.startswith("---") and len(parts) >= 3 else raw.strip()
        return self._body_cache

    def activate(self, arguments: SkillArgumentBundle | dict[str, Any] | str | list[str] | tuple[str, ...] | None = None) -> SkillActivation:
        bundle = SkillArgumentBundle.from_any(arguments)
        content = self._render_arguments(self.instructions, bundle)
        resource_hints = list(self.entry.resource_files[:24])
        return SkillActivation(
            skill_name=self.manifest.name,
            location=self.location,
            content=content,
            argument_bundle=bundle,
            structured_input=bundle.input,
            resource_hints=resource_hints,
            allowed_tools=list(self.manifest.allowed_tools),
        )

    def load_resource(self, relative_path: str) -> SkillResourceLoad:
        cleaned = str(relative_path or "").replace("\\", "/").strip().lstrip("/")
        if not cleaned:
            raise ValueError("Skill resource path is required.")
        if cleaned == "SKILL.md":
            raise ValueError("Use load_skill to activate SKILL.md instructions.")
        root_segment = cleaned.split("/", 1)[0]
        if root_segment not in {"references", "scripts", "assets"}:
            raise ValueError(
                f"Skill resource '{relative_path}' must live under references/, scripts/, or assets/."
            )
        resource_path = (self.root_path / cleaned).resolve()
        root_path = self.root_path.resolve()
        if root_path not in resource_path.parents and resource_path != root_path:
            raise ValueError(f"Skill resource path '{relative_path}' escapes the skill root.")
        allowed_root = (self.root_path / root_segment).resolve()
        if resource_path != allowed_root and allowed_root not in resource_path.parents:
            raise ValueError(
                f"Skill resource '{relative_path}' is outside references/, scripts/, or assets/."
            )
        if not resource_path.exists() or not resource_path.is_file():
            raise FileNotFoundError(f"Skill resource '{relative_path}' was not found.")
        return SkillResourceLoad(
            skill_name=self.manifest.name,
            location=self.location,
            path=cleaned,
            content=resource_path.read_text(encoding="utf-8"),
        )

    def _render_arguments(self, content: str, bundle: SkillArgumentBundle) -> str:
        rendered = content.replace("$ARGUMENTS", bundle.raw)
        for index in range(1, 10):
            replacement = bundle.argv[index - 1] if index - 1 < len(bundle.argv) else ""
            rendered = rendered.replace(f"${index}", replacement)
        return rendered


Skill = SkillPackage
