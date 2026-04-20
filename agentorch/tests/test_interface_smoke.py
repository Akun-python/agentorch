from __future__ import annotations

import asyncio
from pathlib import Path

import agentorch
import pytest
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter


class DummyModel(BaseModelAdapter):
    def __init__(self, *, name: str = "dummy-interface-model", reply: str = "ok") -> None:
        self.config = {"api_key": "sk-dummy-interface-1234567890", "model": name}
        self.reply = reply
        self.closed = False

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content=self.reply),
            content=self.reply,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=5),
        )

    async def aclose(self) -> None:
        self.closed = True


def test_top_level_public_exports_include_high_level_entrypoints() -> None:
    for symbol in (
        "create_agent",
        "create_multi_agent",
        "create_agent_evolution",
        "create_multi_agent_evolution",
        "DeepResearchAgent",
        "AgentDesign",
        "RoleDesign",
        "TeamDesign",
        "compose_agent",
        "compose_team",
    ):
        assert hasattr(agentorch, symbol)


def test_deep_research_agent_config_and_entrypoint_support_workspace_tool_mode() -> None:
    config = agentorch.DeepResearchAgentConfig.from_any(
        {
            "knowledge_scope": ["papers"],
            "include_workspace_tools": True,
            "include_web_search": False,
            "workspace_root": Path.cwd(),
        }
    )

    runtime_config = config.runtime_config()
    assert runtime_config.default_knowledge_scope == ["papers"]
    assert runtime_config.rag_strategy is not None
    assert runtime_config.rag_strategy.knowledge_scope == ["papers"]

    research = agentorch.DeepResearchAgent.create(model=DummyModel(reply="research-ready"), config=config)
    blueprint = research.export_blueprint()

    assert "read_file" in blueprint["runtime"]["tools"]
    assert "brave_search" not in blueprint["runtime"]["tools"]
    research.close()


def test_create_agent_evolution_interface_builds_and_runs_candidates() -> None:
    async def scenario() -> None:
        session = agentorch.create_agent_evolution(
            search_space={
                "reasoning.kind": ["react"],
                "rag.mode": ["off"],
            },
            evolution_config=agentorch.EvolutionConfig(
                algorithm_kind="random_search",
                population_size=1,
                generations=1,
                evaluation_budget=1,
                seed=11,
            ),
            model=DummyModel(reply="evo-agent"),
            evaluator=_agent_evaluator,
            tasks=["task-a"],
            name="evo-agent",
        )

        result = await session.evolve()
        assert result.best_evaluation.fitness == 1.0
        candidate = await session.build_best_candidate(result)
        summary = await session.summarize_candidate(candidate)

        assert session.candidate_kind == "agent"
        assert summary["facade"] == "create_agent"
        assert summary["name"] == "evo-agent"
        await candidate.aclose()

    asyncio.run(scenario())


def test_create_multi_agent_evolution_interface_builds_and_runs_candidates() -> None:
    async def scenario() -> None:
        session = agentorch.create_multi_agent_evolution(
            search_space={
                "reasoning.kind": ["react"],
                "rag.mode": ["off"],
            },
            evolution_config=agentorch.EvolutionConfig(
                algorithm_kind="random_search",
                population_size=1,
                generations=1,
                evaluation_budget=1,
                seed=13,
            ),
            roles=[
                {
                    "name": "planner",
                    "model": DummyModel(name="planner-model", reply="plan-ready"),
                    "capabilities": ["plan"],
                }
            ],
            evaluator=_team_evaluator,
            tasks=["task-b"],
            name="evo-team",
        )

        result = await session.evolve()
        assert result.best_evaluation.fitness == 2.0
        candidate = await session.build_best_candidate(result)
        summary = await session.summarize_candidate(candidate)

        assert session.candidate_kind == "multi_agent"
        assert summary["facade"] == "create_multi_agent"
        assert summary["kind"] == "multi_agent"
        await candidate.aclose()

    asyncio.run(scenario())


def test_create_agent_evolution_closes_candidate_when_evaluator_fails() -> None:
    async def scenario() -> None:
        model = DummyModel(reply="will-close")
        session = agentorch.create_agent_evolution(
            search_space={"reasoning.kind": ["react"]},
            evolution_config=agentorch.EvolutionConfig(
                algorithm_kind="random_search",
                population_size=1,
                generations=1,
                evaluation_budget=1,
                seed=17,
            ),
            model=model,
            evaluator=_failing_agent_evaluator,
            tasks=["task-c"],
            name="evo-agent-fail",
        )

        with pytest.raises(RuntimeError, match="expected evaluator failure"):
            await session.evolve()

        assert model.closed is True

    asyncio.run(scenario())


async def _agent_evaluator(genome, candidate, tasks):
    result = await candidate.run("solve task", thread_id=f"eval-{genome.id}")
    return agentorch.EvaluationResult(
        genome_id=genome.id,
        fitness=1.0,
        metrics={"tasks": float(len(tasks)), "tokens": float(result.usage.total_tokens)},
    )


async def _team_evaluator(genome, candidate, tasks):
    result = await candidate.run("coordinate task", thread_id=f"team-{genome.id}")
    return agentorch.EvaluationResult(
        genome_id=genome.id,
        fitness=2.0,
        metrics={"tasks": float(len(tasks)), "tokens": float(result.usage.total_tokens)},
    )


async def _failing_agent_evaluator(genome, candidate, tasks):
    raise RuntimeError("expected evaluator failure")
