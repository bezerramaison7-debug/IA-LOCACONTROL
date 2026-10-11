param([string]$Voice = 'Microsoft Maria Desktop', [int]$Rate = 0)
# Gera a narração do guia visual (docs\guia-visual\audio\*.wav) com a voz do Windows.
# Requer uma voz em português instalada; a padrão é a Microsoft Maria.
. (Join-Path $PSScriptRoot 'common.ps1')
Add-Type -AssemblyName System.Speech

$Guide = Join-Path $ProjectRoot 'docs\guia-visual'
$Audio = Join-Path $Guide 'audio'
New-Item -ItemType Directory -Force -Path $Audio | Out-Null
$Steps = Get-Content -LiteralPath (Join-Path $Guide 'steps.json') -Raw -Encoding UTF8 | ConvertFrom-Json

$Synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
$Synthesizer.SelectVoice($Voice)
$Synthesizer.Rate = $Rate
# 16 kHz mono mantém a fala nítida com arquivos pequenos.
$Format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
try {
    foreach ($Step in $Steps) {
        $Synthesizer.SetOutputToWaveFile((Join-Path $Audio ($Step.id + '.wav')), $Format)
        $Synthesizer.Speak($Step.text)
        Write-Host "narracao $($Step.id)"
    }
} finally {
    $Synthesizer.SetOutputToNull()
    $Synthesizer.Dispose()
}
