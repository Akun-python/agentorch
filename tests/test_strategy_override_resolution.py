from agentorch import AgentRegistry, AgentSpec, Runtime
from agentorch.config import RuntimeConfig
from agentorch.models.base import BaseModelAdapter
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.strategies import create_memory_governance_strategy


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="ok"),
            content="ok",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def test_context_strategy_resolution_priority_prefers_node_then_metadata_then_agent_then_runtime():
    registry = AgentRegistry()
    registry.register(
        AgentSpec.assistant(
            "planner",
            default_context_strategy={"kind": "balanced", "mode": "balanced"},
        ),
        object(),
    )
    runtime = Runtime(
        model=EchoModel(),
        agent_registry=registry,
        config=RuntimeConfig.agent(
            orchestration_profile="deep_research",
            context_strategy={"kind": "compact", "mode": "compact"},
        ),
    )

    resolved_runtime = runtime._resolve_context_strategy(agent_role="planner")
    resolved_metadata = runtime._resolve_context_strategy(
        metadata={"context_strategy": {"kind": "research_heavy", "mode": "research_heavy"}},
        agent_role="planner",
    )
    resolved_node = runtime._resolve_context_strategy(
        metadata={"context_strategy": {"kind": "research_heavy", "mode": "research_heavy"}},
        node_config={"context_strategy": {"kind": "compact", "mode": "compact", "prompt_char_budget": 9999}},
        agent_role="planner",
    )

    assert resolved_runtime.kind == "balanced"
    assert resolved_metadata.kind == "research_heavy"
    assert resolved_node.prompt_char_budget == 9999


def test_memory_governance_strategy_supports_builtin_and_custom_policy_selection():
    runtime = Runtime(
        model=EchoModel(),
        config=RuntimeConfig.agent(
            memory_governance_strategy={
                "kind": "nutcracker_memory",
                "recall_top_k": 7,
            },
        ),
    )
    resolved_runtime = runtime._resolve_memory_governance_strategy()
    resolved_metadata = runtime._resolve_memory_governance_strategy(
        metadata={
            "memory_governance_strategy": {
                "kind": "custom",
                "promotion_policy": "episodic_salience",
                "index_policy": "scene_hash",
                "recall_policy": "scene_first",
                "decay_policy": "relevance_only",
                "config": {"recall_top_k": 3},
            }
        }
    )
    runtime_strategy = create_memory_governance_strategy(resolved_runtime)
    metadata_strategy = create_memory_governance_strategy(resolved_metadata)
    assert resolved_runtime.kind == "nutcracker_memory"
    assert runtime_strategy.resolved_runtime_config()["recall_top_k"] == 7
    assert resolved_metadata.kind == "custom"
    assert metadata_strategy.policy_bundle()["promotion_policy"] == "episodic_salience"
    assert metadata_strategy.resolved_runtime_config()["recall_top_k"] == 3
