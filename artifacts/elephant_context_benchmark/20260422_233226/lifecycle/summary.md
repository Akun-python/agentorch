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
