param(
    [int]$Port = 9000,
    [switch]$Restart,
    [switch]$InstallDeps,
    [switch]$Warmup
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

if ($InstallDeps) {
    & $Python -m pip install -e "$Backend[stt]"
}

$Existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" -and $_.OwningProcess -gt 0 }
if ($Existing) {
    if ($Restart) {
        $Existing | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
            Stop-Process -Id $_ -Force
        }
        Start-Sleep -Seconds 1
    } else {
        Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" | Out-Null
        if ($Warmup) {
            Invoke-RestMethod -Uri "http://127.0.0.1:$Port/ready" | Out-Null
        }
        Write-Host "STT service already listening on http://127.0.0.1:$Port"
        exit 0
    }
}

Push-Location $Backend
try {
    $EnvFile = Join-Path $Backend ".env"
    if (Test-Path -LiteralPath $EnvFile) {
        Get-Content -LiteralPath $EnvFile | ForEach-Object {
            $Line = $_.Trim()
            if ($Line -and -not $Line.StartsWith("#") -and $Line.Contains("=")) {
                $Name, $Value = $Line.Split("=", 2)
                [Environment]::SetEnvironmentVariable($Name.Trim(), $Value.Trim(), "Process")
            }
        }
    }
    $env:PYTHONPATH = Join-Path $Backend "src"
    $LogDir = Join-Path $Backend "data\logs"
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $StdoutLog = Join-Path $LogDir "stt-server.out.log"
    $StderrLog = Join-Path $LogDir "stt-server.err.log"
    Start-Process -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "kanojo_agent.stt_server:app", "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $Backend `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutLog `
        -RedirectStandardError $StderrLog
    Start-Sleep -Seconds 3
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" | Out-Null
        if ($Warmup) {
            Invoke-RestMethod -Uri "http://127.0.0.1:$Port/ready" | Out-Null
        }
    }
    catch {
        throw "STT service failed to start. See $StdoutLog and $StderrLog."
    }
    Write-Host "STT service started at http://127.0.0.1:$Port"
}
finally {
    Pop-Location
}
