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


def _subsection(text: str, heading: str) -> str:
    pattern = re.compile(rf"{re.escape(heading)}\n(.*?)(?:\n### |\n## |\Z)", re.S)
    match = pattern.search(text)
    assert match is not None, f"Missing heading: {heading}"
    return match.group(1)


def _python_block(section: str) -> str:
    match = re.search(r"```python\n(.*?)```", section, re.S)
    assert match is not None, "Missing python code block"
    return match.group(1)


def test_readmes_recommend_facade_entrypoints():
    readmes = [
        (README_EN, "## Recommended API Style"),
        (README_ZH, "## 当前推荐 API 风格"),
    ]
    for path, heading in readmes:
        section = _section(path.read_text(encoding="utf-8"), heading)
        assert "`create_agent(...)`" in section
        assert "`create_multi_agent(...)`" in section


def test_chinese_readme_quickstart_uses_facade_entrypoints():
    text = README_ZH.read_text(encoding="utf-8")

    minimal_agent = _subsection(text, "### 1. 最小 Agent")
    minimal_code = _python_block(minimal_agent)
    assert "from agentorch import create_agent" in minimal_code
    assert "agent = create_agent(" in minimal_code
    assert "Agent.create(" not in minimal_code

    multi_agent = _subsection(text, "### 7. 多智能体 supervisor 委派")
    multi_agent_code = _python_block(multi_agent)
    assert "from agentorch import AgentCapability, create_agent, create_multi_agent" in multi_agent_code
    assert "planner = create_agent(" in multi_agent_code
    assert "orchestrator = create_multi_agent(" in multi_agent_code
