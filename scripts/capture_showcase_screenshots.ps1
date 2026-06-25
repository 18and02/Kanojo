param(
    [string]$OutDir = "exports-showcase",
    [int]$Port = 0,
    [int]$RemoteDebuggingPort = 0,
    [switch]$EnsureBackend,
    [switch]$KeepServer
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$RootPath = $Root.Path
$Desktop = Join-Path $Root "desktop"
$BundledPnpm = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd"
$BundledNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"

function Resolve-RepoRelativeOutputPath {
    param([string]$Path, [string]$Name)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        throw "$Name must be relative to the repository root."
    }
    $FullPath = [System.IO.Path]::GetFullPath((Join-Path $RootPath $Path))
    $RootPrefix = $RootPath
    if (-not $RootPrefix.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $RootPrefix = "$RootPrefix$([System.IO.Path]::DirectorySeparatorChar)"
    }
    if ($FullPath -eq $RootPath -or -not $FullPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Name must resolve below the repository root: $Path"
    }
    return $FullPath
}

$Target = Resolve-RepoRelativeOutputPath -Path $OutDir -Name "OutDir"

$PnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
if ($PnpmCommand) {
    $Pnpm = $PnpmCommand.Source
} elseif (Test-Path -LiteralPath $BundledPnpm) {
    $Pnpm = $BundledPnpm
} else {
    throw "pnpm not found. Install pnpm globally or use the Codex bundled runtime."
}

if (Test-Path -LiteralPath $BundledNode) {
    $Node = $BundledNode
} else {
    $NodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if (-not $NodeCommand) {
        throw "node not found."
    }
    $Node = $NodeCommand.Source
}

$BrowserCandidates = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
)
$Browser = $BrowserCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $Browser) {
    throw "Microsoft Edge or Google Chrome was not found."
}

if ($EnsureBackend) {
    & (Join-Path $Root "scripts\start_backend.ps1") -BindAddress "0.0.0.0"
}

if ($Port -le 0) {
    $Port = Get-Random -Minimum 5200 -Maximum 5600
}
$BaseUrl = "http://127.0.0.1:$Port"
if ($RemoteDebuggingPort -le 0) {
    $RemoteDebuggingPort = Get-Random -Minimum 9300 -Maximum 9700
}
$ServerStarted = $false
$Existing = $null
try {
    $Existing = Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
} catch {
    $Existing = $null
}

if (-not $Existing) {
    $LogDir = $Target
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $ViteOutLog = Join-Path $LogDir "vite.stdout.log"
    $ViteErrLog = Join-Path $LogDir "vite.stderr.log"
    $ViteArgs = @("exec", "vite", "src/renderer", "--host", "127.0.0.1", "--port", "$Port", "--strictPort")
    $ViteProcess = Start-Process `
        -FilePath $Pnpm `
        -ArgumentList $ViteArgs `
        -WorkingDirectory $Desktop `
        -WindowStyle Hidden `
        -RedirectStandardOutput $ViteOutLog `
        -RedirectStandardError $ViteErrLog `
        -PassThru
    $ServerStarted = $true
    for ($Attempt = 0; $Attempt -lt 30; $Attempt += 1) {
        Start-Sleep -Milliseconds 500
        try {
            Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
            break
        } catch {
            if ($Attempt -eq 29) {
                throw "Vite server did not become ready at $BaseUrl. See $ViteOutLog and $ViteErrLog"
            }
        }
    }
}

try {
    & $Node (Join-Path $Root "scripts\capture_showcase_screenshots.cjs") `
        --url $BaseUrl `
        --out $Target `
        --browser $Browser `
        --remote-port "$RemoteDebuggingPort"
} finally {
    if ($ServerStarted -and -not $KeepServer -and $ViteProcess -and -not $ViteProcess.HasExited) {
        Stop-Process -Id $ViteProcess.Id -Force
    }
}
