from pathlib import Path

from agentorch.skills import SkillLoader


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
