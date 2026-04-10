# Reasoning Module

`agentorch.reasoning` separates abstract reasoning contracts from concrete mechanisms.

## Structure

- `base.py`: configs, abstract interfaces, sessions, and result models
- `registry.py`: registration and lookup
- `factory.py`: framework construction
- `mechanisms/`: concrete reasoning implementations
- `parsers.py`: shared text extraction helpers

## Guidelines

- Add each new reasoning framework in its own file under `mechanisms/`
- Keep `frameworks.py` as a compatibility bridge only
- Do not add new reasoning implementations to compatibility files
- Register built-ins through `bootstrap_reasoning_defaults()`
