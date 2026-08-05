param(
    [string]$BaseUrl = $(if ($env:KANOJO_MAC_BASE_URL) { $env:KANOJO_MAC_BASE_URL } else { "http://kanojo-mac.local:8787" }),
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$Body = @{ dry_run = -not $Apply } | ConvertTo-Json -Depth 4
$Result = Invoke-RestMethod `
    -Uri "$($BaseUrl.TrimEnd('/'))/maintenance/cleanup-test-memories" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body $Body `
    -TimeoutSec 30

$Result | ConvertTo-Json -Depth 12
