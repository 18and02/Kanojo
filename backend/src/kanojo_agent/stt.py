from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kanojo_agent.settings import Settings


class STTNotConfiguredError(RuntimeError):
    pass


class STTTranscriptionError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class STTTranscription:
    text: str
    model: str
    language: str | None = None
    duration: float | None = None
    latency_ms: int | None = None


class STTClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.stt_base_url)

    def transcriptions_url(self) -> str:
        if not self.settings.stt_base_url:
            raise STTNotConfiguredError("STT service is not configured.")
        base_url = self.settings.stt_base_url.rstrip("/")
        if base_url.endswith("/audio/transcriptions"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/audio/transcriptions"
        return f"{base_url}/v1/audio/transcriptions"

    def health_url(self) -> str:
        if not self.settings.stt_base_url:
            raise STTNotConfiguredError("STT service is not configured.")
        base_url = self.settings.stt_base_url.rstrip("/")
        if base_url.endswith("/v1/audio/transcriptions"):
            base_url = base_url[: -len("/v1/audio/transcriptions")]
        elif base_url.endswith("/audio/transcriptions"):
            base_url = base_url[: -len("/audio/transcriptions")]
        elif base_url.endswith("/v1"):
            base_url = base_url[: -len("/v1")]
        return f"{base_url}/health"

    async def health(self) -> dict[str, Any]:
        if not self.configured:
            raise STTNotConfiguredError("STT service is not configured.")

        import httpx

        try:
            async with httpx.AsyncClient(timeout=min(self.settings.stt_timeout_seconds, 10)) as client:
                response = await client.get(self.health_url())
                response.raise_for_status()
                payload = response.json()
        except Exception as error:
            return {
                "available": False,
                "health_url": self.health_url(),
                "error": str(error),
            }
        return {
            "available": True,
            "health_url": self.health_url(),
            "detail": payload,
        }

    async def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "recording.webm",
        content_type: str = "audio/webm",
    ) -> str:
        result = await self.transcribe_with_metadata(
            audio,
            filename=filename,
            content_type=content_type,
        )
        return result.text

    async def transcribe_with_metadata(
        self,
        audio: bytes,
        *,
        filename: str = "recording.webm",
        content_type: str = "audio/webm",
    ) -> STTTranscription:
        if not self.configured:
            raise STTNotConfiguredError("STT service is not configured.")
        if not audio:
            return STTTranscription(text="", model=self.settings.stt_model)

        import httpx

        headers = {}
        if self.settings.stt_api_key:
            headers["Authorization"] = f"Bearer {self.settings.stt_api_key}"

        files = {"file": (filename, audio, content_type or "application/octet-stream")}
        data = {"model": self.settings.stt_model}
        async with httpx.AsyncClient(timeout=self.settings.stt_timeout_seconds) as client:
            try:
                response = await client.post(
                    self.transcriptions_url(),
                    headers=headers,
                    data=data,
                    files=files,
                )
            except httpx.TimeoutException as error:
                raise STTTranscriptionError("STT service timed out.") from error
            except httpx.HTTPError as error:
                raise STTTranscriptionError(f"STT service request failed: {error}") from error

        if response.status_code >= 400:
            raise STTTranscriptionError(
                extract_error_message(response),
                status_code=response.status_code,
            )

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as error:
            raise STTTranscriptionError("STT service returned non-JSON response.") from error

        text = payload.get("text") or payload.get("transcription") or ""
        return STTTranscription(
            text=str(text).strip(),
            model=str(payload.get("model") or self.settings.stt_model),
            language=optional_str(payload.get("language")),
            duration=optional_float(payload.get("duration")),
            latency_ms=optional_int(payload.get("latency_ms")),
        )


def extract_error_message(response: Any) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("error") or payload.get("message")
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("detail") or detail
        if detail:
            return f"STT service failed ({response.status_code}): {detail}"
    return f"STT service failed ({response.status_code})."


def optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
