# Clark's Nutcracker Long-Term Memory Graph Experiments

`experiments.long_term_memory_graph` 是克拉克星鸦启发长时记忆图谱论文的实验包。当前重构后的定位是：保留已有图谱机制层，重建论文实验层，使代码结构直接对应论文中的 E1-E5 协议。

## 目录结构

```text
experiments/long_term_memory_graph/
  api/                # 公共配置、DTO、插件门面
  domain/             # 胶囊构边、召回打分、冲突/陈旧治理、摘要
  storage/            # GraphStore 协议与 Neo4j / InMemory 实现
  integrations/       # AgentTorch bridge 与外部记录回填边界
  core/               # 实验共享层：数据集、方法、AgentTorch 探针、judge、统计、产物
  主模型/             # E1/E3/E5：完整星鸦图谱机制主实验
  研究对比试验/       # E2：强基线对比
  消融实验/           # E4：机制消融与参数敏感性
  tools/              # CLI 入口
  assets/             # Neo4j Browser 等静态资源
```

三类实验入口保持独立，公共逻辑只放在 `core/`，避免把实验矩阵、评测、统计和产物写入堆在一个大脚本里。

## 对应论文协议

- E1 长期记忆问答主实验：Single-hop、Multi-hop、Temporal、Open Domain、Overall。
- E2 强基线对比：默认主对比只跑无长期记忆、向量记忆、平面摘要、朴素图和完整星鸦图谱；proxy 扩展与文献记录单独标注。
- E2 proxy 扩展候选：`rag_chunk_memory`、`graph_rag_memory`、`light_rag_memory`、`hippo_rag2_memory`、`hypergraph_rag_memory`、`openai_memory`、`langmem_memory`、`zep_memory`、`amem_memory`、`mem0_memory`、`mem0_graph_memory`、`mirix_memory`、`memobase_memory`、`memu_memory`、`memos_memory`。
- E3 结构化机制指标：胶囊召回、关系命中、证据完整性、陈旧节点注入、冲突裁决、返回记忆可用性。
- E4 消融与参数敏感性：场景索引、时间边、修正边、冲突抑制、陈旧抑制、图无治理、top-k 和权重扫描。
- E4 固定变体：`full`、`wo_scene_match`、`wo_temporal_edges`、`wo_revision_edges`、`wo_conflict_suppression`、`wo_stale_suppression`、`graph_no_policy`、`multi_level_topk`、`scene_weight_0_3`、`scene_weight_1_2`、`topk_small`、`topk_large`。
- E5 效率与规模：token、相对 token、返回节点/边、召回延迟；Neo4j 大规模正式运行可继续接入该产物格式。

## CLI

默认后端是确定性 AgentTorch 探针，用于验证实验代码、字段和产物，不代表正式论文结果。

```powershell
python -m experiments.long_term_memory_graph main --case-limit 4 --runs 1 --output-dir artifacts/long_term_memory_graph/main
python -m experiments.long_term_memory_graph compare --case-limit 4 --runs 1 --output-dir artifacts/long_term_memory_graph/comparison
python -m experiments.long_term_memory_graph ablate --case-limit 4 --runs 1 --output-dir artifacts/long_term_memory_graph/ablation
python -m experiments.long_term_memory_graph full --case-limit 4 --runs 1 --output-dir artifacts/long_term_memory_graph/full
```

如果要使用真实 AgentTorch API 模型，把 `--model-backend` 切到 `openai` 或 `openai_http`，并通过 `.env` 或当前进程环境提供 API 配置：

```powershell
python -m experiments.long_term_memory_graph main --model-backend openai_http --model qwen-plus --env-file .env --case-limit 1
```

如果要让长时记忆检索也走真实 embedding，把 embedding 相关变量补齐：

```powershell
python -m experiments.long_term_memory_graph main `
  --model-backend openai_http `
  --model qwen-plus `
  --embedding-model text-embedding-3-small `
  --env-file .env `
  --case-limit 1
```

支持的 embedding 环境变量包括：

- `OPENAI_EMBEDDING_API_KEY`
- `OPENAI_EMBEDDING_BASE_URL`
- `OPENAI_EMBEDDING_MODEL`

若未单独提供 `OPENAI_EMBEDDING_API_KEY` 和 `OPENAI_EMBEDDING_BASE_URL`，会回退到共享的 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。

如果要把 proxy 扩展方法也一起本地运行，可显式加：

```powershell
python -m experiments.long_term_memory_graph compare --include-proxy-extension --case-limit 4 --runs 1 --output-dir artifacts/long_term_memory_graph/comparison_proxy
```

也可以先只检查 `.env` 加载链路，不发起模型请求：

```powershell
python -m experiments.long_term_memory_graph check-env --model-backend openai_http --env-file .env
```

如果 judge 单独使用另一套真实凭据，可以检查 judge 侧链路：

```powershell
python -m experiments.long_term_memory_graph check-env --role judge --model-backend openai_http --env-file .env
```

实验包不会把密钥写入产物；`manifest.json` 只记录 `env_loaded`、`env_api_key_present`、`env_base_url_present`、`env_model_present` 这些布尔状态。支持的常用变量名包括：

- `OPENAI_API_KEY`，也兼容 `API_KEY` / `api_key`
- `OPENAI_BASE_URL`，也兼容 `BASE_URL` / `base_url`
- `OPENAI_MODEL`，也兼容 `MODEL_NAME` / `model_name`

如果正式评测希望主模型和 judge 使用不同账号或不同网关，可额外提供：

- `JUDGE_OPENAI_API_KEY`
- `JUDGE_OPENAI_BASE_URL`
- `JUDGE_OPENAI_MODEL`

若未提供 `JUDGE_*`，judge 会回退到共享的 `OPENAI_*`。

正式运行时可传入外部 LoCoMo-style 数据：

```powershell
python -m experiments.long_term_memory_graph compare --dataset-path path\to\cases.jsonl --runs 3
```

`cases.jsonl` 每行包含 `case_id`、`question_type`、`query`、`standard_answer`、`capsules`、`target_capsule_ids`，以及可选的 `target_relation_types`、`stale_capsule_ids`、`conflict_loser_ids`、`knowledge_scope`、`tags`、`entities`。

## 真实 Benchmark 跑法

真实 benchmark 建议至少使用 `--runs 3`，并显式传入 `--model` 与 `--judge-model`，避免不同环境变量别名造成歧义。

```powershell
python -m experiments.long_term_memory_graph compare `
  --env-file .env `
  --model-backend openai_http `
  --model qwen-plus `
  --judge-backend model_judge `
  --judge-model-backend openai_http `
  --judge-model qwen-plus `
  --runs 3 `
  --output-dir artifacts/long_term_memory_graph/compare_real
```

当 case 很多时，可以直接按分片跑：

```powershell
python -m experiments.long_term_memory_graph compare `
  --env-file .env `
  --model-backend openai_http `
  --model qwen-plus `
  --judge-backend model_judge `
  --judge-model-backend openai_http `
  --judge-model qwen-plus `
  --runs 3 `
  --shard-id 0 `
  --num-shards 4 `
  --output-dir artifacts/long_term_memory_graph/compare_real_shard0
```

如果一次运行中断，可以在同一输出目录续跑：

```powershell
python -m experiments.long_term_memory_graph compare `
  --env-file .env `
  --model-backend openai_http `
  --model qwen-plus `
  --judge-backend model_judge `
  --judge-model-backend openai_http `
  --judge-model qwen-plus `
  --runs 3 `
  --resume `
  --output-dir artifacts/long_term_memory_graph/compare_real
```

也可以直接使用批量脚本：

```powershell
powershell -ExecutionPolicy Bypass -File experiments/long_term_memory_graph/tools/run_real_benchmarks.ps1 `
  -Suite compare `
  -EnvFile .env `
  -ModelBackend openai_http `
  -Model qwen-plus `
  -Runs 3 `
  -Resume
```

如果要在批量脚本里同时跑 proxy 扩展，可加 `-EnableProxyExtension`。

## 统一产物

每组实验都会输出：

- `runs.csv`：逐 case 明细，包含论文要求的字段。
- `runs.jsonl`：逐 case 原始记录，便于追溯。
- `report.json`：聚合结果和原始记录。
- `summary.md`：人工阅读摘要。
- `tables.tex`：可进入论文的 LaTeX 表格草稿。
- `mechanism_metrics.tex`：E3 结构化机制指标表。
- `judge_prompt.md`：judge prompt 固定版本。
- `bootstrap_summary.json`：bootstrap 95% CI 汇总。
- `manual_review_sample.jsonl`：人工复核抽样输入。
- `second_judge_inputs.jsonl`：第二 judge 一致性检查输入。
- `parameter_sweep.json`：E4 参数扫描配置与导出结果。
- `efficiency_report.json`：E5 token-accuracy、返回规模和分步延迟摘要。
- `scale_tiers.json`：E5 小/中/大三档规模基准。
- `manifest.json`：命令、后端、数据集和产物路径。

其中 `comparison` 与 `ablation` 的 `summary.md` 现在会额外展示方法矩阵、proxy 扩展可选集、文献参考方法集合、固定消融变体及参数扫描设计，避免实验设计只藏在代码和 manifest 里。

`manifest.json` 还会记录 `record_count`、`aggregate_count`、`token_reference_method` 和 env 检查布尔值，便于确认本次运行是否真的产生了逐 case 记录。`--runs` 和 `--case-limit` 必须大于 0；对比方法名和消融变体名会在运行前校验，避免把空实验或拼写错误的消融写成有效产物。

`runs.csv` 至少包含：

- `case_id`
- `question_type`
- `method`
- `answer`
- `standard_answer`
- `judge_score`
- `judge_raw_output`
- `target_capsule_hit`
- `target_relation_hit`
- `input_tokens`
- `output_tokens`
- `returned_node_count`
- `returned_edge_count`
- `latency_ms`
- `run_round`

其中主实验会额外记录 `capsule_recall_at_k`、`revision_hit_rate`、`detail_lookup_latency_ms`、`latency_breakdown_json`、`source_boundary` 和 `is_proxy`，便于把 E1/E3/E5 的分析直接回填到论文。

## 当前边界

当前代码已经把实验安装、方法矩阵、对比实验、消融实验和产物格式整理为可运行结构；但默认 `deterministic_probe` 只用于工程验证。正式投稿前必须替换为真实模型、真实 judge、三次独立运行、人工复核或双 judge 一致性检查，并从生成的 CSV/JSONL 回填论文数值。

## 环境约束

- 不读取 `.env` 文件。
- Codex 执行过程中不打开或打印 `.env` 内容；真实 API 运行时由实验代码按 `--env-file` 加载。
- 基础 smoke test 使用 `InMemoryGraphStore`，不要求 Neo4j 密码。
- Neo4j 仍保留在 `storage/neo4j.py`，用于后续正式规模实验。
- 推荐使用 `data_analysis_py311` 或其他 Python 3.11 环境运行。
