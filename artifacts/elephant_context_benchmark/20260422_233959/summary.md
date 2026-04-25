# MGCM Chapter Benchmark Summary

- Run ID: `20260422_233959`
- Suite: `full`
- Output Dir: `C:\Users\24260\Desktop\研究生生涯\智能体开发范式\artifacts\elephant_context_benchmark\20260422_233959`
- Context artifacts: `context/`
- Lifecycle artifacts: `lifecycle/`

## Context Suite

# Elephant Context Benchmark Summary

- Run ID: `context`
- Completed runs: `10`
- Failed runs: `0`

## Baseline Comparison

| variant | budget | run_count | task_success | context_recall | key_evidence_retention_rate | stage_focus_hit_rate | budget_utilization |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elephant_full | 12000 | 5 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| multi_agent_default_context | 12000 | 5 | 0.0 | 0.566667 | 0.5 | 0.4 | 1.0 |

## Ablation Comparison

_No rows generated._

## Paired Deltas Versus Elephant Full

| variant | budget | metric | pair_count | mean_delta_vs_elephant_full |
| --- | --- | --- | --- | --- |
| multi_agent_default_context | 12000 | task_success | 5 | -0.8 |
| multi_agent_default_context | 12000 | context_precision | 5 | 0.0 |
| multi_agent_default_context | 12000 | context_recall | 5 | -0.1 |
| multi_agent_default_context | 12000 | key_evidence_retention_rate | 5 | -0.2 |
| multi_agent_default_context | 12000 | stage_focus_hit_rate | 5 | -0.2 |
| multi_agent_default_context | 12000 | redundancy_ratio | 5 | 0.083333 |
| multi_agent_default_context | 12000 | budget_utilization | 5 | 0.0 |
| multi_agent_default_context | 12000 | compaction_gain | 5 | -0.007601 |

## Failure Modes

- `multi_agent_default_context` / `rule_preservation_01` / budget `12000`: first observed field `[planner] agent_role=planner`, planned agents `planner,reviewer`.
- `elephant_full` / `evidence_competition_01` / budget `12000`: first observed field `[evidence_scout] agent_role=evidence_scout`, planned agents `evidence_scout,reviewer`.
- `multi_agent_default_context` / `evidence_competition_01` / budget `12000`: first observed field `[evidence_scout] agent_role=evidence_scout`, planned agents `evidence_scout,reviewer`.
- `multi_agent_default_context` / `delegation_handoff_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
- `multi_agent_default_context` / `tool_conflict_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
- `multi_agent_default_context` / `late_synthesis_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.


## Lifecycle Suite

# MGCM Lifecycle Benchmark Summary

- Run ID: `lifecycle`
- Completed runs: `10`
- Failed runs: `0`

## Baseline Comparison

| variant | run_count | task_success | mechanism_success | retrieval_success | state_integrity | ordering_success |
| --- | --- | --- | --- | --- | --- | --- |
| mgcm_full | 5 | 0.6 | 0.6 | 0.6 | 1.0 | 0.8 |
| mgcm_thread_local_memory | 5 | 0.2 | 0.2 | 0.4 | 0.8 | 0.8 |

## Ablation Comparison

_No rows generated._

## Paired Deltas Versus MGCM Full

| variant | metric | pair_count | mean_delta_vs_mgcm_full |
| --- | --- | --- | --- |
| mgcm_thread_local_memory | task_success | 5 | -0.4 |
| mgcm_thread_local_memory | mechanism_success | 5 | -0.4 |
| mgcm_thread_local_memory | retrieval_success | 5 | -0.2 |
| mgcm_thread_local_memory | state_integrity | 5 | -0.2 |
| mgcm_thread_local_memory | ordering_success | 5 | 0.0 |

## Failure Modes

- `mgcm_full` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `promotion_validation_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `conflict_01`: markers `CONFLICT_RIGHT_01`, state_integrity `0.0`.
- `mgcm_full` / `temporal_decay_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `temporal_decay_01`: markers `none`, state_integrity `1.0`.
