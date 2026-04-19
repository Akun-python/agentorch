# 克拉克星鸦长时记忆图谱章节实验计划表

本文档服务于第二章/第四章“小论文级”实验补强，目标不是简单增加实验数量，而是让每个核心主张都有对应证据，并且证据边界与论文表述一致。

## 最新进展

截至 2026-04-19，已经补齐的实验工具包括：

- `benchmark-baselines`
- `benchmark-baseline-stability`
- `benchmark-latency`
- `benchmark-graph-scale-latency`

其中，`benchmark-baseline-stability` 已支持：

- 多 seed 复现
- mean / std
- bootstrap 95% CI

当前状态判断：

- 工程模块设计：合格
- 离线 baseline 与稳定性实验：可直接运行
- Neo4j 图规模正式实验：工具已完成，真实环境结果仍取决于本机 Neo4j 认证是否可用
- 论文章节证据链：仍需补即插即用接入案例、专项场景实验、失败模式分析与正文表格产物

详细审计结论见：

- `experiments/long_term_memory_graph/EXPERIMENT_DESIGN_AUDIT.md`

## 当前状态

已完成的高价值证据：

- 已有 Neo4j 本地工程效率测试。
- 已有模块级强基线 benchmark：
  - `no_long_term_memory`
  - `vector_memory`
  - `flat_summary_memory`
  - `naive_graph_memory`
  - `clarks_nutcracker_graph`
- 已有统一指标：
  - `capsule_recall@k`
  - `subgraph_relevance`
  - `relation_hit_rate`
  - `returned_memory_usefulness`
  - `stale_node_injection_rate`
  - `conflict_resolution_success`
- 已有当前结论边界：
  - 图谱机制在关系命中、陈旧抑制、冲突消解上优于 `vector_memory` 和 `naive_graph_memory`
  - `flat_summary_memory` 仍是强基线，在首屏 recall / relevance / usefulness 上更强

当前最缺的不是“能不能跑”，而是“实验是否足以支撑章节论文结论”。

## 实验主张与证据映射

| 论文章节主张 | 最低证据要求 | 当前状态 |
| --- | --- | --- |
| 该机制是独立可插拔长期记忆模块 | 至少 2 种不同智能体接入样例 + 标准接口流程 | 未闭合 |
| 该机制优于弱基线 | 强基线 benchmark，统一预算与统一指标 | 已完成基础版 |
| 该机制在结构化子图返回上优于朴素记忆 | 关系命中、冲突消解、陈旧抑制实验 | 已有方向性证据 |
| 该机制可在图数据库上稳定运行 | Neo4j 写入、回查、扩图、详情查询延迟 | 已完成基础版 |
| 该机制不是特例结果 | 多 seed / 多规模 / 多场景稳定性 | 未闭合 |
| 该机制的结论边界清楚 | 失败模式与负面发现分析 | 部分完成 |

## 必须做

这些实验不补，章节会停留在“模块演示”而不是“小论文”。

| 优先级 | 实验项 | 目的 | 最低设计 | 核心输出 | 完成标准 |
| --- | --- | --- | --- | --- | --- |
| P0 | 多 seed 强基线复现实验 | 证明当前结果不是单次偶然 | 同一 benchmark 至少 `3-5` 个 seed；统一首屏预算；保留 5 条 baseline | 聚合表、均值、标准差或 bootstrap CI | 每个核心指标都能给出稳定区间 |
| P0 | 可插拔接入实验 | 证明模块不是绑死单一 runtime | 至少 2 类智能体接入方式；都覆盖 `pre-run recall`、`post-run store`、`detail lookup` | 接入图、流程图、最小案例表 | 无需改 `agentorch` 核心即可接入两个不同封装 |
| P0 | 图规模扩展实验 | 证明 Neo4j 图结构存储在规模增长下仍可用 | 至少 3 档图规模，例如 `10^2 / 5*10^2 / 10^3+` 节点 | latency 曲线、节点/边规模表 | `recall()` 和详情回查延迟随规模变化可解释 |
| P0 | 失败模式案例分析 | 让“为什么还没全面优于强基线”讲清楚 | 选 3 类失败：首屏排序偏差、SAME_TASK 扩展污染、平面摘要压制图谱 | 案例表、检索子图截图、定性分析 | 论文能诚实解释当前弱点来源 |
| P0 | 冲突/修正/陈旧专门场景 | 把图谱优势做成闭环证据 | 人工控制至少 3 类场景：`REVISES`、`CONFLICTS_WITH`、stale suppression | 指标表 + 案例图 | 图谱机制在这三类场景中稳定优于非图谱基线 |
| P0 | 论文级结果表整理 | 把结果转成能直接进正文的表图资产 | 输出正式 CSV、LaTeX 表格、图注文案 | `paper_tables` / 章节表格 / 图注 | 结果能直接进章节，无需二次手工拼接 |

## 建议做

这些实验会明显提高说服力，尤其是如果你想把本章单独投会议。

| 优先级 | 实验项 | 目的 | 最低设计 | 预期价值 |
| --- | --- | --- | --- | --- |
| P1 | 检索链路消融 | 分清收益来自哪里 | 比较 `vector only`、`fulltext only`、`hybrid no rerank`、`hybrid no conflict suppression`、`full pipeline` | 证明不是“图数据库”四个字带来的伪收益 |
| P1 | 构边类型消融 | 检验六类边是否都必要 | 去掉 `TEMPORAL_NEXT`、`REVISES`、`CONFLICTS_WITH` 等单类边重跑 | 证明哪些边真有贡献，哪些只是装饰 |
| P1 | embedding / scene match 敏感性 | 检验当前首屏排序是否可进一步优化 | 调 `embedding_dimensions`、`scene_match_weight`、`reuse_weight` 等 | 直接服务于超过 `flat_summary_memory` 的下一轮优化 |
| P1 | backfill 可用性实验 | 证明旧记录能迁移进图谱 | 从 `records.db` 回填后再做 recall | 强化“历史实验资产可继承” |
| P1 | 子图摘要首屏质量分析 | 评估渐进式披露是否真的有用 | 对比只给节点列表 vs 给子图摘要 | 支撑“可注入提示”的设计合理性 |

## 可选做

这些实验不是当前章节闭环的最低要求，但会增强完整度。

| 优先级 | 实验项 | 目的 | 适用场景 |
| --- | --- | --- | --- |
| P2 | 人工标注子图相关性 | 让 `subgraph_relevance` 更接近人工判断 | 打算冲更强审稿口径时 |
| P2 | 不同领域场景迁移 | 检查场景泛化 | 如果想强化跨任务族泛化 |
| P2 | Browser 可视化样例附录 | 展示 Neo4j 图谱直观性 | 答辩展示、附录材料 |
| P2 | 在线持续写入鲁棒性测试 | 检查长期运行下 graph drift | 如果后续要做系统运行章融合 |

## 具体执行顺序

### 第一阶段：先把章节最小闭环补齐

1. 跑 `3-5` seed 的模块级强基线 benchmark。
2. 补两个可插拔 agent 接入样例。
3. 补图规模扩展实验。
4. 补三类失败模式案例。

这一阶段完成后，你的章节就能形成：

- 基线充分
- 工程可用
- 失败边界清楚

### 第二阶段：再冲“为什么有效”

1. 做检索链路消融。
2. 做构边类型消融。
3. 做冲突/修正/陈旧专门场景。

这一阶段完成后，你就不只是“有结果”，而是“能解释结果来自哪一段机制”。

### 第三阶段：再冲“小论文投稿强度”

1. 做参数敏感性。
2. 补人工标注或更多场景泛化。
3. 整理正式图表、附录案例和开源接口说明。

## 推荐的章节实验结构

建议把第二章/第四章实验节固定成下面 6 小节：

1. 实验目标与研究问题
2. 模块实现与实验设置
3. 强基线比较
4. 消融实验
5. 工程效率与可插拔接入实验
6. 失败模式与讨论

这样结构最稳，因为它直接对应：

- 是否有效
- 为什么有效
- 是否可部署
- 哪些地方还不够强

## 你这章当前最该补的 5 项

如果只看“投入产出比”，优先补下面这 5 项：

1. `3-5` seed 的 baseline benchmark 稳定性统计。
2. 两种智能体接入样例。
3. 图规模扩展 latency 曲线。
4. `REVISES / CONFLICTS_WITH / stale suppression` 三类专门场景。
5. 一组失败模式案例分析，解释为什么 `flat_summary_memory` 还更强。

## 当前最安全的论文结论口径

在这些实验补完之前，章节结论建议坚持以下写法：

- 当前图谱机制已经表现出结构化关系返回、陈旧抑制与冲突消解优势。
- 当前图谱机制相对 `vector_memory` 和 `naive_graph_memory` 更稳健。
- 当前图谱机制尚未在首屏 recall / relevance / usefulness 上全面超过 `flat_summary_memory`。
- 因此，本章当前更适合主张“结构化长期记忆图谱是有前景且可部署的机制”，而不是“已经全面优于所有强基线的成熟方案”。

## 对应产物清单

建议最终至少沉淀这些文件资产：

- `baseline_benchmark_report.json`
- `baseline_benchmark_aggregates.csv`
- `baseline_benchmark_case_rows.csv`
- `seed_stability_report.csv`
- `graph_scale_latency_report.csv`
- `integration_cases.md`
- `failure_mode_cases.md`
- `paper_tables.tex` 或章节专用 LaTeX 表格文件

## 一句话判断

如果目标是“硕士论文章节合格”，最小闭环是：

- 强基线
- 稳定性
- 接入实验
- 工程效率
- 失败模式

如果目标是“独立小论文冲更强 venue”，还必须再加：

- 消融
- 更正式统计
- 更强泛化或人工评审证据
