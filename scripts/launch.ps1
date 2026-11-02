param([ValidateRange(1, 65535)][int]$Port = 8000, [switch]$NoBrowser)
# Inicia o LocaControl sem terminal aberto: confere o banco, aplica atualizações de schema
# com cópia prévia, sobe o servidor em segundo plano e abre o navegador.
. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython

$Url = "http://127.0.0.1:$Port"
$DataDir = Join-Path $ProjectRoot 'data'
$LogDir = Join-Path $DataDir 'logs'
$PidFile = Join-Path $DataDir 'locacontrol.pid'
$Backend = Join-Path $ProjectRoot 'backend'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

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
    $Alembic = @('-m', 'alembic', '-c', (Join-Path $Backend 'alembic.ini'))
    $Database = (& $ProjectPython -c "from app.core.config import Settings; from app.persistence.database import resolve_database_url; print(resolve_database_url(Settings().database_url).database or '')" | Out-String).Trim()
    # No PowerShell 5.1, texto no stderr de um programa vira erro fatal sob 'Stop'.
    $ErrorActionPreference = 'Continue'
    $Current = (& $ProjectPython @Alembic current 2>$null | Out-String)
    $ErrorActionPreference = 'Stop'
    if ($Port -ne 8000 -and -not $env:LOCACONTROL_ALLOWED_ORIGINS) {
        # Fora da porta padrão, o endereço usado precisa constar entre as origens aceitas.
        $env:LOCACONTROL_ALLOWED_ORIGINS = "[`"http://127.0.0.1:$Port`",`"http://localhost:$Port`"]"
    }
    if ($Current -notmatch '\(head\)') {
        if ($Database -and (Test-Path -LiteralPath $Database)) {
            # Atualização de schema nunca roda sem uma cópia consistente do banco.
            $BackupDir = Join-Path $DataDir 'backups'
            New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
            $Copy = Join-Path $BackupDir ("pre-upgrade-{0}.db" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
            Invoke-Checked -Executable $ProjectPython -Arguments @('-I', '-c', "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); ok=d.execute('pragma integrity_check').fetchone()[0]; d.close(); s.close(); sys.exit(0 if ok=='ok' else 1)", $Database, $Copy)
            Write-Host "Cópia do banco antes da atualização: $Copy"
        }
        Write-Host 'Aplicando atualizações do banco de dados...'
        Invoke-Checked -Executable $ProjectPython -Arguments ($Alembic + @('upgrade', 'head'))
    }

    # Edição local (ADR-023): sem login, sem conta admin/admin. Lê LOCACONTROL_LOCAL_MODE do
    # ambiente ou do .env pela mesma configuração usada pelo servidor.
    $LocalMode = (& $ProjectPython -c "from app.core.config import Settings; print(Settings().local_mode)" | Out-String).Trim() -eq 'True'
    # Instalação nova, sem nenhum usuário: cria a conta de primeiro acesso.
    $FirstRun = $false
    if (-not $LocalMode) {
        $FirstRun = (& $ProjectPython -m app.auth.cli default | Out-String).Trim() -eq 'CREATED'
    }

    # Start-Process não coloca aspas nos argumentos: o caminho com espaços precisa delas.
    $ServerArguments = @('-m', 'uvicorn', 'app.main:app', '--app-dir', "`"$Backend`"", '--host', '127.0.0.1', '--port', "$Port")
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
        throw 'O LocaControl não iniciou. Veja data\logs\web.stderr.log.'
    }
    Write-Host "LocaControl iniciado em $Url (processo $($Process.Id)). Para encerrar, use 'Parar LocaControl'."
    if ($FirstRun) {
        Write-Host ''
        Write-Host 'PRIMEIRO ACESSO: usuário "admin" e senha "admin".'
        Write-Host 'O sistema exigirá uma nova senha (12 caracteres ou mais) antes de liberar o uso.'
    }
    Open-App
} finally {
    Pop-Location
}
