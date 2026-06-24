param(
    [string]$BaseUrl = "http://127.0.0.1:8787",
    [string]$Text = "预热 PC 推理节点"
)

$ErrorActionPreference = "Stop"

$Body = @{ text = $Text } | ConvertTo-Json -Depth 4
$Result = Invoke-RestMethod `
    -Uri "$($BaseUrl.TrimEnd('/'))/node/inference/prewarm" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body $Body `
    -TimeoutSec 240

$Result | ConvertTo-Json -Depth 8
