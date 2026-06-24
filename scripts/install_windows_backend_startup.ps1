param(
    [string]$ShortcutName = "Kanojo Backend",
    [string]$BindAddress = "0.0.0.0",
    [int]$Port = 8787,
    [switch]$RunNow,
    [switch]$SkipPrewarm
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$StartScript = Join-Path $Root "scripts\start_backend.ps1"

if (-not (Test-Path -LiteralPath $StartScript)) {
    throw "Backend start script not found: $StartScript"
}

$StartupDir = [Environment]::GetFolderPath("Startup")
if (-not $StartupDir) {
    throw "Unable to resolve the current user's Startup folder."
}

$Launcher = Join-Path $StartupDir "$ShortcutName.cmd"
$Arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$StartScript`"",
    "-BindAddress", "`"$BindAddress`"",
    "-Port", "$Port"
)
if ($SkipPrewarm) {
    $Arguments += "-SkipPrewarm"
}

$CommandLine = "powershell.exe " + ($Arguments -join " ")
Set-Content -LiteralPath $Launcher -Encoding ASCII -Value @(
    "@echo off",
    "cd /d `"$($Root.Path)`"",
    "start `"`" /min $CommandLine"
)

Write-Host "Installed startup launcher: $Launcher"
if ($RunNow) {
    & $StartScript -BindAddress $BindAddress -Port $Port -SkipPrewarm:$SkipPrewarm
}
