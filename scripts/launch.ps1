param([ValidateRange(1, 65535)][int]$Port = 8000, [switch]$NoBrowser)
# Inicia o LocaControl sem terminal aberto. O ponto de entrada app.server confere a pasta de
# dados, obtém o bloqueio de instância única, aplica atualizações de schema com cópia prévia e
# sobe o servidor; este script o executa em segundo plano, aguarda a saúde e abre o navegador.
. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython

$Url = "http://127.0.0.1:$Port"
$LogDir = Join-Path $DataDir 'logs'
$PidFile = Join-Path $DataDir 'locacontrol.pid'
$Backend = Join-Path $ProjectRoot 'backend'
# Códigos de saída de app.server.
$AlreadyRunning = 3
$DataUnavailable = 4

function Test-Health {
    try { return (Invoke-RestMethod -Uri "$Url/health" -TimeoutSec 3).status -eq 'ok' } catch { return $false }
}

function Open-App {
    if (-not $NoBrowser) { Start-Process $Url }
}

if (Test-Health) {
    Write-Host "LocaControl já está em execução em $Url."
    Open-App
    return
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "A porta $Port está em uso por outro programa. Feche-o ou inicie com -Port <outra porta>."
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'frontend\dist\index.html'))) {
    throw 'A interface ainda não foi compilada. Execute scripts\update.ps1 uma vez antes de iniciar.'
}

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = $Backend
    # Preparação em primeiro plano: as mensagens (cópia prévia, primeiro acesso) aparecem aqui.
    # No PowerShell 5.1, texto no stderr de um programa vira erro fatal sob 'Stop'.
    $ErrorActionPreference = 'Continue'
    & $ProjectPython -m app.server --prepare
    $Prepared = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($Prepared -eq $AlreadyRunning) {
        Write-Host 'O LocaControl já está em execução com estes dados (talvez em outra porta).'
        return
    }
    if ($Prepared -eq $DataUnavailable) { throw 'A pasta de dados está indisponível; veja a mensagem acima.' }
    if ($Prepared -ne 0) { throw "A preparação do banco falhou (código $Prepared)." }

    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    # Start-Process não coloca aspas nos argumentos: o caminho com espaços precisa delas.
    $ServerArguments = @('-m', 'app.server', '--port', "$Port")
    $Process = Start-Process -FilePath $ProjectPython -ArgumentList $ServerArguments -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir 'web.stdout.log') `
        -RedirectStandardError (Join-Path $LogDir 'web.stderr.log')
    Set-Content -LiteralPath $PidFile -Value $Process.Id -Encoding ascii

    $Ready = $false
    foreach ($Attempt in 1..40) {
        if ($Process.HasExited) { break }
        if (Test-Health) { $Ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $Ready) {
        if (-not $Process.HasExited) { Stop-Process -Id $Process.Id -Force }
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Get-Content -LiteralPath (Join-Path $LogDir 'web.stderr.log') -Tail 15 -ErrorAction SilentlyContinue
        throw "O LocaControl não iniciou. Veja $LogDir\web.stderr.log."
    }
    Write-Host "LocaControl iniciado em $Url (processo $($Process.Id)). Para encerrar, use 'Parar LocaControl'."
    Open-App
} finally {
    Pop-Location
}
