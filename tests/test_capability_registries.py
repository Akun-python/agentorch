import asyncio

from agentorch import (
    Agent,
    AgentLocalMemoryMechanism,
    AgentCapability,
    AgentSpec,
    BalancedContextStrategy,
    ChatPromptTemplate,
    ClassicRetriever,
    ContextStrategyConfig,
    CooperationStrategyConfig,
    EvaluationResult,
    EvolutionAlgorithm,
    EvolutionConfig,
    EvolutionManager,
    EvolutionResult,
    FewShotExample,
    FewShotPromptCard,
    Genome,
    HybridRetriever,
    IndexedKnowledgeBase,
    MemoryManager,
    MemoryPromotionPolicy,
    MessagesPlaceholderCard,
    create_memory_promotion_policy,
    create_model_adapter,
    ReasoningStrategyConfig,
    Runtime,
    SearchSpace,
    TextPromptCard,
    create_reasoning_framework,
    create_rag_retriever,
    create_retriever,
    create_context_strategy,
    create_cooperation_strategy,
    list_evolution_algorithms,
    list_context_strategies,
    list_cooperation_strategies,
    list_orchestration_profiles,
    list_memory_backends,
    list_memory_promotion_policies,
    list_memory_governance,
    list_memory_mechanisms,
    list_model_providers,
    list_reasoning_frameworks,
    list_retrievers,
    register_context_strategy,
    register_cooperation_strategy,
    register_orchestration_profile,
    register_evolution_algorithm,
    register_memory_mechanism,
    register_memory_promotion_policy,
    register_model_provider,
    register_reasoning_framework,
    register_retriever,
    runtime_config_from_genome,
)
from agentorch.config import MemoryConfig, RuntimeConfig
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.knowledge import BaseRetriever, Document, DocumentChunk, KnowledgeAsset, RetrievalQuery, RetrievedChunk
from agentorch.models import OpenAICompatibleHTTPModel, OpenAIModel
from agentorch.tools import ToolRegistry
from agentorch.memory.base import MemoryGovernance, MemoryMechanism
from agentorch.models.base import BaseModelAdapter
from agentorch.plugins import PluginManager
from agentorch.reasoning import BaseReasoningFramework, ReactConfig, ReasoningResult, ReasoningSessionContext


class EchoModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="ok"),
            content="ok",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


class CustomReasoning(BaseReasoningFramework):
    def __init__(self, config: ReactConfig | None = None) -> None:
        super().__init__(config or ReactConfig())

    async def execute(self, runtime, context: ReasoningSessionContext) -> ReasoningResult:
        session = self.initialize(context)
        session.state["final_output"] = "custom"
        return self.finalize(session)


class FakeRetriever(BaseRetriever):
    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        return [RetrievedChunk(chunk=DocumentChunk(id="c", document_id="d", text=f"hit:{query.query}"), score=1.0, source="fake")]


class NoopGovernance(MemoryGovernance):
    async def search_collective_memory(self, manager, **kwargs):
        return []

    async def promote_collective_memory(self, manager, **kwargs):
        return 0

    async def validate_collective_memory(self, manager, record_id: int):
        return None

    async def deprecate_collective_memory(self, manager, record_id: int):
        return None

    async def collect_candidate_notes(self, manager, thread_id: str, *, task_id: str | None = None):
        return []


class UppercaseSummaryMechanism(MemoryMechanism):
    kind = "uppercase_summary"
    supported_operations = {"summarize_thread"}
    depends_on = ("session_memory",)

    def supports(self, operation: str) -> bool:
        return operation == "summarize_thread"

    async def invoke(self, manager, operation: str, **kwargs):
        messages = manager.session_state.thread_messages.get(kwargs["thread_id"], [])
        return " | ".join(message.content.upper() for message in messages)


class NoopPromotionPolicy(MemoryPromotionPolicy):
    kind = "noop_promotion"

    async def promote(self, manager, **kwargs):
        return [{"kind": "noop", "record_id": 0}]


class FakeEvolution(EvolutionAlgorithm):
    async def evolve(self, manager, *, tasks=None, initial_population=None) -> EvolutionResult:
        genome = Genome(id="fake-1", generation=0, genes={"strategy": "fake"})
        evaluation = EvaluationResult(genome_id=genome.id, fitness=1.0, metrics={"fitness": 1.0})
        return EvolutionResult(best_genome=genome, best_evaluation=evaluation, history=[])


class DummyProviderModel(BaseModelAdapter):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="dummy"),
            content="dummy",
            finish_reason="stop",
            usage=UsageInfo(total_tokens=1),
        )


def test_reasoning_registry_lists_and_runtime_accepts_registered_name():
    register_reasoning_framework("custom_reasoning", CustomReasoning, ReactConfig)
    assert "react" in list_reasoning_frameworks()
    assert "custom_reasoning" in list_reasoning_frameworks()
    framework = create_reasoning_framework("custom_reasoning")
    assert framework.config.kind.value == "react"
    result = asyncio.run(Agent(runtime=Runtime(model=EchoModel(), policy="custom_reasoning")).run("hello", thread_id="custom-r"))
    assert result.output_text == "custom"


def test_evolution_registry_lists_and_supports_custom_algorithm():
    register_evolution_algorithm("fake_algorithm", FakeEvolution)
    assert "genetic" in list_evolution_algorithms()
    assert "random_search" in list_evolution_algorithms()
    assert "hill_climb" in list_evolution_algorithms()
    assert "beam_search" in list_evolution_algorithms()
    assert "fake_algorithm" in list_evolution_algorithms()
    manager = EvolutionManager(
        builder=lambda genome: {"genes": genome.genes},
        evaluator=lambda genome, candidate, tasks: EvaluationResult(genome_id=genome.id, fitness=0.0),
        search_space=SearchSpace({"mode": ["a"]}),
        config=EvolutionConfig(algorithm_kind="fake_algorithm"),
    )
    result = asyncio.run(manager.evolve(tasks=["t"]))
    assert result.best_genome.genes["strategy"] == "fake"


def test_memory_registry_lists_defaults_and_manager_accepts_custom_governance():
    assert "sqlite_record_store" in list_memory_backends()
    assert "mgcm_governance" in list_memory_governance()
    assert "session_memory" in list_memory_mechanisms()
    memory = MemoryManager(governance=NoopGovernance())
    assert asyncio.run(memory.search_collective_memory(query="x")) == []


def test_memory_registry_supports_custom_mechanism():
    register_memory_mechanism("uppercase_summary", UppercaseSummaryMechanism)
    assert "uppercase_summary" in list_memory_mechanisms()
    memory = MemoryManager(
        config=MemoryConfig(
            allow_partial_mechanisms=True,
            required_operations=["append_message", "summarize_thread"],
        ),
        mechanisms=[AgentLocalMemoryMechanism(), "session_memory", "uppercase_summary"],
    )
    asyncio.run(memory.append_message("thread-upper", Message(role="user", content="hello")))
    asyncio.run(memory.append_message("thread-upper", Message(role="assistant", content="world")))
    assert asyncio.run(memory.summarize_thread("thread-upper")) == "HELLO | WORLD"


def test_memory_policy_registry_supports_custom_promotion_policy():
    register_memory_promotion_policy("noop_promotion", NoopPromotionPolicy)
    assert "noop_promotion" in list_memory_promotion_policies()
    policy = create_memory_promotion_policy("noop_promotion")
    result = asyncio.run(policy.promote(MemoryManager()))
    assert result[0]["kind"] == "noop"


def test_knowledge_registry_lists_and_creates_custom_retriever():
    register_retriever("fake_retriever", FakeRetriever)
    assert "keyword" in list_retrievers()
    assert "fake_retriever" in list_retrievers()
    retriever = create_retriever("fake_retriever")
    result = asyncio.run(retriever.retrieve(RetrievalQuery(query="hello")))
    assert result[0].chunk.text == "hit:hello"


def test_plugin_manager_supports_new_extension_kinds():
    manager = PluginManager()
    manager.register_extension("reasoning_framework", {"kind": "custom"})
    manager.register_extension("evolution_algorithm", {"kind": "fake"})
    assert manager.get_extensions("reasoning_framework")[0]["kind"] == "custom"
    assert manager.get_extensions("evolution_algorithm")[0]["kind"] == "fake"


def test_public_api_exports_prompt_rag_and_genome_helpers():
    template = ChatPromptTemplate(
        cards=[
            TextPromptCard(role="system", template="Role={{ role_name }}"),
            FewShotPromptCard(examples=[FewShotExample(input={"topic": "ops"}, user="Topic {{ topic }}", assistant="Answer {{ topic }}")]),
            MessagesPlaceholderCard(variable_name="conversation"),
        ]
    )
    formatted = template.partial(role_name="planner").format_messages(conversation=[Message(role="user", content="hello")])
    assert formatted[0].content == "Role=planner"
    assert any(message.content == "Topic ops" for message in formatted)

    kb = IndexedKnowledgeBase()
    assert isinstance(create_rag_retriever(kb, None), object)
    assert ClassicRetriever is not None
    assert HybridRetriever is not None

    genome = Genome(id="g-api", genes={"reasoning": {"kind": "react"}, "rag": {"mode": "classic"}})
    runtime_config = runtime_config_from_genome(genome, base=RuntimeConfig(enable_retrieval=False))
    assert isinstance(runtime_config.rag_strategy.mode, str)
    assert isinstance(ReasoningStrategyConfig(kind="react"), ReasoningStrategyConfig)


def test_simplified_api_builders_normalize_common_inputs(tmp_path):
    asset = KnowledgeAsset.from_path(tmp_path / "notes.md", scope_tags=["engineering"])
    assert asset.path is not None
    assert asset.metadata["suffix"] == ".md"

    runtime_config = RuntimeConfig.agent(rag="classic", reasoning="react")
    assert runtime_config.rag_strategy is not None
    assert runtime_config.rag_strategy.mode == "classic"
    assert runtime_config.reasoning_strategy is not None
    assert runtime_config.reasoning_strategy.kind.value == "react"

    spec = AgentSpec.assistant(
        "planner",
        capabilities=[AgentCapability.PLAN.value, AgentCapability.TOOL_USE],
        knowledge_scopes=["engineering"],
        default_rag_strategy="hybrid",
        preferred_reasoning_kind="plan_execute",
    )
    assert spec.capabilities[0] == AgentCapability.PLAN
    assert spec.policy_profile.default_rag_strategy is not None
    assert spec.policy_profile.default_rag_strategy.mode == "hybrid"
    assert spec.policy_profile.preferred_reasoning_kind == "plan_execute"

    kb = IndexedKnowledgeBase.create(documents=[Document(id="doc-1", text="hello world")])
    assert "doc-1" in kb.documents

    model = OpenAIModel.from_config("gpt-4.1-mini")
    assert model.config.model == "gpt-4.1-mini"
    http_model = create_model_adapter(
        {
            "provider": "openai_http",
            "model": "gpt-4.1-mini",
            "api_key": "test-key",
            "base_url": "https://example.com/v1",
        }
    )
    assert isinstance(http_model, OpenAICompatibleHTTPModel)

    tools = ToolRegistry.empty()
    assert tools.list_specs() == []


def test_model_provider_registry_supports_custom_factories():
    register_model_provider("dummy_provider", lambda config: DummyProviderModel())
    assert "openai" in list_model_providers()
    assert "openai_http" in list_model_providers()
    assert "dummy_provider" in list_model_providers()

    model = create_model_adapter({"provider": "dummy_provider", "model": "ignored"})
    assert isinstance(model, DummyProviderModel)


def test_strategy_registries_list_and_create_custom_entries():
    class CustomBalancedContext(BalancedContextStrategy):
        pass

    register_context_strategy("custom_balanced_context", CustomBalancedContext)
    register_cooperation_strategy("custom_team", create_cooperation_strategy("distributed_herd").__class__)
    register_orchestration_profile(
        "custom_profile_for_tests",
        lambda: {
            "context_strategy": {"kind": "custom_balanced_context", "mode": "custom", "include_tool_descriptions": True},
            "cooperation_strategy": CooperationStrategyConfig.hybrid().model_dump(),
        },
    )

    assert "custom_balanced_context" in list_context_strategies()
    assert "custom_team" in list_cooperation_strategies()
    assert "custom_profile_for_tests" in list_orchestration_profiles()

    context_strategy = create_context_strategy({"kind": "custom_balanced_context", "mode": "custom"})
    cooperation_strategy = create_cooperation_strategy(CooperationStrategyConfig.hybrid())
    assert isinstance(context_strategy, CustomBalancedContext)
    assert cooperation_strategy.config.topology == "hybrid_herd"
