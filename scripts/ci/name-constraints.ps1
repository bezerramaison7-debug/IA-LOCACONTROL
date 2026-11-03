# CI (Windows): o verificador do Windows (X509Chain/CryptoAPI) aplica as restrições da CA local?
# Instala a CA de teste no repositório Raiz da máquina, constrói as cadeias e a remove.
# - Name Constraints (ADR-026): nome e IP públicos recusados;
# - alcance (SEC-P1E-04): IP privado de OUTRA rede (192.168.51.x) recusado;
# - uso (SEC-P1E-04): certificado de assinatura de código emitido pela CA recusado para esse uso.
param([Parameter(Mandatory)][string]$Folder)
$ErrorActionPreference = 'Stop'
$X509 = [System.Security.Cryptography.X509Certificates.X509Certificate2]
$ServerAuth = '1.3.6.1.5.5.7.3.1'
$CodeSigning = '1.3.6.1.5.5.7.3.3'
$ca = $X509::new((Join-Path $Folder 'ca.cer'))
$store = [System.Security.Cryptography.X509Certificates.X509Store]::new('Root', 'LocalMachine')
$store.Open('ReadWrite')
$store.Add($ca)
try {
    function Test-Chain([string]$File, [string]$Usage) {
        $chain = [System.Security.Cryptography.X509Certificates.X509Chain]::new()
        $chain.ChainPolicy.RevocationMode = 'NoCheck'
        [void]$chain.ChainPolicy.ApplicationPolicy.Add([System.Security.Cryptography.Oid]::new($Usage))
        $ok = $chain.Build($X509::new((Join-Path $Folder $File)))
        $status = ($chain.ChainStatus | ForEach-Object { $_.Status }) -join ','
        Write-Host "$File ($Usage) -> valido=$ok status=[$status]"
        return @{ Ok = $ok; Status = $status }
    }
    $permitted = Test-Chain 'permitted.cer' $ServerAuth
    if (-not $permitted.Ok) { throw 'FALHOU: certificado dentro das restrições foi recusado.' }
    foreach ($file in 'forbidden.cer', 'other-network.cer') {
        $result = Test-Chain $file $ServerAuth
        if ($result.Ok) { throw "FALHOU: o Windows aceitou $file, fora das Name Constraints." }
        if ($result.Status -notmatch 'NameConstraint') { throw "FALHOU: $file recusado por outro motivo ($($result.Status))." }
    }
    $code = Test-Chain 'codesign.cer' $CodeSigning
    if ($code.Ok) { throw 'FALHOU: o Windows aceitou assinatura de código emitida pela CA da loja.' }
    if ($code.Status -notmatch 'NotValidForUsage') { throw "FALHOU: codesign.cer recusado por outro motivo ($($code.Status))." }
    Write-Host 'OK: o Windows aplica as Name Constraints, o alcance da rede da loja e o uso (só servidor TLS) da CA local.'
} finally {
    $store.Remove($ca)
    $store.Close()
}
