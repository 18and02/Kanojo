param(
    [Parameter(Mandatory = $true)]
    [string]$BeforeDir,
    [Parameter(Mandatory = $true)]
    [string]$AfterDir,
    [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Test-RepoChildPath {
    param([string]$Path)
    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $RootPrefix = $Root
    if (-not $RootPrefix.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $RootPrefix = "$RootPrefix$([System.IO.Path]::DirectorySeparatorChar)"
    }
    return $FullPath -ne $Root -and $FullPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Resolve-RepoOutputFile {
    param([string]$Path, [string]$Name)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        $FullPath = [System.IO.Path]::GetFullPath($Path)
    } else {
        $FullPath = [System.IO.Path]::GetFullPath((Join-Path $Root $Path))
    }
    if (-not (Test-RepoChildPath $FullPath)) {
        throw "$Name must resolve below the repository root: $Path"
    }
    $Leaf = [System.IO.Path]::GetFileName($FullPath)
    if ([string]::IsNullOrWhiteSpace($Leaf) -or $Leaf -in @(".", "..")) {
        throw "$Name must resolve to a file, not a directory: $Path"
    }
    if ($Leaf.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0) {
        throw "$Name contains invalid file name characters: $Path"
    }
    $Parent = [System.IO.Path]::GetDirectoryName($FullPath)
    if (-not $Parent -or -not (Test-Path -LiteralPath $Parent)) {
        throw "$Name parent directory does not exist: $Parent"
    }
    return $FullPath
}

function Resolve-ExportDir {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return Resolve-Path -LiteralPath $Path
    }
    return Resolve-Path -LiteralPath (Join-Path $Root $Path)
}

function Read-Summary {
    param([string]$Dir)
    $Path = Join-Path $Dir "evaluation-summary.json"
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing evaluation-summary.json in $Dir"
    }
    return Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json
}

function Read-NodeStatus {
    param([string]$Dir)
    $Path = Join-Path $Dir "node-status.json"
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    return Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json
}

function Number-OrNull {
    param($Value)
    if ($null -eq $Value) {
        return $null
    }
    if ($Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal]) {
        return [double]$Value
    }
    return $null
}

function Format-Number {
    param($Value, [string]$Suffix = "")
    if ($null -eq $Value) {
        return "-"
    }
    return ("{0:N3}{1}" -f ([double]$Value), $Suffix)
}

function Add-ComparisonRow {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Area,
        [string]$Metric,
        $Before,
        $After,
        [string]$Suffix = ""
    )
    $BeforeNumber = Number-OrNull $Before
    $AfterNumber = Number-OrNull $After
    $Delta = if ($null -ne $BeforeNumber -and $null -ne $AfterNumber) {
        $AfterNumber - $BeforeNumber
    } else {
        $null
    }
    $Lines.Add(
        "| $Area | $Metric | $(Format-Number $BeforeNumber $Suffix) | $(Format-Number $AfterNumber $Suffix) | $(Format-Number $Delta $Suffix) |"
    )
}

$BeforePath = Resolve-ExportDir $BeforeDir
$AfterPath = Resolve-ExportDir $AfterDir
$Before = Read-Summary $BeforePath
$After = Read-Summary $AfterPath
$BeforeNode = Read-NodeStatus $BeforePath
$AfterNode = Read-NodeStatus $AfterPath

if (-not $OutFile) {
    $OutFile = Join-Path $AfterPath "evaluation-comparison.md"
}
$OutFile = Resolve-RepoOutputFile -Path $OutFile -Name "OutFile"

$Lines = [System.Collections.Generic.List[string]]::new()
$Lines.Add("# Kanojo Evaluation Comparison")
$Lines.Add("")
$Lines.Add("- Generated at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')")
$Lines.Add("- Before: ``$($BeforePath.Path)``")
$Lines.Add("- After: ``$($AfterPath.Path)``")
$Lines.Add("")
$Lines.Add("## Node Context")
$Lines.Add("")
$Lines.Add("| Field | Before | After |")
$Lines.Add("| --- | --- | --- |")
$Lines.Add("| Node role | $($BeforeNode.node.role) | $($AfterNode.node.role) |")
$Lines.Add("| Memory primary | $($BeforeNode.memory_write_policy.primary) | $($AfterNode.memory_write_policy.primary) |")
$Lines.Add("| Inference primary | $($BeforeNode.inference_route_policy.primary) | $($AfterNode.inference_route_policy.primary) |")
$Lines.Add("| Peer available | $($BeforeNode.peer.available) | $($AfterNode.peer.available) |")
$Lines.Add("")
$Lines.Add("## Metric Delta")
$Lines.Add("")
$Lines.Add("| Area | Metric | Before | After | Delta |")
$Lines.Add("| --- | --- | ---: | ---: | ---: |")
Add-ComparisonRow $Lines "Chat" "Count" $Before.chat.count $After.chat.count
Add-ComparisonRow $Lines "Chat" "Average latency" $Before.chat.avg_latency_ms $After.chat.avg_latency_ms "ms"
Add-ComparisonRow $Lines "Chat" "P95 latency" $Before.chat.p95_latency_ms $After.chat.p95_latency_ms "ms"
Add-ComparisonRow $Lines "Chat" "Memory hit rate" $Before.chat.memory_hit_rate $After.chat.memory_hit_rate
Add-ComparisonRow $Lines "Chat" "Average memory hits" $Before.chat.avg_memory_hits $After.chat.avg_memory_hits
Add-ComparisonRow $Lines "Heartbeat" "Fired rate" $Before.heartbeat.fired_rate $After.heartbeat.fired_rate
Add-ComparisonRow $Lines "Heartbeat" "Blocked count" $Before.heartbeat.blocked_count $After.heartbeat.blocked_count
Add-ComparisonRow $Lines "Avatar" "Average first play" $Before.avatar.avg_first_play_ms $After.avatar.avg_first_play_ms "ms"
Add-ComparisonRow $Lines "Avatar" "Average mouth active" $Before.avatar.avg_mouth_active_ms $After.avatar.avg_mouth_active_ms "ms"
Add-ComparisonRow $Lines "Avatar" "Average mouth active ratio" $Before.avatar.avg_mouth_active_ratio $After.avatar.avg_mouth_active_ratio
Add-ComparisonRow $Lines "Avatar" "Interrupt count" $Before.avatar.interrupt_count $After.avatar.interrupt_count

Set-Content -LiteralPath $OutFile -Encoding UTF8 -Value $Lines
Get-Item -LiteralPath $OutFile | Select-Object FullName,Length,LastWriteTime
