param(
    [string[]]$Candidates = @(
        "http://kanojo-mac.local:8787",
        "http://kanojo-pc.local:8787"
    ),
    [ValidateSet("mac_home", "pc_inference")]
    [string]$PreferredRole = "mac_home",
    [int]$TimeoutSec = 3
)

$ErrorActionPreference = "Stop"

$Index = 0
$Results = foreach ($Candidate in $Candidates) {
    $CandidateIndex = $Index
    $Index += 1
    $Base = $Candidate.TrimEnd("/")
    $Item = [ordered]@{
        index = $CandidateIndex
        base_url = $Base
        health = $false
        status = $false
        role = $null
        node_name = $null
        error = $null
    }
    try {
        $Health = Invoke-RestMethod -Uri "$Base/health" -TimeoutSec $TimeoutSec
        $Item.health = $Health.status -eq "ok"
        $Status = Invoke-RestMethod -Uri "$Base/node/status" -TimeoutSec $TimeoutSec
        $Item.status = $true
        $Item.role = $Status.node.role
        $Item.node_name = $Status.node.name
    } catch {
        $Item.error = $_.Exception.Message
    }
    [pscustomobject]$Item
}

$Best = $Results |
    Where-Object { $_.health -and $_.status } |
    Sort-Object @{ Expression = {
        $RoleOrder = if ($PreferredRole -eq "pc_inference") {
            @("pc_inference", "mac_home")
        } else {
            @("mac_home", "pc_inference")
        }
        $Rank = [Array]::IndexOf($RoleOrder, [string]$_.role)
        if ($Rank -lt 0) { 99 } else { $Rank }
    } }, @{ Expression = { $_.index } } |
    Select-Object -First 1

[pscustomobject]@{
    preferred_role = $PreferredRole
    best = $Best
    results = @($Results)
} | ConvertTo-Json -Depth 5
