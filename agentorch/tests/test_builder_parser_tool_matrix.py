from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

import agentorch
from agentorch.config import ModelConfig, RuntimeConfig
from agentorch.tools import ToolError, ToolRegistry
from agentorch.tools.base import FunctionTool
from agentorch.workflow import Node, WorkflowBuilder


class ValuePayload(BaseModel):
    value: str


class AddInput(BaseModel):
    a: int
    b: int


class EchoInput(BaseModel):
    text: str


class ValueModel(BaseModel):
    value: str


def test_parsing_helpers_cover_sync_async_and_fallback_paths() -> None:
    json_payload = "```json\n{\"name\": \"agentorch\"}\n```"
    assert agentorch.parse_json(json_payload) == {"name": "agentorch"}
    assert agentorch.parse_list("- alpha\n- beta") == ["alpha", "beta"]
    assert agentorch.parse_key_values("x: 1\ny=2") == {"x": "1", "y": "2"}

    parsed = agentorch.parse_pydantic("hello world", ValueModel)
    assert parsed.value == "hello world"

    parser = agentorch.parser_chain(agentorch.JSONParser(), agentorch.TextParser())
    parsed_json = asyncio.run(parser.parse("{\"ok\": true}"))
    prompt = agentorch.format_prompt("Summarize the result", agentorch.TextParser())

    assert parsed_json == {"ok": True}
    assert "Output format" in prompt
    assert "Return plain text only" in prompt


def test_workflow_node_helpers_and_builder_methods_cover_common_paths() -> None:
    model_node = Node.model_node("answer", prompt="answer the user")
    tool_node = Node.tool("lookup", "search_text", arguments={"query": "agent"})
    agent_node = Node.agent("delegate", "planner", input_from_variable="request", goal="plan the task")
    retrieve_node = Node.retrieve("retrieve", question="what is agentorch", output_key="retrieved")
    mount_node = Node.rag_mount("mount", from_variable="retrieved")
    router_node = Node.rag_router("route", output_key="route_info")
    evaluate_node = Node.rag_evaluate("evaluate", from_variable="retrieved", output_key="judgement")
    aggregate_node = Node.aggregate("aggregate", sources=["retrieved", "judgement"], output_key="combined")
    evolution_node = Node.evolution("evolve", output_key="best_candidate", include_history=True)

    chain = agentorch.Workflow.chain(model_node, tool_node, entry_node="answer")
    builder = (
        WorkflowBuilder(max_steps=9)
        .add(retrieve_node, entry=True)
        .connect("retrieve", "mount")
        .add(mount_node)
        .then(router_node)
        .then(evaluate_node, edge_kind="condition", condition="needs_review")
    )
    built = builder.build()

    assert tool_node.config["tool_name"] == "search_text"
    assert agent_node.config["agent_name"] == "planner"
    assert retrieve_node.config["question"] == "what is agentorch"
    assert mount_node.config["from_variable"] == "retrieved"
    assert router_node.config["output_key"] == "route_info"
    assert evaluate_node.config["from_variable"] == "retrieved"
    assert aggregate_node.config["sources"] == ["retrieved", "judgement"]
    assert evolution_node.config["include_history"] is True
    assert chain.get_node("answer").config["prompt"] == "answer the user"
    assert chain.get_edges("answer")[0].target == "lookup"
    assert built.entry_node == "retrieve"
    assert built.get_edges("mount")[0].target == "route"
    assert built.max_steps == 9

    with pytest.raises(KeyError):
        chain.get_node("missing")
    with pytest.raises(ValueError):
        WorkflowBuilder().build()


def test_tool_registry_methods_cover_register_extend_execute_and_lifecycle() -> None:
    closed = {"sync": False, "async": False}

    @agentorch.tool(description="Add two numbers")
    def add_numbers(payload: AddInput) -> dict[str, int]:
        return {"sum": payload.a + payload.b}

    async def echo_text(payload: EchoInput) -> dict[str, str]:
        return {"echo": payload.text}

    async def aclose_callback() -> None:
        closed["async"] = True

    def close_callback() -> None:
        closed["sync"] = True

    echo_tool = FunctionTool(
        name="echo_text",
        description="Echo text",
        input_model=EchoInput,
        func=echo_text,
        aclose_callback=aclose_callback,
        close_callback=close_callback,
    )

    registry = ToolRegistry.empty().register_many(add_numbers)
    registry.extend(ToolRegistry.from_tools(echo_tool))

    specs = registry.list_specs()
    add_result = asyncio.run(registry.execute("add_numbers", {"a": 2, "b": 3}))
    echo_result = asyncio.run(registry.execute("echo_text", {"text": "hello"}))
    asyncio.run(registry.aclose())
    registry.close()

    assert "add_numbers" in registry
    assert "echo_text" in registry
    assert {item["function"]["name"] for item in specs} == {"add_numbers", "echo_text"}
    assert add_result.data["sum"] == 5
    assert echo_result.data["echo"] == "hello"
    assert closed == {"sync": True, "async": True}

    with pytest.raises(ToolError):
        asyncio.run(registry.execute("add_numbers", {"a": 2}))


def test_runtime_and_model_config_helper_methods_cover_common_construction_paths() -> None:
    model_config = ModelConfig.from_any("demo-model", provider="openai_http", max_tokens=128)
    agent_config = RuntimeConfig.agent(
        system_prompt="Use evidence.",
        rag="classic",
        reasoning="react",
        default_knowledge_scope=["demo"],
    )
    workflow_config = RuntimeConfig.workflow(reasoning="plan_execute", max_steps=12)

    assert model_config.model == "demo-model"
    assert model_config.provider == "openai_http"
    assert model_config.max_tokens == 128
    assert agent_config.reasoning_strategy is not None and agent_config.reasoning_strategy.kind.value == "react"
    assert agent_config.rag_strategy is not None and agent_config.rag_strategy.mode == "classic"
    assert agent_config.default_knowledge_scope == ["demo"]
    assert workflow_config.retrieval_mode.value == "explicit_step"
    assert workflow_config.max_steps == 12
