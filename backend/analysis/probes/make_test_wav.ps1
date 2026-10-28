# Writes the MS1 voice probe's test clip (spec C35): an English question spoken by
# Windows' System.Speech, saved as a mono, 16-bit PCM, 16 kHz WAV. Run it in Windows
# PowerShell 5.1 before probes/run_probe.py. The clip goes outside the repo, to
# LUSOT_DATA_DIR\probes\<today>\test_question.wav, where run_probe.py looks for it.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

$root = $env:LUSOT_DATA_DIR
if (-not $root) { $root = 'C:\Systems\Lusot\lusot-data' }
$folder = Join-Path $root ('probes\' + (Get-Date -Format 'yyyy-MM-dd'))
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$path = Join-Path $folder 'test_question.wav'

$format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(
    16000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono
)
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $speaker.SetOutputToWaveFile($path, $format)
    $speaker.Speak('Is the water knee deep at Espana Boulevard right now?')
}
finally {
    $speaker.Dispose()  # closes the WAV file
}
Write-Output "Wrote $path"
