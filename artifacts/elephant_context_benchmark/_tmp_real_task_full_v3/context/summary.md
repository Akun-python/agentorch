# Elephant Context Benchmark Summary

- Run ID: `context`
- Completed runs: `4`
- Failed runs: `0`

## Baseline Comparison

| variant | budget | run_count | task_success | context_recall | key_evidence_retention_rate | stage_focus_hit_rate | budget_utilization |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elephant_full | 12000 | 2 | 1.0 | 1.0 | 1.0 | 1.0 | 0.918334 |
| multi_agent_default_context | 12000 | 2 | 0.5 | 0.0 | 0.0 | 0.0 | 0.762583 |

## Ablation Comparison

_No rows generated._

## Paired Deltas Versus Elephant Full

| variant | budget | metric | pair_count | mean_delta_vs_elephant_full |
| --- | --- | --- | --- | --- |
| multi_agent_default_context | 12000 | task_success | 2 | -0.5 |
| multi_agent_default_context | 12000 | context_precision | 2 | -0.113095 |
| multi_agent_default_context | 12000 | context_recall | 2 | -1.0 |
| multi_agent_default_context | 12000 | key_evidence_retention_rate | 2 | -1.0 |
| multi_agent_default_context | 12000 | stage_focus_hit_rate | 2 | -1.0 |
| multi_agent_default_context | 12000 | redundancy_ratio | 2 | -0.1625 |
| multi_agent_default_context | 12000 | budget_utilization | 2 | -0.15575 |
| multi_agent_default_context | 12000 | compaction_gain | 2 | -0.19019 |

## Failure Modes

- `multi_agent_default_context` / `real_memory_rank_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
