# AgentTorch 发布前全功能审计报告

## 审计范围

- `agentorch` 主包与顶层公开面
- `agentorch/tests` 与 `tests/` 契约、集成、示例 smoke
- `examples/`、根目录 notebook / example 资产与当前公开 API 的一致性
- `pyproject.toml`、README / README.zh-CN 的发布面描述

## 验证基线

- 日期：2026-04-20
- Python：`C:\Users\24260\.conda\envs\data_analysis_py311\python.exe`
- pytest 环境变量：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`
- 全量命令：`python -m pytest agentorch/tests tests`
- 结果：`323 passed, 2 skipped in 158.34s`

说明：

- 全量回归已覆盖 `tests/test_examples_smoke.py` 与 `tests/test_experiments_smoke.py`，因此 `examples/` 与离线实验入口已包含在正式验收路径中。
- 本轮不做真实外部模型与在线服务性能验证，只做本地代码、契约测试与离线 smoke 验证。

## 审计结论

- blocker：0
- high：0
- medium：1
- low：1
- 发布建议：`Go`

结论理由：

- 当前没有发现会阻断 `v1` 发布的功能性缺陷。
- 高层 facade、design 入口、能力插件缝、多代理运行链路与离线实验入口在本地回归下均可通过。
- 本轮发现的最高优先级问题是中文 README 对推荐公开面的错误引导，已在本轮修复，并补上最小回归测试。

## 本轮已修复

### [Closed-High] 中文 README 对稳定公开面的推荐入口漂移

- 复现入口：`README.zh-CN.md`
- 触发条件：中文用户按“当前推荐 API 风格”与“快速开始”示例接入框架
- 实际行为：文档将 `Runtime.create(...)` / `Agent.create(...)` 写成默认推荐用法，并在最小 agent / 工具调用 / 多智能体示例中继续把低层装配 API 当作主入口
- 期望行为：日常使用应优先走 `create_agent(...)` / `create_multi_agent(...)`；`Agent.create(...)` / `Runtime.create(...)` 只应作为手动装配 runtime 的低层能力说明
- 受影响边界：中文 README、稳定面/兼容面认知、一线接入体验
- 修复方向：已将中文 README 推荐入口、快速开始、多智能体示例对齐到 facade 优先语义，并新增 README 契约测试避免再次漂移

## 剩余问题

### [Medium] `examples/` 中 facade 示例与 core assembly 示例仍混排，缺少显式标签

- 复现入口：`examples/basic_agent.py`、`examples/supervisor_agents.py` 与 `examples/rag_ready_runtime.py`、`examples/reasoning_*.py`
- 触发条件：新用户按文件名浏览示例目录时，把 `Agent(runtime=Runtime(...))` 的核心装配示例误认为稳定公开面的首选写法
- 实际行为：部分示例展示 facade 装配，部分示例展示手动 runtime 装配，但目录层没有显式标明“推荐高层入口示例”和“底层装配示例”
- 期望行为：示例资产应让用户一眼区分稳定入口与底层装配入口，避免公开面心智继续漂移
- 受影响边界：示例可发现性、学习曲线、一致性
- 建议修复方向：后续增加 `examples/README.md` 或在示例头部增加一句用途标签，不需要作为当前 `v1` 发布阻断项

### [Low] README 的 Public API Highlights 仍以“可导入面”展示稳定面与兼容导出

- 复现入口：`README.md`、`README.zh-CN.md`
- 触发条件：用户仅阅读“Public API Highlights / 公开 API 重点”而不读推荐入口说明
- 实际行为：该节展示的是当前顶层可导入集合，而不是严格的稳定承诺面
- 期望行为：读者能明确区分“稳定推荐入口”与“兼容保留导出”
- 受影响边界：文档表达清晰度
- 当前状态：本轮已补充“稳定公开面以及兼容导出”的说明，剩余提升空间主要是未来若需要，可以单独列出稳定面清单

## 整改顺序建议

1. 已完成：修正 `README.zh-CN.md` 的推荐入口漂移，并加 README 契约测试。
2. 发布后优先：为 `examples/` 增加 facade / core assembly 的分类说明，降低学习入口歧义。
3. 后续文档整理：若要强化稳定承诺叙事，可把 README 的 “Public API Highlights” 拆成“稳定面”和“兼容导出”两个小节。

## 发布判定

`Go`

判定依据：

- blocker 为 0，high 为 0。
- 当前全量测试结果不低于既有可信基线。
- 示例与实验离线 smoke 已纳入全量验收并通过。
- 已知剩余问题集中在文档可发现性，不构成 `v1` 的功能阻断与兼容性阻断。
