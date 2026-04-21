# Shared Experiment Assets

This directory stores the formal benchmark registry, shared task assets, rubric fragments, and reusable evaluation notes for the paper experiments.

## Benchmark registry

- `benchmark_registry.json` is the single source of truth for the paper-facing benchmark protocol.
- Each RQ experiment maps to one or more formal benchmark anchors.
- The current repository ships benchmark-aligned local slices so the codebase can be executed reproducibly without depending on external dataset downloads during every smoke run.

## Policy

- `formal benchmark` means the experiment design is tied to named public benchmarks rather than ad-hoc demo tasks.
- `benchmark-aligned local slice` means the repository includes small, reproducible tasks that mirror the target benchmark capability and reporting protocol.
- Full benchmark execution can later replace the local slices without changing the experiment runner or result schema.
