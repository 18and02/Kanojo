param(
    [string]$ShortcutName = "Kanojo Backend"
)

$ErrorActionPreference = "Stop"

$StartupDir = [Environment]::GetFolderPath("Startup")
if (-not $StartupDir) {
    throw "Unable to resolve the current user's Startup folder."
}

$Launcher = Join-Path $StartupDir "$ShortcutName.cmd"
if (Test-Path -LiteralPath $Launcher) {
    Remove-Item -LiteralPath $Launcher -Force
    Write-Host "Removed startup launcher: $Launcher"
} else {
    Write-Host "Startup launcher not found: $Launcher"
}
