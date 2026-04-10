"""Evolutionary orchestration primitives for agentorch.

Use this package to evolve agent systems built on top of agentorch by
searching over reasoning, tools, topology, and memory-governance settings.
"""

from .algorithms.beam_search import BeamSearchEvolutionAlgorithm
from .algorithms.genetic import GeneticEvolutionAlgorithm
from .algorithms.hill_climb import HillClimbEvolutionAlgorithm
from .algorithms.random_search import RandomSearchEvolutionAlgorithm
from .base import EvolutionAlgorithm
from .bootstrap import bootstrap_evolution_defaults
from .context import EvolutionExecutionContext
from .factory import EvolutionFactory, create_evolution_algorithm
from .helpers import candidate_from_genome, rag_strategy_from_genome, reasoning_strategy_from_genome, runtime_config_from_genome
from .manager import EvolutionManager
from .registry import (
    EvolutionRegistration,
    EvolutionRegistry,
    get_evolution_algorithm_registration,
    list_evolution_algorithms,
    register_evolution_algorithm,
)
from .search_space import SearchSpace
from .strategies import MutationOperator, TopKSelection
from .types import EvaluationResult, EvolutionConfig, EvolutionResult, GenerationResult, Genome

__all__ = [
    "EvaluationResult",
    "EvolutionAlgorithm",
    "EvolutionConfig",
    "EvolutionExecutionContext",
    "EvolutionFactory",
    "EvolutionManager",
    "EvolutionRegistration",
    "EvolutionRegistry",
    "EvolutionResult",
    "GenerationResult",
    "BeamSearchEvolutionAlgorithm",
    "GeneticEvolutionAlgorithm",
    "Genome",
    "HillClimbEvolutionAlgorithm",
    "MutationOperator",
    "RandomSearchEvolutionAlgorithm",
    "SearchSpace",
    "TopKSelection",
    "bootstrap_evolution_defaults",
    "candidate_from_genome",
    "create_evolution_algorithm",
    "get_evolution_algorithm_registration",
    "list_evolution_algorithms",
    "rag_strategy_from_genome",
    "register_evolution_algorithm",
    "reasoning_strategy_from_genome",
    "runtime_config_from_genome",
]
