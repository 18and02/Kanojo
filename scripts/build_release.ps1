param(
    [string]$OutDir = "release",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
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
$Desktop = Join-Path $Root "desktop"
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
$BundledPnpm = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "backend\.venv not found. Create backend virtualenv first."
}

$PnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
if ($PnpmCommand) {
    $Pnpm = $PnpmCommand.Source
} elseif (Test-Path -LiteralPath $BundledPnpm) {
    $Pnpm = $BundledPnpm
} else {
    throw "pnpm not found."
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

if (-not $SkipTests) {
    & $Python -m pytest (Join-Path $Root "backend\tests")
    & $Python -m ruff check (Join-Path $Root "backend")
}

Push-Location $Desktop
try {
    & $Pnpm build
}
finally {
    Pop-Location
}

$ShortHash = (git -C $Root rev-parse --short HEAD).Trim()
$Archive = Join-Path $ReleaseDir "kanojo-source-$ShortHash.zip"
git -C $Root archive --format zip --output $Archive HEAD
$Portable = & (Join-Path $Root "scripts\build_desktop_portable.ps1") -OutDir $OutDir -SkipBuild
$Manifest = Join-Path $ReleaseDir "SHA256SUMS-$ShortHash.txt"
$Artifacts = @($Archive, $Portable.portable_archive)
$ManifestLines = foreach ($Artifact in $Artifacts) {
    $Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Artifact
    "$($Hash.Hash.ToLowerInvariant())  $([System.IO.Path]::GetFileName($Artifact))"
}
Set-Content -LiteralPath $Manifest -Encoding ASCII -Value $ManifestLines

[pscustomobject]@{
    source_archive = $Archive
    portable_archive = $Portable.portable_archive
    sha256_manifest = $Manifest
    commit = $ShortHash
    desktop_out = (Join-Path $Desktop "out")
} | ConvertTo-Json -Depth 4
