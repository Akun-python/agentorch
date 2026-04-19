# Long-Term Memory Graph

`experiments.long_term_memory_graph` 是一个面向论文与实验的 Neo4j 长时记忆图谱模块。它保持独立实验包定位，不并入 `agentorch` 核心默认路径，但通过稳定根包入口对外暴露可插拔长期记忆能力。

## Architecture

```text
experiments/long_term_memory_graph/
  api/            # 公共配置、DTO、插件门面
  domain/         # claims 规范化、构边、打分、摘要、服务编排
  storage/        # GraphStore 协议与 Neo4j / InMemory 实现
  integrations/   # Agent 适配器、AgentOrch bridge、SQLite backfill
  tools/          # demo seed、benchmark、CLI
  assets/         # Browser Cypher 样例与静态资源
```

## Stable Public API

根包 `experiments.long_term_memory_graph` 只导出以下稳定符号：

- `LongTermMemoryGraphPlugin`
- `GraphMemoryConfig`
- `MemoryCapsuleCandidate`
- `RecallRequest`
- `RecallResponse`
- `CapsuleDetailResponse`
- `BackfillReport`
- `LongTermMemoryAdapter`
- `AgentOrchBridge`

深层导入路径不视为长期稳定接口。

## Runtime Responsibilities

- `LongTermMemoryGraphPlugin` 是薄门面，只保留：
  - `store_capsules`
  - `recall`
  - `fetch_capsule_details`
  - `backfill_from_sqlite`
- 具体流程分别委托给：
  - `CapsuleIngestionService`
  - `RecallService`
  - `DetailQueryService`
  - `SQLiteBackfillImporter`
- 存储边界通过 `storage.base.GraphStore` 协议约束，Neo4j 实现位于 `storage.neo4j.Neo4jGraphStore`。

## Neo4j Requirements

- Python 驱动：官方 `neo4j` 包，作为可选依赖安装
- 数据库版本：Neo4j 5.x
- 节点标签：`:MemoryCapsule`
- 默认召回：向量索引 + 全文索引混合召回
- 默认规模：top-6 候选、top-3 种子、1-hop 扩展、最多 12 节点 / 24 边

## CLI

```powershell
python -m experiments.long_term_memory_graph seed-demo --password 123456
python -m experiments.long_term_memory_graph benchmark-latency --password 123456
python -m experiments.long_term_memory_graph benchmark-baselines
python -m experiments.long_term_memory_graph benchmark-baseline-stability --seeds 5
python -m experiments.long_term_memory_graph benchmark-graph-scale-latency --password 123456 --scale-factors 1,2,4,8
python -m experiments.long_term_memory_graph backfill-sqlite .\records.db --password 123456
```

说明：

- CLI 只读取当前 shell 环境变量，不直接读取 `.env` 文件。
- `seed-demo` / `benchmark-latency` 默认写入 `artifacts/long_term_memory_graph_demo/`。
- `benchmark-baselines` 默认写入 `artifacts/long_term_memory_graph_benchmark/`。
- `benchmark-baseline-stability` 默认写入 `artifacts/long_term_memory_graph_stability/`。
- `benchmark-graph-scale-latency` 默认写入 `artifacts/long_term_memory_graph_scale_latency/`。

## Experiment Tooling

### 1. Baseline benchmark

`benchmark-baselines` 在离线 `InMemoryGraphStore` 上比较以下五类 baseline：

- `no_long_term_memory`
- `vector_memory`
- `flat_summary_memory`
- `naive_graph_memory`
- `clarks_nutcracker_graph`

默认输出：

- `baseline_benchmark_report.json`
- `baseline_benchmark_report.md`
- `baseline_benchmark_aggregates.csv`
- `baseline_benchmark_case_rows.csv`

### 2. Baseline stability benchmark

`benchmark-baseline-stability` 会对同一 benchmark 进行多 seed 复现，利用确定性 `embedding_salt` 生成稳定但不同的检索向量分布，输出跨 seed 聚合统计。

当前统计输出包括：

- mean
- std
- bootstrap 95% CI

默认输出：

- `baseline_stability_report.json`
- `baseline_stability_report.md`
- `baseline_stability_seed_rows.csv`
- `baseline_stability_aggregates.csv`

### 3. Graph-scale latency benchmark

`benchmark-graph-scale-latency` 会在 Neo4j 中自动按 `scale_multiplier` 扩展 demo 图谱规模，逐档执行：

1. `seed-demo`
2. `benchmark-latency`
3. 汇总各档图规模下的节点数、边数、召回时延和详情回查时延

默认输出：

- `graph_scale_latency_report.json`
- `graph_scale_latency_report.md`
- `graph_scale_latency_rows.csv`

### 4. Demo controls

`tools/demo_fixtures.py` 当前支持两个关键实验控制项：

- `embedding_salt`
  - 用于多 seed 稳定性实验中的确定性 embedding 扰动
- `scale_multiplier`
  - 用于图规模扩展实验，按 cohort 扩展场景副本数量

## Readiness Status

从工程模块角度看，当前设计已经满足“合格实验模块”的要求：

- 公共 API 收口明确
- 运行时逻辑、存储逻辑、集成逻辑、工具脚本已分层
- 离线 benchmark、稳定性 benchmark、图规模 benchmark 工具已具备
- pytest 对模型、规则、召回、CLI、benchmark 具备覆盖

从论文章节角度看，当前仍有几项证据需要补齐后才算“完整合格”：

- 两类不同智能体封装方式的即插即用接入案例
- `REVISES / CONFLICTS_WITH / stale suppression` 的专门场景实验
- 失败模式案例分析
- 真实 Neo4j 环境下的图规模 benchmark 正式结果
- 可直接进正文的 LaTeX 表格产物

更详细的合规性与说服力审计见：

- `experiments/long_term_memory_graph/EXPERIMENT_DESIGN_AUDIT.md`

## Demo Assets

- Demo seed 与 benchmark 共用 fixture：`tools/demo_fixtures.py`
- Neo4j Browser Cypher 样例：`assets/demo_browser_queries.cypher`
- 运行时可通过 `experiments.long_term_memory_graph.assets.read_demo_browser_queries()` 读取

## Optional Install

```powershell
pip install -e .[neo4j]
```
