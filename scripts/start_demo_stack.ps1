param(
    [switch]$Restart,
    [switch]$SkipDesktop,
    [switch]$SkipSmoke,
    [switch]$WithStt,
    [switch]$WithTts
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")

if ($WithStt) {
    $SttArgs = @{ Warmup = $true }
    if ($Restart) {
        $SttArgs.Restart = $true
    }
    & (Join-Path $Root "scripts\start_stt.ps1") @SttArgs
}

if ($WithTts) {
    $TtsArgs = @{}
    if ($Restart) {
        $TtsArgs.Restart = $true
    }
    & (Join-Path $Root "scripts\start_tts.ps1") @TtsArgs
}

$BackendArgs = @{ BindAddress = "0.0.0.0" }
if ($Restart) {
    $BackendArgs.Restart = $true
}
& (Join-Path $Root "scripts\start_backend.ps1") @BackendArgs

$FirewallRule = Get-NetFirewallRule -DisplayName "Kanojo Backend 8787" -ErrorAction SilentlyContinue
if (-not $FirewallRule) {
    Write-Warning "Firewall rule 'Kanojo Backend 8787' was not found. Mac may not reach PC."
}

if (-not $SkipSmoke) {
    & (Join-Path $Root "scripts\dual_node_demo.ps1")
}

if (-not $SkipDesktop) {
    & (Join-Path $Root "scripts\start_desktop.ps1") -Restart:$Restart
}
