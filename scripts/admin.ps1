param([ValidateSet('bootstrap', 'recover')][string]$Action = 'bootstrap')
. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython
Push-Location $ProjectRoot
try {
    Invoke-Checked -Executable $ProjectPython -Arguments @('-m', 'app.auth.cli', $Action)
} finally {
    Pop-Location
}
