# Encerra somente o servidor iniciado por launch.ps1, conferindo que o processo é o LocaControl.
. (Join-Path $PSScriptRoot 'common.ps1')
$PidFile = Join-Path $ProjectRoot 'data\locacontrol.pid'
if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host 'LocaControl não está em execução por este atalho.'
    return
}
$ProcessId = 0
if (-not [int]::TryParse((Get-Content -LiteralPath $PidFile -TotalCount 1), [ref]$ProcessId)) {
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host 'Registro de execução inválido removido; nada foi encerrado.'
    return
}
$Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
if ($Process -and $Process.CommandLine -match 'uvicorn' -and $Process.CommandLine -match 'app\.main:app') {
    Stop-Process -Id $ProcessId -Force
    Write-Host 'LocaControl encerrado.'
} else {
    Write-Host 'O processo registrado não é mais o LocaControl; nada foi encerrado.'
}
Remove-Item -LiteralPath $PidFile -Force
