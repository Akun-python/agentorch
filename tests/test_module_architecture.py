from pathlib import Path

from agentorch.evolution import bootstrap_evolution_defaults, list_evolution_algorithms
from agentorch.memory import bootstrap_memory_defaults, list_memory_backends, list_memory_governance
from agentorch.reasoning import bootstrap_reasoning_defaults, list_reasoning_frameworks


def test_bootstrap_functions_are_idempotent():
    bootstrap_reasoning_defaults()
    bootstrap_reasoning_defaults()
    bootstrap_evolution_defaults()
    bootstrap_evolution_defaults()
    bootstrap_memory_defaults()
    bootstrap_memory_defaults()

    assert "react" in list_reasoning_frameworks()
    assert "genetic" in list_evolution_algorithms()
    assert "sqlite_record_store" in list_memory_backends()
    assert "mgcm_governance" in list_memory_governance()


def test_architecture_files_exist_in_expected_locations():
    repo_root = Path(__file__).resolve().parents[1]
    expected_paths = [
        repo_root / "agentorch" / "reasoning" / "mechanisms" / "react.py",
        repo_root / "agentorch" / "evolution" / "algorithms" / "genetic" / "algorithm.py",
        repo_root / "agentorch" / "memory" / "governance" / "mgcm.py",
        repo_root / "agentorch" / "reasoning" / "README.md",
        repo_root / "agentorch" / "evolution" / "README.md",
        repo_root / "agentorch" / "memory" / "README.md",
    ]
    for path in expected_paths:
        assert path.exists(), f"Expected architecture file missing: {path}"
