import asyncio

from agentorch import AgentCapability, AgentRegistry, AgentSpec, Supervisor, TaskBudget, TaskPacket
from experiments.elephant_context import (
    ElephantContextSelector,
    ElephantMemoryEvaluator,
    MatriarchRoutePlanner,
    build_elephant_runtime_config,
    get_elephant_variant,
    distributed_coordination_policy,
    matriarch_coordination_policy,
)


def test_elephant_plugin_runtime_config_stays_within_core_extension_points():
    config = build_elephant_runtime_config(hybrid_selection=True, distributed=False, char_budget=19000)
    assert isinstance(config.context_selector, ElephantContextSelector)
    assert isinstance(config.route_planner, MatriarchRoutePlanner)
    assert isinstance(config.memory_evaluator, ElephantMemoryEvaluator)
    assert config.context_policy.selection_mode == "hybrid"
    assert config.context_policy.char_budget == 19000
    assert config.state_policy.retention_mode == "state_plus_memory"
    assert config.coordination_policy.route_mode == "guided"
    assert config.memory_policy.promotion_mode == "validated"

    resolved_runtime = config.memory_evaluator.resolved_runtime_config(config.memory_policy)
    assert resolved_runtime["validation_threshold"] == 0.65
    assert resolved_runtime["collective_promotion_threshold"] == 2.4


def test_matriarch_route_planner_reorders_guided_plan_but_not_distributed():
    asyncio.run(_test_matriarch_route_planner_reorders_guided_plan_but_not_distributed())


async def _test_matriarch_route_planner_reorders_guided_plan_but_not_distributed():
    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            name="reviewer",
            description="Review specialist",
            tags=["review"],
            capabilities=[AgentCapability.REVIEW],
        ),
        object(),
    )
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            tags=["plan"],
            capabilities=[AgentCapability.PLAN],
        ),
        object(),
    )

    task = TaskPacket(
        task_id="task-1",
        goal="plan review the route",
        context={"collective_memory_evidence": [{"kind": "route", "content": "safe checkpoint route"}]},
        budget=TaskBudget(max_steps=2),
        origin_agent="supervisor",
    )
    planner = MatriarchRoutePlanner()
    supervisor = Supervisor(registry=registry)

    guided_plan = await planner.plan(
        supervisor=supervisor,
        task=task,
        registry=registry,
        coordination_policy=matriarch_coordination_policy(),
    )
    assert [invocation.agent_name for invocation in guided_plan.invocations] == ["planner", "reviewer"]
    assert guided_plan.reason is not None and guided_plan.reason.endswith(":matriarch_reordered")

    distributed_plan = await planner.plan(
        supervisor=supervisor,
        task=task,
        registry=registry,
        coordination_policy=distributed_coordination_policy(),
    )
    assert [invocation.agent_name for invocation in distributed_plan.invocations] == ["reviewer", "planner"]


def test_strict_baselines_disable_elephant_collective_memory_and_mgcm_policy():
    multi_agent = build_elephant_runtime_config(variant="multi_agent_default_context", char_budget=12000)
    single_agent = build_elephant_runtime_config(variant="single_agent_long_context", char_budget=18000)

    assert multi_agent.context_selector is None
    assert multi_agent.route_planner is None
    assert multi_agent.memory_evaluator is None
    assert multi_agent.context_policy.source_enabled("shared_memory") is False
    assert multi_agent.memory_policy.recall_mode == "off"
    assert multi_agent.memory_policy.promotion_mode == "off"
    assert multi_agent.memory_policy.validation_mode == "off"

    assert single_agent.context_policy.source_enabled("shared_memory") is False
    assert single_agent.context_policy.source_enabled("delegation_context") is False
    assert single_agent.memory_policy.recall_mode == "off"
    assert single_agent.memory_policy.promotion_mode == "off"

    assert get_elephant_variant("multi_agent_default_context").use_mgcm_memory_policy is False
    assert get_elephant_variant("single_agent_long_context").use_mgcm_memory_policy is False
