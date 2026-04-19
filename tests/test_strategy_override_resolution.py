from agentorch import AgentRegistry, AgentSpec, Runtime
from agentorch.config import RuntimeConfig
from agentorch.models.base import BaseModelAdapter
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.strategies import ContextPolicy, MemoryPolicy


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="ok"),
            content="ok",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def test_context_policy_resolution_priority_prefers_node_then_metadata_then_agent_then_runtime():
    registry = AgentRegistry()
    registry.register(
        AgentSpec.assistant(
            "planner",
            default_context_policy=ContextPolicy(char_budget=15000, selection_mode="rule"),
        ),
        object(),
    )
    runtime = Runtime(
        model=EchoModel(),
        agent_registry=registry,
        config=RuntimeConfig.agent(
            context_policy=ContextPolicy(char_budget=12000, selection_mode="rule"),
        ),
    )

    resolved_runtime = runtime._resolve_context_policy(agent_role="planner")
    resolved_metadata = runtime._resolve_context_policy(
        metadata={"context_policy": {"char_budget": 22000, "selection_mode": "hybrid"}},
        agent_role="planner",
    )
    resolved_node = runtime._resolve_context_policy(
        metadata={"context_policy": {"char_budget": 22000, "selection_mode": "hybrid"}},
        node_config={"context_policy": {"char_budget": 9999, "selection_mode": "rule"}},
        agent_role="planner",
    )

    assert resolved_runtime.char_budget == 15000
    assert resolved_metadata.selection_mode == "hybrid"
    assert resolved_node.char_budget == 9999


def test_memory_policy_resolution_supports_runtime_and_metadata_overrides():
    runtime = Runtime(
        model=EchoModel(),
        config=RuntimeConfig.agent(
            memory_policy=MemoryPolicy.long_horizon(
                thresholds_and_weights={"recall_top_k": 7},
            ),
        ),
    )
    resolved_runtime = runtime._resolve_memory_policy()
    resolved_metadata = runtime._resolve_memory_policy(
        metadata={
            "memory_policy": {
                "recall_mode": "scene",
                "promotion_mode": "validated",
                "validation_mode": "threshold",
                "thresholds_and_weights": {"recall_top_k": 3, "validation_threshold": 0.6},
            }
        }
    )
    evaluator = runtime.context_kernel.memory_evaluator
    assert resolved_runtime.thresholds_and_weights["recall_top_k"] == 7
    assert evaluator.resolved_runtime_config(resolved_runtime)["recall_top_k"] == 7
    assert resolved_metadata.validation_mode == "threshold"
    assert evaluator.resolved_runtime_config(resolved_metadata)["recall_top_k"] == 3
