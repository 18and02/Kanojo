from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str
    llm_timeout_seconds: float
    memory_extraction_mode: str
    tts_base_url: str | None
    stt_base_url: str | None
    stt_api_key: str | None
    stt_model: str
    stt_timeout_seconds: float
    quiet_hours_start: int
    quiet_hours_end: int
    proactive_cooldown_minutes: int
    activity_grace_minutes: int = 10
    node_name: str = "local"
    node_role: str = "standalone"
    peer_base_url: str | None = None
    peer_timeout_seconds: float = 3
    memory_primary: str = "local"
    offline_write_behavior: str = "local_only"
    inference_primary: str = "auto"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=Path(os.getenv("KANOJO_DB_PATH", "data/kanojo.db")),
            node_name=os.getenv("KANOJO_NODE_NAME", "local"),
            node_role=os.getenv("KANOJO_NODE_ROLE", "standalone"),
            peer_base_url=os.getenv("KANOJO_PEER_BASE_URL"),
            peer_timeout_seconds=float(os.getenv("KANOJO_PEER_TIMEOUT", "3")),
            memory_primary=os.getenv("KANOJO_MEMORY_PRIMARY", "local"),
            offline_write_behavior=os.getenv("KANOJO_OFFLINE_WRITE_BEHAVIOR", "local_only"),
            inference_primary=os.getenv("KANOJO_INFERENCE_PRIMARY", "auto"),
            llm_base_url=os.getenv("KANOJO_LLM_BASE_URL"),
            llm_api_key=os.getenv("KANOJO_LLM_API_KEY"),
            llm_model=os.getenv("KANOJO_LLM_MODEL", "qwen3-14b"),
            llm_timeout_seconds=float(os.getenv("KANOJO_LLM_TIMEOUT", "60")),
            memory_extraction_mode=os.getenv("KANOJO_MEMORY_EXTRACTION", "hybrid"),
            tts_base_url=os.getenv("KANOJO_TTS_BASE_URL"),
            stt_base_url=os.getenv("KANOJO_STT_BASE_URL"),
            stt_api_key=os.getenv("KANOJO_STT_API_KEY"),
            stt_model=os.getenv("KANOJO_STT_MODEL", "whisper-1"),
            stt_timeout_seconds=float(os.getenv("KANOJO_STT_TIMEOUT", "120")),
            quiet_hours_start=int(os.getenv("KANOJO_QUIET_START", "23")),
            quiet_hours_end=int(os.getenv("KANOJO_QUIET_END", "8")),
            proactive_cooldown_minutes=int(os.getenv("KANOJO_PROACTIVE_COOLDOWN", "120")),
            activity_grace_minutes=int(os.getenv("KANOJO_ACTIVITY_GRACE_MINUTES", "10")),
        )
