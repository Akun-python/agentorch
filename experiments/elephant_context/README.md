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
  - `python -m experiments.elephant_context benchmark --suite context --dataset real_task_x --model-backend probe --seeds 0 1 --report-level brief`

## 真实模型环境变量

当 `--model-backend` 使用 `openai` 或 `local-llm` 时，实验会按 `masarch_0_1_0_import_quickstart.ipynb` 的同一套约定读取真实配置：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_CHAT_MODEL` / `OPENAI_MODEL` / `AGENTORCH_MODEL`

同时兼容这些别名：

- `API_KEY` / `api_key`
- `BASE_URL` / `base_url`
- `MODEL_NAME` / `model_name` / `MODEL` / `model`

说明：

- 默认会尝试加载当前工作目录下的 `.env`。
- CLI 会在真实模型运行前先做一次环境探测，缺少 `api_key`、`base_url` 或模型名时会直接报错。
- 返回结果会附带 `env_report`，只暴露布尔状态，不回写也不输出明文密钥。

## Benchmark CLI 扩展参数

- `--model-backend`: `probe` / `openai` / `local-llm`
- `--dataset`: `context_synth` / `lifecycle_synth` / `real_task_x` / `full_synth`
  - `suite=full` + `real_task_x` 会同时运行 context + lifecycle 的真实任务子集。
- `--seeds`: 多 seed 重复运行（例如 `--seeds 0 1 2`）
- `--report-level`: `brief` / `full`

## 产物字段扩展

- `runs.jsonl` 已新增字段：
  - `dataset_id`
  - `model_backend`
  - `seed`
  - `retrieval_trace`
  - `rejection_trace`
  - `cost_metrics`
- 新增统计文件 `metric_stats.csv`，按指标输出 `mean/std/ci95`。
- 新增 `paired_significance.csv`，输出与主 baseline 的配对差值和 sign-test `p-value`。
  - 包含 `effective_pair_count/positive_count/negative_count/tie_count`，平局样本不计入 sign-test 有效样本。

## 兼容策略

为避免破坏旧代码，顶层模块（如 `benchmark.py`、`plugin.py`、`lifecycle_benchmark.py`）保留为兼容层，内部转发到新目录。新代码请优先直接引用 `core/` 与 `benchmarks/` 下的模块。
