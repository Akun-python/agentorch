from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .base import (
    Skill,
    SkillCatalog,
    SkillCatalogConfig,
    SkillCatalogEntry,
    SkillDiagnostic,
    SkillManifest,
    is_kebab_case,
    normalize_string_list,
)


class SkillLoader:
    def load(self, path: str | Path) -> Skill:
        root = Path(path)
        entry, diagnostics = self._load_entry(root, location=root.as_posix(), config=SkillCatalogConfig())
        if entry is None:
            messages = "; ".join(diagnostic.message for diagnostic in diagnostics) or f"Failed to load skill at {root}"
            raise ValueError(messages)
        return Skill(entry=entry)

    def load_entry(self, path: str | Path, *, location: str | None = None) -> SkillCatalogEntry:
        root = Path(path)
        entry, diagnostics = self._load_entry(root, location=location or root.as_posix(), config=SkillCatalogConfig())
        if entry is None:
            messages = "; ".join(diagnostic.message for diagnostic in diagnostics) or f"Failed to load skill at {root}"
            raise ValueError(messages)
        return entry

    def discover(self, root: str | Path) -> list[Skill]:
        base = Path(root)
        if not base.exists() or not base.is_dir():
            return []
        skills: list[Skill] = []
        for skill_root in self._iter_skill_directories(base):
            entry, _ = self._load_entry(skill_root, location=skill_root.as_posix(), config=SkillCatalogConfig())
            if entry is not None:
                skills.append(Skill(entry=entry))
        return skills

    def discover_catalog(
        self,
        workspace_root: str | Path,
        *,
        config: SkillCatalogConfig | dict[str, Any] | None = None,
    ) -> SkillCatalog:
        resolved_config = SkillCatalogConfig.from_any(config)
        workspace = Path(workspace_root)
        diagnostics: list[SkillDiagnostic] = []
        entries: list[SkillCatalogEntry] = []
        seen_names: dict[str, SkillCatalogEntry] = {}

        for relative_root in resolved_config.discovery_roots:
            discovery_root = (workspace / relative_root).resolve()
            if not discovery_root.exists() or not discovery_root.is_dir():
                continue
            for skill_root in self._iter_skill_directories(discovery_root):
                location = self._relative_location(workspace, skill_root)
                entry, entry_diagnostics = self._load_entry(skill_root, location=location, config=resolved_config)
                diagnostics.extend(entry_diagnostics)
                if entry is None:
                    continue
                existing = seen_names.get(entry.manifest.name)
                if existing is not None:
                    diagnostics.append(
                        SkillDiagnostic(
                            level="warning",
                            code="duplicate-skill-name",
                            message=(
                                f"Skill '{entry.manifest.name}' at '{entry.location}' was skipped because "
                                f"'{existing.location}' already defines the same name with higher discovery priority."
                            ),
                            skill_name=entry.manifest.name,
                            location=entry.location,
                        )
                    )
                    continue
                seen_names[entry.manifest.name] = entry
                entries.append(entry)
        return SkillCatalog(config=resolved_config, entries=entries, diagnostics=diagnostics)

    def _iter_skill_directories(self, root: Path) -> list[Path]:
        directories: list[Path] = []
        if (root / "SKILL.md").exists():
            directories.append(root)
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if (child / "SKILL.md").exists():
                directories.append(child)
        return directories

    def _load_entry(
        self,
        root: Path,
        *,
        location: str,
        config: SkillCatalogConfig,
    ) -> tuple[SkillCatalogEntry | None, list[SkillDiagnostic]]:
        skill_file = root / "SKILL.md"
        diagnostics: list[SkillDiagnostic] = []
        if not skill_file.exists():
            diagnostics.append(
                SkillDiagnostic(
                    level="error",
                    code="missing-skill-file",
                    message=f"Missing skill file: {skill_file}",
                    location=location,
                )
            )
            return None, diagnostics
        try:
            raw = skill_file.read_text(encoding="utf-8")
        except Exception as exc:
            diagnostics.append(
                SkillDiagnostic(
                    level="error",
                    code="skill-read-failed",
                    message=f"Failed to read {skill_file}: {exc}",
                    location=location,
                )
            )
            return None, diagnostics

        try:
            metadata, _ = self._parse_frontmatter(raw)
        except Exception as exc:
            diagnostics.append(
                SkillDiagnostic(
                    level="error",
                    code="invalid-frontmatter",
                    message=f"Failed to parse frontmatter for {skill_file}: {exc}",
                    location=location,
                )
            )
            return None, diagnostics

        name = str(metadata.get("name") or root.name).strip()
        description = str(metadata.get("description") or "").strip()
        if not description:
            diagnostics.append(
                SkillDiagnostic(
                    level="error",
                    code="missing-description",
                    message=f"Skill '{name}' is missing the required description field.",
                    skill_name=name or None,
                    location=location,
                )
            )
            return None, diagnostics
        if not is_kebab_case(name):
            diagnostics.append(
                SkillDiagnostic(
                    level="warning",
                    code="non-kebab-case-name",
                    message=f"Skill '{name}' should use kebab-case for cross-platform compatibility.",
                    skill_name=name,
                    location=location,
                )
            )
        if root.name != name:
            diagnostics.append(
                SkillDiagnostic(
                    level="warning",
                    code="directory-name-mismatch",
                    message=f"Skill directory '{root.name}' does not match skill name '{name}'.",
                    skill_name=name,
                    location=location,
                )
            )
        if config.validation_mode == "strict":
            strict_warnings = [diagnostic.code for diagnostic in diagnostics if diagnostic.level == "warning"]
            if strict_warnings:
                diagnostics.append(
                    SkillDiagnostic(
                        level="error",
                        code="strict-validation-failed",
                        message=(
                            f"Skill '{name}' failed strict validation because of: "
                            f"{', '.join(strict_warnings)}."
                        ),
                        skill_name=name,
                        location=location,
                    )
                )
                return None, diagnostics

        manifest = SkillManifest(
            name=name,
            description=description,
            license=self._to_optional_str(metadata.get("license")),
            compatibility=normalize_string_list(metadata.get("compatibility")),
            metadata=dict(metadata.get("metadata") or {}) if isinstance(metadata.get("metadata"), dict) else {},
            allowed_tools=self._resolve_allowed_tools(metadata),
            tags=normalize_string_list(metadata.get("tags")),
            triggers=self._resolve_triggers(metadata),
            summary=self._to_optional_str(metadata.get("summary")),
        )
        entry = SkillCatalogEntry(
            manifest=manifest,
            root_path=root,
            skill_file=skill_file,
            location=location.replace("\\", "/"),
            references_path=(root / "references") if (root / "references").exists() else None,
            scripts_path=(root / "scripts") if (root / "scripts").exists() else None,
            assets_path=(root / "assets") if (root / "assets").exists() else None,
            resource_files=self._resource_files(root),
            diagnostics=list(diagnostics),
        )
        return entry, diagnostics

    def _parse_frontmatter(self, raw: str) -> tuple[dict[str, Any], str]:
        if not raw.startswith("---"):
            return {}, raw
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return {}, raw
        meta_block = parts[1]
        body = parts[2]
        loaded = yaml.safe_load(meta_block) or {}
        if not isinstance(loaded, dict):
            raise TypeError("SKILL.md frontmatter must deserialize to a mapping.")
        return dict(loaded), body

    def _resolve_allowed_tools(self, metadata: dict[str, Any]) -> list[str]:
        return normalize_string_list(
            metadata.get("allowed-tools", metadata.get("allowed_tools", metadata.get("allowedTools")))
        )

    def _resolve_triggers(self, metadata: dict[str, Any]) -> list[str]:
        triggers = normalize_string_list(metadata.get("triggers"))
        when_to_use = metadata.get("when_to_use")
        if when_to_use is not None:
            triggers.extend(normalize_string_list(when_to_use))
        return triggers

    def _resource_files(self, root: Path) -> list[str]:
        files: list[str] = []
        for directory_name in ("references", "scripts", "assets"):
            directory = root / directory_name
            if not directory.exists() or not directory.is_dir():
                continue
            for file_path in sorted(path for path in directory.rglob("*") if path.is_file()):
                files.append(file_path.relative_to(root).as_posix())
        return files

    def _relative_location(self, workspace_root: Path, skill_root: Path) -> str:
        try:
            return skill_root.resolve().relative_to(workspace_root.resolve()).as_posix()
        except Exception:
            return skill_root.resolve().as_posix()

    def _to_optional_str(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
