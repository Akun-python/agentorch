<h1 align="center">agentorch</h1>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh-CN.md">简体中文</a> |
  <a href="README.zh-TW.md">繁體中文</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.ja.md">日本語</a>
</p>

<p align="center">
  <img alt="Version v0.1.0" src="https://img.shields.io/badge/version-v0.1.0-2563eb?style=flat-square">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Downloads" src="https://img.shields.io/github/downloads/Akun-python/agentorch/total?style=flat-square">
  <img alt="License MIT" src="https://img.shields.io/github/license/Akun-python/agentorch?style=flat-square">
</p>

`agentorch` 是一个代码优先、异步优先的 Python 智能体编排框架，用来构建可编程的 agent 系统。它提供结构化工具、工作流、RAG、记忆、推理策略、沙箱执行和多智能体委派能力。

![Architecture Overview](resource/architecture_overview.svg)

## 为什么使用 agentorch

很多 agent 框架要么过度依赖 prompt，要么把核心逻辑藏在 DSL 里，要么强绑定某一种执行方式。`agentorch` 的目标是提供一个 Python 原生的编排层，把关键边界清楚地暴露出来，并保持自由组合能力：

- `models` 统一模型提供方接入
- `tools` 定义结构化动作
- `sandbox` 隔离高风险执行
- `memory` 管理线程状态和群体记忆
- `knowledge` 提供 classic、deliberative、hybrid 三类 RAG
- `reasoning` 提供可切换的推理框架
- `workflow` 提供 Python 定义的 DAG 编排
- `agents` 提供注册、任务包、委派和 supervisor
- `runtime` 将这些能力整合到一起

目标不是隐藏编排，而是让编排可编程、可观察、可扩展。

## 当前支持能力

- OpenAI 兼容的聊天模型接入
- 结构化工具注册与工具调用
- 带沙箱的 Python 代码解释器工具
- 线程记忆、记录、检查点、workspace artifact、shared note
- 面向多智能体系统的 MGCM 群体记忆治理
- 面向 `pdf/docx/md/txt/code/memory/artifacts` 的多格式 RAG
- 可选 RAG 策略：`classic`、`deliberative`、`hybrid`、`off`
- 带 evidence、citations、coverage、visited sources 的报告型检索输出
- 推理框架：`cot`、`react`、`plan_execute`、`tot`、`reflexion`
- Python API 工作流 DAG，支持 retrieve、mount、evaluate、agent 节点
- 多智能体注册与 supervisor 委派
- 进化搜索：`genetic`、`random_search`、`hill_climb`、`beam_search`
- Prompt card 与类 LangChain 的 prompt 组装原语
- tracing 和 usage tracking

## 当前推荐 API 风格

当前推荐 API 风格如下：

高层入口：

- `create_agent(...)`
- `create_multi_agent(...)`

核心装配：

- `ModelConfig.from_any(...)`
- `OpenAIModel.from_config(...)`
- `RuntimeConfig.agent(...)` 与 `RuntimeConfig.workflow(...)`
- `RagStrategyConfig.for_classic(...)`、`for_deliberative(...)`、`for_hybrid(...)`
- `ReasoningStrategyConfig.react(...)`、`plan_execute(...)`、`reflexion(...)`
- `ToolRegistry.from_tools(...)` 与 `ToolRegistry.with_bundles(...)`
- `IndexedKnowledgeBase.create(...)` / `acreate(...)`
- `Runtime.create(...)` / `acreate(...)`
- `Agent.create(...)` / `acreate(...)`
- `WorkflowBuilder()` 配合 `Node.*(...)` shortcuts

日常使用优先选择 facade 高层入口。只有在你需要完全手动装配 runtime 时，再下沉到 `create(...)` / `acreate(...)`。

## 安装

### 环境要求

- Python `3.10+`
- `pip` 或 `uv`
- 推荐使用虚拟环境（`venv` / `conda` / `uv`）

### 安装方式（可直接复制）

1. 本地源码开发安装（推荐贡献者）：

```bash
pip install -e .
```

2. 直接从 GitHub 安装：

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

3. 使用 `uv` 安装（解析更快）：

```bash
uv pip install -e .
```

4. 安装可选 `neo4j` 扩展：

```bash
pip install -e ".[neo4j]"
```

### 一键环境启动

```bash
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# macOS/Linux
# source .venv/bin/activate
pip install -U pip
pip install -e .
```

### 安装验证

```bash
python -c "import agentorch; print(agentorch.__version__ if hasattr(agentorch, '__version__') else 'agentorch imported')"
```

出现输出即表示安装成功。🎉

### 常见安装问题

- 启动时报 `TypeError: ... dict[str, Any]`：通常是 Python 版本低于 3.10。
- `pip install -e .` 失败：先执行 `pip install -U pip setuptools wheel` 再安装。
- 机器上有多个 Python：建议显式写 `py -3.10 -m pip install -e .`（Windows）。

## 环境变量

`agentorch` 现在遵循更标准的 Python 库配置边界：

- 需要完全可控时，直接在代码里显式传入 `model`、`api_key`、`base_url`。
- 需要部署期注入配置时，使用环境变量。
- `.env` 加载是显式启用的：要么自己调用 `initialize_environment(...)`，要么在导入 `agentorch` 之前设置 `AGENTORCH_AUTO_LOAD_ENV=1`。

核心环境变量契约：

- `OPENAI_API_KEY` / `OPENAI_BASE_URL`
- `OPENAI_VISION_MODEL`
- `OPENAI_EMBEDDING_API_KEY` / `OPENAI_EMBEDDING_BASE_URL` / `OPENAI_EMBEDDING_MODEL` / `OPENAI_EMBEDDING_DIMENSIONS`
- `OPENAI_TTS_API_KEY` / `OPENAI_TTS_BASE_URL` / `OPENAI_TTS_MODEL` / `OPENAI_TTS_VOICE` / `OPENAI_TTS_FORMAT` / `OPENAI_TTS_SPEED`
- `OPENAI_IMAGE_API_KEY` / `OPENAI_IMAGE_BASE_URL` / `OPENAI_IMAGE_EXPLICIT_URL` / `OPENAI_IMAGE_MODEL`
- `OPENAI_IMAGE_ASPECT_RATIO` / `OPENAI_IMAGE_SIZE` / `OPENAI_IMAGE_TIMEOUT`
- `OPENAI_IMAGE_FALLBACK_MODELS` / `OPENAI_IMAGE_RETRY_WITHOUT_PROXY` / `OPENAI_IMAGE_DISABLE_ENV_PROXY`
- `OPENAI_VIDEO_API_KEY` / `OPENAI_VIDEO_BASE_URL` / `OPENAI_VIDEO_MODEL` / `OPENAI_VIDEO_DISABLE_ENV_PROXY`

核心库只保留协议级默认值，例如 `/chat/completions`、`/embeddings`、`/audio/speech`、`mp3` 和 `speed=1.0`。它不会替用户默认选择任何供应商网关、模型或密钥。

推荐配置：

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_TTS_MODEL=your-tts-model
OPENAI_TTS_VOICE=your-voice
```

如果你使用 OpenAI-compatible gateway，像 `.../chat/completions`、`.../embeddings`、`.../audio/speech` 这样的完整 URL 会自动被归一化成对应的 provider base URL。

## 快速开始

如果你想快速区分 facade 推荐示例和底层 runtime 装配示例，可先看 [`examples/README.md`](examples/README.md)。

### 0. 5 分钟跑通（详细版）

如果你希望先确认“从安装到运行”链路没问题，可以先跑这个最小闭环。

1. 设置环境变量：

```powershell
$env:OPENAI_API_KEY="sk-xxxx"
```

2. 创建 `quickstart.py`：

```python
from agentorch import create_agent

def main() -> None:
    agent = create_agent(
        model="gpt-4.1-mini",
        system_prompt=(
            "你是一个务实的工程助手。"
            "回答需要简洁、结构化、可执行。"
        ),
        reasoning="react",
        name="hello-agentorch",
    )
    try:
        result = agent.run_sync(
            "请用 3 个要点解释 Agent Orch（Agent Orchestration）。",
            thread_id="hello-001",
        )
        print("=== OUTPUT ===")
        print(result.output_text)
    finally:
        agent.close()

if __name__ == "__main__":
    main()
```

3. 运行：

```bash
python quickstart.py
```

4. 预期结果：

- 启动无异常
- 终端能输出模型回答
- 进程结束时 agent 正常关闭

### 1. 最小 Agent

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="你是一个简洁、准确的助手。",
    reasoning="react",
)

result = agent.run_sync(
    "请用三句话介绍 agentorch 是什么。",
    thread_id="quickstart-001",
)

print(result.output_text)
```

`create_agent(...)` 是单代理的推荐高层入口。若需要完全手动装配 runtime，可使用 `Agent.create(...)` / `Runtime.create(...)`。

### 2. 结构化工具调用

```python
from pydantic import BaseModel

from agentorch import ToolRegistry, create_agent, tool

class AddInput(BaseModel):
    a: int
    b: int

@tool(description="Add two integers together.")
async def add_numbers(input: AddInput):
    return {"sum": input.a + input.b}

agent = create_agent(
    model="gpt-4.1-mini",
    tools=ToolRegistry.from_tools(add_numbers),
    reasoning="react",
)

result = agent.run_sync(
    "请调用 add_numbers 工具计算 123 + 456，并解释结果。",
    thread_id="tool-demo-001",
)

print(result.output_text)
print(result.tool_results)
```

### 3. 工具 bundles

```python
from pathlib import Path

from agentorch import ToolRegistry
from agentorch.sandbox import SandboxManager, SandboxPolicy

sandbox = SandboxManager(
    policy=SandboxPolicy(
        allowed_paths=[Path.cwd()],
        command_allowlist=["python", "git", "powershell", "cmd"],
        timeout=15.0,
    )
)

tools = ToolRegistry.with_bundles(
    workspace_root=Path.cwd(),
    sandbox=sandbox,
)
```

这会一步注册标准的 filesystem、execution、git 工具集。

### 4. 多格式 RAG

```python
from pathlib import Path

from agentorch import IndexedKnowledgeBase, create_agent
from agentorch.knowledge import RagStrategyConfig

knowledge_base = IndexedKnowledgeBase.create(
    paths=[
        Path("docs/architecture.md"),
        Path("docs/meeting_notes.docx"),
        Path("contracts/msa.pdf"),
    ],
    scopes=["architecture", "ops", "legal"],
)

agent = create_agent(
    model="gpt-4.1-mini",
    knowledge_base=knowledge_base,
    rag=RagStrategyConfig.for_deliberative(
        knowledge_scope=["architecture", "ops", "legal"],
        file_types=[".md", ".docx", ".pdf"],
        must_cover=["deployment restrictions"],
        max_steps=3,
    ),
    reasoning="react",
)

result = agent.run_sync(
    "请找出部署限制，并给出最强证据引用。",
    thread_id="rag-demo-001",
)

print(result.output_text)
```

模式说明：

- `classic`：面向 chunk 的词法检索
- `deliberative`：带 source routing 和结构感知深读的主动检索
- `hybrid`：先 classic 粗召回，再 deliberative 抽证
- `off`：关闭 runtime 自动检索注入

### 5. Prompt cards

```python
from agentorch import ChatPromptTemplate, MessagesPlaceholderCard, TextPromptCard
from agentorch.config import RuntimeConfig

prompt = ChatPromptTemplate(
    cards=[
        TextPromptCard(role="system", template="Role={{ agent_role or 'default' }}"),
        MessagesPlaceholderCard(variable_name="conversation"),
        TextPromptCard(role="user", template="{{ user_input }}"),
    ]
)

config = RuntimeConfig.agent(
    reasoning="react",
    prompt_template=prompt,
)
```

### 6. Workflow 编排

```python
from agentorch import Agent, WorkflowBuilder
from agentorch.config import RuntimeConfig
from agentorch.workflow import Node

workflow = (
    WorkflowBuilder()
    .then(Node.retrieve("retrieve", output_key="retrieved", rag_mode="hybrid", must_cover=["owner approval"]))
    .then(Node.rag_mount("mount", from_variable="retrieved", target_key="mounted", mount_result_to="variable"))
    .then(Node.rag_evaluate("score", from_variable="retrieved", output_key="scored"))
    .build()
)

agent = Agent.create(
    model_config="gpt-4.1-mini",
    knowledge_base=knowledge_base,
    workflow=workflow,
    config=RuntimeConfig.workflow(rag="deliberative", reasoning="react"),
)
```

### 7. 多智能体 supervisor 委派

```python
from agentorch import AgentCapability, create_agent, create_multi_agent

planner = create_agent(
    model="gpt-4.1-mini",
    reasoning="plan_execute",
    rag="hybrid",
    name="planner",
    description="架构规划 specialist",
)

orchestrator = create_multi_agent(
    model="gpt-4.1-mini",
    agents=[
        {
            "agent": planner,
            "name": "planner",
            "role": "planner",
            "description": "架构规划 specialist",
            "capabilities": [AgentCapability.PLAN],
            "knowledge_scope": ["architecture"],
        }
    ],
    system_prompt="你负责协调多个 specialist，并把任务委派给最合适的智能体。",
)
```

### 8. 进化搜索

```python
from agentorch import EvolutionConfig, EvolutionManager, SearchSpace

manager = EvolutionManager(
    builder=my_builder,
    evaluator=my_evaluator,
    search_space=SearchSpace(
        {
            "reasoning.kind": ["react", "plan_execute"],
            "rag.mode": ["classic", "hybrid"],
            "workflow.template": ["classic_inline_answer", "retrieve_plan_review"],
        }
    ),
    config=EvolutionConfig(
        algorithm_kind="beam_search",
        population_size=4,
        generations=3,
        evaluation_budget=8,
    ),
)
```

### 11. 端到端生产风格启动模板 🧪

下面这个脚本把常用工程能力串在一起：工具集、RAG、可观测性、上下文策略和记忆策略。

```python
from pathlib import Path

from agentorch import (
    ContextPolicy,
    MemoryPolicy,
    RagStrategyConfig,
    ToolRegistry,
    create_agent,
)
from agentorch.config import ObservabilityConfig, RuntimeConfig
from agentorch.sandbox import SandboxManager, SandboxPolicy

workspace = Path.cwd()
sandbox = SandboxManager(
    policy=SandboxPolicy(
        allowed_paths=[workspace],
        command_allowlist=["python", "git", "powershell", "cmd"],
        allow_shell=False,
        timeout=20.0,
    )
)

tools = ToolRegistry.with_bundles(
    workspace_root=workspace,
    sandbox=sandbox,
    include_filesystem=True,
    include_execution=True,
    include_git=True,
    include_web=False,
)

agent = create_agent(
    model="gpt-4.1-mini",
    name="engineering-assistant",
    system_prompt=(
        "你是一个严谨的软件工程助手。"
        "在需要时使用工具，输出要点清晰、结论可执行。"
    ),
    tools=tools,
    knowledge_paths=["README.md"],
    enable_rag=True,
    rag=RagStrategyConfig.for_hybrid(max_steps=3),
    context_policy=ContextPolicy.evidence_friendly(),
    memory_policy=MemoryPolicy.long_horizon(),
    runtime_config=RuntimeConfig.agent(
        observability=ObservabilityConfig(
            enabled=True,
            sqlite_path=".agentorch/observability.db",
            console_mode="important_only",
        )
    ),
)

try:
    result = agent.run_sync(
        "请总结项目架构，并给出 3 个工程风险及其证据。",
        thread_id="prod-starter-001",
    )
    print(result.output_text)
finally:
    agent.close()
```

这个模板的价值：

- `ToolRegistry.with_bundles(...)`：快速得到可用的工程工具面
- `SandboxManager`：让执行能力可控且可审计
- `RagStrategyConfig.for_hybrid(...)`：兼顾召回率与证据精度
- `ObservabilityConfig`：记录运行事件，便于排障和成本追踪
- `context_policy` + `memory_policy`：让长会话行为更稳定

## Runtime 装配建议

现在 `agentorch` 的 runtime 装配可以更清晰地理解为：

1. `model_config` 或 `model`
2. `tools`
3. `knowledge_base`
4. `config`
   里面包含 `reasoning_strategy`、`rag_strategy`、prompt template、runtime 行为
5. 可选 `workflow`
6. 可选 `agent_registry` 与 `supervisor`

这样你可以在一个位置统一控制：

- 推理行为
- 检索模式与挂载策略
- prompt 结构
- 工具暴露面
- workflow 编排
- 多智能体委派

## 公开 API 重点

当前顶层 API 包括稳定公开面以及兼容导出，常用入口包括：

```python
from agentorch import (
    Agent,
    AgentRegistry,
    AgentSpec,
    ChatPromptTemplate,
    IndexedKnowledgeBase,
    KnowledgeAsset,
    OpenAIModel,
    RagStrategyConfig,
    ReasoningStrategyConfig,
    Runtime,
    ToolRegistry,
    Workflow,
    WorkflowBuilder,
    create_agent,
    create_multi_agent,
    tool,
)
```

## 项目结构

```text
agentorch/
|-- agents/          # Agent 注册、任务包、supervisor、委派
|-- config/          # model、runtime、memory、sandbox 配置
|-- core/            # 通用 message、response、decision 类型
|-- evolution/       # 搜索算法与编排 genome helper
|-- feedback/        # 人类反馈流程与 inbox
|-- knowledge/       # 多格式检索、索引、adapter、RAG 策略
|-- memory/          # 线程记忆、记录、workspace artifact、治理
|-- models/          # 模型提供方适配层
|-- observability/   # tracing、usage tracking、logging
|-- parsing/         # 结构化解析工具
|-- plugins/         # 扩展表面
|-- prompts/         # prompt card 与 prompt builder
|-- reasoning/       # 推理策略与框架注册表
|-- runtime/         # 运行时编排与高层入口
|-- sandbox/         # 沙箱执行
|-- skills/          # skill 加载与注册
|-- tools/           # 结构化工具与 bundle 注册
|-- workflow/        # workflow DAG 定义与 builder
```

## 示例

可运行示例位于：

- [`examples/basic_agent.py`](examples/basic_agent.py)
- [`examples/code_interpreter_agent.py`](examples/code_interpreter_agent.py)
- [`examples/evolution_demo.py`](examples/evolution_demo.py)
- [`examples/evolution_multi_mechanism.py`](examples/evolution_multi_mechanism.py)
- [`examples/evolution_orchestration_search.py`](examples/evolution_orchestration_search.py)
- [`examples/mgcm_demo.py`](examples/mgcm_demo.py)
- [`examples/rag_agent_tool_call.py`](examples/rag_agent_tool_call.py)
- [`examples/rag_mode_comparison.py`](examples/rag_mode_comparison.py)
- [`examples/rag_multiformat_runtime.py`](examples/rag_multiformat_runtime.py)
- [`examples/rag_ready_runtime.py`](examples/rag_ready_runtime.py)
- [`examples/rag_workflow_orchestrated.py`](examples/rag_workflow_orchestrated.py)
- [`examples/supervisor_agents.py`](examples/supervisor_agents.py)
- [`examples/workflow_selectable_rag.py`](examples/workflow_selectable_rag.py)

交互式 notebook：

- [`agentorch_experiments.ipynb`](agentorch_experiments.ipynb)

## 测试

运行完整测试：

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; py -3.13 -m pytest -q
```

## 设计说明

`agentorch` 有意保持这些边界清晰：

- memory 不是 knowledge
- tools 不是 workflows
- workflows 不是 prompt templates
- skills 不是 execution engine
- supervisor routing 不是无限自由 agent 聊天
- RAG 是可配置策略，不是隐藏副作用

这样框架既保持了研究和扩展友好性，也能支持实际系统装配。

## License

MIT
