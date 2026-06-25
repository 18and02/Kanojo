param(
    [string]$InstallRoot,
    [switch]$KeepShortcuts,
    [switch]$AllowCustomRoot
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$DefaultInstallRoot = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "Kanojo\Desktop"
$CustomInstallRoot = [bool]$InstallRoot

function Test-SamePath {
    param([string]$Left, [string]$Right)
    $FullLeft = [System.IO.Path]::GetFullPath($Left).TrimEnd("\", "/")
    $FullRight = [System.IO.Path]::GetFullPath($Right).TrimEnd("\", "/")
    return $FullLeft -eq $FullRight
}

function Test-ChildPath {
    param([string]$Path, [string]$Base)
    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $FullBase = [System.IO.Path]::GetFullPath($Base)
    if (-not $FullBase.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $FullBase = "$FullBase$([System.IO.Path]::DirectorySeparatorChar)"
    }
    return $FullPath.StartsWith($FullBase, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-SafeUninstallRoot {
    param([string]$Path)
    $FullRoot = [System.IO.Path]::GetFullPath($Path)
    if (Test-SamePath -Left $FullRoot -Right $DefaultInstallRoot) {
        return
    }
    if (-not $CustomInstallRoot) {
        throw "Refusing to remove unexpected default install root: $FullRoot"
    }
    if (-not $AllowCustomRoot) {
        throw "Custom InstallRoot requires -AllowCustomRoot: $FullRoot"
    }
    $RepoRoot = [System.IO.Path]::GetFullPath($Root)
    $LocalKanojoRoot = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "Kanojo"
    if ((Test-ChildPath -Path $FullRoot -Base $RepoRoot) -or (Test-ChildPath -Path $FullRoot -Base $LocalKanojoRoot)) {
        return
    }
    throw "Refusing to remove custom install root outside repository or local Kanojo directory: $FullRoot"
}

if ($InstallRoot) {
    if ([System.IO.Path]::IsPathRooted($InstallRoot)) {
        $ResolvedInstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
    } else {
        $ResolvedInstallRoot = [System.IO.Path]::GetFullPath((Join-Path $Root $InstallRoot))
    }
} else {
    $ResolvedInstallRoot = $DefaultInstallRoot
}

$RemovedShortcuts = @()
if (-not $KeepShortcuts) {
    $ShortcutCandidates = @(
        Join-Path ([Environment]::GetFolderPath("Programs")) "Kanojo\Kanojo.lnk"
        Join-Path ([Environment]::GetFolderPath("Desktop")) "Kanojo.lnk"
    )
    foreach ($Shortcut in $ShortcutCandidates) {
        if (Test-Path -LiteralPath $Shortcut) {
            Remove-Item -LiteralPath $Shortcut -Force
            $RemovedShortcuts += $Shortcut
        }
    }
}

$RemovedInstallRoot = $false
if (Test-Path -LiteralPath $ResolvedInstallRoot) {
    $FullRoot = [System.IO.Path]::GetFullPath($ResolvedInstallRoot)
    Assert-SafeUninstallRoot -Path $FullRoot
    Remove-Item -LiteralPath $FullRoot -Recurse -Force
    $RemovedInstallRoot = $true
}

[pscustomobject]@{
    install_root = $ResolvedInstallRoot
    removed_install_root = $RemovedInstallRoot
    removed_shortcuts = $RemovedShortcuts
} | ConvertTo-Json -Depth 5
