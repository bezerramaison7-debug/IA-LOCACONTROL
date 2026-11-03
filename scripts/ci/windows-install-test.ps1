# CI (Windows): instala, usa, conecta uma "estação", atualiza e desinstala o LocaControl em modo
# silencioso, conferindo cada passo. Máquina da CI, não homologação: ver docs/P1E_PROPOSTA.md.
param(
    [Parameter(Mandatory)][string]$Setup,
    [Parameter(Mandatory)][string]$Upgrade,
    # SEC-P1E-01: 'relatar' só registra o que uma conta não administradora consegue fazer;
    # 'exigir' falha se ela conseguir ler ou alterar qualquer arquivo protegido.
    [ValidateSet('relatar', 'exigir')][string]$Isolation = 'exigir'
)
$ErrorActionPreference = 'Stop'
$App = Join-Path $env:ProgramFiles 'LocaControl'
$Data = Join-Path $env:ProgramData 'LocaControl'
$Exe = Join-Path $App 'LocaControl.exe'
$Rule = 'LocaControl (HTTPS da loja)'
$Logs = Join-Path $PWD 'ci-logs'
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Assert($Condition, [string]$Message) {
    if (-not $Condition) { throw "FALHOU: $Message" }
    Write-Host "OK: $Message"
}
function Wait-Health {
    for ($i = 0; $i -lt 120; $i++) {
        try { if ((Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 3).status -eq 'ok') { return $true } } catch {}
        Start-Sleep -Seconds 1
    }
    return $false
}
function Install([string]$File, [string[]]$Extra, [string]$Log) {
    $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=$(Join-Path $Logs $Log)") + $Extra
    return (Start-Process $File -ArgumentList $arguments -Wait -PassThru).ExitCode
}
function Session {
    $web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $me = Invoke-RestMethod 'http://127.0.0.1:8000/api/auth/me' -Headers @{ 'X-LocaControl-Request' = '1' } -WebSession $web
    $headers = @{ 'X-LocaControl-Request' = '1'; 'Origin' = 'http://127.0.0.1:8000'; 'X-CSRF-Token' = $me.csrf_token }
    return @{ Web = $web; Headers = $headers }
}
function Rule-Exists { (netsh advfirewall firewall show rule name="$Rule") -match 'LocalSubnet' }

# Conta local comum (sem administrador) usada pela sonda de isolamento (SEC-P1E-01).
$ProbeUser = 'lc-sonda'
$ProbePassword = 'Sd-' + [guid]::NewGuid().ToString('N').Substring(0, 20) + '!a1'
$ProbeDir = 'C:\ci-sonda'
function Invoke-NonAdminProbe([string]$Label) {
    if (-not (Get-LocalUser -Name $ProbeUser -ErrorAction SilentlyContinue)) {
        New-LocalUser -Name $ProbeUser -Password (ConvertTo-SecureString $ProbePassword -AsPlainText -Force) -AccountNeverExpires -PasswordNeverExpires | Out-Null
        Add-LocalGroupMember -Group (Get-LocalGroup -SID 'S-1-5-32-545') -Member $ProbeUser -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $ProbeDir | Out-Null
        icacls $ProbeDir /grant '*S-1-1-0:(OI)(CI)M' | Out-Null
        Copy-Item (Join-Path $PSScriptRoot 'non-admin-probe.ps1') $ProbeDir
    }
    $out = Join-Path $ProbeDir "$Label.json"
    Remove-Item $out -ErrorAction SilentlyContinue
    $pwsh = (Get-Command pwsh).Source
    $arguments = @('-NoProfile', '-NonInteractive', '-File', (Join-Path $ProbeDir 'non-admin-probe.ps1'), '-Data', $Data, '-Out', $out)
    $credential = [pscredential]::new(".\$ProbeUser", (ConvertTo-SecureString $ProbePassword -AsPlainText -Force))
    try {
        Start-Process $pwsh -Credential $credential -ArgumentList $arguments -WorkingDirectory $ProbeDir -WindowStyle Hidden -Wait | Out-Null
    } catch { Write-Host "Start-Process com outra conta falhou ($($_.Exception.Message)); usando tarefa agendada." }
    if (-not (Test-Path $out)) {
        $quoted = ($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
        $action = New-ScheduledTaskAction -Execute $pwsh -Argument $quoted -WorkingDirectory $ProbeDir
        Register-ScheduledTask -TaskName 'LocaControlSonda' -Action $action -User $ProbeUser -Password $ProbePassword -RunLevel Limited -Force | Out-Null
        Start-ScheduledTask -TaskName 'LocaControlSonda'
        for ($i = 0; $i -lt 60 -and -not (Test-Path $out); $i++) { Start-Sleep -Seconds 1 }
        Unregister-ScheduledTask -TaskName 'LocaControlSonda' -Confirm:$false
    }
    Assert (Test-Path $out) "sonda executada como conta comum ($Label)"
    $result = Get-Content $out -Raw | ConvertFrom-Json
    Write-Host "Sonda ($Label): $($result | ConvertTo-Json -Compress)"
    Assert (-not $result.administrador) "a sonda rodou sem privilégio de administrador ($($result.conta))"
    $exposed = @('le_banco', 'altera_banco', 'le_env', 'altera_env', 'altera_estacoes', 'le_chave_ca', 'le_senha_protegida', 'cria_arquivo', 'decifra_senha', 'abre_chave_ca') |
        Where-Object { $result.$_ }
    if ($Isolation -eq 'relatar') {
        if ($exposed) { Write-Host "REPRODUZIDO (SEC-P1E-01): conta comum consegue: $($exposed -join ', ')" }
        else { Write-Host 'Conta comum sem acesso aos arquivos protegidos.' }
    } else {
        Assert (-not $exposed) "conta comum sem acesso a banco, .env, estações e chaves ($Label)$(if ($exposed) { ': ' + ($exposed -join ', ') })"
    }
    return $result
}

try {
    # 1. Instalação como computador principal com a rede da loja.
    Assert ((Install $Setup @('/MODO=principal', '/REDE=1') 'instalacao.log') -eq 0) 'instalador terminou com código 0'
    Assert (Test-Path $Exe) 'programa em Arquivos de Programas'
    $envFile = Join-Path $Data '.env'
    Assert ((Get-Content $envFile) -contains 'LOCACONTROL_NETWORK_MODE=true') '.env com o modo rede'
    Assert ((Get-Content $envFile) -contains 'LOCACONTROL_LOCAL_MODE=true') '.env com a edição local'
    Assert (Rule-Exists) 'regra de firewall limitada à sub-rede local'
    Add-Content -Path $envFile -Value 'LOCACONTROL_COMPANY_NAME=Loja de Teste CI'

    # 2. Início (como o atalho de inicialização) e dados comerciais de teste.
    Start-Process $Exe -ArgumentList 'servir'
    Assert (Wait-Health) 'servidor respondeu em http://127.0.0.1:8000'
    Assert (Test-Path (Join-Path $Data 'tls\ca.pem')) 'autoridade certificadora local criada'
    Invoke-NonAdminProbe 'instalacao' | Out-Null
    $s = Session
    $body = @{ person_type = 'PF'; legal_name = 'Cliente CI'; document = '52998224725'; addresses = @(@{ street = 'Rua Um'; city = 'São Paulo'; state = 'SP'; postal_code = '01001000' }) } | ConvertTo-Json -Depth 4
    Invoke-RestMethod 'http://127.0.0.1:8000/api/customers' -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($body)) -ContentType 'application/json; charset=utf-8' -Headers $s.Headers -WebSession $s.Web | Out-Null
    Assert ((Invoke-RestMethod 'http://127.0.0.1:8000/api/customers' -WebSession $s.Web).total -eq 1) 'cliente gravado'

    # 3. HTTPS: o Windows recusa antes de confiar na CA; HTTP não escuta na rede.
    # O endereço privado que o próprio servidor pôs no certificado (o que uma estação digitaria).
    $overview = Invoke-RestMethod 'http://127.0.0.1:8000/api/stations' -WebSession $s.Web
    Assert ($overview.tls.available) 'HTTPS da loja disponível'
    $ip = $overview.tls.server_addresses | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' -and $_ -notmatch '^127\.' } | Select-Object -First 1
    Assert ($ip) "endereço privado no certificado do servidor: $ip"
    $untrusted = $true
    try { Invoke-WebRequest "https://${ip}:8443/health" -UseBasicParsing -TimeoutSec 10 | Out-Null } catch { $untrusted = $false }
    Assert (-not $untrusted) 'HTTPS recusado pelo Windows antes de confiar na CA'
    $lanHttp = $true
    try { Invoke-WebRequest "http://${ip}:8000/health" -UseBasicParsing -TimeoutSec 5 | Out-Null } catch { $lanHttp = $false }
    Assert (-not $lanHttp) 'HTTP não escuta na rede'

    # 4. "Conectar à loja": código errado recusa; código certo instala a confiança.
    $code = Invoke-RestMethod 'http://127.0.0.1:8000/api/stations/pairing' -Method Post -Headers $s.Headers -WebSession $s.Web
    $wrong = (Start-Process $Exe -ArgumentList 'conectar', '--servidor', $ip, '--codigo', 'AAAA-AAAA-AAAA-AAAA-AAAA-AAAA-AA', '--sem-navegador' -Wait -PassThru).ExitCode
    Assert ($wrong -eq 2) 'código errado: nada instalado (código 2)'
    Assert (-not (Test-Path (Join-Path $Data 'station.json'))) 'nenhum registro de estação com o código errado'
    $right = (Start-Process $Exe -ArgumentList 'conectar', '--servidor', $ip, '--codigo', $code.code, '--sem-navegador' -Wait -PassThru).ExitCode
    Assert ($right -eq 0) 'código certo: confiança instalada'
    $thumb = (Get-Content (Join-Path $Data 'station.json') -Raw | ConvertFrom-Json).ca_thumbprint
    Assert (Test-Path "Cert:\LocalMachine\Root\$thumb") 'CA da loja no repositório Raiz da máquina'
    $trusted = Invoke-WebRequest "https://${ip}:8443/health" -UseBasicParsing -TimeoutSec 15
    Assert ($trusted.StatusCode -eq 200) 'HTTPS validado pelo Windows depois de confiar na CA'
    Start-Process $Exe -ArgumentList 'desconectar' -Wait
    Assert (-not (Test-Path "Cert:\LocalMachine\Root\$thumb")) 'desconectar removeu a CA'

    # 5. Atualização com o servidor em execução: dados e configuração preservados.
    Assert ((Install $Upgrade @() 'atualizacao.log') -eq 0) 'atualização terminou com código 0'
    Assert ((Get-Content $envFile) -contains 'LOCACONTROL_COMPANY_NAME=Loja de Teste CI') 'linha própria do .env preservada'
    Assert ((Get-Content $envFile) -contains 'LOCACONTROL_NETWORK_MODE=true') 'escolha anterior reaproveitada (modo rede)'
    Start-Process $Exe -ArgumentList 'servir'
    Assert (Wait-Health) 'servidor voltou depois da atualização'
    $s = Session
    Assert ((Invoke-RestMethod 'http://127.0.0.1:8000/api/customers' -WebSession $s.Web).total -eq 1) 'cliente preservado na atualização'

    # 6. Desinstalação silenciosa: programa e firewall removidos, dados preservados.
    Assert ((Start-Process (Join-Path $App 'unins000.exe') -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru).ExitCode -eq 0) 'desinstalador terminou com código 0'
    for ($i = 0; $i -lt 60 -and (Test-Path $Exe); $i++) { Start-Sleep -Seconds 1 }
    Assert (-not (Test-Path $Exe)) 'programa removido'
    Assert (Test-Path (Join-Path $Data 'locacontrol.db')) 'banco preservado na desinstalação'
    Assert (-not (Rule-Exists)) 'regra de firewall removida'
    Write-Host 'PASS: instalação, uso, conexão de estação, atualização e desinstalação no Windows da CI.'
} finally {
    Copy-Item (Join-Path $Data 'logs\*') $Logs -ErrorAction SilentlyContinue
    Copy-Item (Join-Path $ProbeDir '*.json') $Logs -ErrorAction SilentlyContinue
    Remove-LocalUser -Name $ProbeUser -ErrorAction SilentlyContinue
}
# Chegou aqui = todas as conferências passaram; o último netsh (regra já removida) devolve 1.
exit 0
