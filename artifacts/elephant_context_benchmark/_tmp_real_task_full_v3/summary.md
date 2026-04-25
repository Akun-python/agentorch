# MGCM Chapter Benchmark Summary

- Run ID: `_tmp_real_task_full_v3`
- Suite: `full`
- Output Dir: `C:\Users\24260\Desktop\研究生生涯\智能体开发范式\artifacts\elephant_context_benchmark\_tmp_real_task_full_v3`
- Context artifacts: `context/`
- Lifecycle artifacts: `lifecycle/`

## Context Suite

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


## Lifecycle Suite

# MGCM Lifecycle Benchmark Summary

- Run ID: `lifecycle`
- Completed runs: `10`
- Failed runs: `0`

## Baseline Comparison

| variant | run_count | task_success | mechanism_success | retrieval_success | state_integrity | ordering_success |
| --- | --- | --- | --- | --- | --- | --- |
| mgcm_full | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| mgcm_thread_local_memory | 5 | 0.0 | 0.0 | 0.4 | 0.8 | 0.8 |

## Ablation Comparison

_No rows generated._

## Paired Deltas Versus MGCM Full

| variant | metric | pair_count | mean_delta_vs_mgcm_full |
| --- | --- | --- | --- |
| mgcm_thread_local_memory | task_success | 5 | -1.0 |
| mgcm_thread_local_memory | mechanism_success | 5 | -1.0 |
| mgcm_thread_local_memory | retrieval_success | 5 | -0.6 |
| mgcm_thread_local_memory | state_integrity | 5 | -0.2 |
| mgcm_thread_local_memory | ordering_success | 5 | -0.2 |

## Failure Modes

- `mgcm_thread_local_memory` / `succession_real_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `cross_thread_real_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `promotion_validation_real_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `conflict_real_01`: markers `VENUE_RIGHT`, state_integrity `0.0`.
- `mgcm_thread_local_memory` / `temporal_decay_real_01`: markers `RECENT_PROTOCOL_v3`, state_integrity `1.0`.
