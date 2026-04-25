# MGCM Chapter Benchmark Summary

- Run ID: `_tmp_finalize_v2`
- Suite: `full`
- Output Dir: `C:\Users\24260\Desktop\研究生生涯\智能体开发范式\artifacts\elephant_context_benchmark\_tmp_finalize_v2`
- Context artifacts: `context/`
- Lifecycle artifacts: `lifecycle/`

## Context Suite

# Elephant Context Benchmark Summary

- Run ID: `context`
- Completed runs: `8`
- Failed runs: `0`

## Baseline Comparison

| variant | budget | run_count | task_success | context_recall | key_evidence_retention_rate | stage_focus_hit_rate | budget_utilization |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elephant_full | 12000 | 4 | 1.0 | 0.875 | 1.0 | 1.0 | 0.950833 |
| multi_agent_default_context | 12000 | 4 | 0.5 | 0.0 | 0.0 | 0.0 | 0.762583 |

## Ablation Comparison

_No rows generated._

## Paired Deltas Versus Elephant Full

| variant | budget | metric | pair_count | mean_delta_vs_elephant_full |
| --- | --- | --- | --- | --- |
| multi_agent_default_context | 12000 | task_success | 4 | -0.5 |
| multi_agent_default_context | 12000 | context_precision | 4 | -0.096144 |
| multi_agent_default_context | 12000 | context_recall | 4 | -0.875 |
| multi_agent_default_context | 12000 | key_evidence_retention_rate | 4 | -1.0 |
| multi_agent_default_context | 12000 | stage_focus_hit_rate | 4 | -1.0 |
| multi_agent_default_context | 12000 | redundancy_ratio | 4 | -0.224107 |
| multi_agent_default_context | 12000 | budget_utilization | 4 | -0.18825 |
| multi_agent_default_context | 12000 | compaction_gain | 4 | -0.294972 |

## Failure Modes

- `multi_agent_default_context` / `real_memory_rank_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
- `multi_agent_default_context` / `real_memory_rank_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.


## Lifecycle Suite

# MGCM Lifecycle Benchmark Summary

- Run ID: `lifecycle`
- Completed runs: `20`
- Failed runs: `0`

## Baseline Comparison

| variant | run_count | task_success | mechanism_success | retrieval_success | state_integrity | ordering_success |
| --- | --- | --- | --- | --- | --- | --- |
| mgcm_full | 10 | 0.9 | 0.9 | 1.0 | 0.9 | 1.0 |
| mgcm_thread_local_memory | 10 | 0.0 | 0.0 | 0.4 | 0.8 | 0.8 |

## Ablation Comparison

_No rows generated._

## Paired Deltas Versus MGCM Full

| variant | metric | pair_count | mean_delta_vs_mgcm_full |
| --- | --- | --- | --- |
| mgcm_thread_local_memory | task_success | 10 | -0.9 |
| mgcm_thread_local_memory | mechanism_success | 10 | -0.9 |
| mgcm_thread_local_memory | retrieval_success | 10 | -0.6 |
| mgcm_thread_local_memory | state_integrity | 10 | -0.1 |
| mgcm_thread_local_memory | ordering_success | 10 | -0.2 |

## Failure Modes

- `mgcm_thread_local_memory` / `succession_real_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `cross_thread_real_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `promotion_validation_real_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `conflict_real_01`: markers `VENUE_RIGHT`, state_integrity `0.0`.
- `mgcm_thread_local_memory` / `temporal_decay_real_01`: markers `RECENT_PROTOCOL_v3`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `succession_real_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `cross_thread_real_01`: markers `none`, state_integrity `1.0`.
- `mgcm_full` / `promotion_validation_real_01`: markers `Alexander Fleming`, state_integrity `0.0`.
