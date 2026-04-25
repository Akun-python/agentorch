# AgentTorch 当前框架审计报告

生成时间：2026-04-25  
审计范围：`agentorch/`、`agentorch/tests/`、`tests/`、`experiments/` 中与框架运行相关的源码和测试。  
约束：未读取 `.env`，未修改框架源码；只刷新架构指标并运行测试、compile、smoke 检查。

## 总体结论

AgentTorch 当前可以继续作为研究/实验框架使用：在 `data_analysis_py311` 和 Python 3.13 下完整测试均通过，导入图没有检测到循环依赖，核心懒加载注册路径可用，多轮 thread 隔离 smoke 正常。

但存在两个需要优先修复的真实风险：

1. `sanitize_for_export()` 对 `api_key` / `*_api_key` 没有脱敏，`Agent.export_config()` 会泄漏模型密钥。
2. `SQLiteEventStore` 每次打开 SQLite 连接后没有显式关闭，Windows 临时目录清理会触发 `WinError 32` 文件占用。

## 执行证据

- 当前分支：`refactor/agentorch-architecture-rebuild-20260419`
- 当前 HEAD：`59ebc08 完善开题报告研究风格Word版本`
- 当前工作区：已有大量非框架文档/生成物改动；本轮新增/刷新了 `artifacts/agentorch_architecture_audit/metrics.json` 和本报告。
- 可见 API 环境变量：当前 shell 未看到 `OPENAI_API_KEY` / `OPENAI_BASE_URL`，只看到 `ANTHROPIC_BASE_URL`。
- Python 解释器：
  - `C:\Users\24260\.conda\envs\data_analysis_py311\python.exe` -> Python 3.11.13
  - `py -3.13` 可用
- 完整测试：
  - `data_analysis_py311`: `335 passed, 2 skipped in 100.73s`
  - `py -3.13`: `335 passed, 2 skipped in 106.39s`
- compileall：
  - `data_analysis_py311 -m compileall agentorch tests` 通过
  - `py -3.13 -m compileall agentorch tests` 通过
- 架构指标：`artifacts/agentorch_architecture_audit/metrics.json`
  - 循环依赖：`[]`
  - `models/__init__.py` 顶层注册调用：`[]`
  - `agentorch.__all__` 实际长度：143，且等于 `STABLE_API_SYMBOLS`

## Critical

### 1. API key 导出脱敏失效

位置：

- `agentorch/security.py:12`
- `agentorch/security.py:86`
- `agentorch/security.py:104`
- `agentorch/security.py:143`
- `agentorch/runtime/agent.py:29`

影响：

`sanitize_for_export()` 会把路径 key 先用 `_normalize_key()` 转成 `api-key`，但默认敏感 key 配置里是 `api_key`。因此 `api_key`、`embedding_api_key`、`speech_api_key`、`image_api_key`、`video_api_key` 不会被 key 规则命中。`Agent.export_config()` 和 `agent.inspect()` 通过 `_model_summary()` 导出模型配置时会泄漏密钥。

复现 smoke：

```powershell
@'
import json
from agentorch import create_agent
from agentorch.models import OpenAIModel
model = OpenAIModel(model='gpt-test', api_key='sk-test-secret', base_url='https://example.test/v1')
agent = create_agent(model=model, enable_tools=False)
print(json.dumps(agent.export_config().get('model',{}).get('config'), ensure_ascii=False, indent=2))
agent.close()
'@ | & 'C:\Users\24260\.conda\envs\data_analysis_py311\python.exe' -
```

观察结果：导出的 `api_key` 和各 capability `*_api_key` 均为 `sk-test-secret` 原文。

附带问题：`max_tokens` 被误脱敏为 `[REDACTED]`，因为 key 中包含 `token`，这会降低导出配置的可诊断性。

建议修复：

- 统一敏感 key 比较规则：要么默认敏感 key 也 normalize，要么 `_looks_sensitive_key()` 同时比较原始 key 和 normalized key。
- 把 `api_key`、`*_api_key`、`authorization`、`x-api-key` 放入直接测试。
- 避免 `max_tokens` 这类非 secret 字段被 `token` 子串误伤，可改为分隔词匹配或显式 allowlist。
- 新增测试直接覆盖 `sanitize_for_export(ModelConfig(...))`、`Agent.export_config()` 和自定义模型 `config` dict。

## Major

### 2. SQLiteEventStore 连接生命周期不完整

位置：

- `agentorch/observability/telemetry.py:363`
- `agentorch/observability/telemetry.py:416`
- `agentorch/observability/telemetry.py:442`
- `agentorch/observability/telemetry.py:543`
- `agentorch/observability/telemetry.py:546`

影响：

`sqlite3.Connection` 的 `with conn:` 只负责 commit/rollback，不负责 close。`SQLiteEventStore._connect()` 每次返回新连接，但 `emit()`、`get_run_events()` 等路径没有显式关闭连接，`close()` / `aclose()` 当前也是 no-op。Windows 下使用临时目录时，数据库文件可能在目录清理阶段仍被占用并触发 `PermissionError: [WinError 32]`。

复现 smoke：

```powershell
@'
from agentorch.observability import SQLiteEventStore
from agentorch.security import RedactionConfig, PayloadBudgetConfig
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as td:
    store = SQLiteEventStore(Path(td)/'observability.db', redaction=RedactionConfig(), payload_budget=PayloadBudgetConfig())
    store.emit('human_feedback_emitted', {'run_id':'run-1','thread_id':'thread-1'})
    store.get_run_events('run-1')
'@ | & 'C:\Users\24260\.conda\envs\data_analysis_py311\python.exe' -
```

观察结果：退出临时目录时可能出现 `WinError 32`。

建议修复：

- 用 `contextlib.closing(self._connect())` 包裹所有短连接使用路径。
- 或者把 store 改为持有单连接，并让 `close()` / `aclose()` 真正关闭连接。
- 新增 Windows 友好的测试：临时目录内创建、写入、读取、调用 close，然后立即删除目录。

### 3. Runtime 和 OpenAIModel 聚合过重，可维护性风险高

位置：

- `agentorch/runtime/runtime.py:102`
- `agentorch/runtime/runtime.py:868`
- `agentorch/runtime/runtime.py:1202`
- `agentorch/runtime/runtime.py:1279`
- `agentorch/runtime/runtime.py:1317`
- `agentorch/runtime/runtime.py:1582`
- `agentorch/runtime/runtime.py:2195`
- `agentorch/models/openai_model.py:54`
- `agentorch/models/openai_model.py:329`
- `agentorch/models/openai_model.py:416`
- `agentorch/models/openai_model.py:479`

影响：

当前 `runtime.py` 约 2295 行，同时承载运行入口、技能加载、工具执行、RAG 上下文、模型轮次、workflow 委派、collective memory 候选构造等职责。`openai_model.py` 约 892 行，同时承载 chat、embedding、image、speech、video、限流、headers、错误处理等 provider 逻辑。

完整测试通过说明这不是当前运行错误，但后续新增 capability 时容易出现局部修补和跨功能回归。

建议修复：

- 优先拆出非破坏性内部模块，不改变公开 API。
- `runtime.py` 下一步可拆：skill execution、tool execution、retrieval context、model round/event handling。
- `openai_model.py` 下一步可拆：chat/embedding/media/speech/video capability client 或 endpoint builder。
- 每拆一块都保留原入口代理，并配套局部测试。

## Minor

### 4. 架构指标工具不能识别动态 __all__ 长度

位置：

- `tools/architecture_audit/collect_agentorch_architecture_metrics.py:137`
- `tools/architecture_audit/collect_agentorch_architecture_metrics.py:209`
- `agentorch/__init__.py:702`

影响：

`metrics.json` 中 `root_public_api.__all__` 为 `null`，原因是 collector 只识别 list/tuple 字面量赋值，但当前源码是 `__all__ = list(STABLE_API_SYMBOLS)`。这会让审计指标显示不完整。

实际运行验证：

`len(agentorch.__all__) == 143`，且 `set(agentorch.__all__) == set(agentorch.STABLE_API_SYMBOLS)`。

建议修复：

- collector 对 `__all__ = list(STABLE_API_SYMBOLS)` 做轻量求值，或改为在子进程 import 后读取 public API 长度。

## Test Gaps

- 缺少直接覆盖 `sanitize_for_export()` key 命中规则的单元测试，现有 observability 测试因为 payload budget 截断，没有暴露 `api_key` 脱敏失效。
- 缺少 `Agent.export_config()` / `Agent.inspect()` 的密钥不泄漏测试。
- 缺少 `SQLiteEventStore.close()` 真正释放 SQLite 文件句柄的 Windows 生命周期测试。
- 缺少真实 API smoke，因为当前 shell 没有可见 `OPENAI_API_KEY` / `OPENAI_BASE_URL`。

## Blocked

真实 OpenAI-compatible API 请求未执行。原因：当前 shell 没有可见的 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。本轮严格遵守“不读取 `.env`”约束，没有通过 `.env` 兜底加载凭据。

## 运行能力评价

- 单 agent：通过完整测试和 smoke。
- 多轮对话：同一 `thread_id` 能带入历史，不同 `thread_id` smoke 隔离正常。
- 工具调用：完整测试覆盖工具注册、文件工具、代码解释器、git 工具、web 工具基础路径。
- 技能加载：完整测试覆盖 progressive disclosure、`load_skill`、`load_skill_resource`。
- Workflow：完整测试覆盖 workflow 和 runtime delegate 路径，架构指标无循环依赖。
- Memory：完整测试覆盖 session/thread/collective memory，smoke 中线程隔离正常。
- Reasoning：完整测试覆盖 `cot`、`react`、`plan_execute`、`tot`、`reflexion` 和 legacy adapter。
- Sandbox：完整测试覆盖 allowlist、shell 禁用、persistent Python session 关闭。
- Multi-agent：完整测试覆盖 supervisor/coordinator 基础路径和外部 runtime 生命周期。

## 下一步修复批次

1. 修复导出脱敏规则并新增安全测试，commit 建议：`修复配置导出密钥脱敏规则`。
2. 修复 SQLiteEventStore 连接关闭语义并新增 Windows 文件释放测试，commit 建议：`修复事件存储连接释放问题`。
3. 补强架构指标工具对动态 `__all__` 的识别，commit 建议：`完善架构审计公开接口统计`。
4. 分批拆分 `Runtime` 内部执行职责，先拆 skill/tool/retrieval 辅助模块，commit 建议：`拆分运行时执行辅助模块`。
5. 分批拆分 `OpenAIModel` capability 逻辑，commit 建议：`拆分模型多模态能力实现`。
