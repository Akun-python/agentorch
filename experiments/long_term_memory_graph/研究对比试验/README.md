# 研究对比试验

该目录对应论文 E2 强基线对比实验。实验结构参考 `参考文献/长期记忆对比参考文献.pdf` 的 HyperMem 主实验：LoCoMo-style 四类问题、RAG 与 memory system 两组强基线、LLM-as-a-judge accuracy、3 次独立运行均值，以及以 Mem0 为 1.0x 基准的 token-efficiency 对比。所有方法都通过 AgentTorch 统一承载答案生成、线程追踪、token 统计和产物落盘。

当前对比模型的真实实现代码集中放在：

- `研究对比试验/对比模型/`

其中：

- `mem0_official.py`：Mem0 官方 SDK adapter
- `langmem_official.py`：LangMem 官方 adapter
- `zep_official.py`：Zep 官方 SDK adapter
- `registry.py`：对比模型统一注册入口
- `base.py`：官方 adapter 公共结果封装

`long_term_memory_graph/baselines/` 只保留旧导入路径兼容层，不再作为真实实现目录继续扩展。

默认主对比矩阵为：

- `no_long_term_memory`
- `vector_memory`
- `flat_summary_memory`
- `naive_graph_memory`
- `clarks_nutcracker_graph`

当前已接入官方 adapter 的方法为 `mem0_memory`、`langmem_memory`、`zep_memory`。它们不会默认进入主结论表，需要显式加入；其余 proxy 扩展方法仍保留在协议层与代码层，但不会默认进入主结论表。文献记录层仅导出参考元数据，不参与本地聚合。

输出字段对齐论文要求：Single-hop、Multi-hop、Temporal、Open Domain、Overall、LLM-as-a-judge accuracy、Avg Tokens、Relative Tokens、Token Efficiency，以及逐 case 的 judge 原始输出。默认主对比相对 token 基线为 `no_long_term_memory`。

当前未接入官方实现的方法以 AgentTorch 受控 proxy adapter 表示，目的是先跑通同构实验协议和产物格式。正式投稿结果必须替换为官方实现、复现实验脚本，或在论文中明确标注为 proxy。

只加入官方 baseline 的示例：

```powershell
python -m experiments.long_term_memory_graph compare --include-official-baselines --runs 3 --output-dir artifacts/long_term_memory_graph/comparison_official
```

对应 baseline 参考文献已经整理到 `参考文献/长期记忆基线对比参考文献/`。其中 `baseline_reference_manifest.json` 记录每个 baseline 对应的论文或官方资料，`baseline_reference_summary.csv` 便于回填论文参考文献表。由于仓库规则忽略 `参考文献/`，实验 manifest 还会写入轻量级 `reference_catalog`，即使不提交 PDF，也能追溯每个 baseline 的标题、本地目标文件和来源 URL。

```powershell
python -m experiments.long_term_memory_graph compare --runs 3 --output-dir artifacts/long_term_memory_graph/comparison
```

真实 API 后端示例：

```powershell
python -m experiments.long_term_memory_graph compare --model-backend openai_http --model qwen-plus --env-file .env --case-limit 1
```
