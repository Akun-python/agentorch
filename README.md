# agentorch 🤖🧠

<p align="center">
  <img src="resource/agentorch-icon.svg" alt="agentorch multi-agent framework icon" width="120">
</p>

<p align="center">
  <strong>A Python-native, async-first orchestration framework for multi-agent systems.</strong>
</p>

[中文文档 / Chinese README](README.zh-CN.md)

![GitHub stars](https://img.shields.io/github/stars/Akun-python/agentorch?style=flat-square&logo=github)
![GitHub forks](https://img.shields.io/github/forks/Akun-python/agentorch?style=flat-square&logo=github)
![License](https://img.shields.io/github/license/Akun-python/agentorch?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Async First](https://img.shields.io/badge/runtime-async--first-0ea5e9?style=flat-square)

![Tag Multi-Agent](https://img.shields.io/badge/tag-multi--agent-2563eb?style=flat-square)
![Tag Workflow DAG](https://img.shields.io/badge/tag-workflow--dag-0d9488?style=flat-square)
![Tag RAG](https://img.shields.io/badge/tag-rag-7c3aed?style=flat-square)
![Tag Reasoning](https://img.shields.io/badge/tag-reasoning-f97316?style=flat-square)
![Tag Memory MGCM](https://img.shields.io/badge/tag-memory--mgcm-059669?style=flat-square)
![Tag Tool Calling](https://img.shields.io/badge/tag-tool--calling-b45309?style=flat-square)
![Tag Sandbox](https://img.shields.io/badge/tag-sandbox-475569?style=flat-square)
![Tag OpenAI Compatible](https://img.shields.io/badge/tag-openai--compatible-111827?style=flat-square)

`agentorch` is a code-first framework for building programmable agent systems with explicit runtime assembly, structured tools, workflow DAGs, retrieval, long-term memory, reasoning strategies, human feedback, observability, and supervisor-based multi-agent coordination.

The project is designed for systems where one assistant is not enough: specialist agents need scoped knowledge, shared memory, traceable handoffs, controllable tool access, and a coordinator that can route work without turning the codebase into a hidden prompt-only pipeline.

All images referenced by this README live in [`resource/`](resource/).

![agentorch Architecture Overview](resource/architecture_overview.svg)

## Name Meaning: `Agent Orch` = `Agent Orchestration` 🎼

`agentorch` comes from **Agent Orch**, short for **Agent Orchestration**:

- `Agent`: one or more model-powered workers with explicit responsibilities.
- `Orch`: orchestration, meaning coordination, routing, constraints, memory, and lifecycle control.
- `agentorch`: an orchestration runtime where agent systems are assembled in Python as inspectable software artifacts, not opaque prompt chains.

In short: if your problem needs "one brain + tools", many frameworks can work. If your problem needs "a team of specialists + policy + memory + traceability", `agentorch` is designed for that path. ✅

## Why agentorch 🧭

Many agent frameworks make one of two tradeoffs: they hide orchestration inside a prompt-heavy abstraction, or they expose so many knobs that a real system becomes hard to reason about. `agentorch` takes a different route:

- Keep the primary interface Python-native instead of DSL-first.
- Make runtime boundaries explicit: model, tools, memory, knowledge, workflow, policies, supervisor, and extensions are separable.
- Treat multi-agent systems as first-class runtime objects, not as a chat transcript convention.
- Support research workflows where reasoning, retrieval, memory, and delegation strategies need to be compared or evolved.
- Keep provider configuration outside framework internals so model gateways and secrets remain deployment concerns.

The framework is useful for:

- Multi-agent research prototypes and thesis experiments.
- Tool-using assistants that need constrained filesystem, git, shell, web, or media tools.
- RAG systems that need source-aware retrieval plans, evidence reports, and scoped knowledge.
- Long-horizon agents that need thread state, workspace artifacts, episodic records, and collective memory.
- Workflow systems that need explicit DAG execution rather than one monolithic prompt.
- Evaluation loops that search over reasoning, RAG, workflow, and runtime configurations.

## What It Supports 🧩

- **Facade-first construction** with `create_agent(...)`, `create_multi_agent(...)`, `AgentDesign`, `RoleDesign`, and `TeamDesign`.
- **Multi-agent orchestration** with `AgentRegistry`, `Supervisor`, `Coordinator`, `TaskPacket`, handoffs, scoped capabilities, shared memory, and shared knowledge.
- **Runtime policies** for context selection, state retention, coordination, and memory promotion through `ContextPolicy`, `StatePolicy`, `CoordinationPolicy`, and `MemoryPolicy`.
- **OpenAI-compatible models** through `OpenAIModel`, `OpenAICompatibleHTTPModel`, provider registries, and explicit `ModelConfig` objects.
- **Structured tool calling** through the `@tool` decorator, `ToolRegistry`, Pydantic inputs, and standard tool bundles.
- **Sandboxed execution** through `SandboxManager`, `SandboxPolicy`, and a Python interpreter tool.
- **Media capabilities** for speech synthesis, image generation, and video analysis when the selected model adapter supports them.
- **Knowledge and RAG** over markdown, text, code, PDF, DOCX, memory records, and workspace artifacts.
- **Selectable RAG strategies**: `classic`, `deliberative`, `hybrid`, and `off`.
- **Reasoning frameworks**: `cot`, `react`, `plan_execute`, `tot`, and `reflexion`.
- **Workflow DAGs** with model, tool, retrieval, RAG mount, RAG evaluation, aggregate, agent, human, and evolution node types.
- **Skill loading** with progressive disclosure, explicit `SKILL.md` resources, and per-run skill requests.
- **Memory governance** with session memory, summaries, local agent memory, workspace memory, shared notes, record memory, and collective memory.
- **Human-in-the-loop feedback** with inboxes, policies, feedback events, and `resume_from_feedback(...)`.
- **Observability** with structured event tracing, SQLite event storage, usage tracking, and redaction/budget controls.
- **Evolution search** with `genetic`, `random_search`, `hill_climb`, and `beam_search` algorithms.
- **Output parsing** with JSON, Pydantic, key-value, list, text, fallback, and parser-chain helpers.
- **Extension hooks** for run lifecycle, supervisor planning, and handoff customization.

## Recommended API Style

Use facade and design entrypoints for most application code:

- `create_agent(...)`
- `create_multi_agent(...)`
- `AgentDesign`, `RoleDesign`, `TeamDesign`
- `compose_agent(...)`, `compose_team(...)`
- `create_agent_evolution(...)`
- `create_multi_agent_evolution(...)`

Use typed configuration objects when you need explicit control:

- `ModelConfig.from_any(...)`
- `RuntimeConfig.agent(...)` and `RuntimeConfig.workflow(...)`
- `RagStrategyConfig.for_classic(...)`, `for_deliberative(...)`, `for_hybrid(...)`
- `ReasoningStrategyConfig.react(...)`, `plan_execute(...)`, `reflexion(...)`
- `ContextPolicy.default(...)`, `lean(...)`, `evidence_friendly(...)`, `hybrid_budgeted(...)`
- `CoordinationPolicy.distributed(...)`, `hybrid(...)`
- `MemoryPolicy.long_horizon(...)`
- `SkillCatalogConfig(...)` and `SkillRoutingConfig(...)`
- `ObservabilityConfig(...)`

Drop to core assembly only when you need lower-level control:

- `Runtime.create(...)` / `Runtime.acreate(...)`
- `Agent.create(...)` / `Agent.acreate(...)`
- `AgentRegistry().register(...)`
- `Supervisor(registry=...)`
- `WorkflowBuilder()` and `Node.*(...)`
- `ToolRegistry.from_tools(...)` and `ToolRegistry.with_bundles(...)`
- `IndexedKnowledgeBase.create(...)` / `IndexedKnowledgeBase.acreate(...)`

The stable top-level import surface is intentionally curated, while compatibility exports remain available for older callers.

## Installation 📦

### Requirements

- Python `3.10+`
- `pip` or `uv` package installer
- recommended: a virtual environment (`venv`, `conda`, or `uv` managed)

Core runtime dependencies are intentionally small:

```text
openai>=1.30.0
pydantic>=2.7.0
httpx>=0.27.0
jinja2>=3.1.0
```

Optional capabilities may need extra packages depending on the feature:

- PDF parsing: `pdfplumber` or `pypdf`
- DOCX parsing: `python-docx` improves parsing, with XML fallback available
- Long-term graph experiments: install the `neo4j` optional dependency when using Neo4j-backed paths

### Install Methods (Copy-Paste Ready)

1. Install from local source for development (recommended for contributors):

```bash
pip install -e .
```

2. Install from GitHub directly:

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

3. Install with `uv` (faster resolver):

```bash
uv pip install -e .
```

4. Install optional Neo4j extras:

```bash
pip install -e ".[neo4j]"
```

### Quick Environment Bootstrap

```bash
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# macOS/Linux
# source .venv/bin/activate
pip install -U pip
pip install -e .
```

### Verify Installation

```bash
python -c "import agentorch; print(agentorch.__version__ if hasattr(agentorch, '__version__') else 'agentorch imported')"
```

If this prints successfully, installation is complete. 🎉

### Common Installation Issues

- `TypeError: ... dict[str, Any]` on startup: you are likely using Python `<3.10`. Run with `py -3.10` (Windows) or switch interpreter.
- `pip install -e .` fails due to old pip: run `pip install -U pip setuptools wheel` and try again.
- environment has multiple Python versions: use explicit interpreter commands like `py -3.10 -m pip install -e .`.

## Environment Setup 🔐

`agentorch` keeps configuration at a standard library boundary:

- Pass model settings explicitly when you want full control.
- Use environment variables when you want deploy-time configuration.
- Local `.env` loading is opt-in through `initialize_environment(...)`.
- Automatic local env loading only happens when `AGENTORCH_AUTO_LOAD_ENV=1` is set before importing `agentorch`.

Common environment variables:

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_VISION_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_TTS_MODEL=your-tts-model
OPENAI_TTS_VOICE=your-voice
OPENAI_IMAGE_MODEL=your-image-model
OPENAI_VIDEO_MODEL=your-video-model
BRAVE_SEARCH_API_KEY=your-brave-key
```

Provider-specific base URLs are normalized. For example, full endpoint URLs such as `.../chat/completions`, `.../embeddings`, or `.../audio/speech` are reduced to the provider base URL expected by the matching adapter.

Explicit configuration example:

```python
from agentorch import OpenAIModel, create_agent

model = OpenAIModel(
    model="gpt-4.1-mini",
    api_key="YOUR_API_KEY",
    base_url="https://api.openai.com/v1",
)

agent = create_agent(model=model)
```

Opt-in local env loading:

```python
from agentorch.config import initialize_environment

initialize_environment(".env", overwrite=False)
```

## Quick Start ⚡

For a curated map of facade-first examples versus lower-level runtime examples, see [`examples/README.md`](examples/README.md).

### 0. First 5-Minute Run (Detailed)

Use this when you want one end-to-end "it works" script before exploring advanced features.

1. Set environment variable:

```powershell
$env:OPENAI_API_KEY="sk-xxxx"
```

2. Create `quickstart.py`:

```python
from agentorch import create_agent


def main() -> None:
    agent = create_agent(
        model="gpt-4.1-mini",
        system_prompt=(
            "You are a practical engineering assistant. "
            "Return concise answers with clear structure."
        ),
        reasoning="react",
        name="hello-agentorch",
    )
    try:
        result = agent.run_sync(
            "Explain Agent Orch (Agent Orchestration) in 3 bullet points.",
            thread_id="hello-001",
        )
        print("=== OUTPUT ===")
        print(result.output_text)
    finally:
        agent.close()


if __name__ == "__main__":
    main()
```

3. Run it:

```bash
python quickstart.py
```

4. Expected result:
- No exceptions during startup
- A valid assistant response in terminal output
- Thread-scoped run finished with clean shutdown

### 1. Minimal Agent

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="You are a concise and accurate assistant.",
    reasoning="react",
    name="quickstart-agent",
)

result = agent.run_sync(
    "Explain what agentorch is in three short sentences.",
    thread_id="quickstart-001",
)

print(result.output_text)
agent.close()
```

Use `await agent.run(...)` in notebooks and async applications. Use `run_sync(...)` in normal synchronous scripts.

### 2. Structured Tool Calling

```python
from pydantic import BaseModel

from agentorch import ToolRegistry, create_agent, tool


class AddInput(BaseModel):
    a: int
    b: int


@tool(description="Add two integers together.")
async def add_numbers(input: AddInput):
    return {"sum": input.a + input.b}


agent = create_agent(
    model="gpt-4.1-mini",
    tools=ToolRegistry.from_tools(add_numbers),
    reasoning="react",
)

result = agent.run_sync(
    "Use the add_numbers tool to calculate 123 + 456 and explain the result.",
    thread_id="tool-demo-001",
)

print(result.output_text)
print(result.tool_results)
agent.close()
```

### 3. Tool Bundles and Sandboxed Execution

Tool bundles keep common agent actions consistent. Execution tools are only registered when a sandbox is supplied.

```python
from pathlib import Path

from agentorch import ToolRegistry
from agentorch.sandbox import SandboxManager, SandboxPolicy

sandbox = SandboxManager(
    policy=SandboxPolicy(
        allowed_paths=[Path.cwd()],
        command_allowlist=["python", "git", "powershell", "cmd"],
        allow_shell=False,
        timeout=15.0,
    )
)

tools = ToolRegistry.with_bundles(
    workspace_root=Path.cwd(),
    sandbox=sandbox,
    include_filesystem=True,
    include_execution=True,
    include_git=True,
    include_web=False,
)
```

Available bundle families include filesystem, execution, git, web search, and media tools.

### 4. Multi-Agent Supervisor

`create_multi_agent(...)` builds a supervisor-root runtime with registered specialist agents. Shared memory and shared knowledge can be attached at the team level.

```python
from agentorch import AgentCapability, CoordinationPolicy, MemoryPolicy, create_agent, create_multi_agent

planner = create_agent(
    model="gpt-4.1-mini",
    reasoning="plan_execute",
    name="planner",
    description="Breaks goals into implementation plans.",
)

reviewer = create_agent(
    model="gpt-4.1-mini",
    reasoning="react",
    name="reviewer",
    description="Reviews plans for risk and missing evidence.",
)

team = create_multi_agent(
    model="gpt-4.1-mini",
    agents=[
        {
            "agent": planner,
            "name": "planner",
            "role": "planner",
            "description": "Planning specialist",
            "capabilities": [AgentCapability.PLAN],
            "knowledge_scope": ["architecture"],
        },
        {
            "agent": reviewer,
            "name": "reviewer",
            "role": "reviewer",
            "description": "Review specialist",
            "capabilities": [AgentCapability.REVIEW],
            "knowledge_scope": ["quality"],
        },
    ],
    coordination_policy=CoordinationPolicy.distributed(),
    memory_policy=MemoryPolicy.long_horizon(),
    system_prompt="Coordinate specialists and return one concise final answer.",
)

result = team.run_sync(
    "Plan and review a migration path for a multi-agent research assistant.",
    thread_id="team-demo-001",
)

print(result.output_text)
team.close()
```

### 5. Declarative Team Design

When role definitions repeat across projects, use `TeamDesign` and `AgentDesign` as reusable assembly specs.

```python
from agentorch import AgentCapability, AgentDesign, CoordinationPolicy, TeamDesign

role_defaults = AgentDesign(
    model="gpt-4.1-mini",
    profile="workflow",
    reasoning="react",
)

team_design = (
    TeamDesign(
        name="delivery-team",
        description="Planner and reviewer team with shared defaults.",
        role_defaults=role_defaults,
        coordination_policy=CoordinationPolicy.distributed(),
    )
    .add_role(
        "planner",
        description="Planning lead",
        capabilities=[AgentCapability.PLAN],
        knowledge_scope=["architecture"],
        supports_parallel_tasks=True,
    )
    .add_role(
        "reviewer",
        description="Quality reviewer",
        capabilities=[AgentCapability.REVIEW],
        knowledge_scope=["quality"],
        supports_parallel_tasks=True,
    )
)

team = team_design.build()
print(team.export_blueprint()["members"])
team.close()
```

### 6. Multi-Format RAG

```python
from pathlib import Path

from agentorch import IndexedKnowledgeBase, RagStrategyConfig, create_agent

knowledge_base = IndexedKnowledgeBase.create(
    paths=[
        Path("docs/architecture.md"),
        Path("docs/meeting_notes.docx"),
        Path("contracts/msa.pdf"),
    ],
    scopes=["architecture", "ops", "legal"],
)

agent = create_agent(
    model="gpt-4.1-mini",
    knowledge_base=knowledge_base,
    enable_rag=True,
    rag=RagStrategyConfig.for_hybrid(
        knowledge_scope=["architecture", "ops", "legal"],
        file_types=[".md", ".docx", ".pdf"],
        must_cover=["deployment restrictions"],
        max_steps=3,
    ),
    reasoning="react",
)

result = agent.run_sync(
    "Find the deployment restrictions and cite the strongest evidence.",
    thread_id="rag-demo-001",
)

print(result.output_text)
agent.close()
```

Mode guide:

- `classic`: chunk-oriented lexical retrieval.
- `deliberative`: source-routed, structure-aware active retrieval.
- `hybrid`: classic coarse recall followed by deliberative evidence refinement.
- `off`: disable retrieval injection.

### 7. Workflow DAGs

Workflows are Python-defined DAGs. They can retrieve evidence, mount RAG output, call tools, delegate to agents, aggregate results, or run evolution steps.

```python
from agentorch import WorkflowBuilder, create_agent
from agentorch.knowledge import RagStrategyConfig
from agentorch.workflow import Node

workflow = (
    WorkflowBuilder()
    .then(Node.retrieve("retrieve", output_key="retrieved", rag_mode="hybrid", must_cover=["owner approval"]))
    .then(Node.rag_mount("mount", from_variable="retrieved", target_key="mounted", mount_result_to="variable"))
    .then(Node.rag_evaluate("score", from_variable="retrieved", output_key="scored"))
    .then(Node.model_node("answer", task_context_from_variables=["retrieved", "scored"]))
    .build()
)

agent = create_agent(
    model="gpt-4.1-mini",
    workflow=workflow,
    knowledge_paths=["docs/architecture.md"],
    enable_rag=True,
    rag=RagStrategyConfig.for_hybrid(),
    reasoning="react",
)

result = agent.run_sync("Answer with evidence and cite risks.", thread_id="workflow-demo-001")
print(result.output_text)
agent.close()
```

![agentorch Runtime Flow](resource/runtime_flow.svg)

### 8. Skills

Skills are discovered from `SKILL.md` packages and can be loaded progressively. They are useful when an agent needs compact capability descriptions first, then detailed instructions or resources only when selected.

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    workspace_root=".",
    skills=[".skills/research-writer"],
    skill_catalog={
        "discovery_roots": [".skills"],
        "validation_mode": "lenient",
    },
    skill_routing={
        "mode": "progressive",
        "disclosure_level": "progressive",
        "selection_mode": "model",
    },
)

result = agent.run_sync(
    "Draft a section using the research-writer skill.",
    thread_id="skill-demo-001",
    skill_request={"force_load": ["research-writer"], "allow_auto_select": False},
)

print(result.output_text)
agent.close()
```

### 9. Media Capabilities

Media tools are available when the selected model adapter supports the matching capability.

```python
import asyncio

from agentorch import OpenAIModel, create_agent


async def main() -> None:
    model = OpenAIModel(model="gpt-4.1-mini")

    audio = await model.synthesize_speech("Hello from agentorch.")
    print(audio.output_path)

    image = await model.generate_image("A clean icon for a multi-agent framework.")
    print(image.output_path)

    video = await model.analyze_video(
        prompt="Summarize the important events in this clip.",
        video_path="examples/demo.mp4",
    )
    print(video.content)

    agent = create_agent(
        model=model,
        tool_bundles={
            "include_filesystem": False,
            "include_execution": False,
            "include_git": False,
            "include_media": True,
        },
    )
    print(agent.export_blueprint()["runtime"]["tools"])
    agent.close()


asyncio.run(main())
```

For `OpenAIModel` and `OpenAICompatibleHTTPModel`, `include_media=True` registers `text_to_speech`, `generate_image`, and `analyze_video` when supported.

### 10. Output Parsing

Use parser helpers when a run needs structured output without hand-written parsing code.

```python
from pydantic import BaseModel

from agentorch import PydanticParser, create_agent


class Decision(BaseModel):
    action: str
    confidence: float


agent = create_agent(model="gpt-4.1-mini")
parsed = agent.run_parsed_sync(
    "Return JSON for the next action and confidence.",
    thread_id="parser-demo-001",
    parser=PydanticParser(Decision),
)

print(parsed.parsed.action, parsed.parsed.confidence)
agent.close()
```

### 11. End-to-End Production-Style Starter 🧪

The following script combines practical defaults: tool bundles, RAG, observability, and explicit runtime policies.

```python
from pathlib import Path

from agentorch import (
    ContextPolicy,
    MemoryPolicy,
    RagStrategyConfig,
    ToolRegistry,
    create_agent,
)
from agentorch.config import ObservabilityConfig, RuntimeConfig
from agentorch.sandbox import SandboxManager, SandboxPolicy


workspace = Path.cwd()
sandbox = SandboxManager(
    policy=SandboxPolicy(
        allowed_paths=[workspace],
        command_allowlist=["python", "git", "powershell", "cmd"],
        allow_shell=False,
        timeout=20.0,
    )
)

tools = ToolRegistry.with_bundles(
    workspace_root=workspace,
    sandbox=sandbox,
    include_filesystem=True,
    include_execution=True,
    include_git=True,
    include_web=False,
)

agent = create_agent(
    model="gpt-4.1-mini",
    name="engineering-assistant",
    system_prompt=(
        "You are a careful software engineering assistant. "
        "Use tools when needed. Keep answers concise and actionable."
    ),
    tools=tools,
    knowledge_paths=["README.md"],
    enable_rag=True,
    rag=RagStrategyConfig.for_hybrid(max_steps=3),
    context_policy=ContextPolicy.evidence_friendly(),
    memory_policy=MemoryPolicy.long_horizon(),
    runtime_config=RuntimeConfig.agent(
        observability=ObservabilityConfig(
            enabled=True,
            sqlite_path=".agentorch/observability.db",
            console_mode="important_only",
        )
    ),
)

try:
    result = agent.run_sync(
        "Summarize the project architecture and list 3 engineering risks with evidence.",
        thread_id="prod-starter-001",
    )
    print(result.output_text)
finally:
    agent.close()
```

Why this layout is useful:

- `ToolRegistry.with_bundles(...)`: quickly enables a realistic operator toolset.
- `SandboxManager`: keeps command execution constrained and auditable.
- `RagStrategyConfig.for_hybrid(...)`: balances recall and precision for mixed documentation.
- `ObservabilityConfig`: writes trace events for debugging and cost/performance review.
- explicit `context_policy` and `memory_policy`: keeps behavior stable across long sessions.

## Runtime Assembly Guide 🧱

The runtime is intentionally layered. A typical agent or team assembly resolves in this order:

1. Model adapter or `ModelConfig`.
2. Tool registry and optional tool bundles.
3. Skill registry and routing policy.
4. Knowledge base and RAG strategy.
5. Memory manager and memory policy.
6. Runtime config, including prompt template, reasoning, context, state, coordination, observability, and output budgets.
7. Optional workflow DAG.
8. Optional agent registry, supervisor, and coordinator for multi-agent systems.
9. Optional feedback manager and runtime extensions.

This gives one clear place to inspect the assembled system:

```python
blueprint = agent.export_blueprint()
config = agent.export_config()
inspection = agent.inspect()
core_assembly = agent.export_core_assembly()
```

All exports apply redaction by default unless `unsafe_export=True` is explicitly set in runtime config.

## Multi-Agent Concepts

The multi-agent layer is built from concrete runtime types:

- `AgentSpec`: identity, role description, capabilities, tags, scope, and delegation limits.
- `AgentRegistry`: maps specs to runnable agents.
- `Supervisor`: creates routing/delegation plans.
- `Coordinator`: validates tasks, permissions, budgets, escalation, and aggregation.
- `TaskPacket`: the typed unit of delegated work.
- `Handoff`: the typed delegation record between supervisor and specialist.
- `SharedWorkspace` and `SharedNote`: collaboration artifacts.
- `MemoryManager`: thread, workspace, record, and collective-memory state.
- `ContextKernel`: prepares compact handoff context, shared memory evidence, and prompt context.

The default supported topology is `supervisor`. Parallel delegation is controlled through `CoordinationPolicy` and coordinator execution policy, so a team can be guided, distributed, or hybrid without changing the specialist agents.

## Memory and MGCM

The default memory composition includes:

- session memory
- thread summary memory
- agent-local memory
- workspace memory
- shared-note memory
- record memory
- collective memory

Collective memory is governed through MGCM-style mechanisms:

- promotion from validated or salient shared evidence
- scene-first indexing
- relevance-oriented decay
- scoped recall for delegated specialists
- candidate promotion after supervisor aggregation
- citations/evidence records that can be mounted back into prompt context

Use `MemoryPolicy.long_horizon(...)` when a team needs scene-aware long-term recall and cross-thread reuse.

## Policies

`agentorch` keeps runtime behavior explicit through policy objects:

- `ContextPolicy`: what context blocks are allowed into prompts, how much budget they receive, and how overflow is handled.
- `StatePolicy`: how conversation windows, summaries, snapshots, and rollups are retained.
- `CoordinationPolicy`: how handoffs, shared workspace views, route modes, and risk alerts behave.
- `MemoryPolicy`: how long-term recall, promotion, validation, indexing, and decay are selected.

These policies can be supplied directly to `create_agent(...)`, `create_multi_agent(...)`, `RuntimeConfig.agent(...)`, or design objects.

## Extensibility

Extension hooks let application code integrate behavior without patching the runtime core:

- `before_run(...)`
- `after_run(...)`
- `before_supervisor_plan(...)`
- `after_supervisor_plan(...)`
- `before_handoff(...)`
- `after_handoff(...)`

Use `RuntimeExtension` subclasses for logging, policy enforcement, application telemetry, custom state sync, or supervisor-plan intervention.

## Observability

Observability can store structured run events in SQLite, project TODO state, track usage, and emit console events.

```python
from agentorch import create_agent
from agentorch.config import ObservabilityConfig, RuntimeConfig

agent = create_agent(
    model="gpt-4.1-mini",
    runtime_config=RuntimeConfig.agent(
        observability=ObservabilityConfig(
            enabled=True,
            sqlite_path=".agentorch/observability.db",
            console_mode="important_only",
        )
    ),
)
```

Payload budgets and redaction are built into exported runtime state and observability storage.

## Human Feedback

Human feedback is available as runtime-level infrastructure:

- `HumanFeedbackManager`
- `DefaultFeedbackPolicy`
- `InMemoryHumanInbox`
- `ConsoleFeedbackDispatcher`
- `FeedbackKind`, `FeedbackSeverity`, `FeedbackStatus`
- `Runtime.resume_from_feedback(...)`

Workflow node kinds include `human_notify`, `human_input`, and `human_approval`, so a workflow can pause and resume around a real human decision.

## Evolution Search

Evolution search can optimize agent or team candidates over reasoning, RAG, workflow, and config choices.

```python
from agentorch import EvaluationResult, EvolutionConfig, SearchSpace, create_agent_evolution


async def evaluator(genome, agent, tasks):
    scores = []
    task_results = []
    for task in tasks:
        result = await agent.run(task["prompt"], thread_id=task["thread_id"])
        score = 1.0 if "expected" in result.output_text else 0.0
        scores.append(score)
        task_results.append({"thread_id": task["thread_id"], "score": score})

    fitness = sum(scores) / max(1, len(scores))
    return EvaluationResult(
        genome_id=genome.id,
        fitness=fitness,
        metrics={"mean_score": fitness},
        task_results=task_results,
    )


session = create_agent_evolution(
    model="gpt-4.1-mini",
    search_space=SearchSpace(
        {
            "reasoning.kind": ["react", "plan_execute"],
            "rag.mode": ["classic", "hybrid"],
            "workflow.template": ["classic_inline_answer", "retrieve_plan_review"],
        }
    ),
    evaluator=evaluator,
    tasks=[{"prompt": "Solve the benchmark task.", "thread_id": "evo-001"}],
    evolution_config=EvolutionConfig(
        algorithm_kind="beam_search",
        population_size=4,
        generations=3,
        evaluation_budget=8,
    ),
)
```

Use `create_multi_agent_evolution(...)` for team-level search.

## Project Layout

```text
agentorch/
|-- agents/          # Registry, supervisors, coordinators, handoffs, task packets
|-- config/          # Model, runtime, memory, sandbox, observability config
|-- core/            # Messages, run results, context envelopes, usage, stream events
|-- evolution/       # Search algorithms, genomes, sessions, workflow templates
|-- extensions/      # Runtime hook surface
|-- feedback/        # Human feedback inboxes, policies, dispatchers, events
|-- knowledge/       # RAG, ingestion, adapters, retrievers, citations
|-- memory/          # Thread state, records, stores, mechanisms, MGCM governance
|-- models/          # Provider adapters and media-capable model support
|-- observability/   # Tracing, event sinks, SQLite event store, usage tracking
|-- parsing/         # Structured output parsers and parser-chain helpers
|-- plugins/         # Extension manager surface for plugin-style integrations
|-- prompts/         # Prompt cards, templates, and prompt builder
|-- reasoning/       # CoT, ReAct, Plan-Execute, ToT, Reflexion
|-- runtime/         # Agent, Runtime, context kernel, workflow execution
|-- sandbox/         # Sandboxed command and Python-worker execution
|-- skills/          # SKILL.md discovery, catalog, routing, resource loading
|-- tools/           # Tool decorator, registry, filesystem, git, web, media, execution
|-- workflow/        # Workflow DAG data structures and runner
```

Other important directories:

```text
examples/            # Facade and lower-level runtime examples
experiments/         # Research experiment packages and benchmark CLIs
notebooks/           # Notebook resources and demos
resource/            # README images and framework icon
tests/               # Integration and behavior tests
agentorch/tests/     # Public API and package-level tests
```

## Examples

Recommended facade examples:

- [`examples/basic_agent.py`](examples/basic_agent.py)
- [`examples/supervisor_agents.py`](examples/supervisor_agents.py)
- [`examples/evolution_facade_demo.py`](examples/evolution_facade_demo.py)

Core and advanced examples:

- [`examples/code_interpreter_agent.py`](examples/code_interpreter_agent.py)
- [`examples/code_interpreter_session_workflow.py`](examples/code_interpreter_session_workflow.py)
- [`examples/evolution_demo.py`](examples/evolution_demo.py)
- [`examples/evolution_multi_mechanism.py`](examples/evolution_multi_mechanism.py)
- [`examples/evolution_orchestration_search.py`](examples/evolution_orchestration_search.py)
- [`examples/mgcm_demo.py`](examples/mgcm_demo.py)
- [`examples/rag_agent_tool_call.py`](examples/rag_agent_tool_call.py)
- [`examples/rag_mode_comparison.py`](examples/rag_mode_comparison.py)
- [`examples/rag_multiformat_runtime.py`](examples/rag_multiformat_runtime.py)
- [`examples/rag_ready_runtime.py`](examples/rag_ready_runtime.py)
- [`examples/rag_scoped_multi_agent.py`](examples/rag_scoped_multi_agent.py)
- [`examples/rag_workflow_orchestrated.py`](examples/rag_workflow_orchestrated.py)
- [`examples/workflow_multi_agent_graph.py`](examples/workflow_multi_agent_graph.py)
- [`examples/workflow_selectable_rag.py`](examples/workflow_selectable_rag.py)

Interactive notebooks:

- [`agentorch_experiments.ipynb`](agentorch_experiments.ipynb)
- [`agentorch_media_image_debug.ipynb`](agentorch_media_image_debug.ipynb)

## Testing

Recommended local validation:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.13 -m pytest agentorch/tests tests -q
py -3.13 -m compileall agentorch tests
```

On this machine, prefer an explicit `py -3.13` or newer launcher. The default `python` executable may resolve to a Python version below the supported `Python 3.10+` floor.

Focused checks:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.13 -m pytest agentorch/tests/test_readme_contracts.py tests/test_examples_contracts.py -q
py -3.13 -m pytest tests/test_multi_agent_runtime.py tests/test_orchestration_integration.py -q
py -3.13 -m pytest tests/test_memory.py tests/test_skills.py tests/test_workflow.py -q
```

## Design Notes

`agentorch` intentionally keeps these boundaries explicit:

- memory is not knowledge
- tools are not workflows
- workflows are not prompt templates
- skills are not execution engines
- supervisor routing is not free-form group chat
- RAG is a configurable strategy, not a hidden side effect
- model providers are adapters, not framework identity
- exports are redacted unless unsafe export is explicitly requested

These boundaries keep the framework maintainable for multi-agent applications, while still allowing lower-level runtime assembly when a research experiment or production integration needs it.

## Documentation Assets

README image dependencies:

- [`resource/agentorch-icon.svg`](resource/agentorch-icon.svg)
- [`resource/architecture_overview.svg`](resource/architecture_overview.svg)
- [`resource/runtime_flow.svg`](resource/runtime_flow.svg)

Keep new README images in `resource/` so documentation assets stay portable.

## License

MIT
