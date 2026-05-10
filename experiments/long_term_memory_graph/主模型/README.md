# 主模型实验

该目录对应论文实验协议中的 E1、E3 和 E5：

- E1：长期记忆问答主实验，覆盖 Single-hop、Multi-hop、Temporal、Open Domain。
- E3：结构化机制指标，记录胶囊命中、关系命中、陈旧节点注入、冲突裁决和返回记忆可用性。
- E5：效率与规模的基础字段，记录 token、返回节点/边和召回延迟。

默认运行确定性 AgentTorch 探针，只验证实验管线和产物格式；正式投稿数值需要替换真实数据集、真实模型和真实 judge。

```powershell
python -m experiments.long_term_memory_graph main --runs 3 --output-dir artifacts/long_term_memory_graph/main
```

真实 API 后端示例：

```powershell
python -m experiments.long_term_memory_graph main --model-backend openai_http --model qwen-plus --env-file .env --case-limit 1
```
