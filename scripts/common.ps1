Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
# Mesma regra de app.core.config.data_root(): LOCACONTROL_DATA_DIR do ambiente; sem ela, a pasta data\ do projeto.
$DataDir = if ($env:LOCACONTROL_DATA_DIR) { [IO.Path]::GetFullPath($env:LOCACONTROL_DATA_DIR) } else { Join-Path $ProjectRoot 'data' }

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Executable $($Arguments -join ' ')"
    }
}

function Assert-ProjectPython {
    if (-not (Test-Path -LiteralPath $ProjectPython)) {
        throw 'Virtual environment missing. Run scripts/setup.ps1 -Python <python.exe> first.'
    }
}
