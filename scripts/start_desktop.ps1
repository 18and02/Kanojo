param(
    [switch]$EnsureBackend,
    [string]$BackendBindAddress = "0.0.0.0",
    [int]$BackendPort = 8787,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Desktop = Join-Path $Root "desktop"
$BundledPnpm = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd"

$PnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
if ($PnpmCommand) {
    $Pnpm = $PnpmCommand.Source
} elseif (Test-Path -LiteralPath $BundledPnpm) {
    $Pnpm = $BundledPnpm
} else {
    throw "pnpm not found. Install pnpm globally or use the Codex bundled runtime."
}

if ($Restart) {
    $DesktopPath = (Resolve-Path -LiteralPath $Desktop).Path
    Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -in @("electron.exe", "node.exe")) -and
        ($_.CommandLine -like "*$DesktopPath*")
    } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
    }
}

if ($EnsureBackend) {
    $BackendArgs = @{
        BindAddress = $BackendBindAddress
        Port = $BackendPort
    }
    if ($Restart) {
        $BackendArgs.Restart = $true
    }
    & (Join-Path $Root "scripts\start_backend.ps1") @BackendArgs
}

Push-Location $Desktop
try {
    & $Pnpm dev
}
finally {
    Pop-Location
}
