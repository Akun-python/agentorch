---
name: agent-orchestration
description: Use this skill when the task involves multi-agent routing, supervisor delegation, cooperation strategies, task handoff, or collective-memory behavior in an agent system.
triggers: multi-agent, supervisor, delegation, handoff, cooperation strategy, collective memory, elephant system
allowed_tools: read_file, search_text, find_files, deliberative_retrieve, search_knowledge_assets
tags: agents, orchestration, delegation, supervisor
summary: Inspect how tasks are routed across agents and how cooperation, memory, and aggregation interact.
---
Use this skill for orchestration debugging or design. The goal is to understand whether the system is truly delegating work or only carrying strategy metadata.

Workflow:
1. Identify the entrypoint that creates the runtime or preset agent.
2. Check whether `agent_registry` and `supervisor` are actually passed into runtime creation.
3. Trace the run path to see whether execution enters delegation logic or stays inside a single-agent reasoning loop.
4. Inspect cooperation strategy resolution separately from supervisor activation.
5. Verify what evidence of delegation exists in runtime events, task packets, and aggregation outputs.

When to use:
- The user asks whether multi-agent orchestration is really active.
- A cooperation strategy appears in config but delegation is not happening.
- You need to wire a demo from single-agent mode to real supervisor-driven execution.

What good output looks like:
- Clear distinction between configured strategy and actual runtime behavior.
- Exact conditions required to trigger delegation.
- Concrete files and events to inspect for proof.

Common failure modes:
- Assuming strategy metadata means orchestration is active.
- Looking only at presets and missing runtime constructor arguments.
- Ignoring aggregation and memory-promotion stages after delegation.
