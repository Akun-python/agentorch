# Memory Module

`agentorch.memory` is organized into five layers:

- `types.py`: pure memory record models
- `state.py`: session-scoped thread, agent, and workspace state
- `backends/`: persistence backends such as SQLite and in-memory stores
- `governance/`: collective-memory governance implementations such as MGCM
- `mechanisms.py`: composable memory mechanisms that expose pluggable behaviors

## Guidelines

- Add new long-term persistence implementations under `backends/`
- Add new collective-memory governance policies under `governance/`
- Add new composable memory mechanisms under `mechanisms.py` or a future `mechanisms/` package
- Keep `manager.py` as the facade that composes state, backends, and governance
- Do not add new backend implementations to `stores.py`; it is a compatibility bridge only

## Composition

`MemoryManager` can now enable multiple mechanisms through `MemoryConfig.mechanisms`
or the `mechanisms=` constructor argument. Default mechanisms include:

- `session_memory`
- `thread_summary_memory`
- `agent_local_memory`
- `workspace_memory`
- `shared_note_memory`
- `record_memory`
- `collective_memory`

This design keeps the public API stable while allowing new memory strategies to
be registered and composed without rewriting the manager.
