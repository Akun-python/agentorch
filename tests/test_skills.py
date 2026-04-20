from pathlib import Path

import pytest

from agentorch.skills import SkillCatalogConfig, SkillLoader, SkillRegistry, SkillRoutingConfig


def test_skill_loader_parses_manifest(tmp_path: Path):
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "references").mkdir()
    (skill_dir / "scripts").mkdir()
    (skill_dir / "assets").mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: test skill\ntriggers: excel, spreadsheet\nallowed_tools: shell\n---\nUse this skill for spreadsheet work.",
        encoding="utf-8",
    )
    skill = SkillLoader().load(skill_dir)
    assert skill.manifest.name == "demo"
    assert "excel" in skill.manifest.triggers
    assert skill.references_path is not None


def test_skill_loader_supports_standard_frontmatter_and_legacy_aliases(tmp_path: Path):
    standard_dir = tmp_path / "standard-skill"
    standard_dir.mkdir()
    (standard_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: standard-skill\n"
            "description: Standard skill metadata for structured activation\n"
            "license: MIT\n"
            "compatibility:\n"
            "  - claude-code\n"
            "  - agentskills\n"
            "metadata:\n"
            "  owner: platform\n"
            "allowed-tools:\n"
            "  - shell\n"
            "  - brave_search\n"
            "---\n"
            "Use the standard skill body."
        ),
        encoding="utf-8",
    )
    legacy_dir = tmp_path / "legacy-skill"
    legacy_dir.mkdir()
    (legacy_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: legacy-skill\n"
            "description: Legacy aliases still map into the canonical manifest\n"
            "triggers: finance,budget\n"
            "allowed_tools: add_numbers,shell\n"
            "summary: Use this summary for compatibility mode.\n"
            "---\n"
            "Use the legacy skill body."
        ),
        encoding="utf-8",
    )

    standard = SkillLoader().load(standard_dir)
    legacy = SkillLoader().load(legacy_dir)

    assert standard.manifest.license == "MIT"
    assert standard.manifest.compatibility == ["claude-code", "agentskills"]
    assert standard.manifest.metadata == {"owner": "platform"}
    assert standard.manifest.allowed_tools == ["shell", "brave_search"]
    assert legacy.manifest.triggers == ["finance", "budget"]
    assert legacy.manifest.allowed_tools == ["add_numbers", "shell"]
    assert legacy.manifest.summary == "Use this summary for compatibility mode."


def test_skill_registry_progressive_routing_returns_catalog_descriptors(tmp_path: Path):
    skill_dir = tmp_path / "research-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: research\n"
        "description: Evidence-first research workflow\n"
        "summary: Start with evidence gathering, then compare claims.\n"
        "triggers: research,evidence\n"
        "allowed_tools: brave_search,deliberative_retrieve\n"
        "---\n"
        "Use brave_search first, then deliberative_retrieve, and keep citations in the final answer.",
        encoding="utf-8",
    )
    registry = SkillRegistry()
    registry.register(SkillLoader().load(skill_dir))

    routes = registry.route_for(
        "Please research this topic and gather evidence.",
        config=SkillRoutingConfig(mode="progressive", disclosure_level="progressive"),
        available_tools=["brave_search", "deliberative_retrieve"],
    )

    assert len(routes) == 1
    assert routes[0].disclosure_level == "descriptor"
    assert "Location:" in routes[0].content
    assert "Evidence-first research workflow" in routes[0].content
    assert "Recommended Tools: brave_search, deliberative_retrieve" not in routes[0].content


def test_skill_registry_full_disclosure_returns_full_markdown(tmp_path: Path):
    skill_dir = tmp_path / "full-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: full_skill\ndescription: Full skill\ntriggers: finance\nallowed_tools: add_numbers\n---\nUse this skill for finance totals.",
        encoding="utf-8",
    )
    registry = SkillRegistry()
    registry.register(SkillLoader().load(skill_dir))
    routes = registry.route_for("Need finance totals.", config="full")
    assert len(routes) == 1
    assert routes[0].disclosure_level == "full"
    assert routes[0].content == "Use this skill for finance totals."


def test_skill_loader_prefers_dot_claude_catalog_over_legacy_dot_skills(tmp_path: Path):
    claude_skill = tmp_path / ".claude" / "skills" / "shared-skill"
    claude_skill.mkdir(parents=True)
    legacy_skill = tmp_path / ".skills" / "shared-skill"
    legacy_skill.mkdir(parents=True)
    (claude_skill / "SKILL.md").write_text(
        "---\nname: shared-skill\ndescription: canonical claude catalog entry\n---\nUse the canonical claude skill.",
        encoding="utf-8",
    )
    (legacy_skill / "SKILL.md").write_text(
        "---\nname: shared-skill\ndescription: legacy fallback entry\n---\nUse the legacy skill.",
        encoding="utf-8",
    )

    catalog = SkillLoader().discover_catalog(tmp_path, config=SkillCatalogConfig())

    assert [entry.manifest.name for entry in catalog.entries] == ["shared-skill"]
    assert catalog.entries[0].location == ".claude/skills/shared-skill"
    assert any(diagnostic.code == "duplicate-skill-name" for diagnostic in catalog.diagnostics)


def test_skill_loader_warns_on_non_standard_names_in_lenient_mode(tmp_path: Path):
    mismatched_skill = tmp_path / ".claude" / "skills" / "MismatchDir"
    mismatched_skill.mkdir(parents=True)
    (mismatched_skill / "SKILL.md").write_text(
        "---\nname: Mixed_Name\ndescription: Lenient discovery still surfaces diagnostics.\n---\nBody.",
        encoding="utf-8",
    )

    catalog = SkillLoader().discover_catalog(tmp_path, config=SkillCatalogConfig(validation_mode="lenient"))

    assert [entry.manifest.name for entry in catalog.entries] == ["Mixed_Name"]
    assert any(diagnostic.code == "non-kebab-case-name" for diagnostic in catalog.diagnostics)
    assert any(diagnostic.code == "directory-name-mismatch" for diagnostic in catalog.diagnostics)


def test_skill_loader_strict_validation_skips_non_standard_names(tmp_path: Path):
    mismatched_skill = tmp_path / ".claude" / "skills" / "MismatchDir"
    mismatched_skill.mkdir(parents=True)
    (mismatched_skill / "SKILL.md").write_text(
        "---\nname: Mixed_Name\ndescription: Strict validation should reject this entry.\n---\nBody.",
        encoding="utf-8",
    )

    catalog = SkillLoader().discover_catalog(tmp_path, config=SkillCatalogConfig(validation_mode="strict"))

    assert catalog.entries == []
    assert any(diagnostic.code == "strict-validation-failed" for diagnostic in catalog.diagnostics)


def test_skill_loader_skips_missing_description_with_diagnostic(tmp_path: Path):
    broken_skill = tmp_path / ".claude" / "skills" / "broken-skill"
    broken_skill.mkdir(parents=True)
    (broken_skill / "SKILL.md").write_text(
        "---\nname: broken-skill\n---\nBody without required description.",
        encoding="utf-8",
    )

    catalog = SkillLoader().discover_catalog(tmp_path, config=SkillCatalogConfig())

    assert catalog.entries == []
    assert any(diagnostic.code == "missing-description" for diagnostic in catalog.diagnostics)


def test_skill_resource_loading_rejects_escape_and_non_standard_roots(tmp_path: Path):
    skill_dir = tmp_path / "guarded-skill"
    skill_dir.mkdir()
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "guide.md").write_text("Guide", encoding="utf-8")
    (skill_dir / "notes.md").write_text("Notes", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\nname: guarded-skill\ndescription: Guarded resource loading\n---\nGuard the root.",
        encoding="utf-8",
    )

    skill = SkillLoader().load(skill_dir)

    with pytest.raises(ValueError, match="must live under references/, scripts/, or assets/"):
        skill.load_resource("notes.md")
    with pytest.raises(ValueError, match="escapes the skill root"):
        skill.load_resource("references/../../outside.md")
    with pytest.raises(ValueError, match="outside references/, scripts/, or assets/"):
        skill.load_resource("references/../notes.md")
