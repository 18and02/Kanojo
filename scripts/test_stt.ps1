param(
    [string]$AudioPath,
    [string]$SttUrl = "http://127.0.0.1:9000/v1/audio/transcriptions",
    [string]$BackendUrl = "http://127.0.0.1:8787/stt/transcribe",
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not $AudioPath) {
    $AudioPath = Join-Path $Backend "data\stt-test-zh.wav"
}

if (-not (Test-Path -LiteralPath $AudioPath)) {
    throw "Audio file not found: $AudioPath"
}

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
from pathlib import Path
import sys

import httpx

audio_path = Path(sys.argv[1])
stt_url = sys.argv[2]
backend_url = sys.argv[3]
timeout_seconds = int(sys.argv[4])
audio = audio_path.read_bytes()
suffix = audio_path.suffix.lower()
content_type = {
    ".wav": "audio/wav",
    ".webm": "audio/webm",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".ogg": "audio/ogg",
}.get(suffix, "application/octet-stream")

with httpx.Client(timeout=timeout_seconds) as client:
    with audio_path.open("rb") as file:
        direct = client.post(
            stt_url,
            data={"model": "whisper-1"},
            files={"file": (audio_path.name, file, content_type)},
        )
    print(f"local STT: {direct.status_code}")
    print(direct.text)
    direct.raise_for_status()
    direct_text = direct.json().get("text", "").strip()
    if not direct_text:
        raise SystemExit("local STT returned empty text")

    proxied = client.post(
        backend_url,
        content=audio,
        headers={"Content-Type": content_type, "X-Filename": audio_path.name},
    )
    print(f"backend STT: {proxied.status_code}")
    print(proxied.text)
    proxied.raise_for_status()
    payload = proxied.json()
    if payload.get("error"):
        raise SystemExit(payload["error"])
    if not payload.get("text", "").strip():
        raise SystemExit("backend STT returned empty text")
'@

$Script | & $Python - $AudioPath $SttUrl $BackendUrl $TimeoutSeconds
