param([string]$Python = 'python')
. (Join-Path $PSScriptRoot 'common.ps1')

Push-Location $ProjectRoot
try {
    if (-not (Test-Path -LiteralPath $ProjectPython)) {
        Invoke-Checked -Executable $Python -Arguments @('-c', 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ required"')
        Invoke-Checked -Executable $Python -Arguments @('-m', 'venv', '.venv')
    }
    Invoke-Checked -Executable $ProjectPython -Arguments @('-m', 'pip', 'install', '--cache-dir', '.cache/pip', '-r', 'backend/requirements-lock.txt')
    Invoke-Checked -Executable $ProjectPython -Arguments @('-m', 'pip', 'install', '--no-deps', '--no-build-isolation', '-e', './backend')
    Invoke-Checked -Executable 'npm.cmd' -Arguments @('--prefix', 'frontend', 'ci', '--cache', '.cache/npm', '--no-fund', '--no-audit')
    if (-not (Test-Path -LiteralPath '.env')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
    }
    Write-Host 'Setup complete. Run scripts/migrate.ps1, then start-backend.ps1 and start-frontend.ps1.'
} finally {
    Pop-Location
}
