from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import shutil
import tempfile
from time import perf_counter
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile


@dataclass(frozen=True)
class LocalSTTSettings:
    model_name: str
    device: str
    compute_type: str
    language: str | None
    beam_size: int
    vad_filter: bool

    @classmethod
    def from_env(cls) -> "LocalSTTSettings":
        language = os.getenv("KANOJO_LOCAL_STT_LANGUAGE")
        return cls(
            model_name=os.getenv("KANOJO_LOCAL_STT_MODEL", "base"),
            device=os.getenv("KANOJO_LOCAL_STT_DEVICE", "cpu"),
            compute_type=os.getenv("KANOJO_LOCAL_STT_COMPUTE_TYPE", "int8"),
            language=language or None,
            beam_size=int(os.getenv("KANOJO_LOCAL_STT_BEAM_SIZE", "5")),
            vad_filter=os.getenv("KANOJO_LOCAL_STT_VAD", "true").lower()
            not in {"0", "false", "no"},
        )


settings = LocalSTTSettings.from_env()
app = FastAPI(title="Kanojo Local STT Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": settings.model_name,
        "device": settings.device,
        "compute_type": settings.compute_type,
        "language": settings.language,
        "ffmpeg_path": shutil.which("ffmpeg"),
        "model_loaded": model_is_loaded(),
    }


@app.get("/ready")
def ready() -> dict[str, Any]:
    try:
        get_model()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return {
        "status": "ready",
        "model": settings.model_name,
        "device": settings.device,
        "compute_type": settings.compute_type,
        "language": settings.language,
        "model_loaded": model_is_loaded(),
    }


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: str | None = Form(None),
) -> dict[str, Any]:
    audio = await file.read()
    if not audio:
        return {"text": "", "model": model, "language": language}

    suffix = Path(file.filename or "recording.webm").suffix or ".webm"
    started = perf_counter()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(audio)
        temp_path = Path(temp_file.name)

    try:
        whisper_model = get_model()
        segments, info = whisper_model.transcribe(
            str(temp_path),
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            language=language or settings.language,
        )
        text = "".join(segment.text for segment in segments).strip()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "text": text,
        "model": settings.model_name,
        "language": getattr(info, "language", language),
        "duration": getattr(info, "duration", None),
        "latency_ms": int((perf_counter() - started) * 1000),
    }


@lru_cache(maxsize=1)
def get_model() -> Any:
    from faster_whisper import WhisperModel

    return WhisperModel(
        settings.model_name,
        device=settings.device,
        compute_type=settings.compute_type,
    )


def model_is_loaded() -> bool:
    return get_model.cache_info().currsize > 0
