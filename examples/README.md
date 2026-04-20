# AgentTorch Examples Guide

This directory contains two different kinds of examples:

## Recommended Facade Entrypoints

Use these first if you want the stable v1 public surface.

- `basic_agent.py`: minimal single-agent setup with `create_agent(...)`
- `supervisor_agents.py`: minimal multi-agent setup with `create_multi_agent(...)`
- `evolution_facade_demo.py`: evolution search from the facade entrypoints

These examples match the recommended API style in the root README files.

## Core Assembly / Lower-Level Runtime Examples

Use these when you want to see how `Runtime(...)`, `Agent(...)`, or `Agent.acreate(...)`
are assembled directly for advanced control.

- `rag_ready_runtime.py`: manual `Runtime(...)` plus `Agent(runtime=...)`
- `rag_multiformat_runtime.py`: lower-level RAG runtime construction
- `rag_mode_comparison.py`: direct runtime-level retrieval strategy comparison
- `reasoning_cot.py`, `reasoning_plan_execute.py`, `reasoning_reflexion.py`, `reasoning_tot.py`: direct runtime-level reasoning selection
- `tools.py`: explicit runtime assembly with tool bundles, sandboxing, tracing, and streaming inspection

These scripts are intentional low-level examples, not the default entrypoints recommended for day-to-day use.

## Verification

Representative examples in this directory are covered by `tests/test_examples_smoke.py`.
