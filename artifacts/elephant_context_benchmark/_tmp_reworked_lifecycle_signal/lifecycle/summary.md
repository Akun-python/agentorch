# MGCM Lifecycle Benchmark Summary

- Run ID: `lifecycle`
- Completed runs: `6`
- Failed runs: `0`

## Baseline Comparison

| variant | run_count | task_success | mechanism_success | retrieval_success | state_integrity | ordering_success |
| --- | --- | --- | --- | --- | --- | --- |
| mgcm_full | 2 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

## Ablation Comparison

| variant | run_count | task_success | mechanism_success | retrieval_success | state_integrity | ordering_success |
| --- | --- | --- | --- | --- | --- | --- |
| mgcm_no_cross_thread | 2 | 0.5 | 0.5 | 0.5 | 1.0 | 1.0 |
| mgcm_no_temporal_decay | 2 | 0.5 | 0.5 | 1.0 | 1.0 | 0.5 |

## Paired Deltas Versus MGCM Full

| variant | metric | pair_count | mean_delta_vs_mgcm_full |
| --- | --- | --- | --- |
| mgcm_no_cross_thread | task_success | 2 | -0.5 |
| mgcm_no_cross_thread | mechanism_success | 2 | -0.5 |
| mgcm_no_cross_thread | retrieval_success | 2 | -0.5 |
| mgcm_no_cross_thread | state_integrity | 2 | 0.0 |
| mgcm_no_cross_thread | ordering_success | 2 | 0.0 |
| mgcm_no_temporal_decay | task_success | 2 | -0.5 |
| mgcm_no_temporal_decay | mechanism_success | 2 | -0.5 |
| mgcm_no_temporal_decay | retrieval_success | 2 | 0.0 |
| mgcm_no_temporal_decay | state_integrity | 2 | 0.0 |
| mgcm_no_temporal_decay | ordering_success | 2 | -0.5 |

## Failure Modes

- `mgcm_no_cross_thread` / `cross_thread_01`: markers `none`, state_integrity `1.0`.
- `mgcm_no_temporal_decay` / `temporal_decay_01`: markers `RECENT_PRIORITY_01`, state_integrity `1.0`.
