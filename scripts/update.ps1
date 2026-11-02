param([switch]$SkipFrontend)
# Atualiza uma instalação existente sem tocar em data\ (banco, importações, documentos,
# backups). O schema é atualizado por launch.ps1, sempre com cópia prévia do banco.
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
