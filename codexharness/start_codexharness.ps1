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

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ResolvedProjectRoot = (Resolve-Path -LiteralPath $ScriptRoot).Path
}
else {
    $ResolvedProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$srcPath = Join-Path $ScriptRoot "src"
$pathSeparator = [System.IO.Path]::PathSeparator
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $srcPath
}
else {
    $pythonPathEntries = $env:PYTHONPATH -split [regex]::Escape($pathSeparator)
    if ($pythonPathEntries -notcontains $srcPath) {
        $env:PYTHONPATH = "$srcPath$pathSeparator$env:PYTHONPATH"
    }
}

function Get-PythonLauncher {
    $candidates = @(
        @{ Command = "py"; Args = @("-3.13") },
        @{ Command = "py"; Args = @("-3.12") },
        @{ Command = "py"; Args = @("-3.11") },
        @{ Command = "py"; Args = @("-3.10") },
        @{ Command = "python"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) {
            continue
        }

        try {
            & $candidate.Command @($candidate.Args + @("-c", "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)")) *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
        catch {
        }
    }

    throw "Python 3.10+ was not found. Install Python first, or make sure the py/python command is available."
}

function Test-PythonRuntime {
    param(
        [hashtable]$PythonLauncher
    )

    $checkCode = @"
import codexharness
import pydantic
"@

    & $PythonLauncher.Command @($PythonLauncher.Args + @("-c", $checkCode)) *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "The current Python environment is missing dependencies for codexharness. Run: py -3.13 -m pip install -e ."
    }
}

function Resolve-CodexBinary {
    param(
        [string]$Preferred
    )

    if (-not [string]::IsNullOrWhiteSpace($Preferred)) {
        if (Get-Command $Preferred -ErrorAction SilentlyContinue) {
            return $Preferred
        }
        if (Test-Path -LiteralPath $Preferred) {
            return (Resolve-Path -LiteralPath $Preferred).Path
        }
        throw "The specified Codex CLI was not found: $Preferred"
    }

    if (Get-Command "codex" -ErrorAction SilentlyContinue) {
        return "codex"
    }
    if (Get-Command "codex.cmd" -ErrorAction SilentlyContinue) {
        return "codex.cmd"
    }
    if (Get-Command "codex.exe" -ErrorAction SilentlyContinue) {
        return "codex.exe"
    }

    if (-not [string]::IsNullOrWhiteSpace($env:APPDATA)) {
        $npmCodex = Join-Path $env:APPDATA "npm\codex.cmd"
        if (Test-Path -LiteralPath $npmCodex) {
            return $npmCodex
        }
    }

    throw "Codex CLI was not found. Install codex first, or pass -CodexBinary / CODEXHARNESS_CODEX_BIN."
}

function Read-InteractivePrompt {
    Write-Host ""
    Write-Host "Enter the prompt. Multi-line input is supported." -ForegroundColor Cyan
    Write-Host "When finished, type END on a new line and press Enter to start." -ForegroundColor DarkCyan
    Write-Host ""

    $lines = New-Object System.Collections.Generic.List[string]
    while ($true) {
        $line = Read-Host
        if ($line -eq "END") {
            break
        }
        [void]$lines.Add($line)
    }

    $value = [string]::Join([Environment]::NewLine, $lines).Trim()
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "The prompt cannot be empty."
    }
    return $value
}

function New-TempPromptFile {
    param(
        [string]$PromptText
    )

    $fileName = "codexharness-prompt-" + [Guid]::NewGuid().ToString("N") + ".txt"
    $filePath = Join-Path ([System.IO.Path]::GetTempPath()) $fileName
    [System.IO.File]::WriteAllText($filePath, $PromptText, $utf8NoBom)
    return $filePath
}

$python = Get-PythonLauncher
Test-PythonRuntime -PythonLauncher $python

if ([string]::IsNullOrWhiteSpace($Prompt)) {
    $Prompt = Read-InteractivePrompt
}

$resolvedCodexBinary = Resolve-CodexBinary -Preferred $CodexBinary
$promptFile = New-TempPromptFile -PromptText $Prompt

$pythonCommandText = if ($python.Args.Count -gt 0) {
    "$($python.Command) $($python.Args -join ' ')"
}
else {
    $python.Command
}

$initArgs = @(
    "-m", "codexharness",
    "init",
    "--project-root", $ResolvedProjectRoot
)

$runArgs = @(
    "-m", "codexharness",
    "run",
    "--project-root", $ResolvedProjectRoot,
    "--workspace-mode", $WorkspaceMode,
    "--prompt-file", $promptFile,
    "--max-rounds", $MaxRounds,
    "--max-parallel-tasks", $MaxParallelTasks,
    "--planner-max-tasks", $PlannerMaxTasks,
    "--max-task-retries", $MaxTaskRetries,
    "--codex-binary", $resolvedCodexBinary
)

if (-not [string]::IsNullOrWhiteSpace($EnvFile)) {
    $resolvedEnvFile = (Resolve-Path -LiteralPath $EnvFile).Path
    $initArgs += @("--env-file", $resolvedEnvFile)
    $runArgs += @("--env-file", $resolvedEnvFile)
}
if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $runArgs += @("--model", $Model)
}
if (-not [string]::IsNullOrWhiteSpace($CodexModel)) {
    $runArgs += @("--codex-model", $CodexModel)
}
if ($SkipGitRepoCheck) {
    $runArgs += "--codex-skip-git-repo-check"
}
if ($DisableHumanFeedback) {
    $runArgs += "--disable-human-feedback"
}

Write-Host ""
Write-Host "codexharness Windows launcher" -ForegroundColor Green
Write-Host "Project root: $ResolvedProjectRoot"
Write-Host "Python: $pythonCommandText"
Write-Host "Codex CLI: $resolvedCodexBinary"
Write-Host "Workspace mode: $WorkspaceMode"
Write-Host ""

if ($DryRun) {
    Write-Host "Dry run only. The harness will not be started." -ForegroundColor Yellow
    Write-Host "Init command:"
    Write-Host "$pythonCommandText $($initArgs -join ' ')"
    Write-Host ""
    Write-Host "Run command:"
    Write-Host "$pythonCommandText $($runArgs -join ' ')"
    if (Test-Path -LiteralPath $promptFile) {
        Remove-Item -LiteralPath $promptFile -Force
    }
    exit 0
}

$exitCode = 0
Push-Location $ScriptRoot
try {
    & $python.Command @($python.Args + $initArgs)
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        & $python.Command @($python.Args + $runArgs)
        $exitCode = $LASTEXITCODE
    }
}
finally {
    Pop-Location
    if (Test-Path -LiteralPath $promptFile) {
        Remove-Item -LiteralPath $promptFile -Force
    }
}

exit $exitCode
