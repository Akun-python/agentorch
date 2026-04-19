import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentorch.agents import (
    AgentCapability,
    AgentInvocation,
    AgentRegistry,
    AgentRouteDecision,
    AgentSpec,
    DelegationPlan,
    Supervisor,
    TaskPacket,
    TaskStatus,
)
from agentorch.config import MemoryConfig, RuntimeConfig
from agentorch.knowledge import Document, IndexedKnowledgeBase
from agentorch.memory import MemoryManager
from agentorch.models import OpenAIModel
from agentorch.presets import DeepResearchAgentConfig
from agentorch.reasoning import ReasoningStrategyConfig
from agentorch.runtime.agent import Agent
from agentorch.sandbox import SandboxManager, SandboxPolicy
from agentorch.skills import SkillLoader, SkillRegistry
from agentorch.strategies import (
    ContextPolicy,
    CoordinationPolicy,
    MemoryPolicy,
    StatePolicy,
)
from agentorch import create_agent, create_multi_agent
from agentorch.tools import ToolError, ToolRegistry, create_python_interpreter_tool


DEFAULT_RESEARCH_PROMPT = (
    "研究如何进行创新智能体架构设计，多智能体架构有哪些，应具备哪些能力。"
    "优先使用本地知识库，必要时进行网络搜索，并总结最有力的证据。"
)


def _display_subset(payload: dict[str, Any] | None, keys: list[str]) -> dict[str, Any] | None:
    if not payload:
        return None
    return {key: payload.get(key) for key in keys if key in payload}


def _print_child_reasoning_summary(result) -> None:
    child_reasoning = result.reasoning_metadata.get("child_reasoning", {})
    if not child_reasoning:
        print("child_reasoning: None")
        return

    print("child_reasoning:")
    for agent_name, payload in child_reasoning.items():
        reasoning_metadata = payload.get("reasoning_metadata", {}) or {}
        resolved_policies = reasoning_metadata.get("resolved_policies")
        context_budget = reasoning_metadata.get("context_budget_report")
        memory_recall = reasoning_metadata.get("memory_recall_report")
        memory_governance = reasoning_metadata.get("memory_policy_report")
        promotion_trace = reasoning_metadata.get("memory_promotion_trace")

        print(f"- {agent_name}")
        print(f"  status: {payload.get('status')}")
        print(f"  task_id: {payload.get('task_id')}")
        print(f"  reasoning_kind: {payload.get('reasoning_kind')}")
        print(f"  resolved_policies: {resolved_policies}")
        print(
            "  context_budget_report:",
            _display_subset(
                context_budget,
                [
                    "conversation_messages",
                    "estimated_total_chars",
                    "truncated_sections",
                    "compression_reason",
                    "compaction_applied",
                ],
            ),
        )
        print(
            "  memory_recall_report:",
            _display_subset(memory_recall, ["mechanism", "selected_count", "selected"]),
        )
        print(
            "  memory_policy_report:",
            _display_subset(
                memory_governance,
                ["kind", "collective_promotion_policy", "trail_knowledge_enabled", "validation_threshold"],
            ),
        )
        print("  memory_promotion_trace:", promotion_trace)


def _print_result_summary(result) -> None:
    print("Example smoke response:")
    print(result.output_text)
    print("\nReasoning metadata snapshot:")
    print("reasoning_kind:", result.reasoning_kind)
    print("resolved_policies:", result.reasoning_metadata.get("resolved_policies"))
    print("context_budget_report:", result.reasoning_metadata.get("context_budget_report"))
    print("memory_policy_report:", result.reasoning_metadata.get("memory_policy_report"))
    print("memory_recall_report:", result.reasoning_metadata.get("memory_recall_report"))
    print("memory_promotion_trace:", result.reasoning_metadata.get("memory_promotion_trace"))
    print("aggregation:", result.reasoning_metadata.get("aggregation"))
    _print_child_reasoning_summary(result)


def _print_web_fallback_summary(results: list[dict[str, Any]]) -> None:
    if not results:
        print("\nWeb fallback: no supplemental web results were retrieved.")
        return

    print("\nWeb fallback results:")
    for index, item in enumerate(results, start=1):
        print(f"{index}. {item.get('title')}")
        print(f"   query: {item.get('query')}")
        print(f"   url: {item.get('url')}")
        if item.get("description"):
            print(f"   snippet: {item.get('description')}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deep research multi-agent demo.")
    parser.add_argument("--stream", action="store_true", help="Stream runtime events and final output.")
    parser.add_argument("--prompt", default=DEFAULT_RESEARCH_PROMPT, help="Research prompt to run.")
    parser.add_argument("--model", default="gpt-4.1-mini", help="Main orchestrator model.")
    parser.add_argument("--specialist-model", default="gpt-4.1-mini", help="Specialist agent model.")
    return parser.parse_args()


def _is_web_search_configured() -> bool:
    return bool(os.getenv("BRAVE_SEARCH_API_KEY") or os.getenv("BRAVE_API_KEY"))


def _looks_like_insufficient_coverage(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "没有找到",
        "暂无丰富证据",
        "覆盖尚不足",
        "建议在需要时可考虑进行网络搜索",
        "no matching evidence found",
        "insufficient",
        "missing evidence",
        "coverage is weak",
    ]
    return any(marker in lowered for marker in markers)


def _build_web_queries(prompt: str) -> list[str]:
    queries = [prompt]
    if "智能体" in prompt or "agent" in prompt.lower():
        queries.extend(
            [
                "创新智能体架构设计 多智能体 架构 能力",
                "multi-agent architecture design capabilities",
                "planner executor critic multi-agent architecture",
            ]
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = query.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped[:3]


async def _check_web_search_health(tools: ToolRegistry) -> dict[str, Any]:
    if "brave_search" not in tools:
        return {"available": False, "reason": "tool_not_registered"}
    if not _is_web_search_configured():
        return {"available": False, "reason": "missing_api_key"}

    try:
        result = await tools.execute(
            "brave_search",
            {
                "query": "multi-agent systems",
                "count": 1,
                "search_lang": "en",
                "country": "US",
            },
        )
        top_results = result.data.get("results", [])
        return {
            "available": True,
            "reason": "ok",
            "result_count": len(top_results),
            "sample": top_results[:1],
        }
    except ToolError as exc:
        return {"available": False, "reason": str(exc)}


async def _run_web_search_fallback(tools: ToolRegistry, prompt: str) -> list[dict[str, Any]]:
    if "brave_search" not in tools or not _is_web_search_configured():
        return []

    aggregated: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for query in _build_web_queries(prompt):
        try:
            result = await tools.execute(
                "brave_search",
                {
                    "query": query,
                    "count": 5,
                    "search_lang": "en" if query.isascii() else "zh-hans",
                    "country": "US",
                },
            )
        except ToolError:
            continue

        for item in result.data.get("results", []):
            url = item.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            aggregated.append({"query": query, **item})
        if len(aggregated) >= 5:
            break

    return aggregated[:5]


def build_demo_memory(workspace_root: Path) -> MemoryManager:
    memory_root = workspace_root / ".agentorch"
    memory_root.mkdir(exist_ok=True)
    return MemoryManager(
        config=MemoryConfig(
            checkpoint_path=memory_root / "deep_research_checkpoints.db",
            record_path=memory_root / "deep_research_records.db",
            persist_thread_messages=True,
            thread_history_recall_limit=5,
        )
    )


def _build_local_research_documents() -> list[Document]:
    return [
        Document(
            id="research-1",
            text=(
                "Agent orchestration systems benefit from explicit separation between tools, runtime, memory, and workflows. "
                "A robust architecture should isolate evidence gathering from synthesis so that verification and final reasoning "
                "do not collapse into one opaque step."
            ),
            metadata={"scopes": ["research"], "language": "en", "topic": "architecture"},
        ),
        Document(
            id="research-2",
            text=(
                "Deep research agents should compare evidence, note uncertainty, and keep citations visible to the final answer. "
                "When retrieval coverage is incomplete, they should explicitly state what is missing."
            ),
            metadata={"scopes": ["research"], "language": "en", "topic": "evidence"},
        ),
        Document(
            id="research-3",
            text=(
                "常见多智能体架构包括：监督者-执行者、规划者-执行者、评审者-批评者、黑板式协作、"
                "分层委派以及基于工作流图的编排。架构选择应根据任务耦合度、验证难度和并行机会决定。"
            ),
            metadata={"scopes": ["research"], "language": "zh", "topic": "multi-agent-architectures"},
        ),
        Document(
            id="research-4",
            text=(
                "创新智能体架构设计应具备任务分解、角色路由、证据检索、工具调用、记忆治理、失败回退、"
                "结果校验和不确定性表达等能力。"
            ),
            metadata={"scopes": ["research"], "language": "zh", "topic": "capabilities"},
        ),
        Document(
            id="research-5",
            text=(
                "A strong multi-agent system often separates collection of evidence, synthesis of claims, and review of risks. "
                "This structure improves inspectability and makes fallback to web search easier to trigger and diagnose."
            ),
            metadata={"scopes": ["research"], "language": "en", "topic": "design-patterns"},
        ),
    ]


def _build_resource_files(resources: Path) -> list[Path]:
    notes_path = resources / "deep_research_notes.md"
    notes_path.write_text(
        "# Deep Research Notes\n"
        "\n"
        "## Core Principles\n"
        "- Separate evidence collection, reasoning, and final synthesis.\n"
        "- Prefer grounded evidence over unsupported intuition.\n"
        "- If local knowledge is insufficient, escalate to web search when available.\n"
        "- Keep citations, uncertainty, and coverage gaps visible.\n"
        "\n"
        "## Architecture Patterns\n"
        "- Supervisor-worker.\n"
        "- Planner-executor.\n"
        "- Critic loop.\n"
        "- Blackboard/shared memory.\n",
        encoding="utf-8",
    )

    findings_path = resources / "deep_research_findings.txt"
    findings_path.write_text(
        "Workflow-based review keeps research steps inspectable.\n"
        "Evidence-first orchestration makes it easier to diagnose why an answer failed.\n"
        "Chinese and English phrasing should both be represented in local knowledge to improve retrieval recall.\n",
        encoding="utf-8",
    )

    patterns_path = resources / "multi_agent_patterns.md"
    patterns_path.write_text(
        "# Multi-Agent Patterns\n"
        "\n"
        "1. Hierarchical delegation\n"
        "2. Planner-executor\n"
        "3. Reviewer-critic loop\n"
        "4. Debate and adjudication\n"
        "5. Blackboard coordination\n"
        "\n"
        "Recommended capabilities:\n"
        "- decomposition\n"
        "- routing\n"
        "- tool use\n"
        "- retrieval\n"
        "- memory governance\n"
        "- self-checking\n"
        "- fallback handling\n"
        "- citation and uncertainty reporting\n",
        encoding="utf-8",
    )

    return [notes_path, findings_path, patterns_path]


def build_demo_config(*, workspace_root: Path) -> DeepResearchAgentConfig:
    return DeepResearchAgentConfig(
        system_prompt=(
            "You are a deep research orchestrator. Start from local knowledge and retrieval tools, then use web search "
            "if local coverage is weak or clearly incomplete. Be explicit about what evidence was found locally, "
            "what required web confirmation, and what remains uncertain."
        ),
        knowledge_scope=["research"],
        include_web_search=True,
        include_workspace_tools=True,
        include_execution_tools=True,
        include_git_tools=True,
        workspace_root=workspace_root,
        brave_api_key=os.getenv("BRAVE_SEARCH_API_KEY") or os.getenv("BRAVE_API_KEY"),
        coordination_policy=CoordinationPolicy(
            handoff_mode="summary_plus_artifacts",
            workspace_mode="artifacts_first",
            route_mode="guided",
            alert_mode="direct",
        ),
        reasoning_strategy=ReasoningStrategyConfig.plan_execute(
            config={"max_planning_steps": 4, "max_execution_steps": 4}
        ),
        context_policy=ContextPolicy(
            sources={
                "memory_summary": True,
                "retrieval_summary": True,
                "retrieval_evidence": {"enabled": True, "max_items": 6},
                "retrieval_citations": {"enabled": True, "max_items": 8},
                "retrieval_report": True,
                "retrieval_plan": False,
                "tool_descriptions": False,
                "skill_instructions": True,
                "task_packet": {"enabled": True, "representation": "capsule"},
                "delegation_context": {"enabled": True, "representation": "capsule"},
                "shared_memory": {"enabled": True, "max_items": 6},
            },
            char_budget=10000,
            selection_mode="hybrid",
        ),
        state_policy=StatePolicy(
            retention_mode="state_plus_memory",
            summary_refresh_every=20,
            snapshot_every=40,
            rollup_every=20,
        ),
        memory_policy=MemoryPolicy.long_horizon(
            promotion_mode="validated",
            validation_mode="threshold",
            thresholds_and_weights={
                "recall_top_k": 5,
                "allow_cross_thread_recall": True,
                "capsule_promotion_threshold": 0.9,
                "semantic_promotion_threshold": 1.6,
                "scene_index_fields": ["goal", "knowledge_scope", "agent_role", "thread_id"],
                "trail_knowledge_enabled": True,
                "validation_threshold": 0.65,
            },
        ),
        rag_strategy=DeepResearchAgentConfig().rag_strategy.model_copy(
            update={"max_steps": 4, "top_k": 6, "knowledge_scope": ["research"]}
        ),
    )


class ResearchSupervisor(Supervisor):
    async def create_plan(self, task: TaskPacket) -> DelegationPlan:
        decision: AgentRouteDecision = await self.policy.select_agents(task, self.registry)
        selected = decision.selected_agents or [spec.name for spec in self.registry.list_specs()]
        task_plan = self.planner.build_plan(task, selected, reason=decision.reason or "deep_research_fallback")
        invocations: list[AgentInvocation] = []
        for step in task_plan.steps:
            registered = self.registry.get(step.assigned_agent or "")
            invocations.append(
                AgentInvocation(
                    agent_name=registered.spec.name,
                    task=task.model_copy(
                        update={
                            "task_id": f"{task.task_id}:{registered.spec.name}",
                            "parent_task_id": task.task_id,
                            "origin_agent": task.origin_agent or "supervisor",
                            "status": TaskStatus.PENDING,
                            "knowledge_scope": registered.spec.allowed_knowledge_scopes or task.knowledge_scope,
                        }
                    ),
                    delegation_depth=int(task.metadata.get("delegation_depth", 0)) + 1,
                    metadata={"selection_reason": decision.reason or "deep_research_fallback", "step_id": step.step_id},
                )
            )
        return DelegationPlan(invocations=invocations, reason=decision.reason or "deep_research_fallback", task_plan=task_plan)


async def build_research_specialist(
    *,
    name: str,
    role_prompt: str,
    model_name: str,
    kb: IndexedKnowledgeBase,
    sandbox: SandboxManager,
    tools: ToolRegistry,
    skills: SkillRegistry,
    config: DeepResearchAgentConfig,
    memory: MemoryManager,
) -> Agent:
    specialist_context = ContextPolicy(
        sources={
            "memory_summary": True,
            "retrieval_summary": True,
            "retrieval_evidence": {"enabled": True, "max_items": 4},
            "retrieval_citations": False,
            "retrieval_report": False,
            "retrieval_plan": False,
            "tool_descriptions": False,
            "skill_instructions": True,
            "task_packet": {"enabled": True, "representation": "capsule"},
            "delegation_context": {"enabled": True, "representation": "capsule"},
            "shared_memory": {"enabled": True, "max_items": 4},
        },
        conversation_window=6,
        char_budget=14000,
    )
    specialist_reasoning = ReasoningStrategyConfig.react(config={"max_steps": 4})
    return create_agent(
        model=OpenAIModel(
            model=model_name,
            timeout=180.0,
            max_retries=8,
            retry_base_delay=2.5,
            retry_max_delay=45.0,
            retry_jitter=0.5,
            min_request_interval=3.0,
        ),
        profile="research",
        knowledge_base=kb,
        memory=memory,
        tools=tools,
        skills=skills,
        sandbox=sandbox,
        knowledge_scope=config.knowledge_scope,
        runtime_config=RuntimeConfig.agent(
            system_prompt=(
                f"You are {name}. {role_prompt} "
                "Start with local retrieval. If local retrieval is sparse or clearly insufficient and web search is available, "
                "use web search deliberately. Cite evidence when present, describe missing coverage when evidence is weak, "
                "and return a concise specialist memo."
            ),
            rag=config.rag_strategy,
            reasoning=specialist_reasoning,
            context_policy=specialist_context,
            state_policy=config.state_policy,
            coordination_policy=config.coordination_policy,
            memory_policy=config.memory_policy,
            default_knowledge_scope=config.knowledge_scope,
        ),
    )


async def main(
    *,
    stream: bool = False,
    prompt: str = DEFAULT_RESEARCH_PROMPT,
    model_name: str = "gpt-4.1-mini",
    specialist_model_name: str = "gpt-4.1-mini",
) -> None:
    resources = Path("examples") / "resources"
    resources.mkdir(exist_ok=True)
    knowledge_paths = _build_resource_files(resources)

    skill_root = Path.cwd() / ".skills"
    skill_root.mkdir(exist_ok=True)
    skill_dir = skill_root / "deep_research_protocol"
    skill_dir.mkdir(exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: deep_research_protocol\n"
            "description: Evidence-first deep research guidance\n"
            "triggers: research,evidence,citation,compare,investigate\n"
            "allowed_tools: brave_search,deliberative_retrieve,open_retrieved_evidence,search_knowledge_assets,python_interpreter\n"
            "tags: research,evidence,citation\n"
            "---\n"
            "When doing deep research, decompose the question into sub-questions, gather evidence before concluding, "
            "compare competing claims, state uncertainty explicitly, keep citations visible in the final synthesis, "
            "and when local retrieval is weak, try web search before declaring there is no evidence."
        ),
        encoding="utf-8",
    )

    kb = await IndexedKnowledgeBase.acreate(
        documents=_build_local_research_documents(),
        paths=knowledge_paths,
        scopes=["research"],
    )

    sandbox = SandboxManager(
        policy=SandboxPolicy(
            allowed_paths=[Path.cwd()],
            command_allowlist=["python", "git", "powershell", "cmd"],
            timeout=15.0,
        )
    )

    custom_tools = ToolRegistry.from_tools(create_python_interpreter_tool(sandbox))
    skills = SkillRegistry()
    for skill in SkillLoader().discover(skill_root):
        skills.register(skill)

    config = build_demo_config(workspace_root=Path.cwd())
    shared_memory = build_demo_memory(Path.cwd())
    registry = AgentRegistry()

    evidence_scout = await build_research_specialist(
        name="evidence_scout",
        role_prompt="Focus on gathering and validating relevant evidence before drawing conclusions.",
        model_name=specialist_model_name,
        kb=kb,
        sandbox=sandbox,
        tools=custom_tools,
        skills=skills,
        config=config,
        memory=shared_memory,
    )
    registry.register(
        AgentSpec(
            name="evidence_scout",
            description="Collects supporting evidence and retrieves grounded facts.",
            tags=["research", "evidence", "retrieve"],
            capabilities=[AgentCapability.RETRIEVE, AgentCapability.TOOL_USE],
            allowed_knowledge_scopes=["research"],
            default_coordination_policy=config.coordination_policy,
        ),
        evidence_scout,
    )

    synthesis_analyst = await build_research_specialist(
        name="synthesis_analyst",
        role_prompt="Focus on comparing findings, surfacing uncertainty, and producing a clean synthesis.",
        model_name=specialist_model_name,
        kb=kb,
        sandbox=sandbox,
        tools=custom_tools,
        skills=skills,
        config=config,
        memory=shared_memory,
    )
    registry.register(
        AgentSpec(
            name="synthesis_analyst",
            description="Synthesizes research findings into a trustworthy answer.",
            tags=["research", "synthesis", "compare"],
            capabilities=[AgentCapability.AGGREGATE, AgentCapability.REVIEW],
            allowed_knowledge_scopes=["research"],
            default_coordination_policy=config.coordination_policy,
        ),
        synthesis_analyst,
    )

    supervisor = ResearchSupervisor(registry=registry)

    agent = create_multi_agent(
        model=OpenAIModel(
            model=model_name,
            timeout=180.0,
            max_retries=8,
            retry_base_delay=2.5,
            retry_max_delay=45.0,
            retry_jitter=0.5,
            min_request_interval=3.0,
        ),
        agents=[
            {
                "agent": evidence_scout,
                "name": "evidence_scout",
                "role": "evidence_scout",
                "description": "Collects supporting evidence and retrieves grounded facts.",
                "capabilities": [AgentCapability.RETRIEVE, AgentCapability.TOOL_USE],
                "knowledge_scope": ["research"],
            },
            {
                "agent": synthesis_analyst,
                "name": "synthesis_analyst",
                "role": "synthesis_analyst",
                "description": "Synthesizes research findings into a trustworthy answer.",
                "capabilities": [AgentCapability.AGGREGATE, AgentCapability.REVIEW],
                "knowledge_scope": ["research"],
            },
        ],
        shared_memory=shared_memory,
        shared_knowledge=kb,
        system_prompt=config.system_prompt,
        reasoning=config.reasoning_strategy,
        coordination_policy=config.coordination_policy,
        context_policy=config.context_policy,
        state_policy=config.state_policy,
        memory_policy=config.memory_policy,
        runtime_config=config.runtime_config(),
        supervisor=supervisor,
    )

    print("Resolved preset configuration:")
    print(
        {
            "context_policy": getattr(agent.runtime.config.context_policy, "selection_mode", None),
            "state_policy": getattr(agent.runtime.config.state_policy, "retention_mode", None),
            "coordination_policy": getattr(agent.runtime.config.coordination_policy, "route_mode", None),
            "memory_policy": getattr(agent.runtime.config.memory_policy, "recall_mode", None),
            "memory_policy_bundle": {
                "promotion_policy": getattr(agent.runtime.config.memory_policy, "promotion_policy", None),
                "index_policy": getattr(agent.runtime.config.memory_policy, "index_policy", None),
                "recall_policy": getattr(agent.runtime.config.memory_policy, "recall_policy", None),
                "decay_policy": getattr(agent.runtime.config.memory_policy, "decay_policy", None),
            },
            "rag_mode": config.rag_strategy.mode,
            "memory_record_path": str(shared_memory.config.record_path),
        }
    )
    print("Architecture linkage:")
    print("- elephant_context: handoff + collective sharing + prompt compaction")
    print("- nutcracker_memory: episodic promotion + scene indexing + long-term recall")
    print("Available tools:")
    for spec in evidence_scout.runtime.tools.list_specs():
        print("-", spec["function"]["name"])

    web_health = await _check_web_search_health(evidence_scout.runtime.tools)
    print("Web search configured:", _is_web_search_configured())
    print("Web search health:", web_health)
    if not web_health.get("available"):
        print("Web search note: brave_search is not ready, so the agent will rely on local knowledge only.")

    print("Loaded skills:")
    for skill_name in ["deep_research_protocol"]:
        skill = skills.get(skill_name)
        if skill is not None:
            print("-", skill.manifest.name)
    print("Registered specialist agents:")
    for spec in registry.list_specs():
        print("-", spec.name)

    if stream:
        print("Streaming event trace:")
        final_result = None
        async for event in agent.run(prompt, thread_id="deep-research-demo", stream=True):
            if event.event_type == "model_delta" and event.delta_text:
                print(event.delta_text, end="")
                continue
            if event.event_type in {"supervisor_routed", "agent_delegated", "tool_called", "aggregation_completed"}:
                label = event.agent_name or event.payload.get("tool_name") or event.task_id or ""
                print(f"\n[{event.event_type}] {label}".rstrip())
            if event.event_type == "final_result":
                final_result = event.result
        if final_result is not None:
            print()
            _print_result_summary(final_result)
            if _looks_like_insufficient_coverage(final_result.output_text):
                fallback_results = await _run_web_search_fallback(evidence_scout.runtime.tools, prompt)
                _print_web_fallback_summary(fallback_results)
        return

    result = await agent.run(prompt, thread_id="deep-research-demo")
    _print_result_summary(result)
    if _looks_like_insufficient_coverage(result.output_text):
        fallback_results = await _run_web_search_fallback(agent.runtime.tools, prompt)
        _print_web_fallback_summary(fallback_results)


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(
        main(
            stream=args.stream,
            prompt=args.prompt,
            model_name=args.model,
            specialist_model_name=args.specialist_model,
        )
    )
