. (Join-Path $PSScriptRoot 'common.ps1')
Assert-ProjectPython
Invoke-Checked -Executable $ProjectPython -Arguments @((Join-Path $ProjectRoot 'scripts\smoke.py'))
