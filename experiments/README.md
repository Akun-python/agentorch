# AgentOrch Research Experiments

`experiments/` now holds only the two active research experiments in this repository.

## Active experiments

- `experiments/elephant_context/`
  - Elephant-context governance and collective routing policies.
- `experiments/long_term_memory_graph/`
  - Long-term memory graph experiment package, tools, and benchmarks.

## Why this directory was simplified

The old RQ1-RQ5 paper benchmark framework, report generation scripts, cached outputs, and related smoke tests were cluttering the active experiment area.

Those historical materials were preserved and moved to:

- `archive/paper_benchmark_suite/`

The architecture-audit collector was also moved out of the experiment area to:

- `tools/architecture_audit/`

## Notes

- Keep new experiment work under one of the two active experiment packages above.
- Do not put generic benchmark runners, cached outputs, or report artifacts back into `experiments/`.
