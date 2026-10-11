. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython
Push-Location $ProjectRoot
try {
    Invoke-Checked -Executable $ProjectPython -Arguments @('-m', 'pytest', 'backend/tests', '-q')
    Invoke-Checked -Executable 'npm.cmd' -Arguments @('--prefix', 'frontend', 'test')
} finally {
    Pop-Location
}
