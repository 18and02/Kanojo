param(
    [string]$OutDir = "exports-showcase-package",
    [string]$BaseUrl = "http://127.0.0.1:8787",
    [string]$ReleaseDir = "release",
    [switch]$EnsureBackend,
    [switch]$SkipEvaluation,
    [switch]$SkipScreenshots,
    [switch]$IncludeReleaseArtifacts
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

if ([System.IO.Path]::IsPathRooted($OutDir)) {
    throw "OutDir must be relative to the repository root."
}

$Target = Join-Path $Root $OutDir
$DocsTarget = Join-Path $Target "docs"
$ReleaseTarget = Join-Path $Target "release"
New-Item -ItemType Directory -Force -Path $Target, $DocsTarget | Out-Null

function ConvertTo-RepoRelativePath {
    param([string]$Path)
    $FullPath = [System.IO.Path]::GetFullPath($Path)
    if ($FullPath.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $FullPath.Substring($Root.Length).TrimStart("\", "/").Replace("\", "/")
    }
    return $FullPath
}

function Get-ArtifactEntry {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{
            name = [System.IO.Path]::GetFileName($Path)
            exists = $false
            path = ConvertTo-RepoRelativePath $Path
        }
    }
    $Item = Get-Item -LiteralPath $Path
    $Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Path
    return [pscustomobject]@{
        name = $Item.Name
        exists = $true
        path = ConvertTo-RepoRelativePath $Item.FullName
        bytes = $Item.Length
        sha256 = $Hash.Hash.ToLowerInvariant()
    }
}

if ($EnsureBackend) {
    & (Join-Path $Root "scripts\start_backend.ps1")
}

$GeneratedAt = (Get-Date).ToUniversalTime().ToString("o")
$ShortHash = (git -C $Root rev-parse --short HEAD).Trim()
$FullHash = (git -C $Root rev-parse HEAD).Trim()
$Dirty = -not [string]::IsNullOrWhiteSpace((git -C $Root status --porcelain))

$EvaluationFiles = @()
if (-not $SkipEvaluation) {
    $EvaluationOutDir = Join-Path $OutDir "evaluation"
    & (Join-Path $Root "scripts\export_evaluation_snapshot.ps1") -BaseUrl $BaseUrl -OutDir $EvaluationOutDir
    $EvaluationPath = Join-Path $Root $EvaluationOutDir
    $EvaluationFiles = @(
        Get-ChildItem -LiteralPath $EvaluationPath -File -ErrorAction SilentlyContinue |
            Sort-Object Name |
            ForEach-Object {
                [pscustomobject]@{
                    name = $_.Name
                    path = ConvertTo-RepoRelativePath $_.FullName
                    bytes = $_.Length
                }
            }
    )
}

$ScreenshotFiles = @()
if (-not $SkipScreenshots) {
    $ScreenshotOutDir = Join-Path $OutDir "screenshots"
    & (Join-Path $Root "scripts\capture_showcase_screenshots.ps1") -OutDir $ScreenshotOutDir
    $ScreenshotPath = Join-Path $Root $ScreenshotOutDir
    $ScreenshotFiles = @(
        Get-ChildItem -LiteralPath $ScreenshotPath -File -ErrorAction SilentlyContinue |
            Sort-Object Name |
            ForEach-Object {
                [pscustomobject]@{
                    name = $_.Name
                    path = ConvertTo-RepoRelativePath $_.FullName
                    bytes = $_.Length
                }
            }
    )
}

$DocSources = @(
    "README.md",
    "docs\DEMO_RUNBOOK.md",
    "docs\EVALUATION_PLAN.md",
    "docs\SHOWCASE_PACKAGE.md",
    "docs\DEFENSE_MATERIALS.md",
    "docs\FINAL_SELF_CHECK.md"
)
$DocFiles = foreach ($Doc in $DocSources) {
    $Source = Join-Path $Root $Doc
    if (Test-Path -LiteralPath $Source) {
        $Destination = Join-Path $DocsTarget ([System.IO.Path]::GetFileName($Doc))
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        $Item = Get-Item -LiteralPath $Destination
        [pscustomobject]@{
            name = $Item.Name
            path = ConvertTo-RepoRelativePath $Item.FullName
            bytes = $Item.Length
        }
    }
}

$ReleasePath = Join-Path $Root $ReleaseDir
$ReleaseArtifacts = @(
    Join-Path $ReleasePath "kanojo-source-$ShortHash.zip"
    Join-Path $ReleasePath "kanojo-desktop-portable-$ShortHash.zip"
    Join-Path $ReleasePath "SHA256SUMS-$ShortHash.txt"
)
$ReleaseEntries = @($ReleaseArtifacts | ForEach-Object { Get-ArtifactEntry -Path $_ })

if ($IncludeReleaseArtifacts) {
    New-Item -ItemType Directory -Force -Path $ReleaseTarget | Out-Null
    foreach ($Artifact in $ReleaseArtifacts) {
        if (Test-Path -LiteralPath $Artifact) {
            Copy-Item -LiteralPath $Artifact -Destination (Join-Path $ReleaseTarget ([System.IO.Path]::GetFileName($Artifact))) -Force
        }
    }
}

$Manifest = [pscustomobject]@{
    generated_at = $GeneratedAt
    commit = $ShortHash
    full_commit = $FullHash
    dirty = $Dirty
    base_url = $BaseUrl
    out_dir = ConvertTo-RepoRelativePath $Target
    evaluation = @{
        skipped = [bool]$SkipEvaluation
        files = $EvaluationFiles
    }
    screenshots = @{
        skipped = [bool]$SkipScreenshots
        files = $ScreenshotFiles
    }
    docs = $DocFiles
    release = @{
        copied = [bool]$IncludeReleaseArtifacts
        artifacts = $ReleaseEntries
    }
}

$ManifestPath = Join-Path $Target "showcase-package.json"
$Manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

$IndexLines = @(
    "# Kanojo Showcase Package",
    "",
    "- Generated UTC: ``$GeneratedAt``",
    "- Commit: ``$ShortHash``",
    "- Base URL: ``$BaseUrl``",
    "- Dirty working tree: ``$Dirty``",
    "",
    "## Core Files",
    "",
    "- Manifest: ``showcase-package.json``",
    "- Evaluation report: ``evaluation/evaluation-report.md``",
    "- Screenshot manifest: ``screenshots/showcase-screenshots.json``",
    "",
    "## Screenshots"
)

if ($ScreenshotFiles.Count -gt 0) {
    foreach ($File in $ScreenshotFiles | Where-Object { $_.Name -like "*.png" }) {
        $IndexLines += "- ``$($File.path)``"
    }
} else {
    $IndexLines += "- Skipped or not generated."
}

$IndexLines += @(
    "",
    "## Release Artifacts"
)
foreach ($Entry in $ReleaseEntries) {
    if ($Entry.exists) {
        $IndexLines += "- ``$($Entry.name)``: ``$($Entry.sha256)``"
    } else {
        $IndexLines += "- ``$($Entry.name)``: missing; run ``scripts\build_release.ps1`` first."
    }
}

$IndexLines += @(
    "",
    "## Included Docs"
)
foreach ($Doc in $DocFiles) {
    $IndexLines += "- ``$($Doc.path)``"
}

$IndexPath = Join-Path $Target "SHOWCASE_INDEX.md"
Set-Content -LiteralPath $IndexPath -Encoding UTF8 -Value $IndexLines

[pscustomobject]@{
    out_dir = $Target
    index = $IndexPath
    manifest = $ManifestPath
    commit = $ShortHash
    dirty = $Dirty
    evaluation_files = $EvaluationFiles.Count
    screenshot_files = $ScreenshotFiles.Count
    release_artifacts = ($ReleaseEntries | Where-Object { $_.exists }).Count
} | ConvertTo-Json -Depth 5
