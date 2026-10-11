param([switch]$Lan, [ValidateRange(1, 65535)][int]$Port = 5173)
. (Join-Path $PSScriptRoot 'common.ps1')
$BindAddress = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
Push-Location (Join-Path $ProjectRoot 'frontend')
try {
    Invoke-Checked -Executable 'npm.cmd' -Arguments @('run', 'dev', '--', '--configLoader', 'runner', '--host', $BindAddress, '--port', "$Port")
} finally {
    Pop-Location
}
