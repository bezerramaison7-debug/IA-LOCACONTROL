param([switch]$Lan, [switch]$Reload, [ValidateRange(1, 65535)][int]$Port = 8000)
. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython
$BindAddress = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
$BackendArguments = @('-m', 'uvicorn', 'app.main:app', '--app-dir', (Join-Path $ProjectRoot 'backend'), '--host', $BindAddress, '--port', "$Port")
if ($Reload) { $BackendArguments += @('--reload', '--reload-dir', (Join-Path $ProjectRoot 'backend')) }
Push-Location $ProjectRoot
try {
    Invoke-Checked -Executable $ProjectPython -Arguments $BackendArguments
} finally {
    Pop-Location
}
