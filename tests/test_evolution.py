import asyncio

from agentorch import (
    EvaluationResult,
    EvolutionConfig,
    EvolutionManager,
    EvolutionSession,
    Genome,
    SearchSpace,
    candidate_from_genome,
    create_agent_evolution,
    create_multi_agent_evolution,
    list_evolution_algorithms,
    rag_strategy_from_genome,
    reasoning_strategy_from_genome,
    runtime_config_from_genome,
    workflow_from_genome,
)
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="ok"),
            content="ok",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


async def _build_candidate(genome: Genome) -> dict:
    return {"genes": genome.genes}


async def _evaluate_candidate(genome: Genome, candidate: dict, tasks: list[str]) -> EvaluationResult:
    genes = candidate["genes"]
    fitness = 0.0
    reasoning_kind = (
        genes.get("planner", {}).get("reasoning_kind")
        or genes.get("reasoning", {}).get("kind")
    )
    if reasoning_kind == "plan_execute":
        fitness += 3.0
    if genes.get("memory", {}).get("promotion_min_support_agents") == 2:
        fitness += 2.0
    if genes.get("tools", {}).get("tool_policy") == "tool_first":
        fitness += 1.0
    if genes.get("rag", {}).get("mode") == "hybrid":
        fitness += 1.0
    if genes.get("workflow", {}).get("template") == "retrieve_plan_review":
        fitness += 1.0
    fitness += 0.1 * len(tasks)
    return EvaluationResult(
        genome_id=genome.id,
        fitness=fitness,
        metrics={"fitness": fitness},
        task_results=[{"task_count": len(tasks)}],
    )


def test_search_space_samples_nested_genes():
    space = SearchSpace(
        {
            "planner.reasoning_kind": ["react", "plan_execute"],
            "memory.promotion_min_support_agents": [1, 2],
        }
    )
    genes = space.sample(__import__("random").Random(1))
    assert genes["planner"]["reasoning_kind"] in {"react", "plan_execute"}
    assert genes["memory"]["promotion_min_support_agents"] in {1, 2}


def test_evolution_manager_runs_generations_and_returns_best_genome():
    asyncio.run(_test_evolution_manager_runs_generations_and_returns_best_genome())


async def _test_evolution_manager_runs_generations_and_returns_best_genome():
    manager = EvolutionManager(
        builder=_build_candidate,
        evaluator=_evaluate_candidate,
        search_space=SearchSpace(
            {
                "planner.reasoning_kind": ["react", "plan_execute"],
                "memory.promotion_min_support_agents": [1, 2],
                "tools.tool_policy": ["reason_first", "tool_first"],
            }
        ),
        config=EvolutionConfig(
            population_size=6,
            generations=4,
            mutation_rate=0.5,
            elitism=1,
            seed=3,
        ),
    )
    result = await manager.evolve(tasks=["a", "b", "c"])
    assert len(result.history) == 4
    assert result.best_evaluation.fitness >= 6.0
    assert result.best_genome.genes["planner"]["reasoning_kind"] == "plan_execute"
    assert result.best_genome.genes["memory"]["promotion_min_support_agents"] == 2


def test_evolution_manager_accepts_initial_population_and_builds_best_candidate():
    asyncio.run(_test_evolution_manager_accepts_initial_population_and_builds_best_candidate())


async def _test_evolution_manager_accepts_initial_population_and_builds_best_candidate():
    manager = EvolutionManager(
        builder=_build_candidate,
        evaluator=_evaluate_candidate,
        search_space=SearchSpace(
            {
                "planner.reasoning_kind": ["react", "plan_execute"],
                "memory.promotion_min_support_agents": [1, 2],
                "tools.tool_policy": ["reason_first", "tool_first"],
            }
        ),
        config=EvolutionConfig(population_size=2, generations=2, mutation_rate=0.0, elitism=1, seed=5),
    )
    initial_population = [
        Genome(id="g-1", genes={"planner": {"reasoning_kind": "react"}, "memory": {"promotion_min_support_agents": 1}, "tools": {"tool_policy": "reason_first"}}),
        Genome(id="g-2", genes={"planner": {"reasoning_kind": "plan_execute"}, "memory": {"promotion_min_support_agents": 2}, "tools": {"tool_policy": "tool_first"}}),
    ]
    result = await manager.evolve(tasks=["task"], initial_population=initial_population)
    built = await manager.build_candidate(result.best_genome)
    assert built["genes"]["planner"]["reasoning_kind"] == "plan_execute"
    assert result.best_genome.parent_ids == []


def test_multiple_evolution_algorithms_and_genome_helpers():
    asyncio.run(_test_multiple_evolution_algorithms_and_genome_helpers())


async def _test_multiple_evolution_algorithms_and_genome_helpers():
    assert {"genetic", "random_search", "hill_climb", "beam_search"}.issubset(set(list_evolution_algorithms()))
    genome = Genome(
        id="g-helpers",
        genes={
            "reasoning": {"kind": "plan_execute", "config": {"max_steps": 4}},
            "rag": {"mode": "hybrid", "mount": "inline", "injection_policy": "full_report", "top_k": 4},
            "workflow": {"template": "retrieve_plan_review"},
        },
    )
    assert reasoning_strategy_from_genome(genome).kind.value == "plan_execute"
    assert rag_strategy_from_genome(genome).mode == "hybrid"
    runtime_config = runtime_config_from_genome(genome)
    assert runtime_config.reasoning_strategy.kind.value == "plan_execute"
    candidate = candidate_from_genome(genome)
    assert candidate["workflow_template"] == "retrieve_plan_review"
    workflow = workflow_from_genome(genome)
    assert workflow is not None
    assert [node.kind for node in workflow.nodes][:2] == ["retrieve", "model"]

    for algorithm_kind in ("random_search", "hill_climb", "beam_search"):
        manager = EvolutionManager(
            builder=_build_candidate,
            evaluator=_evaluate_candidate,
            search_space=SearchSpace(
                {
                    "reasoning.kind": ["react", "plan_execute"],
                    "rag.mode": ["classic", "hybrid"],
                    "workflow.template": ["classic_inline_answer", "retrieve_plan_review"],
                }
            ),
            config=EvolutionConfig(
                algorithm_kind=algorithm_kind,
                population_size=4,
                generations=3,
                evaluation_budget=6,
                early_stop_patience=2,
                seed=9,
            ),
        )
        result = await manager.evolve(tasks=["a", "b"])
        assert result.best_genome is not None


def test_create_agent_evolution_builds_best_agent_from_real_workflow_template():
    asyncio.run(_test_create_agent_evolution_builds_best_agent_from_real_workflow_template())


async def _test_create_agent_evolution_builds_best_agent_from_real_workflow_template():
    session = create_agent_evolution(
        model=EchoModel(),
        search_space=SearchSpace(
            {
                "reasoning.kind": ["react", "plan_execute"],
                "workflow.template": ["classic_inline_answer", "retrieve_plan_review"],
            }
        ),
        evolution_config=EvolutionConfig(population_size=2, generations=1, seed=11),
        evaluator=lambda genome, candidate, tasks: EvaluationResult(
            genome_id=genome.id,
            fitness=5.0 if candidate.workflow and any(node.kind == "retrieve" for node in candidate.workflow.nodes) else 1.0,
        ),
    )

    result = await session.evolve(tasks=["plan"])
    best_agent = await session.build_best_candidate(result)

    assert isinstance(session, EvolutionSession)
    assert best_agent.workflow is not None
    assert best_agent.workflow.nodes[0].kind == "retrieve"
    assert best_agent.runtime.config.reasoning_strategy.kind.value in {"react", "plan_execute"}
    await best_agent.aclose()


def test_create_multi_agent_evolution_builds_multi_agent_candidate():
    asyncio.run(_test_create_multi_agent_evolution_builds_multi_agent_candidate())


async def _test_create_multi_agent_evolution_builds_multi_agent_candidate():
    session = create_multi_agent_evolution(
        roles=[
            {
                "name": "planner",
                "role": "planner",
                "model": EchoModel(),
                "system_prompt": "plan",
            }
        ],
        model=EchoModel(),
        search_space=SearchSpace({"workflow.template": ["classic_inline_answer"]}),
        evolution_config=EvolutionConfig(population_size=1, generations=1, seed=3),
        evaluator=lambda genome, candidate, tasks: EvaluationResult(
            genome_id=genome.id,
            fitness=2.0 if candidate.export_blueprint()["kind"] == "multi_agent" else 0.0,
        ),
    )

    result = await session.evolve(tasks=["orchestrate"])
    best_system = await session.build_best_candidate(result)

    assert best_system.export_blueprint()["kind"] == "multi_agent"
    assert best_system.workflow is not None
    assert best_system.workflow.nodes[0].kind == "model"
    await best_system.aclose()
