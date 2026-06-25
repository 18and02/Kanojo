param(
    [string]$Repository,
    [string]$TagPattern = "^kanojo-[0-9a-f]{7,40}$",
    [int]$Keep = 2,
    [int]$Limit = 100,
    [switch]$Apply,
    [switch]$CleanupTag
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Resolve-Repository {
    $Remote = (git -C $Root remote get-url origin).Trim()
    if ($Remote -match "github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(\.git)?$") {
        return "$($Matches.owner)/$($Matches.repo)"
    }
    throw "Cannot infer GitHub repository from origin: $Remote. Pass -Repository owner/name."
}

if (-not $Repository) {
    $Repository = Resolve-Repository
}

if ($Keep -lt 0) {
    throw "Keep must be 0 or greater."
}

$GhCommand = Get-Command gh -ErrorAction SilentlyContinue
if (-not $GhCommand) {
    throw "GitHub CLI not found. Install gh and run gh auth login."
}

& gh auth status --hostname github.com | Out-Null

$ReleaseJson = (& gh release list `
    --repo $Repository `
    --json tagName,name,isDraft,isPrerelease,createdAt `
    --limit $Limit) -join "`n"
$ParsedReleases = $ReleaseJson | ConvertFrom-Json
$Releases = @($ParsedReleases)
$Matched = @(
    $Releases |
        Where-Object { $_.isDraft -and $_.tagName -match $TagPattern } |
        Sort-Object { [datetime]$_.createdAt } -Descending
)
$KeepReleases = @($Matched | Select-Object -First $Keep)
$PruneCandidates = @($Matched | Select-Object -Skip $Keep)

if ($Apply) {
    foreach ($Release in $PruneCandidates) {
        $Args = @("release", "delete", $Release.tagName, "--repo", $Repository, "--yes")
        if ($CleanupTag) {
            $Args += "--cleanup-tag"
        }
        & gh @Args
    }
}

[pscustomobject]@{
    dry_run = -not [bool]$Apply
    repository = $Repository
    tag_pattern = $TagPattern
    keep = $Keep
    cleanup_tag = [bool]$CleanupTag
    matched_count = $Matched.Count
    prune_count = $PruneCandidates.Count
    kept = @(
        $KeepReleases | ForEach-Object {
            [pscustomobject]@{
                tag = $_.tagName
                name = $_.name
                created_at = $_.createdAt
            }
        }
    )
    prune_candidates = @(
        $PruneCandidates | ForEach-Object {
            [pscustomobject]@{
                tag = $_.tagName
                name = $_.name
                created_at = $_.createdAt
            }
        }
    )
} | ConvertTo-Json -Depth 6
