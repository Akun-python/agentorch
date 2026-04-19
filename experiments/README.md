# AgentOrch Paper Experiments

This directory contains the formal paper experiment framework for the RQ1-RQ5 evaluation suite.

## Formal benchmark protocol

The experiment layer is benchmark-first rather than demo-first.

- `experiments/tasks/benchmark_registry.json` defines the paper-facing benchmark anchors.
- Each task record can carry `benchmark_id`, `benchmark_name`, `benchmark_split`, and `benchmark_sample_id`.
- The current repository includes reproducible benchmark-aligned local slices for:
  - `GAIA`, `HotpotQA`, `MuSiQue` for long-horizon and distractor-heavy reasoning
  - `LoCoMo`, `LongMemEval` for long-term memory reuse
  - `LongBench`, `InfiniteBench` for budget-robust long-context evaluation
  - `AgentOrch Failure Suite` for observability and diagnostic studies

## Real-model defaults

The formal runners now default to real external model names routed through your OpenAI-compatible gateway:

- `gpt-4o`
- `deepseek-chat`
- `qwen-plus`

The target submission-strength protocol now uses five seeds by default:

- `7,11,19,23,29`

Important: the repository's currently collected formal evidence is still smaller than this target protocol for several RQs. The report generator therefore describes the existing runs as the currently collected `official_subset` slice rather than implying full benchmark coverage.

If your gateway uses different aliases, override them from CLI, for example:

- `py -3.13 experiments/run_formal.py --models "gpt-4o,deepseek-v3,qwen-max"`
- `py -3.13 experiments/run_ablation.py --experiment rq3_seagull_memory --models "gpt-4o,deepseek-chat,qwen-plus"`

## Main entrypoints

- `python experiments/run_one.py --experiment rq1_long_horizon_tasks --variant full_framework`
- `python experiments/run_all.py --variant full_framework --model gpt-4.1-mini --live-web`
- `py -3.13 experiments/run_formal.py --experiment rq1_long_horizon_tasks`
- `py -3.13 experiments/run_ablation.py --experiment rq3_seagull_memory`
- `py -3.13 experiments/run_scaling.py --agent-counts 1,2,4`
- `py -3.13 experiments/paper_suite.py`
- `py -3.13 experiments/generate_report.py`

## Notes

- Results are written to `experiments/results/<experiment>/<timestamp>/<variant>/`.
- Formal benchmark runs are written to `experiments/results_formal/<experiment>/<tag>/<variant>/<model>/seed-<seed>/`.
- Live web tasks require `BRAVE_SEARCH_API_KEY` or `BRAVE_API_KEY`.
- For smoke tests and local development you can use `--model mock:tool`.
- Use `py -3.13` on this machine because the default `python` executable points to Python 3.8 and does not match the current project environment.
- When running pytest locally, prefer `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; py -3.13 -m pytest -q` to avoid unrelated global pytest plugins interfering with this repo.
- `py -3.13 experiments/generate_report.py` now refreshes both the main paper tables and the dedicated elephant-context comparison assets under `experiments/report_assets/`, including `paper_tables.tex` and `elephant_context_tables.tex`.
