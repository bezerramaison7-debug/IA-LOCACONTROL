. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython
Push-Location $ProjectRoot
try {
    Invoke-Checked -Executable $ProjectPython -Arguments @('-m', 'ruff', 'format', 'backend', 'scripts/smoke.py', 'scripts/e2e-auth.py')
    Invoke-Checked -Executable 'npm.cmd' -Arguments @('--prefix', 'frontend', 'run', 'format')
} finally {
    Pop-Location
}
