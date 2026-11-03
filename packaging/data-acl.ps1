# Instalador (SEC-P1E-01): substitui de uma vez a lista de acesso da pasta de dados do LocaControl.
# SYSTEM e Administradores: controle total; com -Servico, a identidade NT SERVICE\LocaControl:
# modificação. Ninguém mais. Sem herança da pasta-mãe; arquivos e subpastas passam a herdar só
# daqui (entradas explícitas de versões anteriores são descartadas).
param([Parameter(Mandatory)][string]$Data, [switch]$Servico)
$ErrorActionPreference = 'Stop'
$inherit = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
$none = [System.Security.AccessControl.PropagationFlags]::None
$allow = [System.Security.AccessControl.AccessControlType]::Allow
function Rule($Identity, [string]$Rights) {
    New-Object System.Security.AccessControl.FileSystemAccessRule($Identity, [System.Security.AccessControl.FileSystemRights]$Rights, $inherit, $none, $allow)
}
$acl = New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
$acl.AddAccessRule((Rule (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')) 'FullControl'))
$acl.AddAccessRule((Rule (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')) 'FullControl'))
if ($Servico) {
    $acl.AddAccessRule((Rule (New-Object System.Security.Principal.NTAccount('NT SERVICE\LocaControl')) 'Modify'))
}
(Get-Item -LiteralPath $Data).SetAccessControl($acl)
& icacls.exe "$Data\*" /reset /T /C /Q | Out-Null
exit 0
