import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import agentorch
from experiments.architecture_audit.collect_agentorch_architecture_metrics import collect_metrics
from agentorch.evolution import bootstrap_evolution_defaults, list_evolution_algorithms
from agentorch.memory import bootstrap_memory_defaults, list_memory_backends, list_memory_governance
from agentorch.models import list_model_providers
from agentorch.reasoning import bootstrap_reasoning_defaults, list_reasoning_frameworks


def _run_fresh_interpreter(script: str) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=repo_root,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_bootstrap_functions_are_idempotent():
    agentorch.bootstrap_defaults()
    agentorch.bootstrap_defaults()
    agentorch.bootstrap_model_defaults()
    agentorch.bootstrap_model_defaults()
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
    assert "openai" in list_model_providers()


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


def test_static_import_graph_removes_recent_architecture_cycles():
    repo_root = Path(__file__).resolve().parents[1]
    cycles = {tuple(component) for component in collect_metrics(repo_root)["cycles"]}

    assert ("runtime.context_compaction", "strategies") not in cycles
    assert ("evolution.session", "runtime.agent", "runtime.runtime") not in cycles


def test_import_agentorch_has_no_registry_side_effects_in_fresh_interpreter():
    payload = _run_fresh_interpreter(
        """
        import json
        import agentorch
        from agentorch.evolution.registry import default_evolution_registry
        from agentorch.memory.registry import (
            memory_backend_registry,
            memory_decay_policy_registry,
            memory_governance_registry,
            memory_index_policy_registry,
            memory_mechanism_registry,
            memory_promotion_policy_registry,
            memory_recall_policy_registry,
        )
        from agentorch.models.registry import _MODEL_FACTORIES
        from agentorch.reasoning.registry import default_reasoning_registry

        print(json.dumps({
            "reasoning": default_reasoning_registry.list(),
            "evolution": default_evolution_registry.list(),
            "memory_backends": memory_backend_registry.list(),
            "memory_governance": memory_governance_registry.list(),
            "memory_mechanisms": memory_mechanism_registry.list(),
            "memory_promotion": memory_promotion_policy_registry.list(),
            "memory_index": memory_index_policy_registry.list(),
            "memory_recall": memory_recall_policy_registry.list(),
            "memory_decay": memory_decay_policy_registry.list(),
            "models": sorted(_MODEL_FACTORIES),
        }))
        """
    )

    assert payload == {
        "reasoning": [],
        "evolution": [],
        "memory_backends": [],
        "memory_governance": [],
        "memory_mechanisms": [],
        "memory_promotion": [],
        "memory_index": [],
        "memory_recall": [],
        "memory_decay": [],
        "models": [],
    }


def test_public_listing_apis_lazy_bootstrap_defaults_in_fresh_interpreter():
    payload = _run_fresh_interpreter(
        """
        import json
        import agentorch

        print(json.dumps({
            "reasoning": agentorch.list_reasoning_frameworks(),
            "evolution": agentorch.list_evolution_algorithms(),
            "memory_backends": agentorch.list_memory_backends(),
            "memory_governance": agentorch.list_memory_governance(),
            "models": agentorch.list_model_providers(),
        }))
        """
    )

    assert {"cot", "legacy_policy", "plan_execute", "react", "reflexion", "tot"}.issubset(set(payload["reasoning"]))
    assert {"genetic", "random_search", "hill_climb", "beam_search"}.issubset(set(payload["evolution"]))
    assert {"in_memory_state_store", "sqlite_checkpoint_store", "sqlite_record_store"}.issubset(
        set(payload["memory_backends"])
    )
    assert "mgcm_governance" in payload["memory_governance"]
    assert {"openai", "openai_http"}.issubset(set(payload["models"]))
