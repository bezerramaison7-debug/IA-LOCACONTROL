# CI (Windows): o verificador do Windows (X509Chain/CryptoAPI) respeita as Name Constraints da CA
# local? Instala a CA de teste no repositório Raiz da máquina, constrói as cadeias e a remove.
param([Parameter(Mandatory)][string]$Folder)
$ErrorActionPreference = 'Stop'
$X509 = [System.Security.Cryptography.X509Certificates.X509Certificate2]
$ca = $X509::new((Join-Path $Folder 'ca.cer'))
$store = [System.Security.Cryptography.X509Certificates.X509Store]::new('Root', 'LocalMachine')
$store.Open('ReadWrite')
$store.Add($ca)
try {
    function Test-Chain([string]$File) {
        $chain = [System.Security.Cryptography.X509Certificates.X509Chain]::new()
        $chain.ChainPolicy.RevocationMode = 'NoCheck'
        $ok = $chain.Build($X509::new((Join-Path $Folder $File)))
        $status = ($chain.ChainStatus | ForEach-Object { $_.Status }) -join ','
        Write-Host "$File -> valido=$ok status=[$status]"
        return @{ Ok = $ok; Status = $status }
    }
    $permitted = Test-Chain 'permitted.cer'
    $forbidden = Test-Chain 'forbidden.cer'
    if (-not $permitted.Ok) { throw 'FALHOU: certificado dentro das restrições foi recusado.' }
    if ($forbidden.Ok) { throw 'FALHOU: o Windows aceitou certificado fora das Name Constraints.' }
    if ($forbidden.Status -notmatch 'NameConstraint') {
        throw "FALHOU: recusado por outro motivo ($($forbidden.Status))."
    }
    Write-Host 'OK: o Windows aplica as Name Constraints da CA local.'
} finally {
    $store.Remove($ca)
    $store.Close()
}
