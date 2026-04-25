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
