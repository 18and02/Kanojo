param(
    [string]$BaseUrl = "http://127.0.0.1:8787",
    [string]$OutDir = "exports",
    [switch]$SkipReport
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Resolve-RepoOutputPath {
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
    return $FullPath
}

$Target = Resolve-RepoOutputPath -Path $OutDir -Name "OutDir"
New-Item -ItemType Directory -Force -Path $Target | Out-Null

$Base = $BaseUrl.TrimEnd("/")

function Save-JsonEndpoint {
    param(
        [string]$Path,
        [string]$FileName
    )
    $Result = Invoke-RestMethod -Uri "$Base$Path" -TimeoutSec 30
    $Result | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $Target $FileName) -Encoding UTF8
}

function Save-TextEndpoint {
    param(
        [string]$Path,
        [string]$FileName
    )
    $Response = Invoke-WebRequest -Uri "$Base$Path" -TimeoutSec 30 -UseBasicParsing
    Set-Content -LiteralPath (Join-Path $Target $FileName) -Encoding UTF8 -Value $Response.Content
}

Save-JsonEndpoint -Path "/node/status" -FileName "node-status.json"
Save-JsonEndpoint -Path "/evaluation/summary" -FileName "evaluation-summary.json"
Save-JsonEndpoint -Path "/evaluation/export?format=json" -FileName "evaluation-events.json"
Save-TextEndpoint -Path "/evaluation/export?format=csv" -FileName "evaluation-events.csv"
Save-JsonEndpoint -Path "/memory-card?session_id=default" -FileName "memory-card.json"
Save-TextEndpoint -Path "/memory-card/export?session_id=default&format=markdown" -FileName "memory-card.md"

if (-not $SkipReport) {
    & (Join-Path $PSScriptRoot "write_evaluation_report.ps1") -OutDir $Target
}

Get-ChildItem -LiteralPath $Target | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize
