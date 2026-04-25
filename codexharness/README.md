# codexharness

`codexharness` 是基于 `AgentTorch` 的 Codex 上层监督编排子工程。

当前实现聚焦 `Phase 1`：

- 独立 `src` 工程结构
- CLI 入口
- 运行时目录布局
- `codex exec --json` 后端
- 会话状态存储
- 任务状态存储
- Workspace 准备
- Planner / Reviewer / Integrator / Operator 基础 agent 装配
- 多轮 loop 骨架

## 运行前提

1. 仓库根目录下的 `agentorch/` 包可用
2. 本机安装了 `codex` CLI
3. 已配置模型访问凭据，例如 OpenAI 兼容环境变量
4. 使用 `Python >= 3.10`，当前仓库建议直接用 `py -3.13`

## .env 配置

`codexharness` 现在支持通过 `.env` 文件加载模型相关配置，不需要再把 `base_url`、`api_key`、`model_name` 写死在命令里或代码里。

并且支持把两套配置拆开：

- `CODEXHARNESS_*`：只给 `codexharness` 自己的 planner / reviewer / integrator 使用
- `CODEXHARNESS_CODEX_*`：只给子进程里的 `codex` CLI 使用

默认会按下面的顺序尝试加载：

1. `--env-file` 指定的文件
2. `--project-root/.env`
3. `codexharness/.env`

常用变量如下：

```env
CODEXHARNESS_MODEL_NAME=gpt-4.1-mini
CODEXHARNESS_BASE_URL=https://api.openai.com/v1
CODEXHARNESS_API_KEY=sk-your-api-key

CODEXHARNESS_CODEX_MODEL_NAME=gpt-5.3-codex
CODEXHARNESS_CODEX_BASE_URL=https://api.openai.com/v1
CODEXHARNESS_CODEX_API_KEY=sk-your-codex-api-key
```

兼容变量：

- `CODEXHARNESS_MODEL`、`CODEXHARNESS_MODEL_NAME`、`MODEL_NAME`、`OPENAI_MODEL`
- `CODEXHARNESS_BASE_URL`、`OPENAI_BASE_URL`、`BASE_URL`
- `CODEXHARNESS_API_KEY`、`OPENAI_API_KEY`、`API_KEY`
- `CODEXHARNESS_CODEX_MODEL`、`CODEXHARNESS_CODEX_MODEL_NAME`
- `CODEXHARNESS_CODEX_BASE_URL`
- `CODEXHARNESS_CODEX_API_KEY`

建议：

- 如果你希望 harness 和 codex 用不同的模型或不同的 API 网关，优先使用 `CODEXHARNESS_*` 和 `CODEXHARNESS_CODEX_*`
- 如果你只配置全局 `OPENAI_*`，那么 harness 和 codex 仍可能共用同一套全局配置

推荐做法：

- 复制 [`.env.example`](c:\Users\24260\Desktop\研究生生涯\智能体开发范式\codexharness\.env.example) 为 `.env`
- 把真实密钥写进 `.env`
- `.gitignore` 已忽略 `.env`，避免误提交

优先级规则：

- 显式 CLI 参数优先，例如 `--model`
- `--codex-model` 只覆盖子进程里的 Codex CLI 模型
- 其次是 `.env`
- 最后才是代码中的默认值

## 快速开始

下面分两种使用方式：

- 如果你在上层仓库根目录执行命令，使用“仓库根目录方式”
- 如果你已经进入 `codexharness/` 目录，使用“子目录方式”

### 仓库根目录方式

以下命令在上层仓库根目录执行，例如：

`C:\Users\24260\Desktop\研究生生涯\智能体开发范式`

```powershell
py -3.13 -m pip install -e .
py -3.13 -m pip install -e .\codexharness
codexharness init --project-root .
codexharness run --project-root . --workspace-mode git-worktree --prompt "为当前仓库生成一份架构巡检清单"
```

如果你不想单独安装 `codexharness`，也可以直接：

```powershell
$env:PYTHONPATH = ".\\codexharness\\src"
py -3.13 -m codexharness run --project-root . --workspace-mode git-worktree --prompt "检查当前项目结构"
```

恢复最近一次 checkpoint：

```powershell
$env:PYTHONPATH = ".\\codexharness\\src"
py -3.13 -m codexharness resume --project-root . --latest --workspace-mode git-worktree
```

### 子目录方式

以下命令在当前 `codexharness/` 目录执行：

`C:\Users\24260\Desktop\研究生生涯\智能体开发范式\codexharness`

```powershell
py -3.13 -m pip install -e .
$env:PYTHONPATH = ".\\src"
py -3.13 -m codexharness init --project-root .
py -3.13 -m codexharness run --project-root . --workspace-mode shared --prompt "检查当前 codexharness 子工程结构"
```

如果你想显式指定 `.env` 文件：

```powershell
$env:PYTHONPATH = ".\\src"
py -3.13 -m codexharness run --project-root . --env-file .\.env --prompt "检查当前项目结构"
```

如果你要单独覆盖子任务 Codex 的模型：

```powershell
$env:PYTHONPATH = ".\\src"
py -3.13 -m codexharness run --project-root . --codex-model gpt-5.3-codex --prompt "检查当前项目结构"
```

## Windows 启动脚本

为了在 Windows 下更方便地启动项目，仓库内新增了两个脚本：

- `start_codexharness.ps1`：PowerShell 主启动脚本
- `start_codexharness.bat`：双击可用的包装脚本

这两个脚本位于当前目录下，默认行为如下：

- 自动查找可用的 `Python 3.10+`
- 自动把 `src/` 加入 `PYTHONPATH`
- 自动检查 `codex` CLI 是否可用
- 启动前自动执行一次 `codexharness init`
- 通过 `--prompt-file` 传入提示词，避免 Windows 命令行转义问题
- 支持通过 `-EnvFile` 把指定 `.env` 传给 Python 入口
- 支持通过 `-CodexModel` 单独覆盖子任务 Codex 的模型

### 交互式启动

在 `codexharness/` 目录下执行：

```powershell
.\start_codexharness.ps1
```

脚本会提示你输入提示词，支持多行输入。输入完成后，单独输入 `END` 并回车即可开始运行。

如果你更习惯双击启动，也可以直接运行：

```bat
start_codexharness.bat
```

### 直接传入提示词

```powershell
.\start_codexharness.ps1 -Prompt "检查当前项目结构并给出改进建议"
```

如果配置不放在默认 `.env`，也可以显式指定：

```powershell
.\start_codexharness.ps1 -EnvFile ".\.env" -Prompt "检查当前项目结构并给出改进建议"
```

如果你只想临时改子任务 Codex 的模型：

```powershell
.\start_codexharness.ps1 -CodexModel "gpt-5.3-codex" -Prompt "检查当前项目结构并给出改进建议"
```

### 常用参数

```powershell
.\start_codexharness.ps1 `
  -ProjectRoot "C:\Users\24260\Desktop\研究生生涯\智能体开发范式" `
  -WorkspaceMode git-worktree `
  -Prompt "为当前仓库生成一份架构巡检清单"
```

常用可选参数：

- `-ProjectRoot`：指定要操作的项目根目录。默认是当前 `codexharness` 目录
- `-WorkspaceMode`：可选 `shared`、`git-worktree`、`copy`
- `-EnvFile`：指定要加载的 `.env` 文件
- `-Prompt`：直接传入单行提示词，跳过交互输入
- `-Model`：覆盖默认模型名
- `-CodexModel`：只覆盖子任务 Codex CLI 的模型
- `-CodexBinary`：指定 `codex` 可执行文件路径
- `-SkipGitRepoCheck`：为子任务传递 `--codex-skip-git-repo-check`
- `-DisableHumanFeedback`：关闭 AgentTorch human feedback
- `-DryRun`：只打印即将执行的命令，不真正启动

### 使用建议

- 如果你要让 harness 操作整个仓库，而不是只操作 `codexharness/` 子目录，建议显式传入上层仓库路径，例如 `-ProjectRoot ".."`
- 写任务优先使用 `-WorkspaceMode git-worktree`
- 第一次运行前，请确认当前 Python 环境已经安装 `codexharness` 依赖；脚本会做导入检查，但不会自动执行 `pip install`
- README 中的“仓库根目录方式”和“子目录方式”不要混用；两套命令的当前工作目录不同

## 测试运行

推荐先在 `codexharness/` 目录下执行一键自检脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_windows.ps1
```

这个脚本会自动完成：

- 给当前会话补上 `src/` 到 `PYTHONPATH`
- 验证 `codexharness` CLI 是否可导入、`--help` 是否正常
- 执行一次 `init`
- 验证 `start_codexharness.ps1` 的参数拼装
- 编译检查 `src/` 和 `scripts/`
- 运行离线 smoke test

可选参数：

- `-SkipSmokeTest`：只做启动前检查，不跑完整 smoke test
- `-KeepTemp`：保留 smoke test 的临时 Git 仓库，方便手动检查产物

注意：

- 如果你是在 `codexharness/` 子目录里直接运行 `py -m codexharness ...`，需要先执行 `py -3.13 -m pip install -e .`，或者先设置 `$env:PYTHONPATH = ".\src"`；否则 Python 默认找不到 `src/codexharness`
- 如果你只是想在 Windows 上直接启动，优先用 `.\start_codexharness.ps1` 或 `start_codexharness.bat`

如果你想先验证项目“能不能完整跑通”，而不依赖真实 OpenAI 接口和真实 Codex CLI，可以直接运行仓库内置的离线 smoke test：

```powershell
py -3.13 .\scripts\run_local_smoke_test.py
```

这个测试会自动完成这些动作：

- 启动一个本地假的 OpenAI-compatible HTTP 服务，供 `codexharness` 自己的 planner / reviewer / integrator 使用
- 调用仓库内置的 `scripts\mock_codex.cmd`，模拟子进程里的 `codex exec --json`
- 创建一个临时 Git 仓库，作为 `--project-root`
- 实际执行一次 `codexharness run`
- 校验最终状态是否为 `completed`
- 校验子任务是否真的写出了 `smoke_output.txt` 和 `codex_mock_meta.json`
- 校验 `codex` 子进程拿到的是独立的 `CODEXHARNESS_CODEX_*` 配置

如果你希望保留临时目录，方便手动检查测试产物：

```powershell
py -3.13 .\scripts\run_local_smoke_test.py --keep-temp
```

离线 smoke test 适合验证：

- CLI 入口是否正常
- `.env` 加载是否正常
- `codexharness` 自己的模型配置是否正常
- 子进程 `codex` 的独立 `model/api/base_url` 配置是否正常
- `run -> child codex -> review -> integrate` 的最小闭环是否正常

如果你要测试真实接口，再把 `.env` 换成你自己的真实配置，然后运行：

```powershell
$env:PYTHONPATH = ".\\src"
py -3.13 -m codexharness run --project-root . --env-file .\.env --prompt "检查当前项目结构并给出改进建议"
```

## 当前限制

- `v1` 只实现 `codex exec --json`
- `run` 通过真实 `codex exec` 启动子任务
- follow-up / checkpoint 恢复优先走真实 `codex exec resume`
- 写任务建议显式使用 `--workspace-mode git-worktree`
- 还没有实现真正的交互式长驻 Codex 终端
