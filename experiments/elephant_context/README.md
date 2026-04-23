# Elephant Context Package

`experiments/elephant_context` 现在采用分层目录，核心机制与实验基准分离，默认兼容历史导入路径。

## 目录结构

```text
experiments/elephant_context/
├─ core/                    # 象群上下文机制核心：配置、策略、插件装配
│  ├─ models.py             # Chapter/Variant 配置模型
│  ├─ variants.py           # baseline/ablation 变体定义
│  └─ plugin.py             # runtime 组装入口 build_elephant_runtime_config(...)
├─ benchmarks/              # 基准与评估实现
│  ├─ context_cases.py      # 上下文治理 benchmark case 定义
│  ├─ context_benchmark.py  # context suite 执行与指标计算
│  ├─ lifecycle_cases.py    # 生命周期 benchmark case 定义
│  ├─ lifecycle_benchmark.py# lifecycle suite 执行与指标计算
│  ├─ chapter_benchmark.py  # full/context/lifecycle 统一入口
│  └─ probe_model.py        # 本地探针模型
├─ tools/                   # CLI 工具
│  ├─ run_benchmark.py
│  └─ inspect_case.py
├─ demo.py                  # 端到端演示脚本
└─ __main__.py              # python -m experiments.elephant_context
```

## 推荐入口

- Python API:
  - `experiments.elephant_context.build_elephant_runtime_config`
  - `experiments.elephant_context.run_elephant_benchmark_sync`
  - `experiments.elephant_context.inspect_elephant_case_sync`
- CLI:
  - `python -m experiments.elephant_context benchmark --suite full --quick`
  - `python -m experiments.elephant_context inspect-case --suite context --case-id rule_preservation_01`

## 兼容策略

为避免破坏旧代码，顶层模块（如 `benchmark.py`、`plugin.py`、`lifecycle_benchmark.py`）保留为兼容层，内部转发到新目录。新代码请优先直接引用 `core/` 与 `benchmarks/` 下的模块。
