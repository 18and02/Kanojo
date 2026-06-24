from __future__ import annotations

import base64
from time import perf_counter
from typing import Any

from kanojo_agent.settings import Settings


class TTSError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TTSClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.tts_base_url)

    def synthesize_url(self) -> str:
        if not self.settings.tts_base_url:
            raise TTSError("TTS service is not configured.")
        base_url = self.settings.tts_base_url.rstrip("/")
        if base_url.endswith("/synthesize"):
            return base_url
        return f"{base_url}/synthesize"

    def health_url(self) -> str:
        if not self.settings.tts_base_url:
            raise TTSError("TTS service is not configured.")
        base_url = self.settings.tts_base_url.rstrip("/")
        if base_url.endswith("/synthesize"):
            base_url = base_url[: -len("/synthesize")]
        return f"{base_url}/health"

    async def health(self) -> dict[str, Any]:
        if not self.configured:
            return {
                "configured": False,
                "available": False,
                "error": "TTS service is not configured.",
            }

        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self.health_url())
        except httpx.ConnectError as error:
            return {
                "configured": True,
                "available": False,
                "health_url": self.health_url(),
                "error": str(error),
            }
        except httpx.HTTPError as error:
            return {
                "configured": True,
                "available": False,
                "health_url": self.health_url(),
                "error": str(error),
            }

        if response.status_code == 404:
            return {
                "configured": True,
                "available": True,
                "health_url": self.health_url(),
                "health_supported": False,
            }
        if response.status_code >= 400:
            return {
                "configured": True,
                "available": False,
                "health_url": self.health_url(),
                "error": extract_error_message(response),
            }

        return {
            "configured": True,
            "available": True,
            "health_url": self.health_url(),
            "health_supported": True,
            "detail": parse_optional_json(response),
        }

    async def synthesize(self, text: str) -> dict[str, Any]:
        if not self.settings.tts_base_url:
            return {"configured": False, "status": "desktop_speech_fallback", "text": text}

        import httpx

        started = perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(self.synthesize_url(), json={"text": text})
            except httpx.TimeoutException as error:
                raise TTSError("TTS service timed out.") from error
            except httpx.HTTPError as error:
                raise TTSError(f"TTS service request failed: {error}") from error

        if response.status_code >= 400:
            raise TTSError(extract_error_message(response), status_code=response.status_code)

        latency_ms = int((perf_counter() - started) * 1000)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type.startswith("audio/") or content_type == "application/octet-stream":
            return {
                "configured": True,
                "status": "ok",
                "text": text,
                "content_type": content_type or "application/octet-stream",
                "audio_base64": base64.b64encode(response.content).decode("ascii"),
                "latency_ms": latency_ms,
            }

        payload = parse_optional_json(response)
        if payload is None:
            raise TTSError("TTS service returned neither audio nor JSON.")
        return normalize_tts_payload(
            payload,
            text=text,
            latency_ms=latency_ms,
            base_url=self.settings.tts_base_url,
        )


def normalize_tts_payload(
    payload: dict[str, Any],
    *,
    text: str,
    latency_ms: int,
    base_url: str | None,
) -> dict[str, Any]:
    audio_url = payload.get("audio_url") or payload.get("url")
    if isinstance(audio_url, str) and audio_url.startswith("/") and base_url:
        audio_url = f"{base_url.rstrip('/')}{audio_url}"
    result = {
        "configured": True,
        "status": payload.get("status") or "ok",
        "text": payload.get("text") or text,
        "audio_url": audio_url,
        "audio_base64": payload.get("audio_base64") or payload.get("audio"),
        "content_type": payload.get("content_type") or payload.get("mime_type") or "audio/wav",
        "model": payload.get("model"),
        "latency_ms": payload.get("latency_ms") or latency_ms,
    }
    return {key: value for key, value in result.items() if value is not None}


def parse_optional_json(response: Any) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_error_message(response: Any) -> str:
    payload = parse_optional_json(response)
    if payload:
        detail = payload.get("detail") or payload.get("error") or payload.get("message")
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("detail") or detail
        if detail:
            return f"TTS service failed ({response.status_code}): {detail}"
    return f"TTS service failed ({response.status_code})."
