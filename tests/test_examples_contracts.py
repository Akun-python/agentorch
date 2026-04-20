from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_README = ROOT / "examples" / "README.md"


def test_examples_readme_classifies_facade_and_core_examples():
    text = EXAMPLES_README.read_text(encoding="utf-8")

    assert "## Recommended Facade Entrypoints" in text
    assert "## Core Assembly / Lower-Level Runtime Examples" in text
    assert "`basic_agent.py`" in text
    assert "`supervisor_agents.py`" in text
    assert "`rag_ready_runtime.py`" in text
    assert "`tools.py`" in text
