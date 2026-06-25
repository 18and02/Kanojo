param(
    [string]$PackageDir = "exports-showcase-package",
    [string]$OutFile = "demo-talk-track.md"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

if ([System.IO.Path]::IsPathRooted($PackageDir)) {
    $Target = (Resolve-Path -LiteralPath $PackageDir).Path
} else {
    $Target = (Resolve-Path -LiteralPath (Join-Path $Root $PackageDir)).Path
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

function Add-TalkSection {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Title,
        [string]$Screen,
        [string]$Talk
    )
    $Lines.Add("### $Title")
    $Lines.Add("")
    $Lines.Add("- Screen: $Screen")
    $Lines.Add("- Talk: $Talk")
    $Lines.Add("")
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

$Lines = [System.Collections.Generic.List[string]]::new()
$Lines.Add("# Kanojo Demo Talk Track")
$Lines.Add("")
$Lines.Add("- Generated at: $GeneratedAt")
$Lines.Add("- Commit: ``$Commit``")
$Lines.Add("- Package directory: ``$PackageDir``")
$Lines.Add("")
$Lines.Add("## Pre-demo Checks")
$Lines.Add("")
$Lines.Add("1. Start and prewarm the PC backend: ``.\scripts\start_backend.ps1 -BindAddress 0.0.0.0 -Restart``")
$Lines.Add("2. Run the dual-node smoke test: ``.\scripts\dual_node_demo.ps1``")
$Lines.Add("3. Generate the showcase package: ``.\scripts\build_showcase_package.ps1 -OutDir $PackageDir``")
$Lines.Add("4. Confirm the GitHub draft release has source, portable, and SHA256 assets.")
$Lines.Add("")
$Lines.Add("## Evidence Summary")
$Lines.Add("")
$Lines.Add("| Item | Current value |")
$Lines.Add("| --- | --- |")
$Lines.Add("| Node role | $(Format-Field $NodeStatus.node.role) |")
$Lines.Add("| Node name | $(Format-Field $NodeStatus.node.name) |")
$Lines.Add("| Peer configured | $(Format-Bool $NodeStatus.peer.configured) |")
$Lines.Add("| Peer available | $(Format-Bool $NodeStatus.peer.available) |")
$Lines.Add("| Peer URL | $(Format-Field $NodeStatus.peer.base_url) |")
$Lines.Add("| Memory primary | $(Format-Field $NodeStatus.memory_write_policy.primary) |")
$Lines.Add("| Inference primary | $(Format-Field $NodeStatus.inference_route_policy.primary) |")
$Lines.Add("| Chat event count | $(Format-Field $Summary.chat.count) |")
$Lines.Add("| Peer route event count | $PeerRouteCount |")
$Lines.Add("| Memory count | $(Format-Field $MemoryCard.memory_count) |")
$Lines.Add("| Heartbeat event count | $(Format-Field $Summary.heartbeat.count) |")
$Lines.Add("| Avatar voice-start count | $(Format-Field $Summary.avatar.voice_start_count) |")
$Lines.Add("")
$Lines.Add("## Three-minute Flow")
$Lines.Add("")
$Lines.Add("| Time | Action | Point |")
$Lines.Add("| --- | --- | --- |")
$Lines.Add("| 0:00-0:20 | Open the control panel | Position Kanojo as a memory-driven desktop companion, not a simple chat shell. |")
$Lines.Add("| 0:20-0:55 | Open node topology | Explain Mac as the always-on memory source and PC as the inference node. |")
$Lines.Add("| 0:55-1:30 | Send one chat message | Show response generation and inference-route evidence. |")
$Lines.Add("| 1:30-2:05 | Open memory card | Show durable memory, reflection, audit, and snapshots. |")
$Lines.Add("| 2:05-2:35 | Open evaluation report | Show exportable latency, hit-rate, heartbeat, and avatar evidence. |")
$Lines.Add("| 2:35-3:00 | Show delivery package | Show portable build, SHA256 manifest, and GitHub draft release. |")
$Lines.Add("")
$Lines.Add("## Talk Script")
$Lines.Add("")
Add-TalkSection $Lines `
    "1. Opening" `
    "Control panel and Live2D avatar" `
    "Kanojo combines long-term memory, proactive heartbeat, voice/avatar feedback, and evaluation events into a desktop companion loop."
Add-TalkSection $Lines `
    "2. Dual-node loop" `
    "Debug node-topology panel" `
    "The Mac mini stays online as the SQLite memory source. The PC runs the local model. PC writes long-term memory back to Mac, while Mac delegates heavy inference to PC."
Add-TalkSection $Lines `
    "3. Chat and inference route" `
    "Chat box and debug log" `
    "Each chat records route, model, latency, and memory hits. The key evidence is the inference_route field proving where generation happened."
Add-TalkSection $Lines `
    "4. Memory governance" `
    "Memory card and memory-audit views" `
    "Long-term memory is inspectable and governable: edit, demote, deactivate, approve, reject, and batch-review audit candidates."
Add-TalkSection $Lines `
    "5. Evaluation and delivery" `
    "evaluation-report.md and SHOWCASE_INDEX.md" `
    "The system exports chat, heartbeat, TTS, and Live2D evidence for thesis evaluation. Release assets are paired with SHA256 checksums."
$Lines.Add("## Screenshot Index")
$Lines.Add("")
if ($ScreenshotManifest -and $ScreenshotManifest.shots) {
    $Lines.Add("| Screen | File |")
    $Lines.Add("| --- | --- |")
    foreach ($Shot in @($ScreenshotManifest.shots)) {
        $RelativeFile = "$($Shot.file)"
        if ($RelativeFile.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
            $RelativeFile = $RelativeFile.Substring($Root.Length).TrimStart("\", "/").Replace("\", "/")
        }
        $Lines.Add("| $(Format-Field $Shot.label $Shot.name) | ``$RelativeFile`` |")
    }
} else {
    $Lines.Add("- Screenshot manifest not found. Run ``.\scripts\capture_showcase_screenshots.ps1`` or the showcase package builder first.")
}
$Lines.Add("")
$Lines.Add("## Short Answers")
$Lines.Add("")
$Lines.Add("- Why two machines: Mac mini is low-power and always on, so it is suitable as the memory source; PC has stronger local inference capacity.")
$Lines.Add("- Why not database dual-write: the project keeps a single source of truth. Failed peer writes are rejected instead of silently falling back to local writes.")
$Lines.Add("- How false memory is reduced: smoke-test text is filtered, extraction candidates enter audit, and the desktop supports approve/reject/edit/demote/deactivate operations.")
$Lines.Add("- How evaluation is proven: exports include chat, heartbeat, memory-hit, TTS/Live2D first-play, mouth-activity, and interruption events.")

$OutPath = Join-Path $Target $OutFile
Set-Content -LiteralPath $OutPath -Encoding UTF8 -Value $Lines
Get-Item -LiteralPath $OutPath | Select-Object FullName,Length,LastWriteTime
