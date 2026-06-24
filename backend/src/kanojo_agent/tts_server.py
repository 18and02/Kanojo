from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tempfile
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class LocalTTSSettings:
    voice: str | None
    rate: int
    volume: int
    timeout_seconds: int

    @classmethod
    def from_env(cls) -> "LocalTTSSettings":
        voice = os.getenv("KANOJO_LOCAL_TTS_VOICE")
        return cls(
            voice=voice or None,
            rate=int(os.getenv("KANOJO_LOCAL_TTS_RATE", "0")),
            volume=int(os.getenv("KANOJO_LOCAL_TTS_VOLUME", "100")),
            timeout_seconds=int(os.getenv("KANOJO_LOCAL_TTS_TIMEOUT", "60")),
        )


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)


settings = LocalTTSSettings.from_env()
app = FastAPI(title="Kanojo Local TTS Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "engine": "windows_sapi",
        "voice": settings.voice,
        "rate": settings.rate,
        "volume": settings.volume,
    }


@app.post("/synthesize")
def synthesize(request: TTSRequest) -> Response:
    started = perf_counter()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        temp_path = Path(temp_file.name)

    try:
        run_windows_sapi(request.text, temp_path)
        audio = temp_path.read_bytes()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    finally:
        temp_path.unlink(missing_ok=True)

    headers = {"X-Kanojo-TTS-Latency-Ms": str(int((perf_counter() - started) * 1000))}
    return Response(audio, media_type="audio/wav", headers=headers)


def run_windows_sapi(text: str, output_path: Path) -> None:
    script = r"""
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  if ($env:KANOJO_LOCAL_TTS_VOICE) {
    $synth.SelectVoice($env:KANOJO_LOCAL_TTS_VOICE)
  }
  $synth.Rate = [int]$env:KANOJO_LOCAL_TTS_RATE
  $synth.Volume = [int]$env:KANOJO_LOCAL_TTS_VOLUME
  $synth.SetOutputToWaveFile($env:KANOJO_TTS_OUTPUT_PATH)
  $text = [Console]::In.ReadToEnd()
  $synth.Speak($text)
}
finally {
  $synth.Dispose()
}
"""
    env = os.environ.copy()
    env["KANOJO_TTS_OUTPUT_PATH"] = str(output_path)
    env["KANOJO_LOCAL_TTS_RATE"] = str(settings.rate)
    env["KANOJO_LOCAL_TTS_VOLUME"] = str(settings.volume)
    if settings.voice:
        env["KANOJO_LOCAL_TTS_VOICE"] = settings.voice

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        input=text,
        text=True,
        capture_output=True,
        timeout=settings.timeout_seconds,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or "Windows SAPI synthesis failed.")
