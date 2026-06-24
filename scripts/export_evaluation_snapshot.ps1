param(
    [string]$BaseUrl = "http://127.0.0.1:8787",
    [string]$OutDir = "exports"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Target = Join-Path $Root $OutDir
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

Get-ChildItem -LiteralPath $Target | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize
