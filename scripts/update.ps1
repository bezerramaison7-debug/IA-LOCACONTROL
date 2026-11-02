param([switch]$SkipFrontend)
# Atualiza somente o programa (.venv, backend, frontend\dist) e nunca escreve na pasta de dados
# (data\ ou LOCACONTROL_DATA_DIR: banco, importações, documentos, backups); a única ação sobre
# ela é parar o servidor, que apaga o próprio registro de processo. O schema é atualizado pelo
# servidor no próximo início (app.server), sempre com cópia prévia do banco.
. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython
Push-Location $ProjectRoot
try {
    & (Join-Path $PSScriptRoot 'stop.ps1')
    Invoke-Checked -Executable $ProjectPython -Arguments @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'backend/requirements-lock.txt')
    Invoke-Checked -Executable $ProjectPython -Arguments @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-deps', '-e', 'backend')
    if (-not $SkipFrontend) {
        if (-not (Get-Command 'npm.cmd' -ErrorAction SilentlyContinue)) {
            throw 'Node.js/npm não encontrado. Instale o Node.js ou use -SkipFrontend com uma pasta frontend\dist já compilada.'
        }
        Invoke-Checked -Executable 'npm.cmd' -Arguments @('--prefix', 'frontend', 'ci')
        Invoke-Checked -Executable 'npm.cmd' -Arguments @('--prefix', 'frontend', 'run', 'build')
    }
    Write-Host 'Atualização concluída. Use "Iniciar LocaControl" para aplicar o banco e abrir o sistema.'
} finally {
    Pop-Location
}
