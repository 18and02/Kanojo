param(
    [switch]$Restart,
    [switch]$WithStt,
    [switch]$SkipStt,
    [switch]$WithTts,
    [switch]$SkipTts,
    [switch]$InstallSttDeps
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")

function Get-EnvValue {
    param(
        [string]$Name
    )
    $Value = [Environment]::GetEnvironmentVariable($Name, "Process")
    $EnvFile = Join-Path $Root "backend\.env"
    if ($Value -or -not (Test-Path -LiteralPath $EnvFile)) {
        return $Value
    }
    foreach ($Line in Get-Content -LiteralPath $EnvFile) {
        $Trimmed = $Line.Trim()
        if (-not $Trimmed -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) {
            continue
        }
        $Key, $RawValue = $Trimmed.Split("=", 2)
        if ($Key.Trim() -eq $Name) {
            return $RawValue.Trim()
        }
    }
    return $null
}

$SttBaseUrl = Get-EnvValue "KANOJO_STT_BASE_URL"
$TtsBaseUrl = Get-EnvValue "KANOJO_TTS_BASE_URL"
$ShouldStartStt = $WithStt -or (
    -not $SkipStt -and
    $SttBaseUrl -and
    $SttBaseUrl.StartsWith("http://127.0.0.1:")
)
$ShouldStartTts = $WithTts -or (
    -not $SkipTts -and
    $TtsBaseUrl -and
    $TtsBaseUrl.StartsWith("http://127.0.0.1:")
)

if ($ShouldStartStt) {
    $SttArgs = @{}
    if ($Restart) {
        $SttArgs.Restart = $true
    }
    if ($InstallSttDeps) {
        $SttArgs.InstallDeps = $true
    }
    & (Join-Path $Root "scripts\start_stt.ps1") @SttArgs
}

if ($ShouldStartTts) {
    $TtsArgs = @{}
    if ($Restart) {
        $TtsArgs.Restart = $true
    }
    & (Join-Path $Root "scripts\start_tts.ps1") @TtsArgs
}

$BackendArgs = @{}
if ($Restart) {
    $BackendArgs.Restart = $true
}
& (Join-Path $Root "scripts\start_backend.ps1") @BackendArgs
$DesktopArgs = @{}
if ($Restart) {
    $DesktopArgs.Restart = $true
}
& (Join-Path $Root "scripts\start_desktop.ps1") @DesktopArgs
