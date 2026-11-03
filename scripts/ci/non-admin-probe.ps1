# CI (Windows), SEC-P1E-01: executado como uma conta local SEM privilégio de administrador.
# Registra o que essa conta consegue fazer com a pasta de dados do LocaControl: ler e alterar o
# banco, o .env e a lista de estações, e — o mais grave — decifrar a senha das chaves (DPAPI) e
# abrir a chave privada da autoridade certificadora da loja. Só lê; nunca altera conteúdo.
param([Parameter(Mandatory)][string]$Data, [Parameter(Mandatory)][string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type -Namespace Sonda -Name Dpapi -MemberDefinition @'
[StructLayout(LayoutKind.Sequential)] public struct Blob { public int Size; public IntPtr Data; }
[DllImport("crypt32.dll", SetLastError = true)]
public static extern bool CryptUnprotectData(ref Blob input, IntPtr description, IntPtr entropy,
    IntPtr reserved, IntPtr prompt, int flags, ref Blob output);
public static byte[] Unprotect(byte[] data) {
    var handle = System.Runtime.InteropServices.GCHandle.Alloc(data, System.Runtime.InteropServices.GCHandleType.Pinned);
    try {
        var input = new Blob { Size = data.Length, Data = handle.AddrOfPinnedObject() };
        var output = new Blob();
        if (!CryptUnprotectData(ref input, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, 1, ref output))
            throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        var result = new byte[output.Size];
        Marshal.Copy(output.Data, result, 0, output.Size);
        return result;
    } finally { handle.Free(); }
}
'@
$me = [Security.Principal.WindowsIdentity]::GetCurrent()
$r = [ordered]@{
    conta = $me.Name
    administrador = ([Security.Principal.WindowsPrincipal]$me).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Try-Open([string]$Path, [string]$Access) {
    try { $s = [IO.File]::Open($Path, 'Open', $Access, 'ReadWrite'); $s.Close(); return $true } catch { return $false }
}
$r.le_banco = Try-Open (Join-Path $Data 'locacontrol.db') 'Read'
$r.altera_banco = Try-Open (Join-Path $Data 'locacontrol.db') 'Write'
$r.le_env = Try-Open (Join-Path $Data '.env') 'Read'
$r.altera_env = Try-Open (Join-Path $Data '.env') 'Write'
$r.altera_estacoes = Try-Open (Join-Path $Data 'stations.json') 'Write'
$r.le_chave_ca = Try-Open (Join-Path $Data 'tls\ca.key') 'Read'
$r.le_senha_protegida = Try-Open (Join-Path $Data 'tls\chave.protegida') 'Read'
$novo = Join-Path $Data "sonda-$PID.txt"
try { [IO.File]::WriteAllText($novo, 'x'); Remove-Item $novo; $r.cria_arquivo = $true } catch { $r.cria_arquivo = $false }
$r.decifra_senha = $false
$r.abre_chave_ca = $false
if ($r.le_senha_protegida) {
    try {
        $senha = [Sonda.Dpapi]::Unprotect([IO.File]::ReadAllBytes((Join-Path $Data 'tls\chave.protegida')))
        $r.decifra_senha = $senha.Length -gt 0
        if ($r.le_chave_ca) {
            Add-Type -TypeDefinition @'
public static class SondaChave {
    public static int Abrir(string pem, string senha) {
        var chave = System.Security.Cryptography.ECDsa.Create();
        chave.ImportFromEncryptedPem(pem, senha);
        return chave.KeySize;
    }
}
'@
            $pem = [IO.File]::ReadAllText((Join-Path $Data 'tls\ca.key'))
            $r.abre_chave_ca = [SondaChave]::Abrir($pem, [Text.Encoding]::ASCII.GetString($senha)) -eq 256
        }
    } catch { $r.erro_dpapi = $_.Exception.Message }
}
$r | ConvertTo-Json | Set-Content -Path $Out -Encoding utf8
