# Evolution Module

`agentorch.evolution` separates orchestration, execution context, and concrete search algorithms.

## Structure

- `types.py`: pure evolution data models
- `context.py`: execution context shared by algorithms
- `manager.py`: orchestration facade
- `registry.py`: algorithm registration and lookup
- `algorithms/`: concrete algorithm implementations

## Guidelines

- Add new search mechanisms under `algorithms/`
- Keep `strategies.py` as a compatibility bridge only
- Register built-ins through `bootstrap_evolution_defaults()`
- Avoid having algorithms reach back into manager private methods
