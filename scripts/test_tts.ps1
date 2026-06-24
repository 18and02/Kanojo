param(
    [string]$Text = "Hello, this is a local TTS smoke test.",
    [string]$TtsUrl = "http://127.0.0.1:9880/synthesize",
    [string]$BackendUrl = "http://127.0.0.1:8787/tts/synthesize",
    [int]$TimeoutSeconds = 120
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

$Script = @'
import base64
import sys

import httpx

text = sys.argv[1]
tts_url = sys.argv[2]
backend_url = sys.argv[3]
timeout_seconds = int(sys.argv[4])

with httpx.Client(timeout=timeout_seconds) as client:
    direct = client.post(tts_url, json={"text": text})
    print(f"local TTS: {direct.status_code} {direct.headers.get('content-type')}")
    direct.raise_for_status()
    if len(direct.content) < 44:
        raise SystemExit("local TTS returned too little audio data")

    proxied = client.post(backend_url, json={"text": text})
    print(f"backend TTS: {proxied.status_code}")
    print(proxied.text[:240])
    proxied.raise_for_status()
    payload = proxied.json()
    if payload.get("error"):
        raise SystemExit(payload["error"])
    audio_base64 = payload.get("audio_base64")
    if not audio_base64:
        raise SystemExit("backend TTS returned no audio_base64")
    if len(base64.b64decode(audio_base64)) < 44:
        raise SystemExit("backend TTS returned too little audio data")
'@

$Script | & $Python - $Text $TtsUrl $BackendUrl $TimeoutSeconds
