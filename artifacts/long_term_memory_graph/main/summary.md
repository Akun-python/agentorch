# Long-Term Memory Graph Experiment: main

- Run ID: `20260509_131550`
- Model backend: `agentorch_probe`
- Judge backend: `deterministic_probe`
- Runs: `1`
- Case count: `4`
- Token reference: `suite_mean`
- Bootstrap samples: `300`

## Main Results

| Method | Variant | Type | Acc. | 95% CI | Capsule Recall@k | Relation Hit | Evidence | Rel. Tok. | Latency (ms) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clarks_nutcracker_graph` | `full` | Overall | 75.00 | [25.00, 100.00] | 1.00 | 0.75 | 1.00 | 1.00 | 6.55 |

## Evidence Boundary

当前默认后端是确定性 AgentTorch 探针，用于验证实验管线、字段、产物和统计口径。
正式论文数值必须改用真实模型和真实 judge 运行后，从本目录 CSV/JSONL 产物回填。
