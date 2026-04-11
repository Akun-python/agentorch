# 部署_观测_日志_Tracing

## 1. 文档定位


- 一个 Agent / LLM 系统上线后，如何被稳定地观察、定位、追踪、计量成本。

如果只记一句话，就是：

- 部署是前提，观测才是让系统可运营的关键。

这份文档主要回答 6 个问题：

- 这次请求经过了哪些节点与工具
- 用了哪个模型，调用了几次
- 哪一步最慢，哪一步失败
- 这次请求到底消耗了多少 token
- 这些 token 和成本是被哪个用户 / 工作流 / 版本吃掉的
- 什么时候需要立刻告警，而不是等用户反馈

## 2. 先收紧范围

原来“部署、日志、Tracing、告警”放在一起时容易写宽。为了让这份文档更聚焦，这里只保留部署侧的最小要求，其余篇幅全部留给观测。

部署侧最小要求只有这些：

- 区分 `local`、`staging`、`production`
- 服务有明确版本号或构建号
- 服务有 `/health` 和 `/ready`
- 配置与密钥通过环境变量管理
- 每次请求都生成并透传唯一标识
- tracing、结构化日志、指标上报至少接通两项，生产环境建议三项全接

如果这些都还没有，就先不要谈复杂观测，因为链路都还串不起来。

## 3. 观测的最小标识体系

一个 Agent 请求会跨越接口层、编排层、模型调用、工具调用、状态存储。没有统一 ID，后面所有日志、trace、token 统计都会碎掉。

至少统一这些标识：

- `request_id`：一次外部请求的唯一编号
- `trace_id`：整条执行链路编号
- `span_id`：trace 内单步执行编号
- `thread_id`：对话线程编号
- `run_id`：一次 agent run 编号
- `user_id`：调用方或业务主体
- `session_id`：客户端会话编号
- `workflow_name`：工作流名称
- `workflow_version`：工作流版本
- `provider`：模型供应商，如 OpenAI、Anthropic
- `model`：具体模型名
- `env`：环境
- `release`：服务版本或发布批次

最重要的原则：

- 同一次请求里的日志、trace、token 统计、成本统计，必须能用 `request_id` 或 `trace_id` 串起来。

## 4. 日志设计

### 4.1 结构化日志是底线

不要只写“开始调用模型”“工具执行成功”这类自然语言日志。生产环境里，日志首先是给检索、聚合、告警系统消费的。

推荐基础字段：

- `timestamp`
- `level`
- `service`
- `env`
- `release`
- `request_id`
- `trace_id`
- `span_id`
- `thread_id`
- `run_id`
- `user_id`
- `event`
- `status`
- `duration_ms`
- `error_type`
- `error_message`

### 4.2 Agent / LLM 相关日志要单独补字段

对于模型调用和工具调用，基础字段还不够。建议额外记录：

- `provider`
- `model`
- `workflow_name`
- `workflow_version`
- `node_name`
- `tool_name`
- `attempt`
- `retry_count`
- `prompt_template`
- `response_format`

如果是模型调用完成事件，还要直接写入 token 与成本相关字段：

- `prompt_tokens`
- `completion_tokens`
- `reasoning_tokens`
- `cache_read_tokens`
- `cache_write_tokens`
- `total_tokens`
- `cost_input_usd`
- `cost_output_usd`
- `cost_total_usd`

### 4.3 推荐日志分类

- 接入日志：请求进入、请求返回、HTTP 状态码、总耗时
- 执行日志：节点执行、模型调用、工具调用、checkpoint 写入
- 安全日志：人工审批、权限拒绝、高风险工具调用
- 业务日志：订单创建、通知发送、知识库更新等业务动作

### 4.4 一条推荐的模型调用日志

```json
{
  "timestamp": "2026-04-07T10:15:32.221Z",
  "level": "INFO",
  "service": "agent-api",
  "env": "production",
  "release": "2026.04.07-1",
  "request_id": "req_9d2b",
  "trace_id": "tr_6fa1",
  "span_id": "sp_llm_02",
  "thread_id": "thread_001",
  "run_id": "run_7842",
  "user_id": "user_123",
  "event": "llm_call_completed",
  "status": "ok",
  "workflow_name": "customer_support",
  "workflow_version": "v12",
  "node_name": "draft_answer",
  "provider": "openai",
  "model": "gpt-5.4",
  "attempt": 1,
  "duration_ms": 1842,
  "prompt_tokens": 3210,
  "completion_tokens": 642,
  "reasoning_tokens": 380,
  "cache_read_tokens": 0,
  "cache_write_tokens": 0,
  "total_tokens": 4232,
  "cost_input_usd": 0.0123,
  "cost_output_usd": 0.0087,
  "cost_total_usd": 0.0210
}
```

### 4.5 敏感信息处理

禁止明文进入日志：

- API key
- 密码
- access token / refresh token
- 完整手机号、身份证号、银行卡号
- 原始用户隐私文本
- 完整 prompt 模板中的密钥或内部策略

可以做的不是“不记”，而是“脱敏后记”：

- 用户输入保留摘要，不保留全文
- prompt 保留模板名和版本，不直接落盘最终拼接全文
- 工具参数保留结构，不保留敏感值

## 5. Tracing 设计

日志回答“发生了什么”，Tracing 回答“它是怎么一步步发生的”。

一条完整 trace 至少应包含这些 span：

- `request_received`
- `context_loaded`
- `prompt_compiled`
- `llm_call`
- `tool_call`
- `state_persisted`
- `human_review`
- `response_returned`

### 5.1 trace 里至少要回答的问题

- 这次请求一共调了几次模型
- 每次模型调用分别用了什么模型
- 哪个节点触发了工具调用
- 哪个工具最慢
- 哪一步失败并触发了重试
- 是否发生了人工审批
- 最终输出之前是否写入了状态或记忆
- 整条链路总耗时是多少

### 5.2 LangSmith 很适合做 Agent tracing

如果项目基于 LangChain / LangGraph / Deep Agents，LangSmith 通常是最顺手的方案。

最常见配置：

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=agent-prod
```

建议 `project` 至少按环境拆开：

- `agent-local`
- `agent-staging`
- `agent-prod`

### 5.3 trace 与日志必须互相跳转

最理想状态不是“日志里有日志，trace 里有 trace”，而是：

- 在日志平台里按 `request_id` 能跳到 trace
- 在 tracing 平台里能看到对应的服务日志
- 在成本仪表盘里能回溯到对应的请求与版本

这一步对排查“为什么 token 突然翻倍”尤其重要。

## 6. 指标设计

指标不要只看服务层，还要覆盖模型层和编排层。

至少分成 4 组：

- 服务指标：QPS、成功率、错误率、P50/P95/P99 延迟
- 编排指标：节点执行次数、重试次数、中断恢复次数、审批次数
- 模型指标：模型调用次数、token 消耗、限流次数、provider 错误率
- 工具指标：工具成功率、工具耗时、外部依赖错误率

推荐重点指标：

- `requests_total`
- `requests_failed_total`
- `request_duration_ms`
- `agent_runs_total`
- `node_executions_total`
- `llm_calls_total`
- `tool_calls_total`
- `tool_call_failures_total`
- `approval_pending_total`
- `interrupt_resume_total`

如果是 Agent 项目，下面这类指标通常比纯 HTTP 指标更有价值：

- 单次请求平均模型调用次数
- 单次请求平均工具调用次数
- 单次请求平均重试次数
- 单次请求平均 token 消耗
- 成功请求与失败请求的 token 差异

## 7. Token 统计专项

这是原文最需要补强的部分。

很多团队只记录“总 token”，但对 Agent 系统来说这远远不够。因为一次用户请求往往包含：

- 多次模型调用
- 多轮重试
- 多个节点
- 工具结果回填后二次生成
- 人工审批前后的额外推理

如果只看一次请求的总量，就看不出 token 是在哪一步膨胀的。

### 7.1 至少记录到调用级，而不是只记录到请求级

推荐分 3 层统计：

- 调用级：每一次 `llm_call` 的 token 明细
- 请求级：同一个 `request_id` 下所有模型调用汇总
- 聚合级：按小时 / 天 / 用户 / 工作流 / 模型的统计结果

### 7.2 token 字段不要只放一个 `total_tokens`

内部建议统一成下面这套字段，即使不同 provider 返回格式不一样，也在接入层做归一化：

- `prompt_tokens`
- `completion_tokens`
- `reasoning_tokens`
- `input_tokens`
- `output_tokens`
- `cache_read_tokens`
- `cache_write_tokens`
- `billable_tokens`
- `total_tokens`

字段建议：

- `prompt_tokens` / `input_tokens`：输入给模型的 token
- `completion_tokens` / `output_tokens`：模型输出 token
- `reasoning_tokens`：如果 provider 暴露了推理 token，就单独记
- `cache_read_tokens`：命中缓存节省掉的输入 token
- `cache_write_tokens`：写入缓存的 token
- `billable_tokens`：真正参与计费的 token
- `total_tokens`：观测意义上的总量，通常用于趋势分析

### 7.3 token 统计至少按这些维度切

- 按 `user_id`
- 按 `workflow_name`
- 按 `workflow_version`
- 按 `provider`
- 按 `model`
- 按 `node_name`
- 按 `tool_name` 前后阶段
- 按 `env`
- 按 `release`
- 按成功 / 失败状态

最有价值的几个问题通常是：

- 哪个工作流最吃 token
- 哪个版本上线后 prompt tokens 突然上涨
- 哪个节点的 reasoning tokens 不成比例地高
- 哪类失败请求在白白烧 token
- 哪个模型虽然质量更高，但成本暴涨太多

### 7.4 token 统计不要忘记“分布”，不要只看平均值

至少看这些聚合口径：

- 平均每请求 `total_tokens`
- P95 每请求 `total_tokens`
- 平均每次模型调用 `prompt_tokens`
- P95 `reasoning_tokens`
- 每用户日均 token
- 每工作流日均 token
- 每版本发布后的 token 增幅

平均值经常掩盖问题。真正把成本打爆的，往往是少量长尾请求。

### 7.5 推荐单独落一张模型调用事实表

如果后续要做 BI、成本归因、告警，建议单独落一张 `llm_call_fact` 表，字段至少包括：

- `ts`
- `env`
- `release`
- `request_id`
- `trace_id`
- `run_id`
- `user_id`
- `workflow_name`
- `workflow_version`
- `node_name`
- `provider`
- `model`
- `attempt`
- `status`
- `duration_ms`
- `prompt_tokens`
- `completion_tokens`
- `reasoning_tokens`
- `cache_read_tokens`
- `cache_write_tokens`
- `billable_tokens`
- `total_tokens`
- `cost_input_usd`
- `cost_output_usd`
- `cost_total_usd`

这一层一旦有了，后面的仪表盘、告警、版本对比都会轻松很多。

## 8. 成本观测

Agent 系统的成本通常不只来自模型本身，还包括：

- 模型 token 成本
- 检索 / 搜索 API 成本
- 外部工具调用成本
- sandbox 执行成本
- 存储、trace、日志摄取成本

但在大多数项目里，第一优先级还是先把模型成本记清楚。

### 8.1 成本字段建议与 token 对齐

建议至少拆成：

- `cost_input_usd`
- `cost_output_usd`
- `cost_reasoning_usd`
- `cost_tools_usd`
- `cost_storage_usd`
- `cost_total_usd`
- `pricing_version`

如果某个 provider 没有直接返回成本，就在服务侧按价格表计算，但一定要把 `pricing_version` 记下来，不然历史回放时会对不上。

### 8.2 成本至少按三层归因

- 用户层：哪个用户 / 客户 / 租户最贵
- 工作流层：哪个 Agent / Workflow 最贵
- 版本层：哪个发布版本把成本推高了

### 8.3 成本分析时最常见的高价值问题

- 成本上涨是因为请求量变多，还是单次请求 token 变大
- 成本上涨是因为 prompt 变长，还是重试次数变多
- 成本上涨是因为模型切换，还是缓存命中率下降
- 是否有失败请求反复调用模型，导致无效烧钱

## 9. 告警与仪表盘

### 9.1 除了错误率，还要给 token 和成本设告警

建议至少有以下告警：

- 5xx 错误率明显升高
- P95 请求耗时明显恶化
- provider `429` 激增
- 某个工具连续失败
- 单次请求 `total_tokens` 超过阈值
- 平均 `prompt_tokens` 相比基线突增
- `reasoning_tokens` 突然异常升高
- 单请求成本超过阈值
- 日成本 / 小时成本异常上涨
- 缓存命中率明显下降

### 9.2 token 告警特别适合做“版本对比”

Agent 项目里，很多事故不是服务挂了，而是：

- 某次 prompt 修改后，平均输入 token 上涨 40%
- 某个节点进入重试循环，导致 token 翻倍
- 某个模型切换后 reasoning tokens 激增

所以最有用的不是绝对阈值，而是：

- 相对上一个稳定版本的涨幅
- 相对过去 7 天同类流量的偏移

### 9.3 最小可用仪表盘建议

如果只做 1 套基础仪表盘，建议至少放这些面板：

- 请求量、错误率、P95 延迟
- 每小时模型调用次数
- 每小时 `prompt_tokens`、`completion_tokens`、`reasoning_tokens`
- 每请求 `total_tokens` 的平均值与 P95
- 每小时成本与单请求成本
- Top 10 最耗 token 的工作流 / 节点 / 用户
- provider 429 和工具失败数

## 10. 上线前最小检查清单

上线前至少确认这些问题已经有答案：

- 是否每次请求都能拿到 `request_id`、`trace_id`、`run_id`
- 是否每次模型调用都记录了 token 明细
- 是否能按用户、工作流、版本看 token 与成本
- 是否能区分成功请求与失败请求的 token 消耗
- 是否能从日志跳到 trace
- 是否能从异常成本点回溯到具体模型调用
- 是否已经对 token 激增和成本激增设置告警
- 是否已经验证过 `staging` 的观测链路完整可用

## 11. 一句话原则

对 Agent / LLM 系统来说，真正要观测的不是“服务活着没有”，而是“每次请求在哪里耗时、在哪里失败、在哪里烧 token、为什么开始烧得更多了”。
