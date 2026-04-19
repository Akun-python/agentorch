import asyncio

from agentorch import AgentCapability, AgentRegistry, AgentSpec, Supervisor, TaskBudget, TaskPacket
from experiments.elephant_context import (
    ElephantContextSelector,
    ElephantMemoryEvaluator,
    MatriarchRoutePlanner,
    build_elephant_runtime_config,
    distributed_coordination_policy,
    matriarch_coordination_policy,
)
from experiments.common.config import ExperimentConfig
from experiments.common.runtime_variants import build_runtime_variant


def test_variant_flags_disable_expected_mechanisms(tmp_path):
    config = ExperimentConfig.for_variant(
        experiment_name="rq1_long_horizon_tasks",
        variant_name="multi_agent_no_elephant",
        model_name="mock:tool",
        judge_model_name=None,
        prompt_budget=12000,
        task_limit=1,
        repeat_count=1,
        output_dir=tmp_path,
        enable_live_web_search=False,
        seed=7,
    )
    runtime, metadata = build_runtime_variant(config, workspace_root=tmp_path, output_dir=tmp_path / "out1")
    assert runtime.config.coordination_policy.route_mode == "distributed"
    assert metadata["method_flags"]["elephant_attention"] is False

    plain_logs = ExperimentConfig.for_variant(
        experiment_name="rq5_observability",
        variant_name="multi_agent_plain_logs",
        model_name="mock:tool",
        judge_model_name=None,
        prompt_budget=12000,
        task_limit=1,
        repeat_count=1,
        output_dir=tmp_path,
        enable_live_web_search=False,
        seed=7,
    )
    runtime_plain, metadata_plain = build_runtime_variant(plain_logs, workspace_root=tmp_path, output_dir=tmp_path / "out2")
    assert runtime_plain.observability.enabled is False
    assert metadata_plain["sqlite_path"] is None


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
