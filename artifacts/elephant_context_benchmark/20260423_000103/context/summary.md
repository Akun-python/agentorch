# Elephant Context Benchmark Summary

- Run ID: `context`
- Completed runs: `5`
- Failed runs: `0`

## Baseline Comparison

| variant | budget | run_count | task_success | context_recall | key_evidence_retention_rate | stage_focus_hit_rate | budget_utilization |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elephant_full | 12000 | 5 | 0.8 | 0.666667 | 0.7 | 0.6 | 1.0 |

## Ablation Comparison

_No rows generated._

## Paired Deltas Versus Elephant Full

_No rows generated._

## Failure Modes

- `elephant_full` / `evidence_competition_01` / budget `12000`: first observed field `[evidence_scout] agent_role=evidence_scout`, planned agents `evidence_scout,reviewer`.
