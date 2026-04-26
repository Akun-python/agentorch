from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
README_EN = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"


def _section(text: str, heading: str) -> str:
    pattern = re.compile(rf"{re.escape(heading)}\n(.*?)(?:\n## |\Z)", re.S)
    match = pattern.search(text)
    assert match is not None, f"Missing heading: {heading}"
    return match.group(1)


def _python_block(section: str) -> str:
    match = re.search(r"```python\n(.*?)```", section, re.S)
    assert match is not None, "Missing python code block"
    return match.group(1)


def test_readmes_follow_concise_structure():
    for path in (README_EN, README_ZH):
        text = path.read_text(encoding="utf-8")
        for heading in ("## WHY", "## WHAT", "## HOW", "## QUICKSTART"):
            _section(text, heading)


def test_readmes_keep_facade_entrypoints_in_what_section():
    for path in (README_EN, README_ZH):
        text = path.read_text(encoding="utf-8")
        what_section = _section(text, "## WHAT")
        assert "`create_agent(...)`" in what_section
        assert "`create_multi_agent(...)`" in what_section


def test_readmes_quickstart_use_create_agent():
    for path in (README_EN, README_ZH):
        text = path.read_text(encoding="utf-8")
        quickstart = _section(text, "## QUICKSTART")
        code = _python_block(quickstart)
        assert "from agentorch import create_agent" in code
        assert "agent = create_agent(" in code
        assert "Agent.create(" not in code
