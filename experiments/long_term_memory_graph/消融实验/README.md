# 消融实验

该目录对应论文 E4 消融与参数敏感性实验。默认变体包括：

- `full`
- `wo_scene_match`
- `wo_temporal_edges`
- `wo_revision_edges`
- `wo_conflict_suppression`
- `wo_stale_suppression`
- `graph_no_policy`
- `multi_level_topk`
- `scene_weight_0_3`
- `scene_weight_1_2`
- `topk_small`
- `topk_large`

每个变体复用同一 case 集、同一 AgentTorch 被试和同一 judge 字段，避免因数据或预算变化造成伪差异。

```powershell
python -m experiments.long_term_memory_graph ablate --runs 3 --output-dir artifacts/long_term_memory_graph/ablation
```

真实 API 后端示例：

```powershell
python -m experiments.long_term_memory_graph ablate --model-backend openai_http --model qwen-plus --env-file .env --case-limit 1
```
