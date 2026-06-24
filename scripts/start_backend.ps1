param(
    [int]$Port = 8787,
    [string]$BindAddress = "127.0.0.1",
    [switch]$SkipPrewarm,
    [switch]$Restart
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

$Existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" -and $_.OwningProcess -gt 0 }
if ($Existing) {
    if ($Restart) {
        $Existing | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
            Stop-Process -Id $_ -Force
        }
        Start-Sleep -Seconds 1
    } else {
        Write-Host "Backend already listening on http://127.0.0.1:$Port"
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
    Start-Process -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "kanojo_agent.main:app", "--host", $BindAddress, "--port", "$Port") `
        -WorkingDirectory $Backend `
        -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" | Out-Null
    Write-Host "Backend started at http://$BindAddress`:$Port"
    $ShouldPrewarm = -not $SkipPrewarm -and (
        $env:KANOJO_PREWARM_ON_START -eq "true" -or
        $env:KANOJO_NODE_ROLE -eq "pc_inference"
    )
    if ($ShouldPrewarm) {
        try {
            $Body = @{ text = "预热 PC 推理节点" } | ConvertTo-Json -Depth 4
            $Prewarm = Invoke-RestMethod `
                -Uri "http://127.0.0.1:$Port/node/inference/prewarm" `
                -Method Post `
                -ContentType "application/json; charset=utf-8" `
                -Body $Body `
                -TimeoutSec 240
            Write-Host "Inference prewarmed with $($Prewarm.llm_model) in $($Prewarm.latency_ms)ms"
        }
        catch {
            Write-Warning "Backend started, but inference prewarm failed: $($_.Exception.Message)"
        }
    }
}
finally {
    Pop-Location
}
