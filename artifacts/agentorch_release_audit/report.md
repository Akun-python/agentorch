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
- 结果：`326 passed, 2 skipped in 159.61s`

说明：

- 全量回归已覆盖 `tests/test_examples_smoke.py`、`tests/test_examples_contracts.py` 与 `tests/test_experiments_smoke.py`，因此 `examples/` 与离线实验入口已包含在正式验收路径中。
- 本轮不做真实外部模型与在线服务性能验证，只做本地代码、契约测试与离线 smoke 验证。

## 审计结论

- blocker：0
- high：0
- medium：0
- low：1
- 发布建议：`Go`

结论理由：

- 当前没有发现会阻断 `v1` 发布的功能性缺陷。
- 高层 facade、design 入口、能力插件缝、多代理运行链路与离线实验入口在本地回归下均可通过。
- 本轮发现的文档与示例入口漂移问题都已完成收口，并补上最小回归测试。

## 本轮已修复

### [Closed-High] 中文 README 对稳定公开面的推荐入口漂移

- 复现入口：`README.zh-CN.md`
- 触发条件：中文用户按“当前推荐 API 风格”与“快速开始”示例接入框架
- 实际行为：文档将 `Runtime.create(...)` / `Agent.create(...)` 写成默认推荐用法，并在最小 agent / 工具调用 / 多智能体示例中继续把低层装配 API 当作主入口
- 期望行为：日常使用应优先走 `create_agent(...)` / `create_multi_agent(...)`；`Agent.create(...)` / `Runtime.create(...)` 只应作为手动装配 runtime 的低层能力说明
- 受影响边界：中文 README、稳定面/兼容面认知、一线接入体验
- 修复方向：已将中文 README 推荐入口、快速开始、多智能体示例对齐到 facade 优先语义，并新增 README 契约测试避免再次漂移

### [Closed-Medium] `examples/` facade 示例与 core assembly 示例缺少显式分层

- 复现入口：`examples/basic_agent.py`、`examples/supervisor_agents.py`、`examples/rag_ready_runtime.py`、`examples/tools.py`
- 触发条件：用户直接浏览 `examples/` 目录寻找上手入口
- 实际行为：facade 示例与手动 runtime 装配示例并列存在，但没有目录级说明，新用户容易把低层示例误读成默认推荐入口
- 期望行为：示例目录应明确区分稳定公开面示例与底层装配示例
- 受影响边界：示例可发现性、API 学习路径、一致性
- 修复方向：已新增 `examples/README.md` 做目录分层说明，给关键代表示例补充模块级用途标签，并新增契约测试保护该分类

## 剩余问题

### [Low] README 的 Public API Highlights 仍以“可导入面”展示稳定面与兼容导出

- 复现入口：`README.md`、`README.zh-CN.md`
- 触发条件：用户仅阅读“Public API Highlights / 公开 API 重点”而不读推荐入口说明
- 实际行为：该节展示的是当前顶层可导入集合，而不是严格的稳定承诺面
- 期望行为：读者能明确区分“稳定推荐入口”与“兼容保留导出”
- 受影响边界：文档表达清晰度
- 当前状态：本轮已补充“稳定公开面以及兼容导出”的说明，剩余提升空间主要是未来若需要，可以单独列出稳定面清单

## 整改顺序建议

1. 已完成：修正 `README.zh-CN.md` 的推荐入口漂移，并加 README 契约测试。
2. 已完成：为 `examples/` 增加 facade / core assembly 分类说明，并补示例契约测试。
3. 后续文档整理：若要强化稳定承诺叙事，可把 README 的 “Public API Highlights” 拆成“稳定面”和“兼容导出”两个小节。

## 发布判定

`Go`

判定依据：

- blocker 为 0，high 为 0。
- 当前全量测试结果不低于既有可信基线。
- 示例与实验离线 smoke 已纳入全量验收并通过。
- 已知剩余问题集中在文档可发现性，不构成 `v1` 的功能阻断与兼容性阻断。
