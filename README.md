<h1 align="center">masarch / agentorch</h1>

<p align="center">
  <a href="https://github.com/Akun-python/agentorch/blob/main/README.md">English</a> |
  <a href="https://github.com/Akun-python/agentorch/blob/main/README.zh-CN.md">简体中文</a> |
  <a href="https://github.com/Akun-python/agentorch/blob/main/README.zh-TW.md">繁體中文</a> |
  <a href="https://github.com/Akun-python/agentorch/blob/main/README.fr.md">Français</a> |
  <a href="https://github.com/Akun-python/agentorch/blob/main/README.ja.md">日本語</a> |
  <a href="https://github.com/Akun-python/agentorch/blob/main/README.ko.md">한국어</a> |
  <a href="https://github.com/Akun-python/agentorch/blob/main/README.es.md">Español</a>
</p>

PyPI distribution: `masarch`  
Python import package: `agentorch`  
Version: `0.1.1`  
Python: `3.10+`  
License: `MIT`

`agentorch` is a code-first, async-first framework for programmable multi-agent orchestration in Python.

It is built for teams that need explicit runtime control, not hidden prompt pipelines.

If your system needs tools, retrieval, memory, workflow, and delegation to work together as software components, `agentorch` gives you that runtime model.

Resources:

- Architecture overview: <https://github.com/Akun-python/agentorch/blob/main/resource/architecture_overview.svg>
- Runtime flow: <https://github.com/Akun-python/agentorch/blob/main/resource/runtime_flow.svg>
- Source repository: <https://github.com/Akun-python/agentorch>

## WHY

### Why This Project Exists 🎯

Many projects hit a wall after the "single assistant + one prompt" phase.

The moment you need specialist roles, constrained tools, repeatable state, and observable handoffs, ad-hoc prompt glue becomes difficult to reason about.

`agentorch` is designed to keep these concerns explicit:

- model adapter choices
- tool exposure and safety boundaries
- retrieval strategy and evidence mounting
- memory retention and promotion
- workflow execution order
- multi-agent coordination and delegation

### Why It Helps Engineering Teams 🧭

- You can inspect system assembly with exported blueprint/config.
- You can enforce policy boundaries with typed configs.
- You can evolve behavior (reasoning/RAG/workflow) without rewriting everything.
- You can test behavior through code-level contracts.

### Why It Helps Research Teams 🔬

- Swappable reasoning modes (`react`, `plan_execute`, etc.)
- Search/evolution support for strategy comparison
- Source-aware RAG flow and evidence-oriented outputs
- Long-horizon memory patterns for iterative tasks

### Typical Scenarios

- multi-agent coding assistants with bounded filesystem/shell access
- research copilots that must cite retrieved sources
- workflow-driven automation that needs deterministic node execution
- long-running assistants with thread/workspace memory

## WHAT

### Core Facade API

- `create_agent(...)`
- `create_multi_agent(...)`

These are the recommended entrypoints for most users.

### Key Runtime Building Blocks 🧩

- model adapters (`OpenAIModel`, compatible HTTP adapters)
- tool registry and bundles
- sandbox manager and policy
- knowledge base and RAG strategy
- memory manager and memory policy
- workflow DAG builder and runner
- observability hooks and SQLite event store

### Built-In Capability Surface

- structured tool calling via Pydantic I/O
- filesystem / execution / git / web / media bundles
- multi-format ingestion (`md`, `txt`, `pdf`, `docx`, code artifacts)
- reasoning strategy selection
- human feedback and resumable flows
- extension hooks for lifecycle interception

### What "Orchestration" Means Here

In `agentorch`, orchestration is not a marketing word.

It means each runtime concern has a concrete type and place in assembly:

- coordinator policies decide routing behavior
- supervisor plans are inspectable objects
- handoffs and task packets are explicit records
- memory scopes and shared state are controlled by policy

### Compatibility and Stability

- Python `3.10+`
- minimal core dependencies
- stable high-level facade surface for day-to-day use
- compatibility exports for older integrations

## HOW

### Installation 📦

Install from PyPI:

```bash
pip install masarch
```

If your package mirror has not synchronized the latest release yet, use the official PyPI index:

```bash
pip install -i https://pypi.org/simple --no-cache-dir masarch
```

Verify the installed distribution and import package:

```bash
python -c "import importlib.metadata as m; import agentorch; print(m.version('masarch')); print(agentorch.__file__)"
```

Query release versions:

```bash
pip index versions masarch -i https://pypi.org/simple
```

Local editable install:

```bash
pip install -e .
```

Direct install from GitHub:

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

Optional extras example:

```bash
pip install "masarch[neo4j]"
```

Local editable install with optional extras:

```bash
pip install -e ".[neo4j]"
```

### Environment Setup

Set provider credentials through environment variables:

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Local `.env` loading is opt-in.

### Recommended Start Path

1. Start with `create_agent(...)` and one minimal tool.
2. Add RAG only after baseline behavior is stable.
3. Add workflow DAG only when execution order matters.
4. Move to `create_multi_agent(...)` when role separation is clear.

### Validation Commands

Run package tests:

```powershell
py -3.10 -m pytest -q
```

Run README contract tests:

```powershell
py -3.10 -m pytest -q agentorch/tests/test_readme_contracts.py
```

### Practical Guardrails ✅

- keep tool allowlists narrow
- avoid enabling shell where not required
- keep thread IDs explicit for traceability
- close agents/runtimes after use

## QUICKSTART

### 1) Minimal Agent (sync)

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="You are concise and accurate.",
    reasoning="react",
)

result = agent.run_sync(
    "Explain what agent orchestration is in three bullet points.",
    thread_id="quickstart-en-001",
)

print(result.output_text)
agent.close()
```

### 2) Tool Calling

```python
from pydantic import BaseModel

from agentorch import ToolRegistry, create_agent, tool

class AddInput(BaseModel):
    a: int
    b: int

@tool(description="Add two integers.")
async def add_numbers(input: AddInput):
    return {"sum": input.a + input.b}

agent = create_agent(
    model="gpt-4.1-mini",
    tools=ToolRegistry.from_tools(add_numbers),
    reasoning="react",
)

result = agent.run_sync("Use add_numbers to compute 12 + 30.", thread_id="quickstart-tools-001")
print(result.output_text)
agent.close()
```

### 3) Multi-Agent Starter

```python
from agentorch import create_agent, create_multi_agent

planner = create_agent(model="gpt-4.1-mini", reasoning="plan_execute", name="planner")
reviewer = create_agent(model="gpt-4.1-mini", reasoning="react", name="reviewer")

team = create_multi_agent(
    model="gpt-4.1-mini",
    agents=[
        {"agent": planner, "name": "planner", "role": "planner"},
        {"agent": reviewer, "name": "reviewer", "role": "reviewer"},
    ],
    system_prompt="Coordinate specialists and return one final answer.",
)

result = team.run_sync("Draft and review a migration plan.", thread_id="quickstart-team-001")
print(result.output_text)
team.close()
```

### 4) Next Steps

- Add RAG with `knowledge_paths` and `enable_rag=True`
- Add workflow DAG when task steps need explicit control
- Add observability storage for trace and usage analysis
- Move policy objects into code for predictable behavior

### Quick FAQ

Q: Should I start with multi-agent first?  
A: Usually no. Start with one strong agent, then split roles when boundaries are clear.

Q: When should I enable workflow DAG?  
A: When task order matters and you want deterministic step execution.

Q: When should I enable long-term memory?  
A: When tasks span multiple threads/sessions and prior outputs must be reused.

Q: How do I keep tool execution safe?  
A: Use sandbox policy, strict allowlists, and narrow workspace scopes.

### Troubleshooting Notes 🛟

- `TypeError` around modern typing syntax usually means Python version is too low.
- If `python` points to an older interpreter, use explicit launcher command (`py -3.10`).
- If output feels unstable, pin model version and keep thread IDs consistent.
- If delegation is noisy, reduce agent count and tighten role descriptions first.

### Reference Entry Points

- Main docs: `README.md` (this file)
- Simplified Chinese: `README.zh-CN.md`
- Examples folder: `examples/`
- Package tests: `agentorch/tests/`

For production usage, treat this README as a launch map and move critical settings into versioned config files.

MIT License.
