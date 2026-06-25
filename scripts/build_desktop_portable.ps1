param(
    [string]$OutDir = "release",
    [switch]$SkipBuild
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

$Desktop = Join-Path $Root "desktop"
$ElectronDist = Join-Path $Desktop "node_modules\electron\dist"
$DesktopOut = Join-Path $Desktop "out"
$ReleaseDir = Resolve-RepoRelativeOutputPath -Path $OutDir -Name "OutDir"
$BundledPnpm = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd"

if (-not (Test-Path -LiteralPath $ElectronDist)) {
    throw "Electron runtime not found: $ElectronDist"
}

if (-not $SkipBuild) {
    $PnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
    if ($PnpmCommand) {
        $Pnpm = $PnpmCommand.Source
    } elseif (Test-Path -LiteralPath $BundledPnpm) {
        $Pnpm = $BundledPnpm
    } else {
        throw "pnpm not found."
    }

    Push-Location $Desktop
    try {
        & $Pnpm build
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath $DesktopOut)) {
    throw "Desktop build output not found: $DesktopOut"
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$ReleaseResolved = (Resolve-Path -LiteralPath $ReleaseDir).Path
$ShortHash = (git -C $Root rev-parse --short HEAD).Trim()
$PortableRoot = Join-Path $ReleaseResolved "kanojo-desktop-portable-$ShortHash"

if (Test-Path -LiteralPath $PortableRoot) {
    $PortableResolved = (Resolve-Path -LiteralPath $PortableRoot).Path
    if (-not $PortableResolved.StartsWith($ReleaseResolved, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside release directory: $PortableResolved"
    }
    Remove-Item -LiteralPath $PortableResolved -Recurse -Force
}

Copy-Item -LiteralPath $ElectronDist -Destination $PortableRoot -Recurse

$ElectronExe = Join-Path $PortableRoot "electron.exe"
$KanojoExe = Join-Path $PortableRoot "Kanojo.exe"
if (Test-Path -LiteralPath $KanojoExe) {
    Remove-Item -LiteralPath $KanojoExe -Force
}
Move-Item -LiteralPath $ElectronExe -Destination $KanojoExe

$AppDir = Join-Path $PortableRoot "resources\app"
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
Copy-Item -LiteralPath $DesktopOut -Destination (Join-Path $AppDir "out") -Recurse
Set-Content -LiteralPath (Join-Path $AppDir "package.json") -Encoding UTF8 -Value (@{
        name = "kanojo-agent-desktop"
        version = "0.1.0"
        type = "module"
        main = "out/main/main.js"
    } | ConvertTo-Json -Depth 4)

$PortableArchive = Join-Path $ReleaseResolved "kanojo-desktop-portable-$ShortHash.zip"
if (Test-Path -LiteralPath $PortableArchive) {
    Remove-Item -LiteralPath $PortableArchive -Force
}
Compress-Archive -Path (Join-Path $PortableRoot "*") -DestinationPath $PortableArchive -Force

[pscustomobject]@{
    portable_archive = $PortableArchive
    portable_dir = $PortableRoot
    executable = $KanojoExe
    commit = $ShortHash
}
