from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import (
    Skill,
    SkillActivation,
    SkillArgumentBundle,
    SkillCatalog,
    SkillCatalogEntry,
    SkillDescriptor,
    SkillDiagnostic,
    SkillRequest,
    SkillRoute,
    SkillRoutingConfig,
)
from .loader import SkillLoader


class SkillRegistry:
    def __init__(
        self,
        *,
        catalog: SkillCatalog | None = None,
        diagnostics: list[SkillDiagnostic] | None = None,
    ) -> None:
        self.catalog = catalog or SkillCatalog()
        self.diagnostics = list(diagnostics or self.catalog.diagnostics)
        self._skills: dict[str, Skill] = {}
        for entry in self.catalog.entries:
            self._skills[entry.manifest.name] = Skill(entry=entry)

    def register(self, skill: Skill | SkillCatalogEntry) -> None:
        package = skill if isinstance(skill, Skill) else Skill(entry=skill)
        self._skills[package.manifest.name] = package
        entry_map = self.catalog.by_name()
        entry_map[package.manifest.name] = package.entry
        self.catalog = self.catalog.model_copy(update={"entries": list(entry_map.values())})

    def register_many(self, *skills: Skill | SkillCatalogEntry) -> "SkillRegistry":
        for skill in skills:
            self.register(skill)
        return self

    def register_catalog(self, catalog: SkillCatalog) -> "SkillRegistry":
        for entry in catalog.entries:
            self.register(entry)
        if catalog.diagnostics:
            self.diagnostics.extend(catalog.diagnostics)
            self.catalog = self.catalog.model_copy(update={"diagnostics": list(self.catalog.diagnostics) + list(catalog.diagnostics)})
        return self

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def get_entry(self, name: str) -> SkillCatalogEntry | None:
        skill = self.get(name)
        return skill.entry if skill is not None else None

    def list_entries(self) -> list[SkillCatalogEntry]:
        return [skill.entry for skill in self._skills.values()]

    def list_descriptors(self) -> list[SkillDescriptor]:
        return [skill.descriptor() for skill in self._skills.values()]

    def available_descriptors(
        self,
        *,
        request: SkillRequest | dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        resolved_request = SkillRequest.from_any(request)
        enabled = set(resolved_request.enabled)
        disabled = set(resolved_request.disabled)
        descriptors: list[dict[str, Any]] = []
        for skill in self._skills.values():
            if enabled and skill.manifest.name not in enabled:
                continue
            if skill.manifest.name in disabled:
                continue
            descriptor = skill.descriptor()
            descriptors.append(
                {
                    "name": descriptor.name,
                    "description": descriptor.description,
                    "location": descriptor.location,
                }
            )
        return descriptors

    def select(self, text: str) -> list[Skill]:
        return [skill for skill in self._skills.values() if skill.matches(text)]

    def instructions_for(self, text: str) -> list[str]:
        return [route.content for route in self.route_for(text, config="full")]

    def activate(
        self,
        name: str,
        *,
        arguments: SkillArgumentBundle | dict[str, Any] | str | list[str] | tuple[str, ...] | None = None,
    ) -> SkillActivation:
        skill = self.get(name)
        if skill is None:
            raise KeyError(f"Skill '{name}' is not registered.")
        return skill.activate(arguments)

    def load_resource(self, name: str, relative_path: str):
        skill = self.get(name)
        if skill is None:
            raise KeyError(f"Skill '{name}' is not registered.")
        return skill.load_resource(relative_path)

    def route_for(
        self,
        text: str,
        *,
        config: SkillRoutingConfig | str | dict[str, object] | None = None,
        available_tools: list[str] | None = None,
        candidates: list[str] | None = None,
    ) -> list[SkillRoute]:
        resolved = SkillRoutingConfig.from_any(config)
        if resolved.mode == "off":
            return []
        allowed_candidates = set(candidates or [])
        available = set(available_tools or [])
        routes: list[SkillRoute] = []
        for skill in self._skills.values():
            if allowed_candidates and skill.manifest.name not in allowed_candidates:
                continue
            matched = skill.matched_triggers(text)
            if not matched:
                continue
            overlap = len(available.intersection(skill.manifest.allowed_tools))
            score = float(len(matched) * 10 + overlap)
            if resolved.disclosure_level == "full" or resolved.mode == "full":
                level = "full"
            elif resolved.disclosure_level == "summary" or resolved.mode == "summary":
                level = "summary"
            elif resolved.disclosure_level == "descriptor" or resolved.mode == "descriptor":
                level = "descriptor"
            else:
                level = "descriptor"
            routes.append(
                SkillRoute(
                    skill_name=skill.manifest.name,
                    score=score,
                    trigger_matches=matched,
                    disclosure_level=level,
                    content=skill.disclosure(level),
                    allowed_tools=list(skill.manifest.allowed_tools) if resolved.include_allowed_tools else [],
                    descriptor=skill.descriptor(),
                    rationale=f"matched terms: {', '.join(matched)}",
                )
            )
        routes.sort(key=lambda item: (-item.score, item.skill_name))
        return routes[: resolved.max_active]

    @classmethod
    def from_workspace(
        cls,
        workspace_root: str | Path,
        *,
        loader: SkillLoader | None = None,
        catalog_config: dict[str, Any] | None = None,
    ) -> "SkillRegistry":
        selected_loader = loader or SkillLoader()
        catalog = selected_loader.discover_catalog(workspace_root, config=catalog_config)
        return cls(catalog=catalog, diagnostics=catalog.diagnostics)
