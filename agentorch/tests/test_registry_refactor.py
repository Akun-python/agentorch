from __future__ import annotations

from uuid import uuid4

import pytest

import agentorch
from agentorch.evolution import EvolutionAlgorithm
from agentorch.knowledge.registry import _KnowledgeRegistry
from agentorch.memory import factory as memory_factory
from agentorch.memory import registry as memory_registry
from agentorch.reasoning import BaseReasoningFramework, ReactConfig, ReasoningResult


def _unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ConfiguredDemoReasoning(BaseReasoningFramework):
    def __init__(self, config: ReactConfig) -> None:
        super().__init__(config)

    async def execute(self, runtime, context) -> ReasoningResult:
        return ReasoningResult(final_output="configured-demo")


class ZeroArgEvolution(EvolutionAlgorithm):
    def __init__(self) -> None:
        self.marker = "zero-arg"

    async def evolve(self, context, *, tasks=None, initial_population=None):
        raise RuntimeError("not used in registry smoke tests")


def test_memory_factory_reexports_registry_creators() -> None:
    assert memory_factory.create_memory_backend is memory_registry.create_memory_backend
    assert memory_factory.create_memory_governance is memory_registry.create_memory_governance
    assert memory_factory.create_memory_mechanism is memory_registry.create_memory_mechanism
    assert memory_factory.create_memory_promotion_policy is memory_registry.create_memory_promotion_policy
    assert memory_factory.create_memory_index_policy is memory_registry.create_memory_index_policy
    assert memory_factory.create_memory_recall_policy is memory_registry.create_memory_recall_policy
    assert memory_factory.create_memory_decay_policy is memory_registry.create_memory_decay_policy


def test_reasoning_registry_uses_config_class_when_registered() -> None:
    reasoning_name = _unique_name("reasoning_configured")
    agentorch.register_reasoning_framework(reasoning_name, ConfiguredDemoReasoning, ReactConfig)

    framework = agentorch.create_reasoning_framework(reasoning_name, max_steps=7)

    assert isinstance(framework, ConfiguredDemoReasoning)
    assert isinstance(framework.config, ReactConfig)
    assert framework.config.max_steps == 7


def test_evolution_registry_preserves_zero_arg_constructor_fallback() -> None:
    evolution_name = _unique_name("evolution_zero")
    agentorch.register_evolution_algorithm(evolution_name, ZeroArgEvolution)

    algorithm = agentorch.create_evolution_algorithm(evolution_name, unexpected="ignored")

    assert isinstance(algorithm, ZeroArgEvolution)
    assert algorithm.marker == "zero-arg"


def test_knowledge_registry_preserves_validation_errors() -> None:
    registry = _KnowledgeRegistry()

    with pytest.raises(ValueError, match="A component class or factory is required."):
        registry.register("invalid")

    with pytest.raises(ValueError, match="Unsupported knowledge component kind: missing"):
        registry.create("missing")
