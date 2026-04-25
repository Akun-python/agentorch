from agentorch import ContextPolicy, ContextSelector, CoordinationPolicy, MemoryEvaluator, MemoryPolicy, RoutePlanner, StatePolicy
from agentorch.strategies import DefaultContextSelector, DefaultMemoryEvaluator, DefaultRoutePlanner


def test_public_policy_types_are_exported_and_old_strategy_surface_is_absent():
    import agentorch

    assert hasattr(agentorch, "ContextPolicy")
    assert hasattr(agentorch, "StatePolicy")
    assert hasattr(agentorch, "CoordinationPolicy")
    assert hasattr(agentorch, "MemoryPolicy")
    assert not hasattr(agentorch, "ContextStrategyConfig")
    assert not hasattr(agentorch, "CooperationStrategyConfig")
    assert not hasattr(agentorch, "LongHorizonStrategyConfig")
    assert not hasattr(agentorch, "MemoryGovernanceStrategyConfig")
    assert not hasattr(agentorch, "MatriarchalElephantStrategy")


def test_default_extension_points_implement_core_interfaces():
    selector = DefaultContextSelector()
    planner = DefaultRoutePlanner()
    evaluator = DefaultMemoryEvaluator()

    assert isinstance(selector, ContextSelector)
    assert isinstance(planner, RoutePlanner)
    assert isinstance(evaluator, MemoryEvaluator)


def test_policy_models_roundtrip_core_fields():
    context = ContextPolicy(char_budget=9000, conversation_window=5)
    state = StatePolicy(summary_refresh_every=8, snapshot_every=16, rollup_every=8)
    coordination = CoordinationPolicy(route_mode="hybrid", alert_mode="hybrid")
    memory = MemoryPolicy.long_horizon()

    assert context.char_budget == 9000
    assert state.summary_refresh_every == 8
    assert coordination.route_mode == "hybrid"
    assert memory.recall_mode == "hybrid"
