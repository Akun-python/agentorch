from __future__ import annotations

from .algorithms.beam_search import BeamSearchEvolutionAlgorithm
from .algorithms.genetic import GeneticEvolutionAlgorithm
from .algorithms.hill_climb import HillClimbEvolutionAlgorithm
from .algorithms.random_search import RandomSearchEvolutionAlgorithm
from .registry import register_evolution_algorithm

_BOOTSTRAPPED = False


def bootstrap_evolution_defaults(*, force: bool = False) -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED and not force:
        return
    register_evolution_algorithm("genetic", GeneticEvolutionAlgorithm)
    register_evolution_algorithm("random_search", RandomSearchEvolutionAlgorithm)
    register_evolution_algorithm("hill_climb", HillClimbEvolutionAlgorithm)
    register_evolution_algorithm("beam_search", BeamSearchEvolutionAlgorithm)
    _BOOTSTRAPPED = True
