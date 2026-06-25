param(
    [string]$Repository,
    [string]$Tag,
    [string]$Title,
    [string]$OutDir = "release",
    [switch]$SkipBuild,
    [switch]$DryRun,
    [switch]$Public,
    [switch]$Prerelease
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Resolve-RepoRelativeOutputPath {
    param([string]$Path, [string]$Name)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        throw "$Name must be relative to the repository root."
    }
    $FullPath = [System.IO.Path]::GetFullPath((Join-Path $Root $Path))
    $RootPrefix = $Root
    if (-not $RootPrefix.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $RootPrefix = "$RootPrefix$([System.IO.Path]::DirectorySeparatorChar)"
    }
    if ($FullPath -eq $Root -or -not $FullPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Name must resolve below the repository root: $Path"
    }
    return $FullPath
}

$ReleaseDir = Resolve-RepoRelativeOutputPath -Path $OutDir -Name "OutDir"

function Resolve-Repository {
    $Remote = (git -C $Root remote get-url origin).Trim()
    if ($Remote -match "github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(\.git)?$") {
        return "$($Matches.owner)/$($Matches.repo)"
    }
    throw "Cannot infer GitHub repository from origin: $Remote. Pass -Repository owner/name."
}

function Test-GitHubReleaseExists {
    param(
        [string]$ReleaseTag,
        [string]$Repo
    )
    $StdOut = [System.IO.Path]::GetTempFileName()
    $StdErr = [System.IO.Path]::GetTempFileName()
    try {
        $Process = Start-Process `
            -FilePath $GhCommand.Source `
            -ArgumentList @("release", "view", $ReleaseTag, "--repo", $Repo) `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput $StdOut `
            -RedirectStandardError $StdErr `
            -Wait
        return $Process.ExitCode -eq 0
    } finally {
        Remove-Item -LiteralPath $StdOut, $StdErr -Force -ErrorAction SilentlyContinue
    }
}

function Get-GitHubReleaseAssetNames {
    param(
        [string]$ReleaseTag,
        [string]$Repo
    )
    $StdOut = [System.IO.Path]::GetTempFileName()
    $StdErr = [System.IO.Path]::GetTempFileName()
    try {
        $Process = Start-Process `
            -FilePath $GhCommand.Source `
            -ArgumentList @("release", "view", $ReleaseTag, "--repo", $Repo, "--json", "assets", "--jq", ".assets[].name") `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput $StdOut `
            -RedirectStandardError $StdErr `
            -Wait
        if ($Process.ExitCode -ne 0) {
            $ErrorText = Get-Content -Raw -LiteralPath $StdErr -ErrorAction SilentlyContinue
            throw "Failed to read release assets: $ErrorText"
        }
        return @(Get-Content -LiteralPath $StdOut -ErrorAction SilentlyContinue)
    } finally {
        Remove-Item -LiteralPath $StdOut, $StdErr -Force -ErrorAction SilentlyContinue
    }
}

if (-not $Repository) {
    $Repository = Resolve-Repository
}

$ShortHash = (git -C $Root rev-parse --short HEAD).Trim()
$FullHash = (git -C $Root rev-parse HEAD).Trim()
if (-not $Tag) {
    $Tag = "kanojo-$ShortHash"
}
if (-not $Title) {
    $Title = "Kanojo demo build $ShortHash"
}

if (-not $SkipBuild) {
    & (Join-Path $Root "scripts\build_release.ps1") -OutDir $OutDir
}

$Artifacts = @(
    Join-Path $ReleaseDir "kanojo-source-$ShortHash.zip"
    Join-Path $ReleaseDir "kanojo-desktop-portable-$ShortHash.zip"
    Join-Path $ReleaseDir "SHA256SUMS-$ShortHash.txt"
)

foreach ($Artifact in $Artifacts) {
    if (-not (Test-Path -LiteralPath $Artifact)) {
        throw "Missing release artifact: $Artifact"
    }
}

$NotesFile = Join-Path $ReleaseDir "release-notes-$ShortHash.md"
$Notes = @(
    "# Kanojo demo build $ShortHash"
    ""
    "- Commit: ``$FullHash``"
    "- Source archive: ``kanojo-source-$ShortHash.zip``"
    "- Portable desktop: ``kanojo-desktop-portable-$ShortHash.zip``"
    "- Checksums: ``SHA256SUMS-$ShortHash.txt``"
    ""
    "## Verify"
    ""
    "Download the source archive, portable desktop zip, and checksum file. From the repository root or extracted source archive, verify the portable package with:"
    ""
    '```powershell'
    "Get-FileHash .\release\kanojo-desktop-portable-$ShortHash.zip -Algorithm SHA256"
    "Get-Content .\release\SHA256SUMS-$ShortHash.txt"
    '```'
    ""
    "## Run"
    ""
    "Start the backend first:"
    ""
    '```powershell'
    ".\scripts\start_backend.ps1 -BindAddress 0.0.0.0"
    '```'
    ""
    "Then install the portable desktop build for the current Windows user:"
    ""
    '```powershell'
    ".\scripts\install_windows_desktop_portable.ps1 -Archive .\release\kanojo-desktop-portable-$ShortHash.zip"
    '```'
    ""
    "The installer validates ``Kanojo.exe`` and creates a Start Menu shortcut by default. For a manual run, extract the portable zip and launch ``Kanojo.exe`` from the extracted directory."
    ""
    "## Showcase package"
    ""
    "Generate a reviewable demo package with screenshots, evaluation report, talk track, recording plan, and slideshow fallback:"
    ""
    '```powershell'
    ".\scripts\build_showcase_package.ps1 -OutDir exports-showcase-package"
    '```'
    ""
    "Open ``exports-showcase-package\SHOWCASE_INDEX.md`` first. Key generated files include ``demo-talk-track.md``, ``recording-plan.md``, and ``showcase-slideshow.mp4`` when ``ffmpeg`` is available."
)
Set-Content -LiteralPath $NotesFile -Encoding UTF8 -Value $Notes

if ($DryRun) {
    [pscustomobject]@{
        dry_run = $true
        repository = $Repository
        tag = $Tag
        title = $Title
        target = $FullHash
        draft = -not $Public
        prerelease = [bool]$Prerelease
        artifacts = $Artifacts
        notes_file = $NotesFile
    } | ConvertTo-Json -Depth 5
    exit 0
}

$GhCommand = Get-Command gh -ErrorAction SilentlyContinue
if (-not $GhCommand) {
    throw "GitHub CLI not found. Install gh and run gh auth login."
}

$ReleaseExists = $false
& gh auth status --hostname github.com | Out-Null
$ReleaseExists = Test-GitHubReleaseExists -ReleaseTag $Tag -Repo $Repository

if ($ReleaseExists) {
    $EditArgs = @("release", "edit", $Tag, "--repo", $Repository, "--title", $Title, "--notes-file", $NotesFile)
    if ($Public) {
        $EditArgs += "--draft=false"
    } else {
        $EditArgs += "--draft=true"
    }
    if ($Prerelease) {
        $EditArgs += "--prerelease"
    } else {
        $EditArgs += "--prerelease=false"
    }
    & gh @EditArgs
    & gh release upload $Tag @Artifacts --repo $Repository --clobber
} else {
    $CreateArgs = @(
        "release", "create", $Tag
    ) + $Artifacts + @(
        "--repo", $Repository,
        "--target", $FullHash,
        "--title", $Title,
        "--notes-file", $NotesFile
    )
    if (-not $Public) {
        $CreateArgs += "--draft"
    }
    if ($Prerelease) {
        $CreateArgs += "--prerelease"
    }
    & gh @CreateArgs
}

$ExpectedAssetNames = @($Artifacts | ForEach-Object { [System.IO.Path]::GetFileName($_) })
$UploadedAssetNames = @(Get-GitHubReleaseAssetNames -ReleaseTag $Tag -Repo $Repository)
$MissingAssetNames = @($ExpectedAssetNames | Where-Object { $_ -notin $UploadedAssetNames })
if ($MissingAssetNames.Count -gt 0) {
    $MissingArtifacts = @(
        $Artifacts | Where-Object {
            [System.IO.Path]::GetFileName($_) -in $MissingAssetNames
        }
    )
    & gh release upload $Tag @MissingArtifacts --repo $Repository --clobber
    $UploadedAssetNames = @(Get-GitHubReleaseAssetNames -ReleaseTag $Tag -Repo $Repository)
    $MissingAssetNames = @($ExpectedAssetNames | Where-Object { $_ -notin $UploadedAssetNames })
    if ($MissingAssetNames.Count -gt 0) {
        throw "Release upload incomplete. Missing assets: $($MissingAssetNames -join ', ')"
    }
}

[pscustomobject]@{
    published = $true
    repository = $Repository
    tag = $Tag
    title = $Title
    target = $FullHash
    draft = -not $Public
    prerelease = [bool]$Prerelease
    artifacts = $Artifacts
    notes_file = $NotesFile
} | ConvertTo-Json -Depth 5
