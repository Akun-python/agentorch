param(
    [ValidateSet("main", "compare", "ablate", "full")]
    [string]$Suite = "compare",
    [string]$EnvFile = ".env",
    [string]$OutputDir = "",
    [string]$ModelBackend = "openai_http",
    [string]$Model = "",
    [string]$JudgeBackend = "model_judge",
    [string]$JudgeModelBackend = "",
    [string]$JudgeModel = "",
    [int]$Runs = 3,
    [int]$Seed = 0,
    [int]$CaseLimit = 0,
    [int]$CaseOffset = 0,
    [int]$ShardId = -1,
    [int]$NumShards = 0,
    [string]$Methods = "",
    [string]$Variants = "",
    [switch]$Resume,
    [switch]$NoEnvFile,
    [switch]$EnableProxyExtension
)

# 真实模型长跑脚本：只拼接命令，不读取或打印密钥。
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $OutputDir) {
    # 默认输出目录带上分片后缀，避免多分片互相覆盖。
    $suffix = if ($ShardId -ge 0 -and $NumShards -gt 0) { "_shard_${ShardId}_of_${NumShards}" } else { "" }
    $OutputDir = "artifacts/long_term_memory_graph/${Suite}_real_benchmark${suffix}"
}

if (-not $Model) {
    # 正式运行强制显式模型，避免误用 shell 里残留的模型别名。
    throw "请显式传入 -Model，避免环境中模型别名不一致。"
}

if (-not $JudgeModelBackend -and $JudgeBackend -eq "model_judge") {
    # 未单独指定 judge 后端时，默认沿用主模型后端。
    $JudgeModelBackend = $ModelBackend
}

if (-not $JudgeModel -and $JudgeBackend -eq "model_judge") {
    # 未单独指定 judge 模型时，默认沿用主模型。
    $JudgeModel = $Model
}

# 统一走包级 CLI，保证 main/compare/ablate/full 的参数含义一致。
$command = @(
    "python",
    "-m",
    "experiments.long_term_memory_graph",
    $Suite,
    "--output-dir",
    $OutputDir,
    "--runs",
    "$Runs",
    "--seed",
    "$Seed",
    "--model-backend",
    $ModelBackend,
    "--model",
    $Model,
    "--judge-backend",
    $JudgeBackend
)

if ($JudgeBackend -eq "model_judge") {
    # 模型裁判必须显式带上后端和模型名。
    $command += @("--judge-model-backend", $JudgeModelBackend, "--judge-model", $JudgeModel)
}

if ($CaseLimit -gt 0) {
    $command += @("--case-limit", "$CaseLimit")
}

if ($CaseOffset -gt 0) {
    $command += @("--case-offset", "$CaseOffset")
}

if ($ShardId -ge 0 -and $NumShards -gt 0) {
    $command += @("--shard-id", "$ShardId", "--num-shards", "$NumShards")
}

if ($Resume) {
    $command += "--resume"
}

if ($NoEnvFile) {
    # 只使用当前进程环境变量。
    $command += "--no-env-file"
} else {
    # 默认仍从指定 env 文件加载，但脚本本身不读取密钥。
    $command += @("--env-file", $EnvFile)
}

if ($Suite -eq "compare") {
    # compare 支持用户指定方法，也支持一键加入 proxy 扩展方法。
    if ($Methods) {
        $command += @("--methods", $Methods)
    } elseif ($EnableProxyExtension) {
        $command += "--include-proxy-extension"
    }
}

if ($Suite -eq "ablate" -and $Variants) {
    # ablate 支持只跑部分消融变体。
    $command += @("--variants", $Variants)
}

Write-Host ("[ltmg] " + ($command -join " ")) -ForegroundColor Cyan
& $command[0] $command[1..($command.Length - 1)]
