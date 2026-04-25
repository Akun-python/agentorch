# 基于 AgentTorch 的 Codex 监督编排实施方案

## 1. 方案定位

这份方案以你当前的修改思路为准，重新收敛为一套可实施的设计。

目标不是做一个单纯的聊天 agent，而是做一个 **Codex 上层监督与编排系统**：

- 接收一个长期、大型、可拆分的用户任务。
- 自动拆分子任务。
- 为每个子任务启动一个 Codex 执行单元。
- 实时捕获 Codex 的输出、进度、状态和结果。
- 将当前结果和原始需求持续比对。
- 自动补充指令、要求自检、触发重试、重新拆解。
- 在多个子任务间维护共享状态与统一验收标准。
- 持续循环，直到完成、阻塞或需要人工介入。

一句话总结：

`AgentTorch 负责决策和编排，Codex CLI 负责外部执行，Harness 负责会话管理、状态管理和闭环控制。`

## 2. 核心设计边界

这版方案先把边界定死，避免后面实现时发散。

### 2.1 这个系统负责什么

- 任务拆解
- 任务路由
- Codex 子任务执行
- 子任务输出采集
- 结果审查
- 差距分析
- 自检与 follow-up
- 长时状态持久化
- 人工兜底

### 2.2 这个系统不直接负责什么

- 不在 v1 里做复杂 GUI 自动化
- 不在 v1 里做真正的“无限自治”
- 不在 v1 里做自动冲突合并策略引擎
- 不在 v1 里依赖终端屏幕抓取作为唯一数据源

### 2.3 两个重要原则

#### 原则 A：Codex 是执行引擎，不是 AgentTorch 内部子 agent

Codex 本质上是一个外部 CLI 进程。它应通过工具层接入，而不是强行等价成 AgentTorch 的内生 agent。

#### 原则 B：长时 loop 放在 Python 守护层，不放在 Workflow DAG 里

AgentTorch 的 `Workflow` 适合表达单轮流程，不适合承载完整的守护进程生命周期。

因此推荐结构：

- AgentTorch：负责一轮中的规划、执行决策、审查、整合
- Python 外层 HarnessLoop：负责长时循环、轮询、超时、恢复、终止条件

## 3. 方案总览

```text
用户需求
   |
   v
Harness API / CLI
   |
   v
HarnessLoop
   |
   +-- Planner Agent
   +-- Codex Operator Agent
   +-- Reviewer Agent
   +-- Integrator Agent
   |
   v
CodexSessionManager
   |
   +-- ExecJsonBackend        v1 推荐
   +-- InteractiveBackend     v2 才引入
   |
   v
多个 Codex CLI 任务实例

持久化:
- Thread messages
- Workspace records
- Shared notes
- Checkpoints
- Session logs
- Task state store
```

## 4. 推荐的总体架构

系统按五层拆分。

### 4.1 接口层

对外暴露两类入口：

- CLI 入口
- Python API 入口

职责：

- 接收用户总任务
- 初始化运行参数
- 指定项目路径
- 指定并发上限
- 指定是否启用交互式会话

### 4.2 编排层

由 `HarnessLoop` 驱动，是整个系统的主控制器。

职责：

- 创建总任务上下文
- 驱动多轮计划/执行/审查循环
- 决定下一轮是否继续
- 控制全局预算、最大轮次、最大重试次数
- 在异常退出后恢复运行

### 4.3 决策层

由 AgentTorch 的多 agent 系统承担。

包括：

- `planner`
- `codex_operator`
- `reviewer`
- `integrator`

职责：

- 任务拆解
- 任务路由
- 子任务跟进策略
- 审查与收敛

### 4.4 执行层

由 `CodexSessionManager` 与多个后端承担。

职责：

- 启动 Codex
- 发送 prompt
- 捕获输出
- 保存日志
- 检测会话状态
- 停止或恢复会话

### 4.5 状态层

由 `MemoryManager + 本地状态存储` 组成。

职责：

- 持久化线程消息
- 持久化任务状态
- 存储子任务 artifact
- 存储 shared notes
- 存储 checkpoint

## 5. AgentTorch 在本方案中的角色

这一部分是最关键的“框架能力映射”。

### 5.1 直接复用的能力

当前仓库里的 AgentTorch 能力与本方案的映射关系如下：

- `create_agent(...)`
  - 用来构建 planner / reviewer / integrator / operator 等单体 agent
- `create_multi_agent(...)`
  - 用来构建多角色决策系统
- `shared_memory`
  - 用来共享整个大任务的线程状态
- `MemoryManager`
  - 用来保存 thread messages、workspace records、shared notes、checkpoint
- `TaskPacket`
  - 用来表达子任务目标和约束
- `SupervisorPolicy`
  - 用来自定义路由策略
- `agent.run(..., stream=True)`
  - 用来实时输出运行事件
- `HumanFeedbackManager`
  - 用来请求用户确认、补充输入、人工接管

### 5.2 不直接复用的能力

当前内置 `run_command` 只能执行一次命令，不适合维护长驻交互式进程。

因此必须自定义：

- `CodexSessionManager`
- `CodexExecJsonBackend`
- `CodexInteractiveBackend`
- 一组 Codex 专用工具

### 5.3 对 Workflow 的使用结论

建议结论很明确：

- `Workflow` 只用于单轮步骤编排，或者干脆在 v1 不使用
- 长时循环一定放在 Python 外层

如果一定要使用 Workflow，建议仅表达一轮：

- plan
- execute
- review
- integrate

而不要把“无限轮询 + 持久守护 + 异常恢复”塞进去。

## 6. 推荐的多 Agent 角色设计

### 6.1 Planner Agent

职责：

- 接收总需求
- 拆分成多个子任务
- 生成每个子任务的验收标准
- 明确每个子任务的读写范围

输入：

- 用户需求
- 项目路径
- 当前全局状态
- 已完成子任务摘要

输出：

- 结构化子任务列表

建议每个子任务至少包含：

- `task_id`
- `goal`
- `acceptance_criteria`
- `constraints`
- `priority`
- `write_scope`
- `depends_on`
- `expected_output`

建议 reasoning：

- `plan_execute`

### 6.2 Codex Operator Agent

职责：

- 调用 Codex 会话工具
- 启动任务
- 监督任务运行
- 读取输出
- 根据审查结论发送补充指令
- 请求 Codex 做自检

输入：

- 子任务清单
- 当前会话状态
- review gap

输出：

- 会话启动结果
- 会话状态快照
- 补充执行指令

建议 reasoning：

- `react`

### 6.3 Reviewer Agent

职责：

- 对比需求和产物
- 审查日志、最后回复、git diff、输出文件
- 判断任务是否真正完成

输出状态建议限定为：

- `completed`
- `needs_followup`
- `redo`
- `blocked`
- `ask_human`

建议 reasoning：

- `reflexion`

### 6.4 Integrator Agent

职责：

- 汇总多个子任务结果
- 判断是否进入下一轮
- 生成下一轮总体指令
- 在冲突出现时决定顺序重做或人工介入

建议 reasoning：

- `plan_execute`

## 7. 调度策略

### 7.1 不使用默认关键字路由

默认关键字路由对这个系统来说太弱，不足以支撑可靠编排。

应该实现自定义 `HarnessSupervisorPolicy`，按阶段路由。

推荐路由键：

- `phase=plan` -> `planner`
- `phase=execute` -> `codex_operator`
- `phase=review` -> `reviewer`
- `phase=integrate` -> `integrator`

### 7.2 并发调度原则

- 读任务可以并发
- 写任务必须隔离工作区
- 存在依赖关系的任务必须串行
- 同一文件集合不能分配给多个 Codex 同时写

### 7.3 建议的调度粒度

不要把任务拆得过碎。

推荐粒度：

- 一个子任务对应一个可验收目标
- 一个子任务控制在一次 Codex 执行能稳定完成的范围内

不推荐：

- 一个函数一个子任务
- 多个子任务同时改同一个核心模块

## 8. Codex 接入策略

这一部分是本系统能否落地的核心。

### 8.1 v1 推荐后端：`ExecJsonBackend`

调用形式：

```powershell
codex exec --json -C <DIR> "<PROMPT>"
```

适合 v1 的原因：

- 输出结构化，容易采集
- 不依赖终端屏幕解析
- 更容易做重试和回放
- 并发管理简单
- 出错边界清晰

结论：

`v1 必须优先使用 exec --json，而不是一开始就做长驻交互式终端。`

### 8.2 v2 才引入：`InteractiveBackend`

调用形式：

```powershell
codex --no-alt-screen -C <DIR>
```

这个模式用于满足你“持续维护同一个 Codex 终端进程”的目标，但不应该作为 v1 起点。

原因：

- 需要处理 TUI 输出
- 需要处理 ANSI 控制符
- 需要处理 stdin/stderr 持续连接
- 需要处理会话丢失与恢复
- Windows 下通常需要 `ConPTY` 或 `pywinpty`

### 8.3 后续可研究但不纳入 v1 的方向

本机 `codex --help` 已显示存在：

- `app-server`
- `mcp-server`
- `resume`
- `fork`

后续可以调研是否能基于这些能力做更稳定的编程式集成，但当前方案不将其作为 MVP 依赖。

## 9. 自定义工具集设计

AgentTorch 要想调度 Codex，就必须有一组稳定、结构化、可序列化的工具。

建议至少实现如下工具。

### 9.1 `prepare_task_workspace`

作用：

- 为子任务准备工作目录

输入：

- `project_root`
- `task_id`
- `mode`
- `write_scope`

输出：

- `workspace_path`
- `workspace_kind`
- `branch_name`
- `ready`

### 9.2 `start_codex_task`

作用：

- 启动一个 Codex 子任务

输入：

- `task_id`
- `cwd`
- `prompt`
- `backend`
- `sandbox_mode`
- `approval_policy`

输出：

- `session_id`
- `pid`
- `log_path`
- `status`
- `started_at`

### 9.3 `poll_codex_session`

作用：

- 读取某个会话的新输出和当前状态

输入：

- `session_id`

输出：

- `status`
- `new_events`
- `new_text`
- `last_activity_at`
- `finished`
- `exit_code`

### 9.4 `send_codex_followup`

作用：

- 向正在运行或待续执行的 Codex 会话发送补充指令

输入：

- `session_id`
- `followup_prompt`

输出：

- `accepted`
- `sent_at`
- `mode`

### 9.5 `request_codex_self_check`

作用：

- 要求 Codex 根据验收标准自检

输入：

- `session_id`
- `acceptance_criteria`

输出：

- `status`
- `self_check_prompt`

### 9.6 `collect_task_artifacts`

作用：

- 收集任务执行证据

输入：

- `task_id`
- `workspace_path`

输出：

- `git_diff_summary`
- `changed_files`
- `last_agent_message`
- `output_files`
- `log_excerpt`

### 9.7 `stop_codex_session`

作用：

- 主动结束异常会话

输入：

- `session_id`

输出：

- `stopped`
- `final_status`
- `exit_code`

### 9.8 `restore_codex_session`

作用：

- 从状态快照恢复会话上下文

输入：

- `session_id`

输出：

- `restored`
- `status`
- `resume_strategy`

## 10. 状态模型设计

这套系统一定要先有状态模型，再谈循环。

### 10.1 `HarnessTask`

建议字段：

- `task_id`
- `parent_task_id`
- `goal`
- `phase`
- `cwd`
- `write_scope`
- `depends_on`
- `acceptance_criteria`
- `expected_output`
- `status`
- `retry_count`
- `assigned_session_id`
- `review_decision`

### 10.2 `CodexSessionState`

建议字段：

- `session_id`
- `task_id`
- `backend`
- `pid`
- `cwd`
- `status`
- `started_at`
- `finished_at`
- `last_activity_at`
- `log_path`
- `last_output_offset`
- `last_agent_message`
- `exit_code`

### 10.3 `ReviewDecision`

建议字段：

- `task_id`
- `decision`
- `score`
- `gap_list`
- `evidence`
- `next_prompt`
- `needs_human`

### 10.4 `LoopCheckpoint`

建议字段：

- `run_id`
- `round_index`
- `active_tasks`
- `completed_tasks`
- `blocked_tasks`
- `session_state_index`
- `shared_summary`
- `saved_at`

## 11. 任务状态机

建议把任务状态控制在以下集合内：

- `pending`
- `prepared`
- `running`
- `waiting_review`
- `needs_followup`
- `completed`
- `blocked`
- `failed`
- `aborted`

状态流转建议：

```text
pending -> prepared -> running -> waiting_review
waiting_review -> completed
waiting_review -> needs_followup -> running
waiting_review -> blocked
running -> failed
failed -> needs_followup
failed -> aborted
```

会话状态建议：

- `starting`
- `running`
- `idle`
- `finished`
- `errored`
- `lost`
- `stopped`

## 12. Memory 与持久化方案

这部分直接建立在 AgentTorch 现有能力上。

### 12.1 使用 `MemoryManager` 作为共享任务记忆

推荐配置：

- 开启 `persist_thread_messages`
- 使用独立 `checkpoint_path`
- 使用独立 `record_path`

推荐保存内容：

- 总任务对话
- 每轮规划摘要
- 每个子任务的执行摘要
- 每次 review 结论
- 每轮全局 checkpoint

### 12.2 使用 workspace records 保存执行证据

每个子任务完成一轮后，至少写入：

- `codex_output_summary`
- `log_excerpt`
- `diff_summary`
- `review_result`
- `artifact_paths`

### 12.3 使用 shared notes 保存全局事实

例如：

- 某接口已重命名
- 某测试框架配置异常
- 某目录不可写
- 某依赖需要先安装

这些结论要对后续子任务可见。

### 12.4 使用 checkpoint 实现恢复

每轮 loop 结束时写一次 checkpoint：

- 当前 round
- 任务状态表
- 会话状态表
- 已生成的 shared notes 摘要

## 13. 工作区与并发策略

这里必须明确一条硬规则。

### 13.1 不允许多个写任务共享同一个 working tree

你原始需求里提到“在相同文件夹里启动多个 codex”，对于读任务可以，但对写任务风险非常高。

正确策略：

- 只读分析类任务：允许共享目录
- 写代码任务：必须隔离工作区

### 13.2 推荐的隔离方式

优先级建议：

1. `git worktree`
2. 独立目录拷贝
3. 同仓库串行写

其中 v1 推荐：

- 读任务并发
- 写任务用 `git worktree`

### 13.3 目录建议

```text
codexharness/
  runtime/
    logs/
    sessions/
    checkpoints/
    artifacts/
  worktrees/
    task-001/
    task-002/
    task-003/
```

## 14. 主循环设计

下面是整个系统的推荐主循环。

### 14.1 单轮流程

1. 读取当前总任务状态
2. Planner 生成或修正子任务清单
3. 为可执行任务准备工作区
4. Operator 启动 Codex 子任务
5. SessionManager 轮询会话输出
6. 收集 artifact 和日志摘要
7. Reviewer 判断是否完成
8. Integrator 决定是否进入下一轮
9. 写 checkpoint

### 14.2 长时循环伪代码

```python
while not loop_state.should_stop():
    plan_result = planner_round(loop_state)
    runnable_tasks = select_runnable_tasks(plan_result, loop_state)

    for task in runnable_tasks:
        workspace = prepare_task_workspace(task)
        session = start_codex_task(task, workspace)
        loop_state.bind_session(task, session)

    while loop_state.has_active_sessions():
        events = poll_all_sessions(loop_state)
        persist_events(events)
        update_session_state(events)
        detect_stuck_sessions(loop_state)

    reviewed = review_finished_tasks(loop_state)
    loop_state.apply_review_results(reviewed)

    integrated = integrate_round(loop_state)
    loop_state.apply_integration(integrated)

    save_checkpoint(loop_state)
```

### 14.3 终止条件

满足任一条件可结束：

- 所有任务 `completed`
- 达到 `max_rounds`
- 达到全局预算上限
- 存在未决阻塞且必须人工介入
- 用户主动停止

## 15. 可观测性与人工兜底

### 15.1 建议开启流式事件输出

顶层 orchestrator 运行时建议使用：

- `agent.run(..., stream=True)`

用于：

- 显示当前阶段
- 显示任务路由
- 显示哪个子任务开始/结束
- 显示聚合完成

### 15.2 建议保存三类日志

- 编排日志
- 会话日志
- 审查日志

### 15.3 人工介入触发条件

满足以下任一条件时触发 `HumanFeedbackManager`：

- 连续多轮无法收敛
- 子任务输出自相矛盾
- 会话丢失且无法恢复
- 多个写任务结果冲突
- 审查结论置信度不足

## 16. MVP 范围定义

为了防止一开始把系统做散，v1 范围必须严格限定。

### 16.1 v1 必做

- 单项目路径输入
- Planner / Operator / Reviewer / Integrator 四角色
- 自定义 `HarnessSupervisorPolicy`
- `ExecJsonBackend`
- 任务状态表
- 会话状态表
- 每轮 checkpoint
- artifact 收集
- 自动 follow-up 一轮以上
- 人工介入兜底

### 16.2 v1 不做

- 长驻交互式终端会话
- 复杂 resume/fork 接续
- 自动合并多个 worktree 的冲突
- 终端 TUI 屏幕解析

### 16.3 v1 验收标准

至少满足以下能力：

- 能接收一个总任务并拆成多个子任务
- 能并发启动多个 Codex 子任务
- 能保存每个子任务的日志和最终结果
- 能根据审查结果再次生成 follow-up
- 能在进程重启后从 checkpoint 恢复至少一轮状态

## 17. 分阶段实施路线

### Phase 1：跑通闭环

目标：

- 基于 `codex exec --json` 跑通一轮到多轮闭环

交付：

- `session_manager.py`
- `backends/exec_json.py`
- `tools/codex_tools.py`
- `agents.py`
- `loop.py`

### Phase 2：支持并发写任务隔离

目标：

- 引入 `git worktree`
- 支持多写任务并发隔离

### Phase 3：支持交互式长驻会话

目标：

- 增加 `interactive_backend.py`
- 支持持续维护同一 Codex 会话
- 支持 follow-up 注入

### Phase 4：增强恢复与治理

目标：

- 会话丢失恢复
- stuck detection
- 更细的预算控制
- 更强的人工接管机制

## 18. 建议的代码结构

```text
codexharness/
  基于AgentTorch的Codex监督编排方案.md
  src/
    codexharness/
      main.py
      config.py
      loop.py
      schemas.py
      routing.py
      agents.py
      state_store.py
      memory_store.py
      session_manager.py
      review_engine.py
      workspace_manager.py
      backends/
        exec_json.py
        interactive_backend.py
      tools/
        codex_tools.py
        workspace_tools.py
        review_tools.py
```

## 19. 最终结论

按你当前这版修改思路，最合理的实现结论是：

- `AgentTorch` 只负责“计划、监督、审查、整合”
- `Codex` 通过工具层作为外部执行引擎接入
- 长时闭环由 Python 外层 `HarnessLoop` 控制
- v1 优先使用 `codex exec --json`
- v2 再补“持续维护同一个 Codex 终端进程”
- 写任务必须隔离工作区，不要多个 Codex 直接并发写同一目录

如果只保留一句工程建议，就是：

`先把监督闭环做对，再去做终端保活；先做结构化执行，再做交互式会话。`

