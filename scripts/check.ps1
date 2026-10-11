. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython
Push-Location $ProjectRoot
try {
    Invoke-Checked -Executable $ProjectPython -Arguments @('-m', 'ruff', 'check', 'backend', 'scripts/smoke.py', 'scripts/e2e-auth.py')
    Invoke-Checked -Executable $ProjectPython -Arguments @('-m', 'ruff', 'format', '--check', 'backend', 'scripts/smoke.py', 'scripts/e2e-auth.py')
    Invoke-Checked -Executable 'npm.cmd' -Arguments @('--prefix', 'frontend', 'run', 'lint')
    Invoke-Checked -Executable 'npm.cmd' -Arguments @('--prefix', 'frontend', 'run', 'format:check')
    Invoke-Checked -Executable 'npm.cmd' -Arguments @('--prefix', 'frontend', 'run', 'build')
} finally {
    Pop-Location
}
