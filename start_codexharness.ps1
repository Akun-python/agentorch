[CmdletBinding()]
param(
    [string]$Prompt,
    [string]$ProjectRoot,
    [string]$EnvFile,
    [ValidateSet("shared", "git-worktree", "copy")]
    [string]$WorkspaceMode = "shared",
    [string]$Model = $env:CODEXHARNESS_MODEL,
    [string]$CodexModel = $env:CODEXHARNESS_CODEX_MODEL,
    [int]$MaxRounds = 3,
    [int]$MaxParallelTasks = 2,
    [int]$PlannerMaxTasks = 4,
    [int]$MaxTaskRetries = 1,
    [string]$CodexBinary = $env:CODEXHARNESS_CODEX_BIN,
    [switch]$SkipGitRepoCheck,
    [switch]$DisableHumanFeedback,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$target = Join-Path $PSScriptRoot "codexharness\start_codexharness.ps1"
if (-not (Test-Path -LiteralPath $target)) {
    throw "The codexharness launcher was not found: $target"
}

$forwardParams = @{}
$resolvedProjectRoot = if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    (Resolve-Path -LiteralPath $PSScriptRoot).Path
}
else {
    (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$forwardParams["ProjectRoot"] = $resolvedProjectRoot
if ($PSBoundParameters.ContainsKey("Prompt")) {
    $forwardParams["Prompt"] = $Prompt
}
if ($PSBoundParameters.ContainsKey("EnvFile")) {
    $forwardParams["EnvFile"] = $EnvFile
}
if ($PSBoundParameters.ContainsKey("WorkspaceMode")) {
    $forwardParams["WorkspaceMode"] = $WorkspaceMode
}
if ($PSBoundParameters.ContainsKey("Model")) {
    $forwardParams["Model"] = $Model
}
if ($PSBoundParameters.ContainsKey("CodexModel")) {
    $forwardParams["CodexModel"] = $CodexModel
}
if ($PSBoundParameters.ContainsKey("MaxRounds")) {
    $forwardParams["MaxRounds"] = $MaxRounds
}
if ($PSBoundParameters.ContainsKey("MaxParallelTasks")) {
    $forwardParams["MaxParallelTasks"] = $MaxParallelTasks
}
if ($PSBoundParameters.ContainsKey("PlannerMaxTasks")) {
    $forwardParams["PlannerMaxTasks"] = $PlannerMaxTasks
}
if ($PSBoundParameters.ContainsKey("MaxTaskRetries")) {
    $forwardParams["MaxTaskRetries"] = $MaxTaskRetries
}
if ($PSBoundParameters.ContainsKey("CodexBinary")) {
    $forwardParams["CodexBinary"] = $CodexBinary
}
if ($SkipGitRepoCheck) {
    $forwardParams["SkipGitRepoCheck"] = $true
}
if ($DisableHumanFeedback) {
    $forwardParams["DisableHumanFeedback"] = $true
}
if ($DryRun) {
    $forwardParams["DryRun"] = $true
}

& $target @forwardParams
exit $LASTEXITCODE
