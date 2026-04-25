from __future__ import annotations

from ..core.models import (
    BenchmarkCollectiveMemory,
    BenchmarkKnowledgeDocument,
    BenchmarkMessageSeed,
    ElephantBenchmarkCase,
)


def _route_context(family: str) -> dict[str, object]:
    return {
        "target_agents": ["planner", "evidence_scout", "reviewer"],
        "preferred_capabilities": ["plan", "retrieve", "review"],
        "max_agents": 3,
        "scenario_family": family,
    }


def _base_messages(prefix: str) -> list[BenchmarkMessageSeed]:
    return [
        BenchmarkMessageSeed(
            role="assistant",
            content=f"{prefix} archive note contains many side comments and timeline fragments that should not override verified evidence.",
        ),
        BenchmarkMessageSeed(
            role="user",
            content=f"{prefix} operator requests a concise verified answer only.",
        ),
        BenchmarkMessageSeed(
            role="assistant",
            content=f"{prefix} stale notes include unrelated dates and names from neighboring events.",
        ),
    ]


def _apollo_case() -> ElephantBenchmarkCase:
    return ElephantBenchmarkCase(
        case_id="real_public_qa_01",
        family="public long-context qa",
        description="Resolve a factual question from mixed public documents with distractors.",
        user_input="[case:real_public_qa_01] In which year did Apollo 11 land on the Moon?",
        stage_tags=["plan", "execute"],
        thread_messages=_base_messages("apollo"),
        knowledge_documents=[
            BenchmarkKnowledgeDocument(
                document_id="apollo-primary",
                text=(
                    "Mission summary: Apollo 11 was the first crewed lunar landing mission. "
                    "Neil Armstrong and Buzz Aldrin landed on the Moon in 1969. "
                    "The mission returned safely after lunar surface activities."
                ),
                scopes=["elephant-benchmark"],
                source_type="public_reference",
                locator={"doc": "apollo_primary"},
            ),
            BenchmarkKnowledgeDocument(
                document_id="apollo-distractor",
                text=(
                    "Nearby mission report: Apollo 13 launched in 1970 and did not land on the Moon. "
                    "Its rescue story is frequently confused with Apollo 11 in casual discussions."
                ),
                scopes=["elephant-benchmark"],
                source_type="public_reference",
                locator={"doc": "apollo_distractor"},
            ),
        ],
        task_context=_route_context("public_long_context_qa"),
        gold_key_segment_ids=["evidence:0"],
        gold_support_segment_ids=["citation:0"],
        stage_focus_segment_ids=["evidence:0"],
        expected_answer_fields={"primary_answer": "1969"},
        critical_markers=["1969"],
        distractor_markers=["1970"],
    )


def _penicillin_case() -> ElephantBenchmarkCase:
    return ElephantBenchmarkCase(
        case_id="real_public_qa_02",
        family="public long-context qa",
        description="Resolve discoverer identity under similar biomedical distractors.",
        user_input="[case:real_public_qa_02] Who discovered penicillin?",
        stage_tags=["plan", "execute"],
        thread_messages=_base_messages("penicillin"),
        knowledge_documents=[
            BenchmarkKnowledgeDocument(
                document_id="penicillin-primary",
                text=(
                    "Historical record: Penicillin was discovered by Alexander Fleming in 1928. "
                    "Large-scale production was later advanced by Howard Florey and Ernst Chain."
                ),
                scopes=["elephant-benchmark"],
                source_type="public_reference",
                locator={"doc": "penicillin_primary"},
            ),
            BenchmarkKnowledgeDocument(
                document_id="penicillin-distractor",
                text=(
                    "Biomedical distractor note: Streptomycin was discovered by Selman Waksman. "
                    "This is a different antibiotic and should not replace penicillin attribution."
                ),
                scopes=["elephant-benchmark"],
                source_type="public_reference",
                locator={"doc": "penicillin_distractor"},
            ),
        ],
        task_context=_route_context("public_long_context_qa"),
        gold_key_segment_ids=["evidence:0"],
        gold_support_segment_ids=["citation:0"],
        stage_focus_segment_ids=["evidence:0"],
        expected_answer_fields={"primary_answer": "Alexander Fleming"},
        critical_markers=["Alexander Fleming"],
        distractor_markers=["Selman Waksman"],
    )


def _cross_session_memory_case() -> ElephantBenchmarkCase:
    return ElephantBenchmarkCase(
        case_id="real_memory_rank_01",
        family="cross-session memory ranking",
        description="Prior validated collective memory should dominate over nearby stale notes.",
        user_input="[case:real_memory_rank_01] What is the validated protocol RFC number for IPv4?",
        stage_tags=["plan", "collective_memory"],
        thread_messages=_base_messages("ipv4"),
        collective_memories=[
            BenchmarkCollectiveMemory(
                kind="protocol_fact",
                content="Validated protocol memory: IPv4 is specified in RFC 791.",
                tags=["protocol", "ipv4", "validated"],
                source_agents=["matriarch"],
                confidence=0.92,
                scope="planning",
            )
        ],
        knowledge_documents=[
            BenchmarkKnowledgeDocument(
                document_id="ipv4-distractor",
                text=(
                    "Distractor: RFC 793 specifies TCP and is often confused with IPv4 references. "
                    "Keep protocol layering distinctions explicit."
                ),
                scopes=["elephant-benchmark"],
                source_type="public_reference",
                locator={"doc": "ipv4_distractor"},
            )
        ],
        task_context=_route_context("cross_session_memory"),
        gold_key_segment_ids=["collective:0"],
        gold_support_segment_ids=["task_packet"],
        stage_focus_segment_ids=["collective:0"],
        expected_answer_fields={"primary_answer": "RFC 791"},
        critical_markers=["RFC 791"],
        distractor_markers=["RFC 793"],
    )


def _cross_session_memory_case_2() -> ElephantBenchmarkCase:
    return ElephantBenchmarkCase(
        case_id="real_memory_rank_02",
        family="cross-session memory ranking",
        description="Collective memory anchor should survive long noisy narration.",
        user_input="[case:real_memory_rank_02] Which conference published the Transformer paper in 2017?",
        stage_tags=["plan", "collective_memory", "retrieval_evidence"],
        thread_messages=_base_messages("transformer"),
        collective_memories=[
            BenchmarkCollectiveMemory(
                kind="paper_fact",
                content="Validated paper memory: Attention Is All You Need was introduced at NeurIPS 2017.",
                tags=["transformer", "paper", "validated"],
                source_agents=["matriarch"],
                confidence=0.9,
                scope="planning",
            )
        ],
        knowledge_documents=[
            BenchmarkKnowledgeDocument(
                document_id="transformer-distractor",
                text=(
                    "Distractor note: BERT appeared later and is associated with NAACL 2019 publication context. "
                    "Do not replace the original Transformer venue."
                ),
                scopes=["elephant-benchmark"],
                source_type="public_reference",
                locator={"doc": "transformer_distractor"},
            )
        ],
        task_context=_route_context("cross_session_memory"),
        gold_key_segment_ids=["collective:0"],
        gold_support_segment_ids=["task_packet"],
        stage_focus_segment_ids=["collective:0"],
        expected_answer_fields={"primary_answer": "NeurIPS 2017"},
        critical_markers=["NeurIPS 2017"],
        distractor_markers=["NAACL 2019"],
    )


def list_real_task_cases() -> list[ElephantBenchmarkCase]:
    return [
        _apollo_case(),
        _penicillin_case(),
        _cross_session_memory_case(),
        _cross_session_memory_case_2(),
    ]


def get_real_task_case(case_id: str) -> ElephantBenchmarkCase:
    for case in list_real_task_cases():
        if case.case_id == case_id:
            return case
    available = ", ".join(case.case_id for case in list_real_task_cases())
    raise KeyError(f"Unknown real-task benchmark case '{case_id}'. Available cases: {available}")


__all__ = ["get_real_task_case", "list_real_task_cases"]
