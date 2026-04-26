<h1 align="center">agentorch</h1>

<p align="center">
  <img src="resource/agentorch-icon.svg" alt="agentorch icon" width="110">
</p>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh-CN.md">简体中文</a> |
  <a href="README.zh-TW.md">繁體中文</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.es.md">Español</a>
</p>

<p align="center">
  <img alt="version v0.1.0" src="https://img.shields.io/badge/version-v0.1.0-2563eb?style=flat-square">
  <img alt="python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="downloads" src="https://img.shields.io/github/downloads/Akun-python/agentorch/total?style=flat-square">
  <img alt="license MIT" src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square">
</p>

`agentorch` 是一个代码优先、异步优先的 Python 多智能体编排框架。

它面向“需要真实工程边界”的系统，而不是只靠提示词拼接的黑盒流程。

当你的场景需要工具调用、检索证据、记忆治理、工作流和多角色协作同时存在时，`agentorch` 提供了明确可控的运行时模型。

该库已按 `agentorch` 包名发布，普通用户可直接通过 `pip install agentorch` 安装；只有在参与框架源码开发时，才需要使用本地 editable 安装。

![agentorch Architecture Overview](resource/architecture_overview.svg)

## WHY

### 为什么做这个框架 🎯

很多项目在“一个助手 + 一段提示词”阶段跑得很快，但一旦进入工程化就容易失控：

- 角色越来越多，但职责边界不清
- 工具能力越来越强，但安全约束不成体系
- 上下文越来越长，但状态不可追踪
- 检索越来越复杂，但证据链不可复核

`agentorch` 的目标是把这些问题从“隐式 prompt 技巧”变成“显式软件结构”。

### 为什么对工程团队有价值 🧭

- 运行时装配可导出、可检查、可调试
- 策略边界可配置、可版本化
- 能从单智能体平滑升级为多智能体协作
- 可以对推理/RAG/工作流策略做持续迭代

### 为什么对研究团队有价值 🔬

- 可切换推理策略（如 `react`、`plan_execute`）
- 可比较不同 RAG 与上下文策略组合
- 可做进化搜索与策略实验
- 能保留多轮任务中的结构化状态

### 典型适用场景

- 代码助手：需要文件、命令、Git、审查协同
- 知识助手：需要检索证据并保持可解释输出
- 自动化流程：需要 DAG 节点级控制与审计
- 长程任务：需要线程/工作区/跨轮记忆复用

## WHAT

### 核心入口 API

- `create_agent(...)`
- `create_multi_agent(...)`

默认建议从这两个入口开始，不必先下沉到底层装配。

### 关键能力模块 🧩

- 模型适配层（OpenAI 与兼容接口）
- 工具注册与工具包（filesystem / execution / git / web / media）
- 沙箱执行与权限策略
- 知识库与 RAG 策略
- 记忆管理与记忆治理
- 工作流 DAG 编排与执行
- 可观测性事件与持久化追踪

### 编排在这里具体指什么

在 `agentorch` 中，编排不是一个模糊概念，而是有明确对象与边界：

- 总指挥负责路由与委派
- 任务包是可追踪的执行单元
- 交接记录是显式结构，不是隐式聊天
- 共享状态受策略约束
- 工具可见性和权限可控

### 稳定性与兼容性

- Python `3.10+`
- 核心依赖保持轻量
- 高层 facade API 面向稳定使用
- 兼容导出可覆盖存量代码迁移

## HOW

### 安装 📦

从 PyPI 安装：

```bash
pip install agentorch
```

框架源码开发时使用本地 editable 安装：

```bash
pip install -e .
```

直接从 GitHub 安装：

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

可选依赖示例：

```bash
pip install "agentorch[neo4j]"
```

### 环境变量配置

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

本地 `.env` 建议显式加载，不建议隐式注入。

### 推荐落地顺序

1. 先用单智能体跑通核心任务。
2. 再加入必要工具，控制权限范围。
3. 再打开 RAG（并验证证据质量）。
4. 最后再引入多智能体委派与策略协同。

### 验证命令

```powershell
py -3.10 -m pytest -q
```

```powershell
py -3.10 -m pytest -q agentorch/tests/test_readme_contracts.py
```

### 工程守则 ✅

- 工具白名单尽量小
- 线程 ID 显式化，便于追踪
- 长任务拆分为可检查步骤
- 运行结束后及时关闭 runtime / agent

## QUICKSTART

### 1) 最小可运行示例

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="你是一个简洁且准确的助手。",
    reasoning="react",
)

result = agent.run_sync(
    "请用三个要点解释什么是智能体编排。",
    thread_id="quickstart-zh-cn-001",
)

print(result.output_text)
agent.close()
```

### 2) 工具调用示例

```python
from pydantic import BaseModel

from agentorch import ToolRegistry, create_agent, tool

class AddInput(BaseModel):
    a: int
    b: int

@tool(description="Add two integers.")
async def add_numbers(input: AddInput):
    return {"sum": input.a + input.b}

agent = create_agent(
    model="gpt-4.1-mini",
    tools=ToolRegistry.from_tools(add_numbers),
    reasoning="react",
)

result = agent.run_sync("请调用 add_numbers 计算 12 + 30。", thread_id="quickstart-tools-zh-cn-001")
print(result.output_text)
agent.close()
```

### 3) 多智能体起步示例

```python
from agentorch import create_agent, create_multi_agent

planner = create_agent(model="gpt-4.1-mini", reasoning="plan_execute", name="planner")
reviewer = create_agent(model="gpt-4.1-mini", reasoning="react", name="reviewer")

team = create_multi_agent(
    model="gpt-4.1-mini",
    agents=[
        {"agent": planner, "name": "planner", "role": "planner"},
        {"agent": reviewer, "name": "reviewer", "role": "reviewer"},
    ],
    system_prompt="协调专家并返回一个最终答案。",
)

result = team.run_sync("先制定再评审一个迁移方案。", thread_id="quickstart-team-zh-cn-001")
print(result.output_text)
team.close()
```

### 4) 下一步建议

- 加入 `knowledge_paths` 与 `enable_rag=True`
- 引入 workflow DAG 固化步骤顺序
- 开启 observability 做成本/质量分析
- 用策略对象固定团队行为边界

MIT License.
