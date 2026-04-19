[CmdletBinding()]
param(
    [switch]$SkipSmokeTest,
    [switch]$KeepTemp
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$srcPath = Join-Path $RepoRoot "src"
$mockCodexBinary = Join-Path $PSScriptRoot "mock_codex.cmd"
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

    throw "Python 3.10+ was not found."
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $RepoRoot
    )

    $displayCommand = if ($Arguments.Count -gt 0) {
        "$Command $($Arguments -join ' ')"
    }
    else {
        $Command
    }

    Write-Host ""
    Write-Host "[$Title]" -ForegroundColor Cyan
    Write-Host $displayCommand

    Push-Location $WorkingDirectory
    try {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Step '$Title' failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

$python = Get-PythonLauncher
$pythonCommandText = if ($python.Args.Count -gt 0) {
    "$($python.Command) $($python.Args -join ' ')"
}
else {
    $python.Command
}

Write-Host "codexharness Windows test runner" -ForegroundColor Green
Write-Host "Repo root: $RepoRoot"
Write-Host "Python: $pythonCommandText"
Write-Host "PYTHONPATH: $env:PYTHONPATH"

Invoke-Step -Title "CLI help" -Command $python.Command -Arguments ($python.Args + @("-m", "codexharness", "--help"))
Invoke-Step -Title "Runtime init" -Command $python.Command -Arguments ($python.Args + @("-m", "codexharness", "init", "--project-root", $RepoRoot))
Invoke-Step -Title "Launcher dry run" -Command "powershell" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $RepoRoot "start_codexharness.ps1"),
    "-Prompt", "smoke",
    "-DryRun",
    "-CodexBinary", $mockCodexBinary
)
Invoke-Step -Title "Compileall" -Command $python.Command -Arguments ($python.Args + @("-m", "compileall", "src", "scripts"))

if (-not $SkipSmokeTest) {
    $smokeArgs = @(".\scripts\run_local_smoke_test.py")
    if ($KeepTemp) {
        $smokeArgs += "--keep-temp"
    }

    Invoke-Step -Title "Offline smoke test" -Command $python.Command -Arguments ($python.Args + $smokeArgs)
}

Write-Host ""
Write-Host "All codexharness Windows checks passed." -ForegroundColor Green
if ($SkipSmokeTest) {
    Write-Host "Smoke test was skipped."
}
else {
    Write-Host "Smoke test used the local mock server and mock Codex CLI."
}
