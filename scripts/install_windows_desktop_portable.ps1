param(
    [string]$Archive,
    [string]$InstallRoot,
    [switch]$DesktopShortcut,
    [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Resolve-PortableArchive {
    if ($Archive) {
        if ([System.IO.Path]::IsPathRooted($Archive)) {
            return (Resolve-Path -LiteralPath $Archive).Path
        }
        return (Resolve-Path -LiteralPath (Join-Path $Root $Archive)).Path
    }
    $Latest = Get-ChildItem -LiteralPath (Join-Path $Root "release") -Filter "kanojo-desktop-portable-*.zip" -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $Latest) {
        throw "No portable archive found. Run scripts\build_release.ps1 first."
    }
    return $Latest.FullName
}

function Resolve-InstallRoot {
    if ($InstallRoot) {
        if ([System.IO.Path]::IsPathRooted($InstallRoot)) {
            return [System.IO.Path]::GetFullPath($InstallRoot)
        }
        return [System.IO.Path]::GetFullPath((Join-Path $Root $InstallRoot))
    }
    return Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "Kanojo\Desktop"
}

function Assert-SafeInstallPath {
    param([string]$Path, [string]$Base)
    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $FullBase = [System.IO.Path]::GetFullPath($Base)
    if (-not $FullPath.StartsWith($FullBase, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to install outside install root: $FullPath"
    }
    if ([System.IO.Path]::GetFileName($FullPath) -notlike "kanojo-desktop-portable-*") {
        throw "Refusing to replace unexpected install directory: $FullPath"
    }
}

function New-Shortcut {
    param(
        [string]$Path,
        [string]$Target,
        [string]$WorkingDirectory
    )
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($Path)
    $Shortcut.TargetPath = $Target
    $Shortcut.WorkingDirectory = $WorkingDirectory
    $Shortcut.IconLocation = $Target
    $Shortcut.Save()
}

$ArchivePath = Resolve-PortableArchive
$ResolvedInstallRoot = Resolve-InstallRoot
$InstallName = [System.IO.Path]::GetFileNameWithoutExtension($ArchivePath)
$InstallDir = Join-Path $ResolvedInstallRoot $InstallName

New-Item -ItemType Directory -Force -Path $ResolvedInstallRoot | Out-Null
if (Test-Path -LiteralPath $InstallDir) {
    Assert-SafeInstallPath -Path $InstallDir -Base $ResolvedInstallRoot
    Remove-Item -LiteralPath $InstallDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Expand-Archive -LiteralPath $ArchivePath -DestinationPath $InstallDir -Force

$Executable = Join-Path $InstallDir "Kanojo.exe"
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Installed portable package does not contain Kanojo.exe: $Executable"
}

$Shortcuts = @()
if (-not $NoShortcuts) {
    $ProgramsDir = Join-Path ([Environment]::GetFolderPath("Programs")) "Kanojo"
    New-Item -ItemType Directory -Force -Path $ProgramsDir | Out-Null
    $StartMenuShortcut = Join-Path $ProgramsDir "Kanojo.lnk"
    New-Shortcut -Path $StartMenuShortcut -Target $Executable -WorkingDirectory $InstallDir
    $Shortcuts += $StartMenuShortcut

    if ($DesktopShortcut) {
        $DesktopDir = [Environment]::GetFolderPath("Desktop")
        $DesktopShortcutPath = Join-Path $DesktopDir "Kanojo.lnk"
        New-Shortcut -Path $DesktopShortcutPath -Target $Executable -WorkingDirectory $InstallDir
        $Shortcuts += $DesktopShortcutPath
    }
}

[pscustomobject]@{
    archive = $ArchivePath
    install_root = $ResolvedInstallRoot
    install_dir = $InstallDir
    executable = $Executable
    shortcuts = $Shortcuts
} | ConvertTo-Json -Depth 5
