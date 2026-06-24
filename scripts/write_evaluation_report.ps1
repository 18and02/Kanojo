param(
    [string]$OutDir = "exports",
    [string]$ReportName = "evaluation-report.md"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
if ([System.IO.Path]::IsPathRooted($OutDir)) {
    $Target = Resolve-Path -LiteralPath $OutDir
} else {
    $Target = Resolve-Path -LiteralPath (Join-Path $Root $OutDir)
}

function Read-JsonFile {
    param([string]$FileName)
    $Path = Join-Path $Target $FileName
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing exported file: $Path"
    }
    return Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json
}

function Format-Value {
    param($Value, [string]$Suffix = "")
    if ($null -eq $Value) {
        return "-"
    }
    if ($Value -is [double] -or $Value -is [float] -or $Value -is [decimal]) {
        return ("{0:N3}{1}" -f $Value, $Suffix)
    }
    return "$Value$Suffix"
}

function Add-MetricRow {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Area,
        [string]$Metric,
        $Value,
        [string]$Suffix = ""
    )
    $Lines.Add("| $Area | $Metric | $(Format-Value $Value $Suffix) |")
}

$Summary = Read-JsonFile "evaluation-summary.json"
$NodeStatus = Read-JsonFile "node-status.json"
$Events = Read-JsonFile "evaluation-events.json"
$MemoryCard = Read-JsonFile "memory-card.json"
$Items = @($Events.items)
$ChatRoutes = @(
    $Items |
        Where-Object { $_.event_type -eq "chat" -and $_.payload -and $_.payload.inference_route } |
        ForEach-Object { $_.payload.inference_route }
)

$GeneratedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
$ReportPath = Join-Path $Target $ReportName
$Lines = [System.Collections.Generic.List[string]]::new()

$Lines.Add("# Kanojo Evaluation Report")
$Lines.Add("")
$Lines.Add("- Generated at: $GeneratedAt")
$Lines.Add("- Source directory: ``" + $Target.Path + "``")
$Lines.Add("")
$Lines.Add("## Node Baseline")
$Lines.Add("")
$Lines.Add("| Field | Value |")
$Lines.Add("| --- | --- |")
$Lines.Add("| Node name | $($NodeStatus.node.name) |")
$Lines.Add("| Node role | $($NodeStatus.node.role) |")
$Lines.Add("| LLM configured | $($NodeStatus.node.llm_configured) |")
$Lines.Add("| TTS configured | $($NodeStatus.node.tts_configured) |")
$Lines.Add("| STT configured | $($NodeStatus.node.stt_configured) |")
$Lines.Add("| Memory primary | $($NodeStatus.memory_write_policy.primary) |")
$Lines.Add("| Inference primary | $($NodeStatus.inference_route_policy.primary) |")
$Lines.Add("| Peer configured | $($NodeStatus.peer.configured) |")
$Lines.Add("| Peer available | $($NodeStatus.peer.available) |")
$Lines.Add("| Peer base URL | $($NodeStatus.peer.base_url) |")
$Lines.Add("")
$Lines.Add("## Key Metrics")
$Lines.Add("")
$Lines.Add("| Area | Metric | Value |")
$Lines.Add("| --- | --- | --- |")
Add-MetricRow $Lines "Chat" "Count" $Summary.chat.count
Add-MetricRow $Lines "Chat" "Average latency" $Summary.chat.avg_latency_ms "ms"
Add-MetricRow $Lines "Chat" "P95 latency" $Summary.chat.p95_latency_ms "ms"
Add-MetricRow $Lines "Chat" "Memory hit rate" $Summary.chat.memory_hit_rate
Add-MetricRow $Lines "Chat" "Average memory hits" $Summary.chat.avg_memory_hits
Add-MetricRow $Lines "Heartbeat" "Count" $Summary.heartbeat.count
Add-MetricRow $Lines "Heartbeat" "Fired count" $Summary.heartbeat.fired_count
Add-MetricRow $Lines "Heartbeat" "Blocked count" $Summary.heartbeat.blocked_count
Add-MetricRow $Lines "Heartbeat" "Fired rate" $Summary.heartbeat.fired_rate
Add-MetricRow $Lines "Avatar" "Voice starts" $Summary.avatar.voice_start_count
Add-MetricRow $Lines "Avatar" "Average first play" $Summary.avatar.avg_first_play_ms "ms"
Add-MetricRow $Lines "Avatar" "Lip sync count" $Summary.avatar.lip_sync_count
Add-MetricRow $Lines "Avatar" "Average mouth active" $Summary.avatar.avg_mouth_active_ms "ms"
Add-MetricRow $Lines "Avatar" "Average mouth active ratio" $Summary.avatar.avg_mouth_active_ratio
Add-MetricRow $Lines "Avatar" "Interrupt count" $Summary.avatar.interrupt_count
$Lines.Add("")
$Lines.Add("## Inference Routes")
$Lines.Add("")
if ($ChatRoutes.Count -eq 0) {
    $Lines.Add("- No chat inference route events were found.")
} else {
    $Lines.Add("| Selected route | Count | Models |")
    $Lines.Add("| --- | ---: | --- |")
    $ChatRoutes |
        Group-Object selected |
        Sort-Object Count -Descending |
        ForEach-Object {
            $Models = @(
                $_.Group |
                    ForEach-Object { $_.llm_model } |
                    Where-Object { $_ } |
                    Sort-Object -Unique
            ) -join ", "
            $Lines.Add("| $($_.Name) | $($_.Count) | $Models |")
        }
}
$Lines.Add("")
$Lines.Add("## Memory Card")
$Lines.Add("")
$Lines.Add("- Memory count: $($MemoryCard.memory_count)")
$Lines.Add("- Conversation count: $($MemoryCard.conversation_count)")
$Lines.Add("- Summary: $($MemoryCard.summary)")
$Lines.Add("")
$Lines.Add("## Recent Events")
$Lines.Add("")
$Lines.Add("| Time | Type | Source | Latency | Result |")
$Lines.Add("| --- | --- | --- | ---: | --- |")
@($Summary.recent_events) |
    Select-Object -First 10 |
    ForEach-Object {
        $Latency = if ($null -ne $_.latency_ms) { "$($_.latency_ms)ms" } else { "-" }
        $Result = if ($_.event_type -eq "chat" -and $_.payload.inference_route) {
            "route=$($_.payload.inference_route.selected), model=$($_.payload.inference_route.llm_model)"
        } elseif ($_.event_type -eq "heartbeat") {
            "fired=$($_.fired), reason=$($_.reason)"
        } else {
            "-"
        }
        $Lines.Add("| $($_.created_at) | $($_.event_type) | $($_.source) | $Latency | $Result |")
    }
$Lines.Add("")
$Lines.Add("## Exported Files")
$Lines.Add("")
Get-ChildItem -LiteralPath $Target |
    Where-Object { $_.Name -ne $ReportName } |
    Sort-Object Name |
    ForEach-Object {
        $Lines.Add("- ``" + $_.Name + "`` ($($_.Length) bytes)")
    }

Set-Content -LiteralPath $ReportPath -Encoding UTF8 -Value $Lines
Get-Item -LiteralPath $ReportPath | Select-Object FullName,Length,LastWriteTime
