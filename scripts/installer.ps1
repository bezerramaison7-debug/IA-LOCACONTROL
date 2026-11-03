param([string]$AppVersion, [switch]$SkipPackage)
# Gera o instalador do Windows (dist-installer\LocaControl-Setup-<versão>.exe): empacota o programa
# com scripts\package.ps1 e compila packaging\locacontrol.iss com o Inno Setup 6 (ISCC.exe).
# Não toca na pasta de dados. Ver docs/INSTALLATION.md e docs/P1E_PROPOSTA.md.
. (Join-Path $PSScriptRoot 'common.ps1')
if (-not $AppVersion) {
    $line = Select-String -Path (Join-Path $ProjectRoot 'backend\app\__init__.py') -Pattern '__version__ = "(.+)"'
    $AppVersion = $line.Matches[0].Groups[1].Value
}
if (-not $SkipPackage) { & (Join-Path $PSScriptRoot 'package.ps1') }
$Iscc = @(
    $env:ISCC,
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $Iscc) { throw 'Inno Setup 6 não encontrado (instale-o ou defina ISCC com o caminho do ISCC.exe).' }
Invoke-Checked $Iscc @("/DAppVersion=$AppVersion", (Join-Path $ProjectRoot 'packaging\locacontrol.iss'))
Write-Host "Instalador: $(Join-Path $ProjectRoot "dist-installer\LocaControl-Setup-$AppVersion.exe")"
