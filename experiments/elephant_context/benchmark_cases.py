from __future__ import annotations

from .models import (
    BenchmarkCollectiveMemory,
    BenchmarkKnowledgeDocument,
    BenchmarkMessageSeed,
    ElephantBenchmarkCase,
)


def _noise_block(label: str, *, repeat: int = 24) -> str:
    sentence = (
        f"{label} noisy discussion keeps repeating outdated snippets, anecdotal guesses, "
        f"and irrelevant coordination chatter that should not override validated context."
    )
    return " ".join(sentence for _ in range(repeat))


def _route_context(family: str, handoff_anchor: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "target_agents": ["planner", "evidence_scout", "reviewer"],
        "preferred_capabilities": ["plan", "retrieve", "review"],
        "max_agents": 3,
        "scenario_family": family,
    }
    if handoff_anchor is not None:
        payload["handoff_anchor"] = handoff_anchor
    return payload


def _base_messages(prefix: str, distractor: str) -> list[BenchmarkMessageSeed]:
    return [
        BenchmarkMessageSeed(role="assistant", content=f"{prefix} legacy memo references {distractor}. {_noise_block(prefix + '-legacy-a')}"),
        BenchmarkMessageSeed(role="user", content=f"{prefix} field chatter repeats {distractor}. {_noise_block(prefix + '-legacy-b')}"),
        BenchmarkMessageSeed(role="assistant", content=_noise_block(prefix + "-summary")),
        BenchmarkMessageSeed(role="assistant", content=_noise_block(prefix + "-handoff")),
        BenchmarkMessageSeed(role="assistant", content=_noise_block(prefix + "-tail")),
    ]


def _rule_preservation_case(index: int) -> ElephantBenchmarkCase:
    critical = f"RULE-RP-{index:02d}-ALPHA"
    distractor = f"RULE-RP-{index:02d}-BETA"
    prefix = f"rule-preservation-{index:02d}"
    return ElephantBenchmarkCase(
        case_id=f"rule_preservation_{index:02d}",
        family="early critical rule preservation",
        description="Keep a validated early rule from shared memory despite later noisy chatter.",
        user_input=f"[case:rule_preservation_{index:02d}] Determine the governing checkpoint rule for convoy {index:02d}.",
        stage_tags=["plan", "collective_memory"],
        thread_messages=_base_messages(prefix, distractor),
        collective_memories=[
            BenchmarkCollectiveMemory(
                kind="checkpoint_rule",
                content=f"Validated checkpoint rule for convoy {index:02d}: {critical}. {_noise_block(prefix + '-validated', repeat=14)}",
                tags=["rule", "validated", f"convoy-{index:02d}"],
                source_agents=["matriarch"],
                confidence=0.92,
                scope="planning",
            )
        ],
        task_context=_route_context("rule_preservation"),
        gold_key_segment_ids=["collective:0"],
        gold_support_segment_ids=["task_packet"],
        stage_focus_segment_ids=["collective:0"],
        expected_answer_fields={"primary_answer": critical},
        critical_markers=[critical],
        distractor_markers=[distractor],
    )


def _evidence_competition_case(index: int) -> ElephantBenchmarkCase:
    critical = f"EVID-EC-{index:02d}-PRIMARY"
    distractor = f"EVID-EC-{index:02d}-DISTRACTOR"
    prefix = f"evidence-competition-{index:02d}"
    shared_anchor = f"ANCHOR-EC-{index:02d}"
    return ElephantBenchmarkCase(
        case_id=f"evidence_competition_{index:02d}",
        family="distractor-heavy evidence competition",
        description="Prefer the highest-value retrieved evidence under distractor pressure.",
        user_input=f"[case:evidence_competition_{index:02d}] Retrieve the verified evidence packet for site {index:02d}.",
        stage_tags=["plan", "execute"],
        thread_messages=_base_messages(prefix, distractor),
        knowledge_documents=[
            BenchmarkKnowledgeDocument(
                document_id=f"ec-{index:02d}-primary",
                text=(
                    f"verified evidence packet site {index:02d} primary signal {critical}. "
                    f"verified evidence packet site {index:02d} primary signal {critical}. "
                    f"{_noise_block(prefix + '-primary', repeat=12)}"
                ),
                scopes=["elephant-benchmark"],
                source_type="case_document",
                locator={"doc": "primary"},
            ),
            BenchmarkKnowledgeDocument(
                document_id=f"ec-{index:02d}-secondary",
                text=f"secondary evidence packet for site {index:02d}. {_noise_block(prefix + '-secondary', repeat=12)}",
                scopes=["elephant-benchmark"],
                source_type="case_document",
                locator={"doc": "secondary"},
            ),
            BenchmarkKnowledgeDocument(
                document_id=f"ec-{index:02d}-distractor",
                text=(
                    f"verified evidence packet site {index:02d} alternate signal {distractor}. "
                    f"verified evidence packet site {index:02d} alternate signal {distractor}. "
                    f"{_noise_block(prefix + '-distractor', repeat=12)}"
                ),
                scopes=["elephant-benchmark"],
                source_type="case_document",
                locator={"doc": "distractor"},
            ),
        ],
        collective_memories=[
            BenchmarkCollectiveMemory(
                kind="retrieval_anchor",
                content=f"Prior validated routing anchor for site {index:02d}: {shared_anchor}. {_noise_block(prefix + '-anchor', repeat=8)}",
                tags=["anchor", "retrieval"],
                source_agents=["matriarch"],
                confidence=0.81,
                scope="planning",
            )
        ],
        task_context=_route_context("evidence_competition"),
        gold_key_segment_ids=["evidence:0"],
        gold_support_segment_ids=["citation:0"],
        stage_focus_segment_ids=["evidence:0", "citation:0"],
        expected_answer_fields={"primary_answer": critical},
        critical_markers=[critical],
        distractor_markers=[distractor],
    )


def _delegation_handoff_case(index: int) -> ElephantBenchmarkCase:
    critical = f"HANDOFF-DH-{index:02d}-ANCHOR"
    distractor = f"HANDOFF-DH-{index:02d}-MISREAD"
    prefix = f"delegation-handoff-{index:02d}"
    return ElephantBenchmarkCase(
        case_id=f"delegation_handoff_{index:02d}",
        family="delegation handoff continuity",
        description="Preserve a handoff anchor across delegated execution.",
        user_input=f"[case:delegation_handoff_{index:02d}] Continue the delegated checkpoint analysis for relay {index:02d}.",
        stage_tags=["plan", "delegation_context"],
        thread_messages=_base_messages(prefix, distractor),
        collective_memories=[
            BenchmarkCollectiveMemory(
                kind="relay_memory",
                content=f"Validated relay memory for delegation case {index:02d}. {_noise_block(prefix + '-relay', repeat=10)}",
                tags=["handoff", "relay"],
                source_agents=["matriarch"],
                confidence=0.83,
                scope="planning",
            )
        ],
        task_context=_route_context("delegation_handoff", handoff_anchor=critical),
        gold_key_segment_ids=["delegation_context:handoff"],
        gold_support_segment_ids=["task_packet"],
        stage_focus_segment_ids=["delegation_context:handoff", "task_packet"],
        expected_answer_fields={"primary_answer": critical},
        critical_markers=[critical],
        distractor_markers=[distractor],
    )


def _tool_conflict_case(index: int) -> ElephantBenchmarkCase:
    critical = f"TOOL-TC-{index:02d}-VERIFIED"
    distractor = f"TOOL-TC-{index:02d}-CHATTER"
    prefix = f"tool-conflict-{index:02d}"
    messages = [
        BenchmarkMessageSeed(role="assistant", content=f"{prefix} narrative note keeps quoting {distractor}. {_noise_block(prefix + '-chat-a')}"),
        BenchmarkMessageSeed(role="user", content=f"{prefix} operator summary repeats {distractor}. {_noise_block(prefix + '-chat-b')}"),
        BenchmarkMessageSeed(role="tool", name="sensor_fusion", tool_call_id=f"tool-{index:02d}", content=f"verified tool observation for incident {index:02d}: {critical}. {_noise_block(prefix + '-tool', repeat=10)}"),
        BenchmarkMessageSeed(role="assistant", content=_noise_block(prefix + "-chat-c")),
        BenchmarkMessageSeed(role="assistant", content=_noise_block(prefix + "-chat-d")),
    ]
    return ElephantBenchmarkCase(
        case_id=f"tool_conflict_{index:02d}",
        family="tool result versus conversation conflict",
        description="Prefer verified tool output over conversational contradiction.",
        user_input=f"[case:tool_conflict_{index:02d}] Resolve the verified incident status for node {index:02d}.",
        stage_tags=["execute", "tool_observation"],
        thread_messages=messages,
        collective_memories=[
            BenchmarkCollectiveMemory(
                kind="incident_anchor",
                content=f"Validated incident anchor for node {index:02d}. {_noise_block(prefix + '-anchor', repeat=8)}",
                tags=["tool", "anchor"],
                source_agents=["matriarch"],
                confidence=0.8,
                scope="planning",
            )
        ],
        task_context=_route_context("tool_conflict"),
        gold_key_segment_ids=["conversation:2"],
        gold_support_segment_ids=["task_packet"],
        stage_focus_segment_ids=["conversation:2"],
        expected_answer_fields={"primary_answer": critical},
        critical_markers=[critical],
        distractor_markers=[distractor],
    )


def _late_synthesis_case(index: int) -> ElephantBenchmarkCase:
    final_answer = f"SYN-LS-{index:02d}-LOCKED"
    memory_marker = f"SYN-LS-{index:02d}-MEMORY"
    evidence_marker = f"SYN-LS-{index:02d}-EVIDENCE"
    distractor = f"SYN-LS-{index:02d}-NOISE"
    prefix = f"late-synthesis-{index:02d}"
    return ElephantBenchmarkCase(
        case_id=f"late_synthesis_{index:02d}",
        family="synthesis under noisy late chatter",
        description="Retain the synthesis-critical memory and evidence under late noisy chatter.",
        user_input=f"[case:late_synthesis_{index:02d}] Synthesize the final locked resolution for mission {index:02d}.",
        stage_tags=["aggregate", "collective_memory", "retrieval_evidence"],
        thread_messages=_base_messages(prefix, distractor),
        knowledge_documents=[
            BenchmarkKnowledgeDocument(
                document_id=f"ls-{index:02d}-primary",
                text=(
                    f"mission {index:02d} synthesis evidence {evidence_marker}. "
                    f"mission {index:02d} synthesis evidence {evidence_marker}. "
                    f"{_noise_block(prefix + '-primary', repeat=12)}"
                ),
                scopes=["elephant-benchmark"],
                source_type="case_document",
                locator={"doc": "primary"},
            ),
            BenchmarkKnowledgeDocument(
                document_id=f"ls-{index:02d}-noise",
                text=(
                    f"mission {index:02d} noisy synthesis note {distractor}. "
                    f"mission {index:02d} noisy synthesis note {distractor}. "
                    f"{_noise_block(prefix + '-noise', repeat=12)}"
                ),
                scopes=["elephant-benchmark"],
                source_type="case_document",
                locator={"doc": "noise"},
            ),
        ],
        collective_memories=[
            BenchmarkCollectiveMemory(
                kind="synthesis_memory",
                content=f"Validated synthesis memory for mission {index:02d}: {memory_marker}. {_noise_block(prefix + '-memory', repeat=10)}",
                tags=["synthesis", "validated"],
                source_agents=["matriarch"],
                confidence=0.9,
                scope="planning",
            )
        ],
        task_context=_route_context("late_synthesis"),
        gold_key_segment_ids=["collective:0", "evidence:0"],
        gold_support_segment_ids=["citation:0"],
        stage_focus_segment_ids=["collective:0", "evidence:0"],
        expected_answer_fields={"primary_answer": final_answer},
        critical_markers=[memory_marker, evidence_marker],
        distractor_markers=[distractor],
    )


def list_elephant_benchmark_cases() -> list[ElephantBenchmarkCase]:
    cases: list[ElephantBenchmarkCase] = []
    for index in range(1, 5):
        cases.append(_rule_preservation_case(index))
        cases.append(_evidence_competition_case(index))
        cases.append(_delegation_handoff_case(index))
        cases.append(_tool_conflict_case(index))
        cases.append(_late_synthesis_case(index))
    return cases


def get_elephant_benchmark_case(case_id: str) -> ElephantBenchmarkCase:
    for case in list_elephant_benchmark_cases():
        if case.case_id == case_id:
            return case
    available = ", ".join(case.case_id for case in list_elephant_benchmark_cases())
    raise KeyError(f"Unknown elephant benchmark case '{case_id}'. Available cases: {available}")


__all__ = ["get_elephant_benchmark_case", "list_elephant_benchmark_cases"]
