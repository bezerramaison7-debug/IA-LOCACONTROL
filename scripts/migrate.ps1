param([ValidateSet('upgrade', 'current', 'check', 'history')][string]$Action = 'upgrade')
. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython
$MigrationArguments = @('-m', 'alembic', '-c', (Join-Path $ProjectRoot 'backend\alembic.ini'), $Action)
if ($Action -eq 'upgrade') { $MigrationArguments += 'head' }
Invoke-Checked -Executable $ProjectPython -Arguments $MigrationArguments
