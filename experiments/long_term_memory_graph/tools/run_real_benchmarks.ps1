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

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $OutputDir) {
    $suffix = if ($ShardId -ge 0 -and $NumShards -gt 0) { "_shard_${ShardId}_of_${NumShards}" } else { "" }
    $OutputDir = "artifacts/long_term_memory_graph/${Suite}_real_benchmark${suffix}"
}

if (-not $Model) {
    throw "请显式传入 -Model，避免环境中模型别名不一致。"
}

if (-not $JudgeModelBackend -and $JudgeBackend -eq "model_judge") {
    $JudgeModelBackend = $ModelBackend
}

if (-not $JudgeModel -and $JudgeBackend -eq "model_judge") {
    $JudgeModel = $Model
}

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
    $command += "--no-env-file"
} else {
    $command += @("--env-file", $EnvFile)
}

if ($Suite -eq "compare") {
    if ($Methods) {
        $command += @("--methods", $Methods)
    } elseif ($EnableProxyExtension) {
        $command += "--include-proxy-extension"
    }
}

if ($Suite -eq "ablate" -and $Variants) {
    $command += @("--variants", $Variants)
}

Write-Host ("[ltmg] " + ($command -join " ")) -ForegroundColor Cyan
& $command[0] $command[1..($command.Length - 1)]
