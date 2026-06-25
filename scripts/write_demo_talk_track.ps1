param(
    [string]$PackageDir = "exports-showcase-package",
    [string]$OutFile = "demo-talk-track.md",
    [string]$Template = "docs\templates\DEMO_TALK_TRACK.zh.md"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Assert-LeafOutputFileName {
    param([string]$FileName, [string]$Name)
    if ([string]::IsNullOrWhiteSpace($FileName)) {
        throw "$Name must not be empty."
    }
    if ([System.IO.Path]::IsPathRooted($FileName) -or $FileName -match "[\\/]" -or $FileName -in @(".", "..")) {
        throw "$Name must be a file name, not a path: $FileName"
    }
    if ($FileName.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0) {
        throw "$Name contains invalid file name characters: $FileName"
    }
    return $FileName
}

function Resolve-RepoDirectoryPath {
    param([string]$Path, [string]$Name)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        $FullPath = [System.IO.Path]::GetFullPath($Path)
    } else {
        $FullPath = [System.IO.Path]::GetFullPath((Join-Path $Root $Path))
    }
    $RootPrefix = $Root
    if (-not $RootPrefix.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $RootPrefix = "$RootPrefix$([System.IO.Path]::DirectorySeparatorChar)"
    }
    if ($FullPath -eq $Root -or -not $FullPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Name must resolve below the repository root: $Path"
    }
    if (-not (Test-Path -LiteralPath $FullPath)) {
        throw "$Name does not exist: $FullPath"
    }
    return $FullPath
}

$Target = Resolve-RepoDirectoryPath -Path $PackageDir -Name "PackageDir"
$OutFile = Assert-LeafOutputFileName -FileName $OutFile -Name "OutFile"

if ([System.IO.Path]::IsPathRooted($Template)) {
    $TemplatePath = $Template
} else {
    $TemplatePath = Join-Path $Root $Template
}

function Read-JsonIfExists {
    param([string]$RelativePath)
    $Path = Join-Path $Target $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    return Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json
}

function Format-Field {
    param($Value, [string]$Fallback = "-")
    if ($null -eq $Value -or "$Value" -eq "") {
        return $Fallback
    }
    return "$Value"
}

function Format-Bool {
    param($Value)
    if ($null -eq $Value) {
        return "-"
    }
    if ([bool]$Value) {
        return "yes"
    }
    return "no"
}

function ConvertTo-RepoRelativePath {
    param([string]$Path)
    $FullPath = [System.IO.Path]::GetFullPath($Path)
    if ($FullPath.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $FullPath.Substring($Root.Length).TrimStart("\", "/").Replace("\", "/")
    }
    return $FullPath
}

$Manifest = Read-JsonIfExists "showcase-package.json"
$NodeStatus = Read-JsonIfExists "evaluation\node-status.json"
$Summary = Read-JsonIfExists "evaluation\evaluation-summary.json"
$MemoryCard = Read-JsonIfExists "evaluation\memory-card.json"
$ScreenshotManifest = Read-JsonIfExists "screenshots\showcase-screenshots.json"
$Events = Read-JsonIfExists "evaluation\evaluation-events.json"

$GeneratedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
$Commit = if ($Manifest) { $Manifest.commit } else { (git -C $Root rev-parse --short HEAD).Trim() }
$ChatEvents = @()
if ($Events -and $Events.items) {
    $ChatEvents = @($Events.items | Where-Object { $_.event_type -eq "chat" })
}
$PeerRouteCount = @(
    $ChatEvents |
        Where-Object {
            $_.payload -and
            $_.payload.inference_route -and
            $_.payload.inference_route.selected -eq "peer"
        }
).Count

$ScreenshotRows = [System.Collections.Generic.List[string]]::new()
if ($ScreenshotManifest -and $ScreenshotManifest.shots) {
    foreach ($Shot in @($ScreenshotManifest.shots)) {
        $RelativeFile = Format-Field $Shot.file
        if ($RelativeFile -ne "-") {
            $RelativeFile = ConvertTo-RepoRelativePath $RelativeFile
        }
        $ScreenshotRows.Add("| $(Format-Field $Shot.label $Shot.name) | ``$RelativeFile`` |")
    }
} else {
    $ScreenshotRows.Add("| - | Screenshot manifest not found. Run ``.\scripts\capture_showcase_screenshots.ps1`` or the showcase package builder first. |")
}

if (Test-Path -LiteralPath $TemplatePath) {
    $Content = Get-Content -Raw -Encoding UTF8 -LiteralPath $TemplatePath
} else {
    $Content = @"
# Kanojo Demo Talk Track

- Generated at: {{GENERATED_AT}}
- Commit: `{{COMMIT}}`
- Package directory: `{{PACKAGE_DIR}}`

## Evidence Summary

| Item | Current value |
| --- | --- |
| Node role | {{NODE_ROLE}} |
| Peer available | {{PEER_AVAILABLE}} |
| Memory primary | {{MEMORY_PRIMARY}} |
| Inference primary | {{INFERENCE_PRIMARY}} |
| Chat event count | {{CHAT_COUNT}} |
| Peer route event count | {{PEER_ROUTE_COUNT}} |
| Memory count | {{MEMORY_COUNT}} |

## Screenshot Index

| Screen | File |
| --- | --- |
{{SCREENSHOT_ROWS}}
"@
}

$Replacements = @{
    "{{GENERATED_AT}}" = $GeneratedAt
    "{{COMMIT}}" = Format-Field $Commit
    "{{PACKAGE_DIR}}" = $PackageDir
    "{{NODE_ROLE}}" = Format-Field $NodeStatus.node.role
    "{{NODE_NAME}}" = Format-Field $NodeStatus.node.name
    "{{PEER_CONFIGURED}}" = Format-Bool $NodeStatus.peer.configured
    "{{PEER_AVAILABLE}}" = Format-Bool $NodeStatus.peer.available
    "{{PEER_URL}}" = Format-Field $NodeStatus.peer.base_url
    "{{MEMORY_PRIMARY}}" = Format-Field $NodeStatus.memory_write_policy.primary
    "{{INFERENCE_PRIMARY}}" = Format-Field $NodeStatus.inference_route_policy.primary
    "{{CHAT_COUNT}}" = Format-Field $Summary.chat.count
    "{{PEER_ROUTE_COUNT}}" = "$PeerRouteCount"
    "{{MEMORY_COUNT}}" = Format-Field $MemoryCard.memory_count
    "{{HEARTBEAT_COUNT}}" = Format-Field $Summary.heartbeat.count
    "{{AVATAR_VOICE_START_COUNT}}" = Format-Field $Summary.avatar.voice_start_count
    "{{SCREENSHOT_ROWS}}" = ($ScreenshotRows -join "`n")
}

foreach ($Key in $Replacements.Keys) {
    $Content = $Content.Replace($Key, $Replacements[$Key])
}

$OutPath = Join-Path $Target $OutFile
Set-Content -LiteralPath $OutPath -Encoding UTF8 -Value $Content
Get-Item -LiteralPath $OutPath | Select-Object FullName,Length,LastWriteTime
