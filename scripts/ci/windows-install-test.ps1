# CI (Windows): instala, usa, conecta uma "estação", atualiza sob carga, reinstala e desinstala o
# LocaControl em modo silencioso, conferindo cada passo. Máquina da CI, não homologação: ver
# docs/VALIDATION.md. Revisão do PR #8: SEC-P1E-01 (identidade do serviço, ACLs, conta comum sem
# acesso), REL-P1E-02 (atualização sob carga sem perda nem corrupção), UX-P1E-03 (estação: código
# de saída e nada instalado sem a identidade conferida).
param(
    [Parameter(Mandatory)][string]$Setup,
    [Parameter(Mandatory)][string]$Upgrade,
    # Python e backend do checkout, para um "computador principal" de teste na porta 18443 que a
    # estação instalada pelo instalador vai conectar (a mesma máquina faz os dois papéis).
    [Parameter(Mandatory)][string]$DevPython,
    [Parameter(Mandatory)][string]$Backend,
    # 'relatar' só registra o que uma conta não administradora consegue fazer; 'exigir' falha.
    [ValidateSet('relatar', 'exigir')][string]$Isolation = 'exigir'
)
$ErrorActionPreference = 'Stop'
$App = Join-Path $env:ProgramFiles 'LocaControl'
$Data = Join-Path $env:ProgramData 'LocaControl'
$Exe = Join-Path $App 'LocaControl.exe'
$Rule = 'LocaControl (HTTPS da loja)'
$Service = 'LocaControl'
$Logs = Join-Path $PWD 'ci-logs'
$Setup = (Resolve-Path $Setup).Path
$Upgrade = (Resolve-Path $Upgrade).Path
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Assert($Condition, [string]$Message) {
    if (-not $Condition) { throw "FALHOU: $Message" }
    Write-Host "OK: $Message"
}
function Wait-Health([int]$Port = 8000) {
    for ($i = 0; $i -lt 180; $i++) {
        try { if ((Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 3).status -eq 'ok') { return $true } } catch {}
        Start-Sleep -Seconds 1
    }
    return $false
}
function Install([string]$File, [string[]]$Extra, [string]$Log) {
    $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=$(Join-Path $Logs $Log)") + $Extra
    return (Start-Process $File -ArgumentList $arguments -Wait -PassThru).ExitCode
}
function Run-Exe([string[]]$Arguments) {
    return (Start-Process $Exe -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden).ExitCode
}
function Session([int]$Port = 8000) {
    $web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $me = Invoke-RestMethod "http://127.0.0.1:$Port/api/auth/me" -Headers @{ 'X-LocaControl-Request' = '1' } -WebSession $web
    $headers = @{ 'X-LocaControl-Request' = '1'; 'Origin' = "http://127.0.0.1:$Port"; 'X-CSRF-Token' = $me.csrf_token }
    return @{ Web = $web; Headers = $headers; Port = $Port }
}
function Post($S, [string]$Path, $Body = $null) {
    $json = if ($null -ne $Body) { [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 5)) } else { $null }
    return Invoke-RestMethod "http://127.0.0.1:$($S.Port)$Path" -Method Post -Body $json -ContentType 'application/json; charset=utf-8' -Headers $S.Headers -WebSession $S.Web
}
function Rule-Exists { (netsh advfirewall firewall show rule name="$Rule") -match 'LocalSubnet' }
function Python-Db([string]$Code) {
    # Leitura só (mode=ro) do banco, como administrador, com o Python do checkout.
    $out = & $DevPython -c "import pathlib, sqlite3, sys; c = sqlite3.connect(pathlib.Path(sys.argv[1]).as_uri() + '?mode=ro', uri=True); $Code" (Join-Path $Data 'locacontrol.db')
    if ($LASTEXITCODE -ne 0) { throw "Python falhou: $Code" }
    return $out
}

# ---- conta local comum (sem administrador) ------------------------------------------------
$ProbeUser = 'lc-sonda'
$ProbePassword = 'Sd-' + [guid]::NewGuid().ToString('N').Substring(0, 20) + '!a1'
$ProbeDir = 'C:\ci-sonda'
function Initialize-ProbeUser {
    if (Get-LocalUser -Name $ProbeUser -ErrorAction SilentlyContinue) { return }
    New-LocalUser -Name $ProbeUser -Password (ConvertTo-SecureString $ProbePassword -AsPlainText -Force) -AccountNeverExpires -PasswordNeverExpires | Out-Null
    Add-LocalGroupMember -Group (Get-LocalGroup -SID 'S-1-5-32-545') -Member $ProbeUser -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $ProbeDir | Out-Null
    icacls $ProbeDir /grant '*S-1-1-0:(OI)(CI)M' | Out-Null
    Copy-Item (Join-Path $PSScriptRoot 'non-admin-probe.ps1') $ProbeDir
}
function Invoke-AsProbeUser([string]$Label, [string]$Body) {
    Initialize-ProbeUser
    $done = Join-Path $ProbeDir "$Label.done"
    Remove-Item $done -ErrorAction SilentlyContinue
    $script = Join-Path $ProbeDir "$Label.ps1"
    Set-Content -Path $script -Encoding utf8 -Value ($Body + "`r`nSet-Content -Path '$done' -Value 'ok'")
    $pwsh = (Get-Command pwsh).Source
    $arguments = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $script)
    $credential = [pscredential]::new(".\$ProbeUser", (ConvertTo-SecureString $ProbePassword -AsPlainText -Force))
    try {
        Start-Process $pwsh -Credential $credential -ArgumentList $arguments -WorkingDirectory $ProbeDir -WindowStyle Hidden -LoadUserProfile -Wait | Out-Null
    } catch { Write-Host "Start-Process com outra conta falhou ($($_.Exception.Message)); usando tarefa agendada." }
    if (-not (Test-Path $done)) {
        $quoted = ($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
        $action = New-ScheduledTaskAction -Execute $pwsh -Argument $quoted -WorkingDirectory $ProbeDir
        Register-ScheduledTask -TaskName 'LocaControlSonda' -Action $action -User $ProbeUser -Password $ProbePassword -RunLevel Limited -Force | Out-Null
        Start-ScheduledTask -TaskName 'LocaControlSonda'
        for ($i = 0; $i -lt 120 -and -not (Test-Path $done); $i++) { Start-Sleep -Seconds 1 }
        Unregister-ScheduledTask -TaskName 'LocaControlSonda' -Confirm:$false
    }
    Assert (Test-Path $done) "executado como conta comum ($Label)"
}
function Invoke-NonAdminProbe([string]$Label) {
    $out = Join-Path $ProbeDir "$Label.json"
    Remove-Item $out -ErrorAction SilentlyContinue
    Invoke-AsProbeUser "sonda-$Label" "& '$ProbeDir\non-admin-probe.ps1' -Data '$Data' -Out '$out'"
    $result = Get-Content $out -Raw | ConvertFrom-Json
    Write-Host "Sonda ($Label): $($result | ConvertTo-Json -Compress)"
    Assert (-not $result.administrador) "a sonda rodou sem privilégio de administrador ($($result.conta))"
    $exposed = @('le_banco', 'altera_banco', 'le_env', 'altera_env', 'altera_estacoes', 'le_chave_ca', 'le_senha_protegida', 'cria_arquivo', 'decifra_senha', 'abre_chave_ca') |
        Where-Object { $result.$_ }
    if ($Isolation -eq 'relatar') {
        if ($exposed) { Write-Host "REPRODUZIDO (SEC-P1E-01): conta comum consegue: $($exposed -join ', ')" }
    } else {
        Assert (-not $exposed) "conta comum sem acesso a banco, .env, estações e chaves ($Label)$(if ($exposed) { ': ' + ($exposed -join ', ') })"
    }
}
function Assert-DataAcl([string]$Label, [bool]$WithService = $true) {
    $acl = Get-Acl $Data
    Assert $acl.AreAccessRulesProtected "pasta de dados sem herança da pasta-mãe ($Label)"
    $sids = foreach ($rule in $acl.Access) {
        try { $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { $rule.IdentityReference.Value }
    }
    # Usuários, Usuários autenticados, Todos, Interativo, Proprietário criador
    $others = @('S-1-5-32-545', 'S-1-5-11', 'S-1-1-0', 'S-1-5-4', 'S-1-3-0')
    $found = $sids | Where-Object { $others -contains $_ }
    Assert (-not $found) "nenhuma permissão para outros usuários na pasta de dados ($Label)$(if ($found) { ': ' + ($found -join ', ') })"
    Assert (($sids -contains 'S-1-5-18') -and ($sids -contains 'S-1-5-32-544')) "SYSTEM e Administradores com acesso ($Label)"
    $service = $acl.Access | Where-Object { $_.IdentityReference.Value -eq "NT SERVICE\$Service" }
    if ($WithService) { Assert ($service) "identidade do serviço com acesso à pasta de dados ($Label)" }
    foreach ($file in @('.env', 'tls\ca.key', 'tls\chave.protegida', 'locacontrol.db') | ForEach-Object { Join-Path $Data $_ } | Where-Object { Test-Path $_ }) {
        $explicit = (Get-Acl $file).Access | Where-Object { -not $_.IsInherited }
        Assert (-not $explicit) "$([IO.Path]::GetFileName($file)) só com permissões herdadas da pasta ($Label)"
    }
}
function Assert-Service([string]$Label) {
    $svc = Get-CimInstance Win32_Service -Filter "Name='$Service'"
    Assert ($svc) "serviço $Service instalado ($Label)"
    Assert ($svc.StartName -eq "NT SERVICE\$Service") "serviço com identidade própria: $($svc.StartName) ($Label)"
    Assert ($svc.State -eq 'Running') "serviço em execução ($Label)"
    $owner = Invoke-CimMethod -InputObject (Get-CimInstance Win32_Process -Filter "ProcessId=$($svc.ProcessId)") -MethodName GetOwner
    Assert (($owner.Domain -eq 'NT SERVICE') -and ($owner.User -eq $Service)) "servidor rodando como NT SERVICE\$Service ($Label)"
}
function New-Cpf([int]$Seed) {
    $d = [int[]](('{0:D9}' -f (100000000 + $Seed)).ToCharArray() | ForEach-Object { [int]"$_" })
    foreach ($size in 9, 10) {
        $sum = 0
        for ($i = 0; $i -lt $size; $i++) { $sum += $d[$i] * ($size + 1 - $i) }
        $r = ($sum * 10) % 11
        $d += @(if ($r -eq 10) { 0 } else { $r })
    }
    return -join $d
}
function Customer([int]$Seed) {
    return @{ person_type = 'PF'; legal_name = "Cliente CI $Seed"; document = (New-Cpf $Seed); addresses = @(@{ street = 'Rua Um'; city = 'São Paulo'; state = 'SP'; postal_code = '01001000' }) }
}

$dev = $null
try {
    # 1. Principal com a rede da loja: serviço com identidade própria e pasta de dados fechada.
    Assert ((Install $Setup @('/MODO=principal', '/REDE=1') 'instalacao.log') -eq 0) 'instalador terminou com código 0'
    Assert (Test-Path $Exe) 'programa em Arquivos de Programas'
    Assert (Wait-Health) 'servidor (serviço) respondeu em http://127.0.0.1:8000'
    Assert-Service 'instalação'
    Assert (-not (Test-Path (Join-Path ([Environment]::GetFolderPath('CommonStartup')) 'LocaControl (servidor).lnk'))) 'sem início pela pasta Inicializar (o serviço inicia sozinho)'
    $envFile = Join-Path $Data '.env'
    Assert ((Get-Content $envFile) -contains 'LOCACONTROL_NETWORK_MODE=true') '.env com o modo rede'
    Assert ((Get-Content $envFile) -contains 'LOCACONTROL_LOCAL_MODE=true') '.env com a edição local'
    Assert (Rule-Exists) 'regra de firewall limitada à sub-rede local'
    Add-Content -Path $envFile -Value 'LOCACONTROL_COMPANY_NAME=Loja de Teste CI'
    $s = Session
    $overview = Invoke-RestMethod 'http://127.0.0.1:8000/api/stations' -WebSession $s.Web
    Assert ($overview.tls.available) 'HTTPS da loja disponível (chaves protegidas pela conta do serviço)'
    Assert ($overview.tls.protection -match 'serviço') "proteção da senha das chaves: $($overview.tls.protection)"
    Assert (Test-Path (Join-Path $Data 'tls\ca.pem')) 'autoridade certificadora local criada'
    Post $s '/api/customers' (Customer 1) | Out-Null
    Assert ((Invoke-RestMethod 'http://127.0.0.1:8000/api/customers' -WebSession $s.Web).total -eq 1) 'cliente gravado'
    Assert-DataAcl 'instalação'
    Invoke-NonAdminProbe 'instalacao'

    # 2. Conta comum: não lê a pasta de dados, mas o atalho dela sobe o serviço parado.
    Assert ((Run-Exe @('parar')) -eq 0) 'parar (administrador): encerramento controlado do serviço'
    Assert ((Get-Service $Service).Status -eq 'Stopped') 'serviço parado'
    Assert (-not (Test-Path (Join-Path $Data 'locacontrol.pid'))) 'encerramento normal (sem PID deixado para trás)'
    $abrirExit = Join-Path $ProbeDir 'abrir.exit'
    Invoke-AsProbeUser 'abrir' "`$p = Start-Process -FilePath '$Exe' -ArgumentList 'abrir', '--sem-navegador' -Wait -PassThru -WindowStyle Hidden; Set-Content -Path '$abrirExit' -Value `$p.ExitCode"
    Assert ((Get-Content $abrirExit) -eq '0') "abrir pela conta comum terminou com 0 (código $(Get-Content $abrirExit))"
    Assert (Wait-Health) 'o atalho da conta comum iniciou o serviço'
    Assert-Service 'iniciado pela conta comum'
    $stopExit = Join-Path $ProbeDir 'parar.exit'
    Invoke-AsProbeUser 'parar' "`$p = Start-Process -FilePath '$Exe' -ArgumentList 'parar', '--espera', '5' -Wait -PassThru -WindowStyle Hidden; Set-Content -Path '$stopExit' -Value `$p.ExitCode"
    Assert ((Get-Content $stopExit) -ne '0') "conta comum não consegue parar o servidor (código $(Get-Content $stopExit))"
    Assert ((Get-Service $Service).Status -eq 'Running') 'serviço segue em execução'

    # 3. HTTPS: o Windows recusa antes de confiar na CA; HTTP não escuta na rede.
    $s = Session
    $overview = Invoke-RestMethod 'http://127.0.0.1:8000/api/stations' -WebSession $s.Web
    $ip = $overview.tls.server_addresses | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' -and $_ -notmatch '^127\.' } | Select-Object -First 1
    Assert ($ip) "endereço privado no certificado do servidor: $ip"
    $untrusted = $true
    try { Invoke-WebRequest "https://${ip}:8443/health" -UseBasicParsing -TimeoutSec 10 | Out-Null } catch { $untrusted = $false }
    Assert (-not $untrusted) 'HTTPS recusado pelo Windows antes de confiar na CA'
    $lanHttp = $true
    try { Invoke-WebRequest "http://${ip}:8000/health" -UseBasicParsing -TimeoutSec 5 | Out-Null } catch { $lanHttp = $false }
    Assert (-not $lanHttp) 'HTTP não escuta na rede'

    # 4. "Conectar à loja" pela linha de comando: código errado não instala; certo instala.
    $code = Post $s '/api/stations/pairing'
    Assert ((Run-Exe @('conectar', '--servidor', $ip, '--codigo', 'AAAA-AAAA-AAAA-AAAA-AAAA-AAAA-AA', '--sem-navegador')) -eq 2) 'código errado: nada instalado (código 2)'
    Assert (-not (Test-Path (Join-Path $Data 'station.json'))) 'nenhum registro de estação com o código errado'
    Assert ((Run-Exe @('conectar', '--servidor', $ip, '--codigo', $code.code, '--sem-navegador')) -eq 0) 'código certo: confiança instalada'
    $thumb = (Get-Content (Join-Path $Data 'station.json') -Raw | ConvertFrom-Json).ca_thumbprint
    Assert (Test-Path "Cert:\LocalMachine\Root\$thumb") 'CA da loja no repositório Raiz da máquina'
    $trusted = Invoke-WebRequest "https://${ip}:8443/health" -UseBasicParsing -TimeoutSec 15
    Assert ($trusted.StatusCode -eq 200) 'HTTPS validado pelo Windows depois de confiar na CA'
    Assert ((Run-Exe @('desconectar')) -eq 0) 'desconectar'
    Assert (-not (Test-Path "Cert:\LocalMachine\Root\$thumb")) 'desconectar removeu a CA'

    # 5. Atualização sob carga (REL-P1E-02): gravações contínuas, backup antes, troca do programa.
    Post $s '/api/backups' | Out-Null
    $stopLoad = Join-Path $env:RUNNER_TEMP 'carga.parar'
    $saved = Join-Path $env:RUNNER_TEMP 'carga.gravados'
    Remove-Item $stopLoad, $saved -ErrorAction SilentlyContinue
    $load = Start-Job -ArgumentList $stopLoad, $saved, ${function:New-Cpf}.ToString(), ${function:Customer}.ToString() -ScriptBlock {
        param($StopFile, $Saved, $CpfCode, $CustomerCode)
        Set-Item -Path function:New-Cpf -Value $CpfCode
        Set-Item -Path function:Customer -Value $CustomerCode
        $seed = 1000; $web = $null; $headers = $null
        while (-not (Test-Path $StopFile)) {
            try {
                if (-not $web) {
                    $web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
                    $me = Invoke-RestMethod 'http://127.0.0.1:8000/api/auth/me' -Headers @{ 'X-LocaControl-Request' = '1' } -WebSession $web -TimeoutSec 5
                    $headers = @{ 'X-LocaControl-Request' = '1'; 'Origin' = 'http://127.0.0.1:8000'; 'X-CSRF-Token' = $me.csrf_token }
                }
                $seed++
                $body = [Text.Encoding]::UTF8.GetBytes(((Customer $seed) | ConvertTo-Json -Depth 5))
                $created = Invoke-RestMethod 'http://127.0.0.1:8000/api/customers' -Method Post -Body $body -ContentType 'application/json; charset=utf-8' -Headers $headers -WebSession $web -TimeoutSec 15
                Add-Content -Path $Saved -Value $created.document  # só o que o servidor confirmou
            } catch {
                $web = $null
                Start-Sleep -Milliseconds 300
            }
        }
    }
    Start-Sleep -Seconds 5
    $before = @(Get-Content $saved -ErrorAction SilentlyContinue).Count
    Assert ($before -gt 0) "gravações em andamento antes da atualização ($before)"
    Assert ((Install $Upgrade @() 'atualizacao.log') -eq 0) 'atualização com gravações em andamento terminou com código 0'
    Assert (Wait-Health) 'serviço voltou depois da atualização'
    Start-Sleep -Seconds 5
    Set-Content -Path $stopLoad -Value 'parar'
    Wait-Job $load -Timeout 60 | Out-Null
    Remove-Job $load -Force
    $confirmed = @(Get-Content $saved)
    Assert ($confirmed.Count -gt $before) "gravações confirmadas antes e depois da atualização ($($confirmed.Count))"
    $stored = @(Python-Db "print('\n'.join(r[0] for r in c.execute('SELECT document FROM customers')))")
    $lost = $confirmed | Where-Object { $stored -notcontains $_ }
    Assert (-not $lost) "nenhuma gravação confirmada perdida na atualização$(if ($lost) { ': ' + ($lost -join ', ') })"
    Assert ((Python-Db "print(c.execute('PRAGMA integrity_check').fetchone()[0])") -eq 'ok') 'banco íntegro depois da atualização sob carga (integrity_check)'
    Assert (-not (Get-ChildItem (Join-Path $Data 'backups') -Force -Filter '.locacontrol_*')) 'nenhum backup incompleto deixado'
    Assert (-not (Test-Path (Join-Path $Data 'atualizacao-em-andamento.json'))) 'nenhuma atualização do banco pela metade'
    Assert ((Get-Content $envFile) -contains 'LOCACONTROL_COMPANY_NAME=Loja de Teste CI') 'linha própria do .env preservada'
    Assert ((Get-Content $envFile) -contains 'LOCACONTROL_NETWORK_MODE=true') 'escolha anterior reaproveitada (modo rede)'
    Assert-Service 'atualização'
    Assert-DataAcl 'atualização'
    Invoke-NonAdminProbe 'atualizacao'

    # 6. Reinstalação corrige permissões alteradas (regressão de ACL, como uma versão antiga).
    icacls $Data /grant '*S-1-5-32-545:(OI)(CI)M' | Out-Null
    icacls $envFile /grant '*S-1-5-32-545:(F)' | Out-Null
    Assert ((Install $Upgrade @() 'reinstalacao.log') -eq 0) 'reinstalação terminou com código 0'
    Assert (Wait-Health) 'serviço voltou depois da reinstalação'
    Assert-DataAcl 'reinstalação'
    Invoke-NonAdminProbe 'reinstalacao'
    $s = Session
    Assert ((Invoke-RestMethod 'http://127.0.0.1:8000/api/customers' -WebSession $s.Web).total -eq $stored.Count) 'clientes preservados na reinstalação'

    # 7. Desinstalação silenciosa: serviço, programa e firewall removidos; dados preservados.
    Assert ((Start-Process (Join-Path $App 'unins000.exe') -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru).ExitCode -eq 0) 'desinstalador terminou com código 0'
    for ($i = 0; $i -lt 60 -and (Test-Path $Exe); $i++) { Start-Sleep -Seconds 1 }
    Assert (-not (Test-Path $Exe)) 'programa removido'
    Assert (-not (Get-Service $Service -ErrorAction SilentlyContinue)) 'serviço removido'
    Assert (Test-Path (Join-Path $Data 'locacontrol.db')) 'banco preservado na desinstalação'
    Assert (-not (Rule-Exists)) 'regra de firewall removida'

    # 8. Estação pelo instalador (UX-P1E-03), contra um principal de teste na porta 18443.
    $devData = Join-Path $env:RUNNER_TEMP 'principal-de-teste'
    New-Item -ItemType Directory -Force -Path $devData | Out-Null
    $saveEnv = @{}
    $devEnv = @{ LOCACONTROL_DATA_DIR = $devData; LOCACONTROL_LOCAL_MODE = 'true'; LOCACONTROL_NETWORK_MODE = 'true'; LOCACONTROL_BACKUP_SCHEDULER = 'false'; PYTHONPATH = $Backend }
    foreach ($key in $devEnv.Keys) { $saveEnv[$key] = [Environment]::GetEnvironmentVariable($key); [Environment]::SetEnvironmentVariable($key, $devEnv[$key]) }
    $dev = Start-Process $DevPython -ArgumentList '-m', 'app.server', '--port', '18000', '--https-port', '18443' -WorkingDirectory $Backend -PassThru -RedirectStandardOutput (Join-Path $Logs 'principal-de-teste.log') -RedirectStandardError (Join-Path $Logs 'principal-de-teste.err')
    foreach ($key in $devEnv.Keys) { [Environment]::SetEnvironmentVariable($key, $saveEnv[$key]) }
    Assert (Wait-Health 18000) 'principal de teste em execução'
    $p = Session 18000
    for ($i = 0; $i -lt 30; $i++) {
        try { if ((Invoke-WebRequest "https://${ip}:18443/health" -UseBasicParsing -SkipCertificateCheck -TimeoutSec 3).StatusCode -eq 200) { break } } catch {}
        Start-Sleep -Seconds 1
    }
    $null = Post $p '/api/stations/pairing'  # código válido no principal, mas a estação digita outro
    $wrong = Install $Setup @('/MODO=estacao', "/SERVIDOR=$ip", '/PORTA=18443', '/CODIGO=AAAA-AAAA-AAAA-AAAA-AAAA-AAAA-AA') 'estacao-codigo-errado.log'
    Assert ($wrong -eq 20) "estação com código errado: instalador sai com 20 (saiu com $wrong)"
    Assert (-not (Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -match 'LocaControl' })) 'nenhuma CA da loja instalada com o código errado'
    Assert (-not (Get-ItemProperty 'HKLM:\Software\LocaControl' -Name UrlDaLoja -ErrorAction SilentlyContinue)) 'estação não registrada como conectada'
    Assert ((Get-Content (Join-Path $Logs 'estacao-codigo-errado.log') -Raw) -match 'confere com o c') 'motivo exato no registro do instalador'
    Assert-DataAcl 'estação' $false
    $code = Post $p '/api/stations/pairing'
    $right = Install $Setup @('/MODO=estacao', "/SERVIDOR=$ip", '/PORTA=18443', "/CODIGO=$($code.code)") 'estacao.log'
    Assert ($right -eq 0) "estação com o código certo: instalador sai com 0 (saiu com $right)"
    Assert (-not (Get-Service $Service -ErrorAction SilentlyContinue)) 'estação sem serviço de servidor'
    $url = (Get-ItemProperty 'HKLM:\Software\LocaControl' -Name UrlDaLoja).UrlDaLoja
    Assert ($url -eq "https://${ip}:18443/") "endereço da loja registrado: $url"
    $thumb = (Get-Content (Join-Path $Data 'station.json') -Raw | ConvertFrom-Json).ca_thumbprint
    Assert (Test-Path "Cert:\LocalMachine\Root\$thumb") 'CA do principal de teste instalada na estação'
    Assert ((Invoke-WebRequest "https://${ip}:18443/health" -UseBasicParsing -TimeoutSec 15).StatusCode -eq 200) 'HTTPS do principal validado pelo Windows na estação'
    $openExit = Join-Path $ProbeDir 'abrir-estacao.exit'
    Invoke-AsProbeUser 'abrir-estacao' "`$p = Start-Process -FilePath '$Exe' -ArgumentList 'abrir', '--sem-navegador' -Wait -PassThru -WindowStyle Hidden; Set-Content -Path '$openExit' -Value `$p.ExitCode"
    Assert ((Get-Content $openExit) -eq '0') 'conta comum abre o endereço da loja na estação'
    Assert ((Start-Process (Join-Path $App 'unins000.exe') -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru).ExitCode -eq 0) 'desinstalação da estação terminou com código 0'
    for ($i = 0; $i -lt 60 -and (Test-Path $Exe); $i++) { Start-Sleep -Seconds 1 }
    Assert (-not (Test-Path "Cert:\LocalMachine\Root\$thumb")) 'desinstalação da estação removeu a CA'
    Write-Host 'PASS: instalação, serviço isolado, conta comum, estação, atualização sob carga, reinstalação e desinstalação no Windows da CI.'
} finally {
    if ($dev -and -not $dev.HasExited) { Stop-Process -Id $dev.Id -Force -ErrorAction SilentlyContinue }
    Copy-Item (Join-Path $Data 'logs\*') $Logs -ErrorAction SilentlyContinue
    Copy-Item (Join-Path $ProbeDir '*.json') $Logs -ErrorAction SilentlyContinue
    Remove-LocalUser -Name $ProbeUser -ErrorAction SilentlyContinue
}
# Chegou aqui = todas as conferências passaram; o último comando nativo pode ter deixado 1.
exit 0
