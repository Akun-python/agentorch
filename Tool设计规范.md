# Tool设计规范

## 1. 文档定位

这份文档不再只讨论“单个 Tool 怎么写”，而是把它放回更完整的 Agent 能力结构里：

- `Tool`：原子执行单元，负责真正与外部世界交互
- `Skill`：任务封装单元，负责触发说明、操作流程、资源组织与工具使用约束
- `Workflow`：编排单元，负责把多个 Tool / Skill 串成完整任务流程

如果只定义 Tool，而不考虑 Skill，常见结果是：

- 模型知道“有这个函数”，但不知道什么时候该用
- 参数 schema 虽然正确，但模型选错工具
- 同一类任务每次都要重新解释流程
- 文档、脚本、模板分散在各处，能力无法复用

这份规范的目标是把“能力设计”统一成一句话：

- 用 Skill 定义任务边界与方法，用 Tool 承担原子动作与副作用。

## 2. Tool、Skill、Workflow 的分工

### 2.1 Tool 是什么

Tool 是一个可被模型调用的原子动作。

它应该具备这些特征：

- 有明确名称
- 有清晰输入 schema
- 有稳定输出结构
- 有可控副作用
- 有超时、重试、权限与观测边界

典型例子：

- `search_docs`
- `read_file`
- `create_ticket`
- `send_email`

### 2.2 Skill 是什么

Skill 不是一个函数，而是一组面向任务的能力封装。

它通常包含：

- 触发描述：什么时候应该使用这个 Skill
- 工作流程：先做什么，后做什么
- 工具使用规则：哪些 Tool 可以用，哪些情况不要用
- 参考资料：schema、业务规则、策略说明
- 脚本资源：可重复执行的脚本
- 输出资源：模板、资产、样板文件

Skill 更像“给另一个 Agent 的任务说明书 + 资源包”。

### 2.3 Workflow 是什么

Workflow 是更上层的编排。

它关心的是：

- 多步任务如何流转
- 状态如何更新
- 何时调用模型
- 何时调用工具
- 何时中断、审批、恢复

### 2.4 三者的关系

- Tool 解决“做这一个动作”
- Skill 解决“这一类任务应该怎么做”
- Workflow 解决“多个动作如何组成一个完整流程”

一个成熟能力通常不是只有 Tool，而是：

- `Skill + Tool`

复杂场景下则是：

- `Workflow + Skill + Tool`

## 3. 什么时候该做 Tool，什么时候该做 Skill

### 3.1 只做 Tool 的场景

满足以下条件时，单独做 Tool 通常就够：

- 动作简单且通用
- 不依赖复杂流程知识
- 不需要额外参考资料
- 不需要脚本或模板资源

例子：

- `get_current_time`
- `read_file`
- `list_directory`

### 3.2 必须配 Skill 的场景

以下情况建议一定是 `Skill + Tool` 一起设计：

- 任务有明确流程，不是“一次函数调用”能说明白
- 工具选择依赖业务规则
- 需要查阅参考文档、schema、政策或模板
- 需要脚本提升稳定性与复用性
- 高风险操作需要额外约束或审批

例子：

- 工单处理
- 财务审批
- 数据库分析
- PDF / DOCX 处理
- 多系统联动的客服流程

### 3.3 该上 Workflow 的场景

如果一个任务天然包含固定的多步流转，就不要把所有逻辑塞到 Skill 或单个 Tool 里。

典型信号：

- 需要多次模型调用
- 需要状态机或 checkpoint
- 需要人工审批
- 需要回滚、恢复、重试策略

## 4. 设计总原则

- Skill 定义任务方法，Tool 承担原子动作
- Tool 只做一件事，不把查询、决策、写入、通知混成一个动作
- Skill 要简洁，只保留真正高价值、非显然的信息
- 重复且脆弱的操作优先沉淀为脚本，而不是每次临场生成代码
- 详细规则放到 references，不把所有背景都塞进 SKILL.md
- 高风险副作用放在 Tool 边界处理，不放任模型自由发挥
- 日志、Tracing、token、成本要能回溯到 Skill 与 Tool

## 5. Tool 边界规范

一个 Tool 应只负责一个明确动作，不要把“查询 + 决策 + 写入 + 通知”塞进同一个工具。

推荐拆分：

- `search_orders`
- `get_order_detail`
- `update_order_status`
- `send_order_notification`

不推荐：

- `handle_order`

判断标准：

- 工具名能否用一句动词短语描述清楚
- 输入 schema 是否能在 3 到 8 个字段内讲清楚
- 成功输出是否只有一种主语义
- 出错时是否能清楚判断失败落在哪个动作

## 6. Skill 封装规范

### 6.1 Skill 的职责

一个 Skill 至少要回答这些问题：

- 什么时候触发它
- 遇到这类任务时优先采用什么流程
- 需要读哪些 references
- 需要用哪些 Tool
- 哪些情况需要停下来确认或审批

### 6.2 Skill 的目录结构

推荐结构：

```text
my-skill/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── scripts/
├── references/
└── assets/
```

说明：

- `SKILL.md`：必需，写元数据和核心使用说明
- `agents/openai.yaml`：推荐，给界面层展示信息
- `scripts/`：重复且需要稳定执行的脚本
- `references/`：按需加载的参考资料
- `assets/`：最终产物中会用到的模板或素材

### 6.3 SKILL.md 的约束

`SKILL.md` 的 frontmatter 只保留：

- `name`
- `description`

其中：

- `name` 使用小写字母、数字、连字符
- `description` 要写清楚“它做什么”以及“什么时候触发”

不要把“何时使用这个 Skill”只写在正文里，因为触发主要依赖 `description`。

### 6.4 Progressive Disclosure

Skill 要尽量按三层组织信息：

- 元数据层：`name` 与 `description`
- 核心说明层：`SKILL.md` 正文
- 资源层：`scripts/`、`references/`、`assets/`

原则是：

- 把最核心的流程写在 `SKILL.md`
- 把详细 schema、规则、示例移到 `references/`
- 把需要稳定执行的逻辑移到 `scripts/`

### 6.5 Skill 不要变成文档仓库

不要在 Skill 目录里堆这些文件：

- `README.md`
- `QUICK_REFERENCE.md`
- `CHANGELOG.md`
- 各种过程性说明文档

Skill 是给 Agent 用的，不是给人做项目归档的。

## 7. Tool 与 Skill 的组合方式

### 7.1 模式一：直接 Tool

适合简单、通用、低上下文任务。

例子：

- `read_file`
- `search_web`

### 7.2 模式二：Skill + 单 Tool

适合流程简单，但需要上下文约束的任务。

例子：

- `send_external_email`

Skill 负责：

- 说明只有在用户明确要求联系他人时才发送
- 说明外部邮件要确认收件人与内容

Tool 负责：

- 真实发信动作
- 幂等、超时、审计日志

### 7.3 模式三：Skill + Tool 集合

适合同一任务域下有多个原子动作。

例子：

- `ticketing` Skill
- `search_ticket`
- `create_ticket`
- `update_ticket`
- `add_ticket_comment`

Skill 负责：

- 告诉模型什么时候应该查工单、什么时候创建工单
- 解释优先级映射、归属团队规则

Tool 负责：

- 每个具体动作的执行

### 7.4 模式四：Skill + Tool + Scripts + References

适合脆弱、复杂或强领域化任务。

例子：

- `pdf-review`
- `docx-redline`
- `finance-reconciliation`

此时：

- Skill 给出流程
- Tool 提供动作接口
- Scripts 保证关键步骤稳定
- References 提供规则、schema、政策

## 8. Tool 命名规范

### 8.1 命名原则

- 使用 `snake_case`
- 使用动词开头
- 名称体现副作用强弱
- 避免模糊词：`process`、`handle`、`manage`、`do_task`

推荐：

- `search_docs`
- `read_file`
- `create_ticket`
- `send_email`
- `execute_sql_query`

不推荐：

- `tool1`
- `doc_tool`
- `task_manager`
- `run`

### 8.2 危险操作要显式命名

高风险 Tool 必须让模型和人都一眼看出风险：

- `delete_file`
- `transfer_funds`
- `execute_shell_command`
- `send_external_email`

不要用伪中性名字掩盖副作用：

- `apply_changes`
- `finalize_request`

### 8.3 Skill 命名与 Tool 命名不要混

建议：

- Skill 用任务域命名：`ticketing`、`pdf-review`
- Tool 用动作命名：`create_ticket`、`extract_pdf_text`

这样模型在“选 Skill”与“选 Tool”时语义更清楚。

## 9. 输入 Schema 规范

### 9.1 基本要求

- 所有参数必须有明确类型
- 参数名要贴近业务，不要用 `data`、`payload`、`params`
- docstring 要说明何时使用该 Tool，而不只是参数含义
- 可选参数要少，默认值要保守

### 9.2 Schema 设计原则

- 优先显式字段，不要塞 JSON 字符串
- 一个字段只表达一个概念
- 对枚举值做收敛，不让模型自由发挥
- 对高风险字段增加约束

示例：

```python
from langchain.tools import tool
from typing import Literal


@tool
def create_ticket(
    title: str,
    description: str,
    priority: Literal["low", "medium", "high"],
    owner_team: Literal["ops", "sales", "support"],
) -> str:
    """Create an internal support ticket.

    Use this tool when a ticket must actually be created in the ticket system.
    """
    return "ticket_created"
```

不推荐的反例：

```python
@tool
def create_ticket(payload: str) -> str:
    """Create ticket"""
    ...
```

### 9.3 Skill 要补“何时用 Tool”的语义说明

仅有 Tool schema 还不够，Skill 里还应补充：

- 调用前需要确认哪些前提
- 哪些字段缺失时不能调用
- 哪些场景优先读 references 再决定
- 哪些情况必须人工确认

也就是说：

- Tool 负责“参数长什么样”
- Skill 负责“什么时候该填这些参数”

## 10. 输出与错误处理规范

### 10.1 输出规范

Tool 输出应服务于后续推理和观测，而不是只返回“成功/失败”。

推荐输出包含：

- 结果摘要
- 关键标识符
- 是否成功
- 是否可重试
- 人可读错误原因

推荐：

```python
{
  "ok": True,
  "ticket_id": "T-1024",
  "summary": "Ticket created for ops team"
}
```

不推荐：

```python
"done"
```

### 10.2 错误分类

至少区分三类：

- 用户输入错误
- 外部依赖错误
- 系统内部错误

### 10.3 错误返回原则

- 让模型知道失败原因
- 让程序知道是否可重试
- 不暴露敏感内部细节

推荐模式：

```python
{
  "ok": False,
  "error_type": "validation_error",
  "retryable": False,
  "message": "order_id is required"
}
```

### 10.4 Skill 要定义失败后的处理策略

Skill 里应写清楚：

- 哪类 Tool 错误允许自动重试
- 哪类错误应该改用别的 Tool
- 哪类错误应该向用户追问
- 哪类错误必须终止并请求人工审批

## 11. 幂等性、超时与重试

### 11.1 幂等性

幂等性是“重试不产生额外副作用”的能力。

必须优先保证幂等的 Tool：

- 发消息
- 创建工单
- 支付 / 转账
- 写数据库
- 调用外部付费 API

常见策略：

- 使用 `request_id` / `idempotency_key`
- 写操作前先查重
- 把“创建”改成“upsert”
- 对重复请求返回同一结果

### 11.2 超时

每个 Tool 都应定义超时边界，不能无限等待。

建议：

- 快查询工具：1 到 5 秒
- 普通 API 工具：5 到 15 秒
- 重任务工具：15 到 60 秒

### 11.3 重试

只对“暂时性失败”重试：

- 网络抖动
- `429`
- `5xx`

不要自动重试：

- 参数错误
- 权限不足
- 业务校验失败
- 无幂等键的非幂等写操作

### 11.4 Skill 要声明自动化边界

Skill 中建议显式写明：

- 哪些 Tool 可自动重试
- 哪些写操作禁止自动重试
- 哪些高风险场景必须停下来确认

## 12. 权限边界与审批

Tool 不是“给模型一个万能入口”，而是“给模型一个最小可用能力”。

原则：

- 默认最小权限
- 读写分离
- 内外部操作分离
- 高风险 Tool 必须可审批

推荐拆分：

- `read_customer_profile`
- `update_customer_profile`

不推荐：

- `customer_profile_tool`

高风险 Tool 建议增加：

- 人工审批
- 白名单资源范围
- 路径 / 库表限制
- 审计日志

Skill 中则要写清楚：

- 什么情况下可以调用高风险 Tool
- 什么情况下必须先确认用户意图
- 什么情况下必须升级为人工审批

## 13. 可观测性要求

### 13.1 Tool 级观测

每次 Tool 调用至少记录：

- `tool_name`
- `request_id`
- `trace_id`
- `run_id`
- 输入摘要
- 开始时间 / 结束时间
- 耗时
- 成功或失败
- 错误类型
- 重试次数

### 13.2 Skill 级观测

如果一个 Tool 是在某个 Skill 语境下被调用，还应补充：

- `skill_name`
- `skill_version`
- `workflow_name`
- `node_name`
- `resource_ref`

这样才能回答这些问题：

- 是哪个 Skill 最容易触发错误调用
- 是哪个 Skill 让模型选错了 Tool
- 是哪个版本的 Skill 上线后调用量或失败率突增

### 13.3 敏感信息脱敏

不要把原始敏感字段直接打进日志，例如：

- token
- 密码
- 完整身份证号
- 完整银行卡号
- 完整用户隐私文本

## 14. 版本与兼容性

Tool schema 一旦被多个 Agent 或前端依赖，就应视为接口契约。

规范：

- 新增字段优先保持向后兼容
- 删除字段前先废弃
- 重大变更要升版本
- 在文档里写清楚变更影响

推荐命名：

- `search_docs_v2`
- `create_ticket_v2`

同时也要单独管理 Skill 版本，因为下面两种变更影响不同：

- Tool 版本变化：输入输出契约变化
- Skill 版本变化：触发逻辑、流程说明、资源组织变化

不要把两者混成一个版本号。

## 15. 测试与验证

### 15.1 Tool 测试清单

每个 Tool 至少覆盖：

- 正常输入
- 缺字段
- 非法枚举
- 外部依赖超时
- 外部依赖 `429` / `5xx`
- 重试是否符合预期
- 幂等是否成立
- 权限边界是否生效

### 15.2 Skill 验证清单

每个 Skill 至少检查：

- `SKILL.md` frontmatter 是否合规
- `description` 是否足够触发
- `references/` 是否能被正确定位
- `scripts/` 是否真的可运行
- 是否存在重复、过长、无用说明
- 是否清楚说明 Tool 的使用边界

如果是在实际 Skill 目录中落地，建议跑一次验证脚本：

```bash
scripts/quick_validate.py <path/to/skill-folder>
```

### 15.3 前向测试

复杂 Skill 建议用真实任务做前向测试，关注的不是“能不能完成”，而是：

- 是否真的会触发这个 Skill
- 是否会正确选 Tool
- 是否会读对 references
- 是否会在高风险步骤停下来

## 16. 最小组合模板

下面是一个更推荐的“Skill + Tool”最小组合，而不是只交付一个 Tool。

Skill 目录：

```text
ticketing/
├── SKILL.md
├── scripts/
│   └── normalize_ticket.py
└── references/
    └── priority_mapping.md
```

`SKILL.md` 示例：

```markdown
---
name: ticketing
description: Create, search, and update support tickets. Use when the task involves filing, triaging, or updating internal support issues and requires structured ticket workflow rules.
---

Use `create_ticket` only when the issue must actually be filed.
Read `references/priority_mapping.md` when the user urgency is ambiguous.
Use `scripts/normalize_ticket.py` if the raw user input must be normalized into ticket fields.
Do not call write tools before required fields are confirmed.
Escalate before using high-risk external notification actions.
```

Tool 示例：

```python
from langchain.tools import tool
from typing import Literal


@tool
def create_ticket(
    title: str,
    description: str,
    priority: Literal["low", "medium", "high"],
    owner_team: Literal["ops", "sales", "support"],
    idempotency_key: str,
) -> dict:
    """Create a support ticket in the internal ticketing system.

    Use this tool only when a ticket should actually be created.
    """
    return {
        "ok": True,
        "ticket_id": "T-1024",
        "summary": "Ticket created for support team",
    }
```

## 17. 落地检查项

在把一个能力交给智能体前，逐项确认：

- 这是一个 Tool，还是应该是 `Skill + Tool`
- Tool 名称是否清楚表达动作
- Skill 描述是否清楚表达触发条件
- 输入 schema 是否足够窄
- 输出是否可供后续推理
- 是否定义错误分类、超时、重试与幂等
- 是否限制权限范围
- 是否接入日志与 Tracing
- 是否能从 Tool 调用回溯到 Skill / Workflow
- 是否有单测、失败样例与真实任务验证

## 18. 一句话原则

不要把 Tool 设计成“模型的万能手”，而要把能力设计成“Skill 负责教会模型何时做什么，Tool 负责安全稳定地把这件事做成”。
