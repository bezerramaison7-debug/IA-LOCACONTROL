param([string]$OutDir)
# Gera o executável do servidor (pasta dist-app\LocaControl) a partir de packaging\locacontrol.spec.
# Não toca na pasta de dados. Requer frontend\dist compilado e PyInstaller no .venv.
. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython
if (-not $OutDir) { $OutDir = Join-Path $ProjectRoot 'dist-app' }
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'frontend\dist\index.html'))) {
    throw 'Compile a interface antes: npm --prefix frontend run build'
}
$Work = Join-Path $ProjectRoot 'build\pyinstaller'
# O PyInstaller registra o progresso no stderr; no PowerShell 5.1 isso viraria erro fatal.
$ErrorActionPreference = 'Continue'
& $ProjectPython -m PyInstaller --noconfirm --clean --distpath $OutDir --workpath $Work `
    (Join-Path $ProjectRoot 'packaging\locacontrol.spec')
$ErrorActionPreference = 'Stop'
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou (código $LASTEXITCODE)." }
Write-Host "Executável: $(Join-Path $OutDir 'LocaControl\LocaControl.exe')"
