from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentorch import ToolRegistry, create_agent as create_agent_agentorch
from agentorch.core import Message, ModelRequest, ModelResponse, ToolCall, UsageInfo
from agentorch.knowledge import Document as AgentOrchDocument
from agentorch.knowledge import InMemoryKnowledgeBase, RagStrategyConfig
from agentorch.models.base import BaseModelAdapter
from agentorch.models.openai_model import OpenAIModel
from agentorch.tools import tool as agentorch_tool
from agentorch.workflow import Context, Edge, Node, Workflow, WorkflowRunner

from langchain.agents import create_agent as create_agent_langchain
from langchain_core.documents import Document as LCDocument
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import tool as lc_tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class AddInput(BaseModel):
    a: int
    b: int


@agentorch_tool(description="Add two integers.")
async def add_numbers_agentorch(input: AddInput):
    return {"sum": input.a + input.b}


@lc_tool(args_schema=AddInput)
def add_numbers_langchain(a: int, b: int) -> dict[str, int]:
    """Add two integers."""
    return {"sum": a + b}


@agentorch_tool(name="add_numbers", description="Add two integers.")
async def add_numbers_agentorch_real(input: AddInput):
    return {"sum": input.a + input.b}


@lc_tool("add_numbers", args_schema=AddInput)
def add_numbers_langchain_real(a: int, b: int) -> dict[str, int]:
    """Add two integers."""
    return {"sum": a + b}


class AgentOrchToolModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        last_tool = next((m.content for m in reversed(request.messages) if m.role == "tool"), "")
        if last_tool:
            text = f"Final answer based on tool: {last_tool}"
            return ModelResponse(
                message=Message(role="assistant", content=text),
                content=text,
                finish_reason="stop",
                usage=UsageInfo(total_tokens=10),
            )
        tool_call = ToolCall(
            id="call-1",
            name="add_numbers_agentorch",
            arguments={"a": 123, "b": 456},
        )
        return ModelResponse(
            message=Message(role="assistant", content="", tool_calls=[tool_call]),
            content="",
            tool_calls=[tool_call],
            finish_reason="tool_calls",
            usage=UsageInfo(total_tokens=5),
        )


class LangChainToolModel(BaseChatModel):
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "tool-bench-chat"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {}

    def bind_tools(self, tools: Sequence[Any], *, tool_choice: str | None = None, **kwargs: Any) -> Runnable:
        return self

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        self.calls += 1
        last_tool = next((m for m in reversed(messages) if isinstance(m, ToolMessage)), None)
        if last_tool is not None:
            msg = AIMessage(content=f"Final answer based on tool: {last_tool.content}")
            return ChatResult(generations=[ChatGeneration(message=msg)])
        msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "add_numbers_langchain",
                    "args": {"a": 123, "b": 456},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        )
        return ChatResult(generations=[ChatGeneration(message=msg)])


class AgentOrchMemoryModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.last_user_count = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        users = [m.content for m in request.messages if m.role == "user"]
        self.last_user_count = len(users)
        if users and users[-1].startswith("What is my favorite animal"):
            remembered = "UNKNOWN"
            for text in users[:-1]:
                if text.startswith("My favorite animal is "):
                    remembered = text.replace("My favorite animal is ", "").strip(". ")
            text = remembered
        else:
            text = "stored"
        return ModelResponse(
            message=Message(role="assistant", content=text),
            content=text,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=8),
        )


class LangChainMemoryModel(BaseChatModel):
    observed_human_messages: int = 0

    @property
    def _llm_type(self) -> str:
        return "memory-probe-chat"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {}

    def bind_tools(self, tools: Sequence[Any], *, tool_choice: str | None = None, **kwargs: Any) -> Runnable:
        return self

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        users = [str(m.content) for m in messages if getattr(m, "type", "") == "human"]
        self.observed_human_messages = len(users)
        if users and users[-1].startswith("What is my favorite animal"):
            remembered = "UNKNOWN"
            for text in users[:-1]:
                if text.startswith("My favorite animal is "):
                    remembered = text.replace("My favorite animal is ", "").strip(". ")
            msg = AIMessage(content=remembered)
        else:
            msg = AIMessage(content="stored")
        return ChatResult(generations=[ChatGeneration(message=msg)])


class AgentOrchRagModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.last_system_prompt = ""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        system_text = "\n".join(m.content for m in request.messages if m.role == "system")
        self.last_system_prompt = system_text
        match = re.search(r"Deployment restriction: .*", system_text)
        evidence = match.group(0) if match else "NO_EVIDENCE"
        text = f"Restriction: owner approval is required before release. Evidence: {evidence}"
        return ModelResponse(
            message=Message(role="assistant", content=text),
            content=text,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=18),
        )


class LangChainRagModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "rag-chat"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {}

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        system_text = "\n".join(str(m.content) for m in messages if getattr(m, "type", "") == "system")
        match = re.search(r"Deployment restriction: .*", system_text)
        evidence = match.group(0) if match else "NO_EVIDENCE"
        msg = AIMessage(content=f"Restriction: owner approval is required before release. Evidence: {evidence}")
        return ChatResult(generations=[ChatGeneration(message=msg)])


def load_env_file(path: Path) -> dict[str, str]:
    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def normalize_base_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned[: -len("/chat/completions")]
    return cleaned


def normalize_answer_token(text: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "", text.strip().lower())


def truncate_error(exc: Exception, limit: int = 220) -> str:
    payload = f"{type(exc).__name__}: {exc}"
    return payload[:limit]


def build_agentorch_real_model(model_name: str, api_key: str, base_url: str) -> OpenAIModel:
    return OpenAIModel(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        timeout=90.0,
        max_retries=1,
        temperature=0.0,
    )


def build_langchain_real_model(model_name: str, api_key: str, base_url: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        timeout=90.0,
        max_retries=1,
        temperature=0.0,
        use_responses_api=False,
    )


def probe_real_model(model_name: str, api_key: str, base_url: str) -> tuple[bool, str]:
    try:
        model = build_langchain_real_model(model_name=model_name, api_key=api_key, base_url=base_url)
        response = model.invoke("Reply with exactly PONG.")
        return normalize_answer_token(response.content) == "pong", str(response.content).strip()
    except Exception as exc:
        return False, truncate_error(exc)


def resolve_real_model(api_key: str, base_url: str, requested_model: str | None = None) -> tuple[str | None, list[dict[str, str]]]:
    candidates = [requested_model] if requested_model else ["gpt-4o-mini", "gpt-4o", "deepseek-chat", "qwen-plus"]
    attempts: list[dict[str, str]] = []
    for candidate in candidates:
        if not candidate:
            continue
        ok, detail = probe_real_model(candidate, api_key=api_key, base_url=base_url)
        attempts.append({"model": candidate, "status": "ok" if ok else "failed", "detail": detail})
        if ok:
            return candidate, attempts
    return None, attempts


def run_agentorch_tool() -> dict[str, Any]:
    model = AgentOrchToolModel()
    agent = create_agent_agentorch(
        model=model,
        tools=ToolRegistry.from_tools(add_numbers_agentorch),
        reasoning="react",
    )
    started = time.perf_counter()
    result = agent.run_sync(
        "Use add_numbers to compute 123 + 456 and explain the result in one sentence.",
        thread_id="cmp-tool-at",
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "success": "579" in result.output_text and len(result.tool_results) == 1,
        "output": result.output_text,
        "tool_results": [item.output for item in result.tool_results],
        "tool_call_count": len(result.tool_results),
        "model_calls": model.calls,
        "elapsed_ms": round(elapsed_ms, 2),
    }


def run_langchain_tool() -> dict[str, Any]:
    model = LangChainToolModel()
    agent = create_agent_langchain(model=model, tools=[add_numbers_langchain], system_prompt="You are concise.")
    started = time.perf_counter()
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Use add_numbers to compute 123 + 456 and explain the result in one sentence.",
                }
            ]
        }
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    final_message = result["messages"][-1]
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    return {
        "success": "579" in final_message.content and len(tool_messages) == 1,
        "output": final_message.content,
        "tool_results": [m.content for m in tool_messages],
        "tool_call_count": len(tool_messages),
        "message_types": [type(m).__name__ for m in result["messages"]],
        "model_calls": model.calls,
        "elapsed_ms": round(elapsed_ms, 2),
    }


def run_agentorch_memory() -> dict[str, Any]:
    model = AgentOrchMemoryModel()
    agent = create_agent_agentorch(model=model, reasoning="react")
    agent.run_sync("My favorite animal is seagull.", thread_id="cmp-mem-at")
    result = agent.run_sync("What is my favorite animal? Answer with one word.", thread_id="cmp-mem-at")
    return {
        "success": result.output_text.strip().lower() == "seagull",
        "turn2_output": result.output_text,
        "observed_user_messages_on_turn2": model.last_user_count,
    }


def run_langchain_memory() -> dict[str, Any]:
    plain_model = LangChainMemoryModel()
    plain_agent = create_agent_langchain(model=plain_model, tools=[])
    plain_agent.invoke({"messages": [{"role": "user", "content": "My favorite animal is seagull."}]})
    plain_result = plain_agent.invoke({"messages": [{"role": "user", "content": "What is my favorite animal? Answer with one word."}]})

    memory_model = LangChainMemoryModel()
    memory_agent = create_agent_langchain(model=memory_model, tools=[], checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "cmp-mem-lc"}}
    memory_agent.invoke({"messages": [{"role": "user", "content": "My favorite animal is seagull."}]}, config=config)
    memory_result = memory_agent.invoke(
        {"messages": [{"role": "user", "content": "What is my favorite animal? Answer with one word."}]},
        config=config,
    )

    return {
        "default_agent": {
            "success": plain_result["messages"][-1].content.strip().lower() == "seagull",
            "turn2_output": plain_result["messages"][-1].content,
            "observed_user_messages_on_turn2": plain_model.observed_human_messages,
        },
        "with_checkpointer": {
            "success": memory_result["messages"][-1].content.strip().lower() == "seagull",
            "turn2_output": memory_result["messages"][-1].content,
            "observed_user_messages_on_turn2": memory_model.observed_human_messages,
        },
    }


async def run_agentorch_rag_async() -> dict[str, Any]:
    knowledge_base = InMemoryKnowledgeBase()
    await knowledge_base.ingest(
        [
            AgentOrchDocument(
                id="doc1",
                text="Deployment restriction: owner approval is required before release.",
                metadata={"scopes": ["policy"]},
            ),
            AgentOrchDocument(
                id="doc2",
                text="Refund policy: refunds are allowed within 7 days.",
                metadata={"scopes": ["policy"]},
            ),
        ]
    )
    model = AgentOrchRagModel()
    agent = create_agent_agentorch(
        model=model,
        knowledge_base=knowledge_base,
        rag=RagStrategyConfig.for_deliberative(knowledge_scope=["policy"]),
        reasoning="react",
        enable_memory=False,
    )
    result = await agent.run("What is the deployment restriction? Cite evidence.", thread_id="cmp-rag-at")
    return {
        "success": "owner approval" in result.output_text.lower() and "deployment restriction" in result.output_text.lower(),
        "output": result.output_text,
        "prompt_has_retrieved_knowledge": "Retrieved Knowledge:" in model.last_system_prompt,
        "prompt_has_citations": "Citations:" in model.last_system_prompt,
        "prompt_contains_thread_history_citation": "thread_history" in model.last_system_prompt,
    }


def run_langchain_rag() -> dict[str, Any]:
    documents = [
        LCDocument(
            page_content="Deployment restriction: owner approval is required before release.",
            metadata={"source": "doc1"},
        ),
        LCDocument(page_content="Refund policy: refunds are allowed within 7 days.", metadata={"source": "doc2"}),
    ]

    def retrieve(question: str) -> dict[str, str]:
        selected = [doc for doc in documents if "deployment" in doc.page_content.lower()]
        context = "\n".join(f"[{doc.metadata['source']}] {doc.page_content}" for doc in selected)
        return {"question": question, "context": context}

    chain = (
        RunnableLambda(retrieve)
        | ChatPromptTemplate.from_messages(
            [
                ("system", "Answer using only this context and cite evidence.\nContext:\n{context}"),
                ("human", "{question}"),
            ]
        )
        | LangChainRagModel()
    )
    result = chain.invoke("What is the deployment restriction? Cite evidence.")
    return {
        "success": "owner approval" in result.content.lower() and "deployment restriction" in result.content.lower(),
        "output": result.content,
        "retrieval_wiring": "manual_retriever_plus_prompt",
    }


def run_agentorch_workflow_graph() -> dict[str, Any]:
    async def double_handler(node: Node, context: Context) -> dict[str, Any]:
        return {"status": "completed", "value": context.state["value"] * 2}

    async def format_handler(node: Node, context: Context) -> dict[str, Any]:
        value = context.variables["double"]["value"]
        return {"status": "completed", "text": f"value={value}"}

    workflow = Workflow(
        entry_node="double",
        nodes=[
            Node(id="double", kind="tool"),
            Node(id="format", kind="aggregate"),
        ],
        edges=[
            Edge(source="double", target="format", kind="success"),
        ],
    )
    runner = WorkflowRunner({"tool": double_handler, "aggregate": format_handler})
    result = asyncio.run(runner.run(workflow, Context(thread_id="wf-at", user_input="unused", state={"value": 3})))
    return {
        "success": result.get("text") == "value=6",
        "result": result,
        "node_order": ["double", "format"],
    }


def run_langchain_workflow_graph() -> dict[str, Any]:
    class GraphState(dict):
        pass

    def double_node(state: dict[str, Any]) -> dict[str, Any]:
        return {"value": state["value"] * 2}

    def format_node(state: dict[str, Any]) -> dict[str, Any]:
        return {"text": f"value={state['value']}"}

    graph = StateGraph(dict)
    graph.add_node("double", double_node)
    graph.add_node("format", format_node)
    graph.add_edge(START, "double")
    graph.add_edge("double", "format")
    graph.add_edge("format", END)
    app = graph.compile()
    result = app.invoke({"value": 3})
    return {
        "success": result.get("text") == "value=6",
        "result": result,
        "graph_nodes": ["double", "format"],
    }


def run_inspection_surface() -> dict[str, Any]:
    agentorch_agent = create_agent_agentorch(
        model=AgentOrchToolModel(),
        tools=ToolRegistry.from_tools(add_numbers_agentorch),
        reasoning="react",
    )
    langchain_agent = create_agent_langchain(
        model=LangChainToolModel(),
        tools=[add_numbers_langchain],
        system_prompt="You are concise.",
    )
    return {
        "agentorch_inspect_keys": sorted(agentorch_agent.inspect().keys()),
        "agentorch_runtime_keys": sorted(agentorch_agent.inspect().get("runtime", {}).keys()),
        "langchain_graph_nodes": sorted(langchain_agent.get_graph().nodes.keys()),
        "langchain_graph_edge_count": len(langchain_agent.get_graph().edges),
    }


def run_agentorch_real_tool(*, model_name: str, api_key: str, base_url: str, run_suffix: str) -> dict[str, Any]:
    agent = create_agent_agentorch(
        model=build_agentorch_real_model(model_name=model_name, api_key=api_key, base_url=base_url),
        tools=ToolRegistry.from_tools(add_numbers_agentorch_real),
        system_prompt=(
            "You are concise. When the add_numbers tool is available, you must use it for arithmetic. "
            "Return the final result in the form RESULT=<integer>."
        ),
        reasoning="react",
    )
    started = time.perf_counter()
    result = agent.run_sync(
        "Compute 123 + 456. You must use the add_numbers tool, not mental math.",
        thread_id=f"real-tool-at-{run_suffix}",
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "success": "579" in result.output_text and len(result.tool_results) >= 1,
        "output": result.output_text,
        "tool_call_count": len(result.tool_results),
        "tool_outputs": [item.output for item in result.tool_results],
        "elapsed_ms": round(elapsed_ms, 2),
    }


def run_langchain_real_tool(*, model_name: str, api_key: str, base_url: str) -> dict[str, Any]:
    agent = create_agent_langchain(
        model=build_langchain_real_model(model_name=model_name, api_key=api_key, base_url=base_url),
        tools=[add_numbers_langchain_real],
        system_prompt=(
            "You are concise. When the add_numbers tool is available, you must use it for arithmetic. "
            "Return the final result in the form RESULT=<integer>."
        ),
    )
    started = time.perf_counter()
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Compute 123 + 456. You must use the add_numbers tool, not mental math.",
                }
            ]
        }
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    final_message = result["messages"][-1]
    return {
        "success": "579" in final_message.content and len(tool_messages) >= 1,
        "output": final_message.content,
        "tool_call_count": len(tool_messages),
        "tool_outputs": [m.content for m in tool_messages],
        "elapsed_ms": round(elapsed_ms, 2),
    }


def run_agentorch_real_memory(*, model_name: str, api_key: str, base_url: str, run_suffix: str) -> dict[str, Any]:
    agent = create_agent_agentorch(
        model=build_agentorch_real_model(model_name=model_name, api_key=api_key, base_url=base_url),
        system_prompt="Answer with exactly one token. If the answer is missing from conversation history, reply ONLY UNKNOWN.",
        reasoning="react",
    )
    thread_id = f"real-memory-at-{run_suffix}"
    agent.run_sync("My invented keyword is glorbax.", thread_id=thread_id)
    result = agent.run_sync("What is my invented keyword? Reply with one token.", thread_id=thread_id)
    token = normalize_answer_token(result.output_text)
    return {
        "success": token == "glorbax",
        "output": result.output_text,
        "normalized_output": token,
    }


def run_langchain_real_memory(*, model_name: str, api_key: str, base_url: str, run_suffix: str) -> dict[str, Any]:
    plain_agent = create_agent_langchain(
        model=build_langchain_real_model(model_name=model_name, api_key=api_key, base_url=base_url),
        tools=[],
        system_prompt="Answer with exactly one token. If the answer is missing from conversation history, reply ONLY UNKNOWN.",
    )
    plain_agent.invoke({"messages": [{"role": "user", "content": "My invented keyword is glorbax."}]})
    plain_result = plain_agent.invoke({"messages": [{"role": "user", "content": "What is my invented keyword? Reply with one token."}]})

    mem_agent = create_agent_langchain(
        model=build_langchain_real_model(model_name=model_name, api_key=api_key, base_url=base_url),
        tools=[],
        system_prompt="Answer with exactly one token. If the answer is missing from conversation history, reply ONLY UNKNOWN.",
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": f"real-memory-lc-{run_suffix}"}}
    mem_agent.invoke({"messages": [{"role": "user", "content": "My invented keyword is glorbax."}]}, config=config)
    mem_result = mem_agent.invoke(
        {"messages": [{"role": "user", "content": "What is my invented keyword? Reply with one token."}]},
        config=config,
    )
    return {
        "default_agent": {
            "success": normalize_answer_token(plain_result["messages"][-1].content) == "glorbax",
            "output": plain_result["messages"][-1].content,
            "normalized_output": normalize_answer_token(plain_result["messages"][-1].content),
        },
        "with_checkpointer": {
            "success": normalize_answer_token(mem_result["messages"][-1].content) == "glorbax",
            "output": mem_result["messages"][-1].content,
            "normalized_output": normalize_answer_token(mem_result["messages"][-1].content),
        },
    }


async def run_agentorch_real_rag_async(*, model_name: str, api_key: str, base_url: str, run_suffix: str) -> dict[str, Any]:
    knowledge_base = InMemoryKnowledgeBase()
    await knowledge_base.ingest(
        [
            AgentOrchDocument(
                id="doc1",
                text="Deployment restriction token: skylark-approval is required before release.",
                metadata={"scopes": ["policy"]},
            ),
            AgentOrchDocument(
                id="doc2",
                text="Refund token: amber-refund applies within 7 days.",
                metadata={"scopes": ["policy"]},
            ),
        ]
    )
    agent = create_agent_agentorch(
        model=build_agentorch_real_model(model_name=model_name, api_key=api_key, base_url=base_url),
        knowledge_base=knowledge_base,
        rag=RagStrategyConfig.for_deliberative(knowledge_scope=["policy"]),
        system_prompt="Answer only from retrieved evidence. If missing, reply ONLY UNKNOWN. Include the exact token.",
        reasoning="react",
        enable_memory=False,
    )
    result = await agent.run(
        "What exact deployment restriction token is required before release? Cite the evidence briefly.",
        thread_id=f"real-rag-at-{run_suffix}",
    )
    token = normalize_answer_token(result.output_text)
    return {
        "success": "skylark-approval" in token,
        "output": result.output_text,
        "normalized_output": token,
    }


def run_langchain_real_rag(*, model_name: str, api_key: str, base_url: str) -> dict[str, Any]:
    documents = [
        LCDocument(page_content="Deployment restriction token: skylark-approval is required before release.", metadata={"source": "doc1"}),
        LCDocument(page_content="Refund token: amber-refund applies within 7 days.", metadata={"source": "doc2"}),
    ]

    def retrieve(question: str) -> dict[str, str]:
        selected = [doc for doc in documents if "deployment restriction token" in doc.page_content.lower()]
        context = "\n".join(f"[{doc.metadata['source']}] {doc.page_content}" for doc in selected)
        return {"question": question, "context": context}

    chain = (
        RunnableLambda(retrieve)
        | ChatPromptTemplate.from_messages(
            [
                ("system", "Answer only from this context. If missing, reply ONLY UNKNOWN. Include the exact token.\nContext:\n{context}"),
                ("human", "{question}"),
            ]
        )
        | build_langchain_real_model(model_name=model_name, api_key=api_key, base_url=base_url)
    )
    result = chain.invoke("What exact deployment restriction token is required before release? Cite the evidence briefly.")
    token = normalize_answer_token(result.content)
    return {
        "success": "skylark-approval" in token,
        "output": result.content,
        "normalized_output": token,
    }


def collect_real_model_results(*, env_file: Path, requested_model: str | None = None) -> dict[str, Any]:
    loaded = load_env_file(env_file)
    api_key = loaded.get("OPENAI_API_KEY") or loaded.get("API_KEY")
    base_url = normalize_base_url(loaded.get("OPENAI_BASE_URL") or loaded.get("BASE_URL"))
    if not api_key or not base_url:
        return {
            "available": False,
            "env_file": str(env_file),
            "error": "API_KEY/BASE_URL not found in env file.",
        }

    model_name, probe_attempts = resolve_real_model(api_key=api_key, base_url=base_url, requested_model=requested_model)
    if model_name is None:
        return {
            "available": False,
            "env_file": str(env_file),
            "probe_attempts": probe_attempts,
            "error": "No working model was found from the candidate list.",
        }

    run_suffix = str(int(time.time()))
    return {
        "available": True,
        "env_file": str(env_file),
        "selected_model": model_name,
        "probe_attempts": probe_attempts,
        "tool_call": {
            "question": "Compute 123 + 456. You must use the add_numbers tool, not mental math.",
            "agentorch": run_agentorch_real_tool(model_name=model_name, api_key=api_key, base_url=base_url, run_suffix=run_suffix),
            "langchain": run_langchain_real_tool(model_name=model_name, api_key=api_key, base_url=base_url),
        },
        "memory": {
            "turn1": "My invented keyword is glorbax.",
            "turn2": "What is my invented keyword? Reply with one token.",
            "agentorch": run_agentorch_real_memory(model_name=model_name, api_key=api_key, base_url=base_url, run_suffix=run_suffix),
            "langchain": run_langchain_real_memory(model_name=model_name, api_key=api_key, base_url=base_url, run_suffix=run_suffix),
        },
        "rag": {
            "question": "What exact deployment restriction token is required before release? Cite the evidence briefly.",
            "agentorch": asyncio.run(run_agentorch_real_rag_async(model_name=model_name, api_key=api_key, base_url=base_url, run_suffix=run_suffix)),
            "langchain": run_langchain_real_rag(model_name=model_name, api_key=api_key, base_url=base_url),
        },
    }


def collect_results() -> dict[str, Any]:
    return {
        "environment": {
            "python": "{}".format(__import__("sys").version),
            "cwd": str(Path.cwd()),
        },
        "tool_call": {
            "question": "Use add_numbers to compute 123 + 456 and explain the result in one sentence.",
            "agentorch": run_agentorch_tool(),
            "langchain": run_langchain_tool(),
        },
        "memory": {
            "turn1": "My favorite animal is seagull.",
            "turn2": "What is my favorite animal? Answer with one word.",
            "agentorch": run_agentorch_memory(),
            "langchain": run_langchain_memory(),
        },
        "rag": {
            "question": "What is the deployment restriction? Cite evidence.",
            "agentorch": asyncio.run(run_agentorch_rag_async()),
            "langchain": run_langchain_rag(),
        },
        "workflow_graph": {
            "task": "Start with value=3, double it, then format the final text.",
            "agentorch": run_agentorch_workflow_graph(),
            "langchain": run_langchain_workflow_graph(),
        },
        "inspection_surface": run_inspection_surface(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local agentorch vs LangChain/LangGraph comparison.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--env-file", type=Path, default=None, help="Optional .env file to load for real-model comparison.")
    parser.add_argument("--real-model", type=str, default=None, help="Optional explicit model name for real-model comparison.")
    args = parser.parse_args()

    results = collect_results()
    if args.env_file is not None:
        results["real_model_compare"] = collect_real_model_results(env_file=args.env_file, requested_model=args.real_model)
    rendered = json.dumps(results, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
