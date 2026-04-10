from pathlib import Path

from agentorch.skills import SkillLoader, SkillRegistry, SkillRoutingConfig


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


def test_skill_registry_progressive_routing_returns_summaries(tmp_path: Path):
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
    assert routes[0].disclosure_level == "summary"
    assert "Start with evidence gathering, then compare claims." in routes[0].content
    assert "Evidence-first research workflow" in routes[0].content
    assert "Recommended Tools: brave_search, deliberative_retrieve" in routes[0].content


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
