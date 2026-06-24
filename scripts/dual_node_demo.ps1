param(
    [string]$PcBase = "http://kanojo-pc.local:8787",
    [string]$MacBase = "http://kanojo-mac.local:8787",
    [switch]$SkipChat,
    [switch]$WritebackTest,
    [switch]$CleanupAfterWrite
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$BackendPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path -LiteralPath $BackendPython) {
    $Python = $BackendPython
} elseif (Test-Path -LiteralPath $BundledPython) {
    $Python = $BundledPython
} else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        throw "Python not found."
    }
    $Python = $PythonCommand.Source
}

$ArgsList = @(
    (Join-Path $PSScriptRoot "dual_node_demo.py"),
    "--pc-base", $PcBase,
    "--mac-base", $MacBase
)
if ($SkipChat) {
    $ArgsList += "--skip-chat"
}
if ($WritebackTest) {
    $ArgsList += "--writeback-test"
}
if ($CleanupAfterWrite) {
    $ArgsList += "--cleanup-after-write"
}

& $Python @ArgsList
