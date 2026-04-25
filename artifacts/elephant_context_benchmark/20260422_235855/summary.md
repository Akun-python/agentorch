# MGCM Chapter Benchmark Summary

- Run ID: `20260422_235855`
- Suite: `full`
- Output Dir: `C:\Users\24260\Desktop\研究生生涯\智能体开发范式\artifacts\elephant_context_benchmark\20260422_235855`
- Context artifacts: `context/`
- Lifecycle artifacts: `lifecycle/`

## Context Suite

# Elephant Context Benchmark Summary

- Run ID: `context`
- Completed runs: `480`
- Failed runs: `0`

## Baseline Comparison

| variant | budget | run_count | task_success | context_recall | key_evidence_retention_rate | stage_focus_hit_rate | budget_utilization |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elephant_full | 6000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_full | 12000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_full | 18000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| multi_agent_default_context | 6000 | 20 | 0.0 | 0.566667 | 0.5 | 0.4 | 1.0 |
| multi_agent_default_context | 12000 | 20 | 0.0 | 0.566667 | 0.5 | 0.4 | 1.0 |
| multi_agent_default_context | 18000 | 20 | 0.0 | 0.566667 | 0.5 | 0.4 | 1.0 |
| single_agent_long_context | 6000 | 20 | 0.4 | 0.566667 | 0.5 | 0.5 | 1.0 |
| single_agent_long_context | 12000 | 20 | 0.4 | 0.566667 | 0.5 | 0.5 | 1.0 |
| single_agent_long_context | 18000 | 20 | 0.4 | 0.566667 | 0.5 | 0.5 | 1.0 |

## Ablation Comparison

| variant | budget | run_count | task_success | context_recall | key_evidence_retention_rate | stage_focus_hit_rate | budget_utilization |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elephant_distributed_routing | 6000 | 20 | 0.2 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_distributed_routing | 12000 | 20 | 0.2 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_distributed_routing | 18000 | 20 | 0.2 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_drop_only | 6000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_drop_only | 12000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_drop_only | 18000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_flat_attention | 6000 | 20 | 0.8 | 0.733333 | 0.8 | 0.7 | 1.0 |
| elephant_flat_attention | 12000 | 20 | 0.8 | 0.733333 | 0.8 | 0.7 | 1.0 |
| elephant_flat_attention | 18000 | 20 | 0.8 | 0.733333 | 0.8 | 0.7 | 1.0 |
| elephant_no_redundancy | 6000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_no_redundancy | 12000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_no_redundancy | 18000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_rule_only | 6000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_rule_only | 12000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |
| elephant_rule_only | 18000 | 20 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |

## Paired Deltas Versus Elephant Full

| variant | budget | metric | pair_count | mean_delta_vs_elephant_full |
| --- | --- | --- | --- | --- |
| elephant_distributed_routing | 6000 | task_success | 20 | -0.6 |
| elephant_distributed_routing | 6000 | context_precision | 20 | -0.017857 |
| elephant_distributed_routing | 6000 | context_recall | 20 | 0.0 |
| elephant_distributed_routing | 6000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_distributed_routing | 6000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_distributed_routing | 6000 | redundancy_ratio | 20 | 0.083333 |
| elephant_distributed_routing | 6000 | budget_utilization | 20 | 0.0 |
| elephant_distributed_routing | 6000 | compaction_gain | 20 | 0.015305 |
| elephant_distributed_routing | 12000 | task_success | 20 | -0.6 |
| elephant_distributed_routing | 12000 | context_precision | 20 | -0.017857 |
| elephant_distributed_routing | 12000 | context_recall | 20 | 0.0 |
| elephant_distributed_routing | 12000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_distributed_routing | 12000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_distributed_routing | 12000 | redundancy_ratio | 20 | 0.083333 |
| elephant_distributed_routing | 12000 | budget_utilization | 20 | 0.0 |
| elephant_distributed_routing | 12000 | compaction_gain | 20 | 0.015305 |
| elephant_distributed_routing | 18000 | task_success | 20 | -0.6 |
| elephant_distributed_routing | 18000 | context_precision | 20 | -0.017857 |
| elephant_distributed_routing | 18000 | context_recall | 20 | 0.0 |
| elephant_distributed_routing | 18000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_distributed_routing | 18000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_distributed_routing | 18000 | redundancy_ratio | 20 | 0.083333 |
| elephant_distributed_routing | 18000 | budget_utilization | 20 | 0.0 |
| elephant_distributed_routing | 18000 | compaction_gain | 20 | 0.015305 |
| elephant_drop_only | 6000 | task_success | 20 | 0.0 |
| elephant_drop_only | 6000 | context_precision | 20 | 0.0 |
| elephant_drop_only | 6000 | context_recall | 20 | 0.0 |
| elephant_drop_only | 6000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_drop_only | 6000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_drop_only | 6000 | redundancy_ratio | 20 | 0.0 |
| elephant_drop_only | 6000 | budget_utilization | 20 | 0.0 |
| elephant_drop_only | 6000 | compaction_gain | 20 | -2.8e-05 |
| elephant_drop_only | 12000 | task_success | 20 | 0.0 |
| elephant_drop_only | 12000 | context_precision | 20 | 0.0 |
| elephant_drop_only | 12000 | context_recall | 20 | 0.0 |
| elephant_drop_only | 12000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_drop_only | 12000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_drop_only | 12000 | redundancy_ratio | 20 | 0.0 |
| elephant_drop_only | 12000 | budget_utilization | 20 | 0.0 |
| elephant_drop_only | 12000 | compaction_gain | 20 | -2.7e-05 |
| elephant_drop_only | 18000 | task_success | 20 | 0.0 |
| elephant_drop_only | 18000 | context_precision | 20 | 0.0 |
| elephant_drop_only | 18000 | context_recall | 20 | 0.0 |
| elephant_drop_only | 18000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_drop_only | 18000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_drop_only | 18000 | redundancy_ratio | 20 | 0.0 |
| elephant_drop_only | 18000 | budget_utilization | 20 | 0.0 |
| elephant_drop_only | 18000 | compaction_gain | 20 | -2.7e-05 |
| elephant_flat_attention | 6000 | task_success | 20 | 0.0 |
| elephant_flat_attention | 6000 | context_precision | 20 | 0.028571 |
| elephant_flat_attention | 6000 | context_recall | 20 | 0.066667 |
| elephant_flat_attention | 6000 | key_evidence_retention_rate | 20 | 0.1 |
| elephant_flat_attention | 6000 | stage_focus_hit_rate | 20 | 0.1 |
| elephant_flat_attention | 6000 | redundancy_ratio | 20 | 0.0 |
| elephant_flat_attention | 6000 | budget_utilization | 20 | 0.0 |
| elephant_flat_attention | 6000 | compaction_gain | 20 | -0.003048 |
| elephant_flat_attention | 12000 | task_success | 20 | 0.0 |
| elephant_flat_attention | 12000 | context_precision | 20 | 0.028571 |
| elephant_flat_attention | 12000 | context_recall | 20 | 0.066667 |
| elephant_flat_attention | 12000 | key_evidence_retention_rate | 20 | 0.1 |
| elephant_flat_attention | 12000 | stage_focus_hit_rate | 20 | 0.1 |
| elephant_flat_attention | 12000 | redundancy_ratio | 20 | 0.0 |
| elephant_flat_attention | 12000 | budget_utilization | 20 | 0.0 |
| elephant_flat_attention | 12000 | compaction_gain | 20 | -0.003048 |
| elephant_flat_attention | 18000 | task_success | 20 | 0.0 |
| elephant_flat_attention | 18000 | context_precision | 20 | 0.028571 |
| elephant_flat_attention | 18000 | context_recall | 20 | 0.066667 |
| elephant_flat_attention | 18000 | key_evidence_retention_rate | 20 | 0.1 |
| elephant_flat_attention | 18000 | stage_focus_hit_rate | 20 | 0.1 |
| elephant_flat_attention | 18000 | redundancy_ratio | 20 | 0.0 |
| elephant_flat_attention | 18000 | budget_utilization | 20 | 0.0 |
| elephant_flat_attention | 18000 | compaction_gain | 20 | -0.003048 |
| elephant_no_redundancy | 6000 | task_success | 20 | 0.0 |
| elephant_no_redundancy | 6000 | context_precision | 20 | 0.0 |
| elephant_no_redundancy | 6000 | context_recall | 20 | 0.0 |
| elephant_no_redundancy | 6000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_no_redundancy | 6000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_no_redundancy | 6000 | redundancy_ratio | 20 | 0.0 |
| elephant_no_redundancy | 6000 | budget_utilization | 20 | 0.0 |
| elephant_no_redundancy | 6000 | compaction_gain | 20 | -4.9e-05 |
| elephant_no_redundancy | 12000 | task_success | 20 | 0.0 |
| elephant_no_redundancy | 12000 | context_precision | 20 | 0.0 |
| elephant_no_redundancy | 12000 | context_recall | 20 | 0.0 |
| elephant_no_redundancy | 12000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_no_redundancy | 12000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_no_redundancy | 12000 | redundancy_ratio | 20 | 0.0 |
| elephant_no_redundancy | 12000 | budget_utilization | 20 | 0.0 |
| elephant_no_redundancy | 12000 | compaction_gain | 20 | -4.9e-05 |
| elephant_no_redundancy | 18000 | task_success | 20 | 0.0 |
| elephant_no_redundancy | 18000 | context_precision | 20 | 0.0 |
| elephant_no_redundancy | 18000 | context_recall | 20 | 0.0 |
| elephant_no_redundancy | 18000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_no_redundancy | 18000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_no_redundancy | 18000 | redundancy_ratio | 20 | 0.0 |
| elephant_no_redundancy | 18000 | budget_utilization | 20 | 0.0 |
| elephant_no_redundancy | 18000 | compaction_gain | 20 | -4.9e-05 |
| elephant_rule_only | 6000 | task_success | 20 | 0.0 |
| elephant_rule_only | 6000 | context_precision | 20 | 0.0 |
| elephant_rule_only | 6000 | context_recall | 20 | 0.0 |
| elephant_rule_only | 6000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_rule_only | 6000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_rule_only | 6000 | redundancy_ratio | 20 | 0.0 |
| elephant_rule_only | 6000 | budget_utilization | 20 | 0.0 |
| elephant_rule_only | 6000 | compaction_gain | 20 | -2.8e-05 |
| elephant_rule_only | 12000 | task_success | 20 | 0.0 |
| elephant_rule_only | 12000 | context_precision | 20 | 0.0 |
| elephant_rule_only | 12000 | context_recall | 20 | 0.0 |
| elephant_rule_only | 12000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_rule_only | 12000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_rule_only | 12000 | redundancy_ratio | 20 | 0.0 |
| elephant_rule_only | 12000 | budget_utilization | 20 | 0.0 |
| elephant_rule_only | 12000 | compaction_gain | 20 | -2.7e-05 |
| elephant_rule_only | 18000 | task_success | 20 | 0.0 |
| elephant_rule_only | 18000 | context_precision | 20 | 0.0 |
| elephant_rule_only | 18000 | context_recall | 20 | 0.0 |
| elephant_rule_only | 18000 | key_evidence_retention_rate | 20 | 0.0 |
| elephant_rule_only | 18000 | stage_focus_hit_rate | 20 | 0.0 |
| elephant_rule_only | 18000 | redundancy_ratio | 20 | 0.0 |
| elephant_rule_only | 18000 | budget_utilization | 20 | 0.0 |
| elephant_rule_only | 18000 | compaction_gain | 20 | -2.7e-05 |
| multi_agent_default_context | 6000 | task_success | 20 | -0.8 |
| multi_agent_default_context | 6000 | context_precision | 20 | 0.0 |
| multi_agent_default_context | 6000 | context_recall | 20 | -0.1 |
| multi_agent_default_context | 6000 | key_evidence_retention_rate | 20 | -0.2 |
| multi_agent_default_context | 6000 | stage_focus_hit_rate | 20 | -0.2 |
| multi_agent_default_context | 6000 | redundancy_ratio | 20 | 0.083333 |
| multi_agent_default_context | 6000 | budget_utilization | 20 | 0.0 |
| multi_agent_default_context | 6000 | compaction_gain | 20 | -0.007599 |
| multi_agent_default_context | 12000 | task_success | 20 | -0.8 |
| multi_agent_default_context | 12000 | context_precision | 20 | 0.0 |
| multi_agent_default_context | 12000 | context_recall | 20 | -0.1 |
| multi_agent_default_context | 12000 | key_evidence_retention_rate | 20 | -0.2 |
| multi_agent_default_context | 12000 | stage_focus_hit_rate | 20 | -0.2 |
| multi_agent_default_context | 12000 | redundancy_ratio | 20 | 0.083333 |
| multi_agent_default_context | 12000 | budget_utilization | 20 | 0.0 |
| multi_agent_default_context | 12000 | compaction_gain | 20 | -0.007601 |
| multi_agent_default_context | 18000 | task_success | 20 | -0.8 |
| multi_agent_default_context | 18000 | context_precision | 20 | 0.0 |
| multi_agent_default_context | 18000 | context_recall | 20 | -0.1 |
| multi_agent_default_context | 18000 | key_evidence_retention_rate | 20 | -0.2 |
| multi_agent_default_context | 18000 | stage_focus_hit_rate | 20 | -0.2 |
| multi_agent_default_context | 18000 | redundancy_ratio | 20 | 0.083333 |
| multi_agent_default_context | 18000 | budget_utilization | 20 | 0.0 |
| multi_agent_default_context | 18000 | compaction_gain | 20 | -0.007601 |
| single_agent_long_context | 6000 | task_success | 20 | -0.4 |
| single_agent_long_context | 6000 | context_precision | 20 | 0.0 |
| single_agent_long_context | 6000 | context_recall | 20 | -0.1 |
| single_agent_long_context | 6000 | key_evidence_retention_rate | 20 | -0.2 |
| single_agent_long_context | 6000 | stage_focus_hit_rate | 20 | -0.1 |
| single_agent_long_context | 6000 | redundancy_ratio | 20 | -0.25 |
| single_agent_long_context | 6000 | budget_utilization | 20 | 0.0 |
| single_agent_long_context | 6000 | compaction_gain | 20 | -0.015198 |
| single_agent_long_context | 12000 | task_success | 20 | -0.4 |
| single_agent_long_context | 12000 | context_precision | 20 | 0.0 |
| single_agent_long_context | 12000 | context_recall | 20 | -0.1 |
| single_agent_long_context | 12000 | key_evidence_retention_rate | 20 | -0.2 |
| single_agent_long_context | 12000 | stage_focus_hit_rate | 20 | -0.1 |
| single_agent_long_context | 12000 | redundancy_ratio | 20 | -0.25 |
| single_agent_long_context | 12000 | budget_utilization | 20 | 0.0 |
| single_agent_long_context | 12000 | compaction_gain | 20 | -0.015205 |
| single_agent_long_context | 18000 | task_success | 20 | -0.4 |
| single_agent_long_context | 18000 | context_precision | 20 | 0.0 |
| single_agent_long_context | 18000 | context_recall | 20 | -0.1 |
| single_agent_long_context | 18000 | key_evidence_retention_rate | 20 | -0.2 |
| single_agent_long_context | 18000 | stage_focus_hit_rate | 20 | -0.1 |
| single_agent_long_context | 18000 | redundancy_ratio | 20 | -0.25 |
| single_agent_long_context | 18000 | budget_utilization | 20 | 0.0 |
| single_agent_long_context | 18000 | compaction_gain | 20 | -0.015205 |

## Failure Modes

- `multi_agent_default_context` / `rule_preservation_01` / budget `6000`: first observed field `[planner] agent_role=planner`, planned agents `planner,reviewer`.
- `multi_agent_default_context` / `rule_preservation_01` / budget `12000`: first observed field `[planner] agent_role=planner`, planned agents `planner,reviewer`.
- `multi_agent_default_context` / `rule_preservation_01` / budget `18000`: first observed field `[planner] agent_role=planner`, planned agents `planner,reviewer`.
- `single_agent_long_context` / `rule_preservation_01` / budget `6000`: first observed field `agent_role=single_agent`, planned agents `single_agent`.
- `single_agent_long_context` / `rule_preservation_01` / budget `12000`: first observed field `agent_role=single_agent`, planned agents `single_agent`.
- `single_agent_long_context` / `rule_preservation_01` / budget `18000`: first observed field `agent_role=single_agent`, planned agents `single_agent`.
- `elephant_full` / `evidence_competition_01` / budget `6000`: first observed field `[evidence_scout] agent_role=evidence_scout`, planned agents `evidence_scout,reviewer`.
- `elephant_full` / `evidence_competition_01` / budget `12000`: first observed field `[evidence_scout] agent_role=evidence_scout`, planned agents `evidence_scout,reviewer`.


## Lifecycle Suite

# MGCM Lifecycle Benchmark Summary

- Run ID: `lifecycle`
- Completed runs: `105`
- Failed runs: `0`

## Baseline Comparison

| variant | run_count | task_success | mechanism_success | retrieval_success | state_integrity | ordering_success |
| --- | --- | --- | --- | --- | --- | --- |
| mgcm_full | 15 | 0.466667 | 0.466667 | 0.5 | 1.0 | 0.8 |
| mgcm_thread_local_memory | 15 | 0.133333 | 0.133333 | 0.433333 | 0.666667 | 0.8 |

## Ablation Comparison

| variant | run_count | task_success | mechanism_success | retrieval_success | state_integrity | ordering_success |
| --- | --- | --- | --- | --- | --- | --- |
| mgcm_no_collective_governance | 15 | 0.333333 | 0.333333 | 0.433333 | 0.866667 | 0.8 |
| mgcm_no_conflict_resolution | 15 | 0.266667 | 0.266667 | 0.5 | 0.8 | 0.8 |
| mgcm_no_cross_thread | 15 | 0.466667 | 0.466667 | 0.5 | 1.0 | 0.8 |
| mgcm_no_persistent_inheritance | 15 | 0.466667 | 0.466667 | 0.5 | 1.0 | 0.8 |
| mgcm_no_temporal_decay | 15 | 0.466667 | 0.466667 | 0.5 | 1.0 | 0.8 |

## Paired Deltas Versus MGCM Full

| variant | metric | pair_count | mean_delta_vs_mgcm_full |
| --- | --- | --- | --- |
| mgcm_no_collective_governance | task_success | 15 | -0.133333 |
| mgcm_no_collective_governance | mechanism_success | 15 | -0.133333 |
| mgcm_no_collective_governance | retrieval_success | 15 | -0.066667 |
| mgcm_no_collective_governance | state_integrity | 15 | -0.133333 |
| mgcm_no_collective_governance | ordering_success | 15 | 0.0 |
| mgcm_no_conflict_resolution | task_success | 15 | -0.2 |
| mgcm_no_conflict_resolution | mechanism_success | 15 | -0.2 |
| mgcm_no_conflict_resolution | retrieval_success | 15 | 0.0 |
| mgcm_no_conflict_resolution | state_integrity | 15 | -0.2 |
| mgcm_no_conflict_resolution | ordering_success | 15 | 0.0 |
| mgcm_no_cross_thread | task_success | 15 | 0.0 |
| mgcm_no_cross_thread | mechanism_success | 15 | 0.0 |
| mgcm_no_cross_thread | retrieval_success | 15 | 0.0 |
| mgcm_no_cross_thread | state_integrity | 15 | 0.0 |
| mgcm_no_cross_thread | ordering_success | 15 | 0.0 |
| mgcm_no_persistent_inheritance | task_success | 15 | 0.0 |
| mgcm_no_persistent_inheritance | mechanism_success | 15 | 0.0 |
| mgcm_no_persistent_inheritance | retrieval_success | 15 | 0.0 |
| mgcm_no_persistent_inheritance | state_integrity | 15 | 0.0 |
| mgcm_no_persistent_inheritance | ordering_success | 15 | 0.0 |
| mgcm_no_temporal_decay | task_success | 15 | 0.0 |
| mgcm_no_temporal_decay | mechanism_success | 15 | 0.0 |
| mgcm_no_temporal_decay | retrieval_success | 15 | 0.0 |
| mgcm_no_temporal_decay | state_integrity | 15 | 0.0 |
| mgcm_no_temporal_decay | ordering_success | 15 | 0.0 |
| mgcm_thread_local_memory | task_success | 15 | -0.333333 |
| mgcm_thread_local_memory | mechanism_success | 15 | -0.333333 |
| mgcm_thread_local_memory | retrieval_success | 15 | -0.066667 |
| mgcm_thread_local_memory | state_integrity | 15 | -0.333333 |
| mgcm_thread_local_memory | ordering_success | 15 | 0.0 |

## Failure Modes

- `mgcm_full` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_no_persistent_inheritance` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_no_cross_thread` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_no_collective_governance` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_no_conflict_resolution` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_no_temporal_decay` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_thread_local_memory` / `promotion_validation_01`: markers `none`, state_integrity `1.0`.
