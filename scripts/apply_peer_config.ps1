param(
    [Parameter(Mandatory = $true)]
    [string]$PeerBaseUrl,
    [int]$Port = 8787,
    [string]$BindAddress = "0.0.0.0",
    [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$EnvFile = Join-Path $Backend ".env"
$Key = "KANOJO_PEER_BASE_URL"

try {
    $Uri = [Uri]$PeerBaseUrl
    if ($Uri.Scheme -notin @("http", "https")) {
        throw "PeerBaseUrl must use http or https."
    }
} catch {
    throw "Invalid PeerBaseUrl: $PeerBaseUrl"
}

if (-not (Test-Path -LiteralPath $Backend)) {
    throw "Backend directory not found: $Backend"
}

$BackupFile = $null
if (Test-Path -LiteralPath $EnvFile) {
    $Timestamp = Get-Date -Format "yyyyMMddHHmmss"
    $BackupFile = "$EnvFile.bak-$Timestamp"
    Copy-Item -LiteralPath $EnvFile -Destination $BackupFile -Force
    $Lines = Get-Content -LiteralPath $EnvFile -Encoding UTF8
} else {
    $Lines = @()
}

$Updated = $false
$NextLines = foreach ($Line in $Lines) {
    if ($Line -match "^\s*$([regex]::Escape($Key))=") {
        $Updated = $true
        "$Key=$PeerBaseUrl"
    } else {
        $Line
    }
}
if (-not $Updated) {
    $NextLines += "$Key=$PeerBaseUrl"
}
Set-Content -LiteralPath $EnvFile -Value $NextLines -Encoding UTF8

$NodeStatus = $null
if (-not $SkipRestart) {
    & (Join-Path $Root "scripts\start_backend.ps1") -Port $Port -BindAddress $BindAddress -Restart
    $NodeStatus = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/node/status" -TimeoutSec 10
}

[pscustomobject]@{
    applied = $true
    key = $Key
    value = $PeerBaseUrl
    env_file = $EnvFile
    backup_file = $BackupFile
    restarted = -not $SkipRestart
    peer_configured = if ($NodeStatus) { $NodeStatus.peer.configured } else { $null }
    peer_available = if ($NodeStatus) { $NodeStatus.peer.available } else { $null }
    node_role = if ($NodeStatus) { $NodeStatus.node.role } else { $null }
} | ConvertTo-Json -Depth 5
