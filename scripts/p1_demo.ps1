param(
    [ValidateSet("reset-seed", "status", "export-json", "export-csv")]
    [string]$Action = "status",
    [string]$Output
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path -LiteralPath $VenvPython) {
    $Python = $VenvPython
} elseif (Test-Path -LiteralPath $BundledPython) {
    $Python = $BundledPython
} else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        throw "Python not found. Install Python or create backend\.venv first."
    }
    $Python = $PythonCommand.Source
}

$EnvFile = Join-Path $Backend ".env"
if (Test-Path -LiteralPath $EnvFile) {
    Get-Content -LiteralPath $EnvFile | ForEach-Object {
        $Line = $_.Trim()
        if ($Line -and -not $Line.StartsWith("#") -and $Line.Contains("=")) {
            $Name, $Value = $Line.Split("=", 2)
            $Name = $Name.Trim()
            if (-not [Environment]::GetEnvironmentVariable($Name, "Process")) {
                [Environment]::SetEnvironmentVariable($Name, $Value.Trim(), "Process")
            }
        }
    }
}

$env:PYTHONPATH = Join-Path $Backend "src"
$Script = Join-Path $Root "scripts\p1_demo_data.py"

if ($Action -eq "export-json") {
    $Args = @($Script, "export", "--format", "json")
} elseif ($Action -eq "export-csv") {
    $Args = @($Script, "export", "--format", "csv")
} else {
    $Args = @($Script, $Action)
}

if ($Output) {
    $Args += @("--output", $Output)
}

& $Python @Args
