param(
    [string]$InstallRoot,
    [switch]$KeepShortcuts,
    [switch]$AllowCustomRoot
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

if ($InstallRoot) {
    if ([System.IO.Path]::IsPathRooted($InstallRoot)) {
        $ResolvedInstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
    } else {
        $ResolvedInstallRoot = [System.IO.Path]::GetFullPath((Join-Path $Root $InstallRoot))
    }
} else {
    $ResolvedInstallRoot = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "Kanojo\Desktop"
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
    if (-not $AllowCustomRoot -and ([System.IO.Path]::GetFileName($FullRoot) -ne "Desktop" -or $FullRoot -notmatch "Kanojo")) {
        throw "Refusing to remove unexpected install root: $FullRoot"
    }
    Remove-Item -LiteralPath $FullRoot -Recurse -Force
    $RemovedInstallRoot = $true
}

[pscustomobject]@{
    install_root = $ResolvedInstallRoot
    removed_install_root = $RemovedInstallRoot
    removed_shortcuts = $RemovedShortcuts
} | ConvertTo-Json -Depth 5
