param(
    [string]$OutDir = "release",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$ReleaseDir = Join-Path $Root $OutDir
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

[pscustomobject]@{
    source_archive = $Archive
    commit = $ShortHash
    desktop_out = (Join-Path $Desktop "out")
} | ConvertTo-Json -Depth 4
