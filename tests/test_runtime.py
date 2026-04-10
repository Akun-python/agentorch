import asyncio
from pydantic import BaseModel

from agentorch.agents import AgentCapability, AgentRegistry, AgentSpec, Supervisor
from agentorch.core import Message, ModelRequest, ModelResponse, PromptContext, StreamChunk, ToolCall, UsageInfo
from agentorch.knowledge import RagStrategyConfig, RetrievalReport
from agentorch.reasoning import ReasoningStrategyConfig
from agentorch.models.base import BaseModelAdapter
from agentorch.memory import MemoryManager
from agentorch.prompts import ChatPromptTemplate, MessagesPlaceholderCard, TextPromptCard
from agentorch.runtime import Agent, Runtime
from agentorch.runtime.context_compaction import compact_task_packet
from agentorch.config import MemoryConfig, RuntimeConfig
from agentorch.strategies import BaseContextStrategy, ContextStrategyConfig, create_memory_governance_strategy
from agentorch.tools import ToolRegistry, tool
from agentorch.knowledge import IndexedKnowledgeBase


class FakeModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.calls = 0
        self.seen_requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.seen_requests.append(request)
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"query": "weather"})],
                    metadata={},
                ),
                content="",
                tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"query": "weather"})],
                finish_reason="tool_calls",
                usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        return ModelResponse(
            message=Message(role="assistant", content="The weather is sunny."),
            content="The weather is sunny.",
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        )


class StreamingTextModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="unused"),
            content="unused",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )

    async def stream(self, request: ModelRequest):
        yield StreamChunk(delta_text="Hello ")
        yield StreamChunk(delta_text="streaming world", finish_reason="stop")


class LookupInput(BaseModel):
    query: str


@tool(description="Return a fake lookup result.")
async def lookup(input: LookupInput):
    return {"query": input.query, "result": "sunny"}


def test_runtime_runs_model_tool_and_finish():
    asyncio.run(_test_runtime_runs_model_tool_and_finish())


async def _test_runtime_runs_model_tool_and_finish():
    model = FakeModel()
    tools = ToolRegistry()
    tools.register(lookup)
    runtime = Runtime(model=model, tools=tools)
    agent = Agent(runtime=runtime)
    result = await agent.run("what is the weather", thread_id="thread-1")
    assert result.output_text == "The weather is sunny."
    assert len(result.tool_results) == 1
    assert result.usage.total_tokens == 25
    second_request = model.seen_requests[1]
    assert len(second_request.messages) == 4
    assistant_messages = [message for message in second_request.messages if message.role == "assistant"]
    assert assistant_messages
    assert assistant_messages[-1].tool_calls[0].name == "lookup"


def test_runtime_stream_emits_model_delta_and_final_result():
    asyncio.run(_test_runtime_stream_emits_model_delta_and_final_result())


async def _test_runtime_stream_emits_model_delta_and_final_result():
    runtime = Runtime(model=StreamingTextModel())
    agent = Agent(runtime=runtime)
    events = [event async for event in agent.run("hello", thread_id="stream-thread", stream=True)]
    event_types = [event.event_type for event in events]
    assert "run_started" in event_types
    assert "reasoning_started" in event_types
    assert event_types.count("model_delta") == 2
    assert event_types[-1] == "final_result"
    assert events[-1].result is not None
    assert events[-1].result.output_text == "Hello streaming world"


def test_runtime_stream_emits_tool_events():
    asyncio.run(_test_runtime_stream_emits_tool_events())


async def _test_runtime_stream_emits_tool_events():
    model = FakeModel()
    tools = ToolRegistry()
    tools.register(lookup)
    runtime = Runtime(model=model, tools=tools)
    agent = Agent(runtime=runtime)
    events = [event async for event in agent.run("what is the weather", thread_id="tool-stream-thread", stream=True)]
    event_types = [event.event_type for event in events]
    assert "tool_called" in event_types
    assert "tool_result" in event_types
    assert events[-1].event_type == "final_result"
    assert events[-1].result is not None
    assert events[-1].result.output_text == "The weather is sunny."


def test_runtime_acreate_accepts_custom_tools_and_web_tools():
    asyncio.run(_test_runtime_acreate_accepts_custom_tools_and_web_tools())


async def _test_runtime_acreate_accepts_custom_tools_and_web_tools():
    runtime = await Runtime.acreate(
        model=StreamingTextModel(),
        custom_tools=[lookup],
        include_web_tools=True,
    )
    assert "lookup" in runtime.tools
    assert "brave_search" in runtime.tools


def test_supervisor_stream_includes_child_events_and_aggregate_result():
    asyncio.run(_test_supervisor_stream_includes_child_events_and_aggregate_result())


async def _test_supervisor_stream_includes_child_events_and_aggregate_result():
    registry = AgentRegistry()
    evidence_scout = Agent(runtime=Runtime(model=StreamingTextModel()))
    synthesis_analyst = Agent(runtime=Runtime(model=StreamingTextModel()))
    registry.register(
        AgentSpec(
            name="evidence_scout",
            description="Evidence specialist",
            tags=["research"],
            capabilities=[AgentCapability.RETRIEVE],
            allowed_knowledge_scopes=["research"],
        ),
        evidence_scout,
    )
    registry.register(
        AgentSpec(
            name="synthesis_analyst",
            description="Synthesis specialist",
            tags=["research"],
            capabilities=[AgentCapability.AGGREGATE],
            allowed_knowledge_scopes=["research"],
        ),
        synthesis_analyst,
    )
    runtime = Runtime(
        model=StreamingTextModel(),
        agent_registry=registry,
        supervisor=Supervisor(registry=registry),
        config=RuntimeConfig(default_knowledge_scope=["research"]),
    )
    agent = Agent(runtime=runtime)
    events = [event async for event in agent.run("research trustworthy agents", thread_id="supervisor-stream", stream=True)]
    event_types = [event.event_type for event in events]
    delegated_agents = {event.agent_name for event in events if event.event_type == "agent_delegated"}
    assert "agent_delegated" in event_types
    assert delegated_agents == {"evidence_scout", "synthesis_analyst"}
    final_event = events[-1]
    assert final_event.event_type == "final_result"
    assert final_event.result is not None
    assert final_event.result.reasoning_kind == "supervisor_aggregate"
    assert final_event.result.reasoning_metadata["child_reasoning"]


def test_runtime_registers_deliberative_retrieval_tools():
    asyncio.run(_test_runtime_registers_deliberative_retrieval_tools())


async def _test_runtime_registers_deliberative_retrieval_tools():
    runtime = Runtime(model=FakeModel(), knowledge_base=IndexedKnowledgeBase(), config=RuntimeConfig(enable_retrieval=True))
    assert "deliberative_retrieve" in runtime.tools
    assert "search_knowledge_assets" in runtime.tools
    assert "open_retrieved_evidence" in runtime.tools


def test_rag_strategy_summary_only_filters_prompt_payload(tmp_path):
    asyncio.run(_test_rag_strategy_summary_only_filters_prompt_payload(tmp_path))


async def _test_rag_strategy_summary_only_filters_prompt_payload(tmp_path):
    md = tmp_path / "ops.md"
    md.write_text("# Ops\nowner approval required\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([md], scopes=["ops"])
    class EchoSystemModel(BaseModelAdapter):
        def __init__(self) -> None:
            self.seen_requests: list[ModelRequest] = []

        async def generate(self, request: ModelRequest) -> ModelResponse:
            self.seen_requests.append(request)
            system_message = next(message for message in request.messages if message.role == "system")
            return ModelResponse(
                message=Message(role="assistant", content=system_message.content),
                content=system_message.content,
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )

    model = EchoSystemModel()
    runtime = Runtime(
        model=model,
        knowledge_base=kb,
        config=RuntimeConfig(
            enable_retrieval=True,
            rag_strategy=RagStrategyConfig(mode="classic", injection_policy="summary_only", file_types=[".md"], knowledge_scope=["ops"]),
        ),
    )
    agent = Agent(runtime=runtime)
    await agent.run("find owner approval", thread_id="rag-strategy")
    first_request = model.seen_requests[0]
    system_message = next(message for message in first_request.messages if message.role == "system")
    assert "Retrieved Knowledge" in system_message.content
    assert "Retrieved Evidence" not in system_message.content


def test_runtime_accepts_structured_chat_prompt_template():
    asyncio.run(_test_runtime_accepts_structured_chat_prompt_template())


async def _test_runtime_accepts_structured_chat_prompt_template():
    class EchoPromptModel(BaseModelAdapter):
        async def generate(self, request: ModelRequest) -> ModelResponse:
            return ModelResponse(
                message=Message(role="assistant", content=request.messages[0].content),
                content=request.messages[0].content,
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )

    runtime = Runtime(
        model=EchoPromptModel(),
        config=RuntimeConfig(
            prompt_template=ChatPromptTemplate(
                cards=[
                    TextPromptCard(role="system", template="Role={{ agent_role or 'default' }}"),
                    MessagesPlaceholderCard(variable_name="conversation"),
                    TextPromptCard(role="user", template="{{ user_input }}"),
                ]
            )
        ),
    )
    agent = Agent(runtime=runtime)
    result = await agent.run("hello template", thread_id="prompt-template-thread", metadata={"agent_role": "planner"})
    assert "Role=planner" in result.output_text


def test_runtime_config_agent_shortcuts_and_reasoning_strategy_are_applied(tmp_path):
    asyncio.run(_test_runtime_config_agent_shortcuts_and_reasoning_strategy_are_applied(tmp_path))


async def _test_runtime_config_agent_shortcuts_and_reasoning_strategy_are_applied(tmp_path):
    md = tmp_path / "ops.md"
    md.write_text("# Ops\nowner approval required\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([md], scopes=["ops"])

    class EchoSystemModel(BaseModelAdapter):
        async def generate(self, request: ModelRequest) -> ModelResponse:
            system_message = next(message for message in request.messages if message.role == "system")
            return ModelResponse(
                message=Message(role="assistant", content=system_message.content),
                content=system_message.content,
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )

    runtime = Runtime(
        model=EchoSystemModel(),
        knowledge_base=kb,
        config=RuntimeConfig.agent(
            rag=RagStrategyConfig.for_classic(knowledge_scope=["ops"], file_types=[".md"], injection_policy="summary_only"),
            reasoning=ReasoningStrategyConfig.plan_execute(config={"max_steps": 2}),
        ),
    )
    result = await Agent(runtime=runtime).run("find owner approval", thread_id="runtime-shortcuts")
    assert "Retrieved Knowledge" in result.output_text
    assert runtime.reasoning_framework.config.kind.value == "plan_execute"


def test_runtime_accepts_dict_config_shortcuts():
    runtime = Runtime(
        model=FakeModel(),
        config={
            "reasoning_strategy": "react",
            "rag_strategy": "classic",
            "enable_retrieval": True,
        },
    )
    assert runtime.config.rag_strategy is not None
    assert runtime.config.rag_strategy.mode == "classic"
    assert runtime.reasoning_framework.config.kind.value == "react"


def test_runtime_create_and_agent_create_provide_high_level_entrypoints(tmp_path):
    md = tmp_path / "ops.md"
    md.write_text("# Ops\nowner approval required\n", encoding="utf-8")

    runtime = Runtime.create(
        model=FakeModel(),
        config={"rag_strategy": {"mode": "classic", "knowledge_scope": ["ops"], "file_types": [".md"]}, "enable_retrieval": True},
        knowledge_paths=[md],
        knowledge_scope=["ops"],
    )
    assert runtime.knowledge_base is not None
    assert isinstance(runtime.knowledge_base, IndexedKnowledgeBase)

    agent = Agent.create(
        model=FakeModel(),
        workflow=None,
        config={"reasoning_strategy": "react"},
    )
    assert agent.runtime.reasoning_framework.config.kind.value == "react"


class CustomCompactStrategy(BaseContextStrategy):
    pass


def test_runtime_orchestration_profile_expands_and_reasoning_metadata_reports_context_budget():
    asyncio.run(_test_runtime_orchestration_profile_expands_and_reasoning_metadata_reports_context_budget())


async def _test_runtime_orchestration_profile_expands_and_reasoning_metadata_reports_context_budget():
    class EchoSystemModel(BaseModelAdapter):
        async def generate(self, request: ModelRequest) -> ModelResponse:
            system_message = next(message for message in request.messages if message.role == "system")
            return ModelResponse(
                message=Message(role="assistant", content=system_message.content),
                content=system_message.content,
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )

    runtime = Runtime(
        model=EchoSystemModel(),
        config=RuntimeConfig.agent(orchestration_profile="deep_research"),
    )
    result = await Agent(runtime=runtime).run("hello", thread_id="profile-runtime")
    assert runtime.config.context_strategy is not None
    assert runtime.config.cooperation_strategy is not None
    assert result.reasoning_metadata["resolved_context_strategy"]["kind"] == "compact"
    assert "context_budget_report" in result.reasoning_metadata
    assert result.reasoning_metadata["context_budget_report"]["conversation_messages"] >= 1


def test_runtime_accepts_custom_context_strategy_instance():
    config = RuntimeConfig.agent(
        orchestration_profile="deep_research",
        context_strategy=CustomCompactStrategy(ContextStrategyConfig.compact(prompt_char_budget=7777)),
    )
    assert isinstance(config.context_strategy, CustomCompactStrategy)
    runtime = Runtime(model=FakeModel(), config=config)
    resolved = runtime._resolve_context_strategy()
    assert resolved.prompt_char_budget == 7777


def test_budget_aware_compaction_prioritizes_high_value_evidence():
    asyncio.run(_test_budget_aware_compaction_prioritizes_high_value_evidence())


async def _test_budget_aware_compaction_prioritizes_high_value_evidence():
    runtime = Runtime(
        model=FakeModel(),
        config=RuntimeConfig.agent(
            context_strategy=ContextStrategyConfig.compact(
                include_retrieval_evidence=True,
                include_retrieval_citations=True,
                include_retrieval_report=True,
                budget_aware_compaction=True,
                salience_mode="rule",
                prompt_char_budget=700,
                retrieval_evidence_max_items=5,
                citation_max_items=5,
            )
        ),
    )
    prompt_context = PromptContext(
        system_prompt="system",
        user_input="research evidence about timeout mitigation in multi-agent runs",
        conversation=[
            Message(role="user", content="research timeout mitigation"),
            Message(role="assistant", content="planning"),
            Message(role="tool", content='{"result":"' + ("x" * 300) + '"}'),
        ],
        retrieved_evidence=[
            {
                "source_type": "document",
                "summary": "timeout mitigation evidence for multi-agent runs " * 5,
                "content": "budget-aware context compaction keeps the strongest evidence",
            }
        ],
        citations=[{"document_id": "doc-1", "snippet": "unrelated citation " * 30}],
        retrieval_report={"summary": "verbose report " * 40},
        skill_instructions=["Skill: deep_research_protocol\nPurpose: evidence-first research guidance"],
        task_packet={"task_id": "task-1", "goal": "research timeout mitigation", "metadata": {"delegation_depth": 1}, "context": {}},
        delegation_context={"handoff": {"from_agent": "supervisor", "to_agent": "evidence_scout", "reason": "keyword_match", "task": {"metadata": {"delegation_depth": 1}}}},
        prompt_variables={"thread_id": "thread-1"},
    )
    compacted, budget = await runtime._apply_context_strategy_to_prompt_context(
        prompt_context,
        context_strategy=runtime._resolve_context_strategy(),
        long_horizon_strategy=runtime._resolve_long_horizon_strategy(),
        stage="plan",
        selected_skill_routes=[],
    )
    assert budget["compaction_applied"] is True
    assert budget["estimated_total_chars_after"] < budget["estimated_total_chars_before"]
    assert len(compacted.retrieved_evidence) == 1
    assert len(compacted.citations) == 0
    assert "salience_report" in budget


def test_compact_task_packet_preserves_delegated_input_payload():
    compacted = compact_task_packet(
        {
            "task_id": "task-1",
            "goal": "review retrieval payload",
            "input": {
                "retrieval_input": {
                    "report": {"summary": "owner approval required before release"},
                    "evidence": [{"content": "owner approval required before release"}],
                }
            },
            "parent_task_id": "parent-1",
            "origin_agent": "workflow",
            "knowledge_scope": ["ops"],
            "metadata": {"thread_id": "thread-1", "delegation_depth": 2, "ignored": "drop-me"},
            "expected_output": {"kind": "report"},
            "artifact_refs": ["artifact-1"],
            "context": {
                "workflow_node": "delegate",
                "variables": {"retrieved": {"report": "verbose"}},
                "cooperation_report": {"topology": "solo"},
            },
        }
    )
    assert compacted is not None
    assert compacted["input"]["retrieval_input"]["evidence"][0]["content"] == "owner approval required before release"
    assert compacted["metadata"] == {"thread_id": "thread-1", "delegation_depth": 2}
    assert "expected_output" not in compacted
    assert "artifact_refs" not in compacted


class RerankAwareModel(BaseModelAdapter):
    def __init__(self) -> None:
        self.seen_requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.seen_requests.append(request)
        if request.metadata.get("purpose") == "context_salience_rerank":
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content='{"adjustments":[{"segment_id":"skill:0","adjustment":0.2,"reason":"task_alignment"}]}',
                ),
                content='{"adjustments":[{"segment_id":"skill:0","adjustment":0.2,"reason":"task_alignment"}]}',
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )
        return ModelResponse(message=Message(role="assistant", content="ok"), content="ok", finish_reason="stop", usage=UsageInfo(total_tokens=1))


def test_budget_aware_compaction_hybrid_mode_records_rerank_adjustment():
    asyncio.run(_test_budget_aware_compaction_hybrid_mode_records_rerank_adjustment())


async def _test_budget_aware_compaction_hybrid_mode_records_rerank_adjustment():
    model = RerankAwareModel()
    runtime = Runtime(
        model=model,
        config=RuntimeConfig.agent(
            context_strategy=ContextStrategyConfig.research_heavy(
                prompt_char_budget=600,
                salience_rerank_top_k=4,
            )
        ),
    )
    prompt_context = PromptContext(
        system_prompt="system",
        user_input="research evidence about timeout mitigation",
        retrieved_evidence=[{"source_type": "document", "summary": "relevant evidence"}],
        citations=[{"document_id": "doc-1", "snippet": "citation"}],
        retrieval_report={"summary": "verbose retrieval report " * 60},
        skill_instructions=["Skill: deep_research_protocol\nPurpose: evidence-first research guidance"],
        prompt_variables={"thread_id": "thread-2"},
    )
    compacted, budget = await runtime._apply_context_strategy_to_prompt_context(
        prompt_context,
        context_strategy=runtime._resolve_context_strategy(),
        long_horizon_strategy=runtime._resolve_long_horizon_strategy(),
        stage="plan",
        selected_skill_routes=[
            {
                "skill_name": "deep_research_protocol",
                "content": "Skill: deep_research_protocol\nPurpose: evidence-first deep research guidance",
                "descriptor": {
                    "name": "deep_research_protocol",
                    "description": "Evidence-first deep research guidance",
                    "allowed_tools": ["brave_search"],
                },
            }
        ],
    )
    assert compacted.skill_instructions
    assert any(item["segment_id"] == "skill:0" and item["rerank_adjustment"] > 0 for item in budget["segment_scores"])
    assert any(request.metadata.get("purpose") == "context_salience_rerank" for request in model.seen_requests)


def test_runtime_augments_retrieval_with_persisted_thread_history(tmp_path):
    asyncio.run(_test_runtime_augments_retrieval_with_persisted_thread_history(tmp_path))


async def _test_runtime_augments_retrieval_with_persisted_thread_history(tmp_path):
    runtime = Runtime(
        model=FakeModel(),
        config=RuntimeConfig(
            enable_retrieval=True,
        ),
        memory=MemoryManager(
            config=MemoryConfig(
                checkpoint_path=tmp_path / "checkpoints.db",
                record_path=tmp_path / "records.db",
                thread_history_recall_limit=3,
            )
        ),
    )
    await runtime.memory.append_message("thread-history", Message(role="user", content="owner approval required before release"))
    await runtime.memory.append_message("thread-history", Message(role="assistant", content="release checklist updated"))

    report, memory_recall_report = await runtime._augment_report_with_memory_sources(
        RetrievalReport(summary="", retrieval_context=""),
        thread_id="thread-history",
        query="approval required",
        knowledge_scope=["ops"],
        source_filters=[],
        memory_strategy=create_memory_governance_strategy({"kind": "mgcm"}),
    )
    assert any(item.source_type == "thread_history" for item in report.evidence)
    assert "thread_history" in report.visited_sources
    assert memory_recall_report["mechanism"] == "mgcm"


def test_runtime_nutcracker_memory_promotes_episodic_capsule_and_reports_metadata(tmp_path):
    asyncio.run(_test_runtime_nutcracker_memory_promotes_episodic_capsule_and_reports_metadata(tmp_path))


async def _test_runtime_nutcracker_memory_promotes_episodic_capsule_and_reports_metadata(tmp_path):
    class EchoSystemModel(BaseModelAdapter):
        async def generate(self, request: ModelRequest) -> ModelResponse:
            return ModelResponse(
                message=Message(role="assistant", content="owner approval required before release and evidence captured"),
                content="owner approval required before release and evidence captured",
                finish_reason="stop",
                usage=UsageInfo(total_tokens=1),
            )

    md = tmp_path / "ops.md"
    md.write_text("# Ops\nowner approval required before release\n", encoding="utf-8")
    kb = IndexedKnowledgeBase()
    await kb.ingest_paths([md], scopes=["ops"])
    runtime = Runtime(
        model=EchoSystemModel(),
        knowledge_base=kb,
        memory=MemoryManager(
            config=MemoryConfig(
                checkpoint_path=tmp_path / "checkpoints.db",
                record_path=tmp_path / "records.db",
            )
        ),
        config=RuntimeConfig.agent(
            rag=RagStrategyConfig.for_classic(knowledge_scope=["ops"], file_types=[".md"]),
            memory_governance_strategy={"kind": "nutcracker_memory", "capsule_promotion_threshold": 0.2},
        ),
    )
    result = await Agent(runtime=runtime).run("find owner approval", thread_id="nutcracker-thread")
    capsules = await runtime.memory.record_store.search(thread_id="nutcracker-thread", kinds=["episodic_capsule"])
    assert capsules
    assert result.reasoning_metadata["memory_governance_report"]["kind"] == "nutcracker_memory"
    assert result.reasoning_metadata["memory_promotion_trace"][0]["kind"] == "episodic_capsule"
