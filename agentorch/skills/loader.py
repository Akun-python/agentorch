from __future__ import annotations

from pathlib import Path

from .base import Skill, SkillManifest


class SkillLoader:
    def load(self, path: str | Path) -> Skill:
        root = Path(path)
        skill_file = root / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Missing skill file: {skill_file}")
        raw = skill_file.read_text(encoding="utf-8")
        metadata, body = self._parse_frontmatter(raw)
        manifest = SkillManifest(
            name=metadata.get("name", root.name),
            description=metadata.get("description", ""),
            triggers=self._to_list(metadata.get("triggers", "")),
            allowed_tools=self._to_list(metadata.get("allowed_tools", "")),
            tags=self._to_list(metadata.get("tags", "")),
            summary=metadata.get("summary"),
        )
        return Skill(
            manifest=manifest,
            root_path=root,
            markdown=body.strip(),
            references_path=(root / "references") if (root / "references").exists() else None,
            scripts_path=(root / "scripts") if (root / "scripts").exists() else None,
            assets_path=(root / "assets") if (root / "assets").exists() else None,
        )

    def discover(self, root: str | Path) -> list[Skill]:
        base = Path(root)
        if not base.exists() or not base.is_dir():
            return []
        skills: list[Skill] = []
        if (base / "SKILL.md").exists():
            skills.append(self.load(base))
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            if (child / "SKILL.md").exists():
                skills.append(self.load(child))
        return skills

    def _parse_frontmatter(self, raw: str) -> tuple[dict[str, str], str]:
        if not raw.startswith("---"):
            return {}, raw
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return {}, raw
        meta_block = parts[1]
        body = parts[2]
        metadata: dict[str, str] = {}
        for line in meta_block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
        return metadata, body

    def _to_list(self, value: str) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
