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
