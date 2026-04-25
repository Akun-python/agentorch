# MGCM Chapter Benchmark Summary

- Run ID: `_tmp_real_task_context`
- Suite: `context`
- Output Dir: `C:\Users\24260\Desktop\研究生生涯\智能体开发范式\artifacts\elephant_context_benchmark\_tmp_real_task_context`
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
| elephant_full | 12000 | 4 | 0.5 | 0.875 | 1.0 | 1.0 | 0.950833 |
| multi_agent_default_context | 12000 | 4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.762583 |

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

- `elephant_full` / `real_public_qa_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
- `multi_agent_default_context` / `real_public_qa_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
- `multi_agent_default_context` / `real_memory_rank_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
- `elephant_full` / `real_public_qa_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
- `multi_agent_default_context` / `real_public_qa_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
- `multi_agent_default_context` / `real_memory_rank_01` / budget `12000`: first observed field `[reviewer] agent_role=reviewer`, planned agents `reviewer,planner`.
