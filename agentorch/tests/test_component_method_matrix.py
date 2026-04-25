from __future__ import annotations

import asyncio
import random
from uuid import uuid4

import agentorch
from agentorch.agents import SharedNote, TaskArtifact
from agentorch.config import MemoryConfig, ModelConfig, RuntimeConfig
from agentorch.core import Message
from agentorch.evolution import EvolutionAlgorithm, get_evolution_algorithm_registration
from agentorch.knowledge import Document, DocumentChunk, KnowledgeAsset, RetrievalQuery
from agentorch.models.base import BaseModelAdapter
from agentorch.reasoning import BaseReasoningFramework, ReactConfig, ReasoningResult, get_reasoning_framework_registration


def _unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class DemoModelAdapter(BaseModelAdapter):
    def __init__(self, model_name: str) -> None:
        self.config = {"provider": "demo", "model": model_name}

    async def generate(self, request):  # pragma: no cover - not needed for registry checks
        raise RuntimeError("not used")


class DemoReasoningFramework(BaseReasoningFramework):
    async def execute(self, runtime, context) -> ReasoningResult:
        return ReasoningResult(final_output="demo-reasoning")


class DemoEvolutionAlgorithm(EvolutionAlgorithm):
    def __init__(self, marker: str = "demo-evolution") -> None:
        self.marker = marker

    async def evolve(self, context, *, tasks=None, initial_population=None):
        genome = agentorch.Genome(id="demo", genes={"marker": self.marker})
        evaluation = agentorch.EvaluationResult(genome_id=genome.id, fitness=9.0)
        return agentorch.EvolutionResult(best_genome=genome, best_evaluation=evaluation)


def test_model_config_and_provider_registry_methods_support_builtin_and_custom_paths() -> None:
    model_config = ModelConfig.from_any("demo-model", provider="custom-provider", temperature=0.2)

    assert model_config.model == "demo-model"
    assert model_config.provider == "custom-provider"
    assert model_config.temperature == 0.2
    assert "openai" in agentorch.list_model_providers()

    provider_name = _unique_name("provider")
    agentorch.register_model_provider(provider_name, lambda config: DemoModelAdapter(config.model or "missing"))
    adapter = agentorch.create_model_adapter({"provider": provider_name, "model": "custom-model"})

    assert provider_name in agentorch.list_model_providers()
    assert isinstance(adapter, DemoModelAdapter)
    assert adapter.config["model"] == "custom-model"


def test_knowledge_registry_factory_and_helper_methods_cover_builtin_and_custom_components(tmp_path) -> None:
    assert "keyword" in agentorch.list_retrievers()
    assert "fixed_token_chunk" in agentorch.list_chunking_strategies()
    assert "text" in agentorch.list_document_adapters()

    retriever = agentorch.create_retriever(
        "keyword",
        chunks=[
            DocumentChunk(
                id="chunk-1",
                document_id="doc-1",
                text="agent orchestration with retrieval",
                metadata={"scopes": ["papers"]},
            )
        ],
    )
    retrieval = asyncio.run(retriever.retrieve(RetrievalQuery(query="retrieval", top_k=1, scopes=["papers"])))
    assert retrieval[0].chunk.document_id == "doc-1"

    chunker = agentorch.create_chunking_strategy("fixed_token_chunk", chunk_size=2, chunk_overlap=0)
    chunks = asyncio.run(chunker.chunk([Document(id="doc-2", text="one two three four")]))
    assert [chunk.text for chunk in chunks] == ["one two", "three four"]

    text_path = tmp_path / "note.txt"
    text_path.write_text("framework test content", encoding="utf-8")
    asset = KnowledgeAsset.from_path(text_path, scope_tags=["demo"])
    adapter = agentorch.create_document_adapter("text")
    parsed = asyncio.run(adapter.parse(asset))
    assert parsed.title == "note.txt"
    assert parsed.sections[0].text == "framework test content"

    embedding_name = _unique_name("embedding")
    reranker_name = _unique_name("reranker")
    agentorch.register_embedding_provider(embedding_name, factory=lambda dimensions=3: {"dimensions": dimensions})
    agentorch.register_reranker(reranker_name, factory=lambda top_k=1: {"top_k": top_k})

    assert agentorch.create_embedding_provider(embedding_name, dimensions=6)["dimensions"] == 6
    assert agentorch.create_reranker(reranker_name, top_k=4)["top_k"] == 4
    assert embedding_name in agentorch.list_embedding_providers()
    assert reranker_name in agentorch.list_rerankers()


def test_memory_registry_factory_and_manager_methods_cover_storage_and_collective_paths(tmp_path) -> None:
    config = MemoryConfig(
        checkpoint_path=tmp_path / "checkpoints.db",
        record_path=tmp_path / "records.db",
    )
    manager = agentorch.MemoryManager.compose(
        "session_memory",
        "thread_summary_memory",
        "agent_local_memory",
        "workspace_memory",
        "shared_note_memory",
        "record_memory",
        "collective_memory",
        config=config,
    )

    async def scenario() -> None:
        await manager.append_message("thread-1", Message(role="user", content="hello framework"))
        messages = await manager.get_thread_messages("thread-1")
        summary = await manager.summarize_thread("thread-1")

        await manager.append_agent_memory("thread-1", "coder", {"goal": "fix tests"})
        agent_memory = await manager.get_agent_memory("thread-1", "coder")

        artifact = TaskArtifact(name="draft", content="artifact-content")
        workspace_record = await manager.write_workspace_record(
            "thread-1",
            task_id="task-1",
            owner_agent="coder",
            artifact=artifact,
        )
        workspace_records = await manager.read_workspace_records("thread-1")

        note = SharedNote(
            note_id="note-1",
            task_id="task-1",
            author_agent="coder",
            content="candidate insight",
            metadata={"collective_candidate": True},
        )
        await manager.add_shared_note("thread-1", note)
        notes = await manager.get_shared_notes("thread-1")
        candidates = await manager.collect_candidate_notes("thread-1", task_id="task-1")

        collective_id = await manager.promote_collective_memory(
            thread_id="thread-1",
            kind="lesson",
            content="validated answer",
            tags=["memory"],
            source_agents=["coder"],
        )
        collective = await manager.search_collective_memory(query="validated", thread_id="thread-1")
        validated = await manager.validate_collective_memory(collective_id)
        deprecated = await manager.deprecate_collective_memory(collective_id)

        await manager.checkpoint("thread-1", "cp-1", {"step": 1})
        checkpoint = await manager.load_checkpoint("thread-1", "cp-1")

        assert [message.content for message in messages] == ["hello framework"]
        assert "hello framework" in summary
        assert agent_memory == [{"goal": "fix tests"}]
        assert workspace_record.name == "draft"
        assert workspace_records[0].content == "artifact-content"
        assert notes[0].content == "candidate insight"
        assert candidates[0].note_id == "note-1"
        assert collective[0]["kind"] == "lesson"
        assert validated is not None and validated["status"] == "validated"
        assert deprecated is not None and deprecated["status"] == "deprecated"
        assert checkpoint == {"step": 1}

    asyncio.run(scenario())

    descriptions = manager.describe_mechanisms()
    assert "session_memory" in manager.list_mechanisms()
    assert manager.get_mechanism("session_memory").kind == "session_memory"
    assert any(item["kind"] == "collective_memory" for item in descriptions)

    assert "in_memory_state_store" in agentorch.list_memory_backends()
    assert "mgcm_governance" in agentorch.list_memory_governance()
    assert "session_memory" in agentorch.list_memory_mechanisms()
    assert "episodic_salience" in agentorch.list_memory_promotion_policies()
    assert "scene_hash" in agentorch.list_memory_index_policies()
    assert "scene_first" in agentorch.list_memory_recall_policies()
    assert "relevance_only" in agentorch.list_memory_decay_policies()

    backend = agentorch.create_memory_backend("in_memory_state_store")
    sqlite_backend = agentorch.create_memory_backend("sqlite_record_store", path=tmp_path / "factory-records.db")
    governance = agentorch.create_memory_governance("mgcm_governance")
    mechanism = agentorch.create_memory_mechanism("session_memory")
    promotion = agentorch.create_memory_promotion_policy("episodic_salience")
    index_policy = agentorch.create_memory_index_policy("scene_hash")
    recall = agentorch.create_memory_recall_policy("scene_first")
    decay = agentorch.create_memory_decay_policy("relevance_only")

    assert backend.__class__.__name__ == "InMemoryStateStore"
    assert sqlite_backend.path.name == "factory-records.db"
    assert governance.__class__.__name__ == "MGCMMemoryGovernance"
    assert mechanism.kind == "session_memory"
    assert promotion.kind == "episodic_salience"
    assert index_policy.kind == "scene_hash"
    assert recall.kind == "scene_first"
    assert decay.kind == "relevance_only"

    backend_name = _unique_name("memory_backend")
    agentorch.register_memory_backend(backend_name, factory=lambda marker="ok": {"marker": marker})
    assert agentorch.create_memory_backend(backend_name, marker="custom") == {"marker": "custom"}


def test_reasoning_evolution_and_search_space_methods_cover_builtin_custom_and_helper_paths() -> None:
    assert "react" in agentorch.list_reasoning_frameworks()
    assert get_reasoning_framework_registration("cot").kind == "cot"

    framework = agentorch.create_reasoning_framework("cot")
    assert framework.config.kind.value == "cot"

    reasoning_name = _unique_name("reasoning")
    agentorch.register_reasoning_framework(
        reasoning_name,
        None,
        factory=lambda max_steps=2: DemoReasoningFramework(ReactConfig(max_steps=max_steps)),
    )
    custom_framework = agentorch.create_reasoning_framework(reasoning_name, max_steps=5)
    assert reasoning_name in agentorch.list_reasoning_frameworks()
    assert isinstance(custom_framework, DemoReasoningFramework)
    assert custom_framework.config.max_steps == 5

    assert "random_search" in agentorch.list_evolution_algorithms()
    assert get_evolution_algorithm_registration("random_search").kind == "random_search"

    search_space = agentorch.SearchSpace({"reasoning.kind": ["react", "cot"], "workflow.template": ["classic_inline_answer"]})
    algorithm = agentorch.create_evolution_algorithm(
        "random_search",
        search_space=search_space,
        config=agentorch.EvolutionConfig(
            algorithm_kind="random_search",
            population_size=1,
            generations=1,
            evaluation_budget=1,
            seed=23,
        ),
    )
    assert algorithm.__class__.__name__ == "RandomSearchEvolutionAlgorithm"

    evolution_name = _unique_name("evolution")
    agentorch.register_evolution_algorithm(
        evolution_name,
        None,
        factory=lambda marker="custom": DemoEvolutionAlgorithm(marker=marker),
    )
    custom_algorithm = agentorch.create_evolution_algorithm(evolution_name, marker="explicit")
    assert evolution_name in agentorch.list_evolution_algorithms()
    assert isinstance(custom_algorithm, DemoEvolutionAlgorithm)
    assert custom_algorithm.marker == "explicit"

    genome = agentorch.Genome(
        id="genome-1",
        genes={
            "reasoning": {"kind": "react", "config": {"max_steps": 3}},
            "rag": {"mode": "classic", "top_k": 4},
            "workflow": {"template": "classic_inline_answer"},
        },
    )
    sampled = search_space.sample(random.Random(1))
    mutated = search_space.mutate(sampled, rng=random.Random(2), mutation_rate=1.0)
    neighbor = search_space.neighbor(genome, rng=random.Random(3), child_id="genome-2", generation=1)
    runtime_config = agentorch.runtime_config_from_genome(genome, base=RuntimeConfig())
    workflow = agentorch.workflow_from_genome(genome)
    candidate = agentorch.candidate_from_genome(genome)

    assert sampled["reasoning"]["kind"] in {"react", "cot"}
    assert mutated["workflow"]["template"] == "classic_inline_answer"
    assert neighbor.id == "genome-2"
    assert runtime_config.reasoning_strategy is not None and runtime_config.reasoning_strategy.kind.value == "react"
    assert workflow is not None and workflow.entry_node == "answer"
    assert candidate["workflow_template"] == "classic_inline_answer"
