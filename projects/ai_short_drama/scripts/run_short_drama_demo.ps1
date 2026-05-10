$projectRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $projectRoot "configs\\short_drama_demo.example.json"
$entryPath = Join-Path $projectRoot "backend\\main.py"

py $entryPath --config $configPath
