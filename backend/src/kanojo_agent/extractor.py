from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from kanojo_agent.llm import LLMClient
from kanojo_agent.memory import infer_memory_kind
from kanojo_agent.settings import Settings


VALID_KINDS = {"event", "preference", "relationship", "reflection"}


@dataclass(frozen=True)
class MemoryCandidate:
    kind: str
    content: str
    importance: float
    confidence: float
    reason: str
    method: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryDecision:
    candidate: MemoryCandidate
    accepted: bool
    reason: str
    memory_id: int | None = None
    audit_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "accepted": self.accepted,
            "reason": self.reason,
            "memory_id": self.memory_id,
            "audit_id": self.audit_id,
        }


class MemoryExtractor:
    def __init__(self, settings: Settings, llm: LLMClient):
        self.settings = settings
        self.llm = llm

    async def extract(self, text: str) -> tuple[str, list[MemoryCandidate], str | None]:
        mode = self.settings.memory_extraction_mode.lower()
        if mode not in {"heuristic", "llm", "hybrid"}:
            mode = "hybrid"

        if mode in {"llm", "hybrid"} and self.llm.configured:
            try:
                candidates = await self._extract_with_llm(text)
                if mode == "hybrid" and not candidates:
                    fallback = self._extract_with_heuristic(text)
                    if fallback:
                        return "heuristic_fallback", fallback, "llm returned no durable candidates"
                return "llm", candidates, None
            except Exception as exc:  # pragma: no cover - depends on external model
                if mode == "llm":
                    return "llm", [], f"llm extraction failed: {type(exc).__name__}: {exc}"
                candidates = self._extract_with_heuristic(text)
                return "heuristic_fallback", candidates, (
                    f"llm extraction failed, used heuristic fallback: {type(exc).__name__}: {exc}"
                )

        return "heuristic", self._extract_with_heuristic(text), None

    async def _extract_with_llm(self, text: str) -> list[MemoryCandidate]:
        raw_items = await self.llm.extract_memory_json(text)
        candidates: list[MemoryCandidate] = []
        for item in raw_items:
            candidate = self._candidate_from_dict(item, method="llm")
            if candidate:
                candidates.append(candidate)
        return candidates

    def _extract_with_heuristic(self, text: str) -> list[MemoryCandidate]:
        kind = infer_memory_kind(text)
        if not kind:
            return []

        content = normalize_memory_content(kind, text)
        confidence = 0.65
        importance = 0.55
        if kind in {"event", "relationship"}:
            importance = 0.65
        if "可能" in text or "也许" in text or "大概" in text:
            confidence = 0.48

        return [
            MemoryCandidate(
                kind=kind,
                content=content,
                importance=importance,
                confidence=confidence,
                reason="heuristic marker matched",
                method="heuristic",
            )
        ]

    def _candidate_from_dict(self, item: dict[str, Any], method: str) -> MemoryCandidate | None:
        kind = str(item.get("kind", "")).strip()
        content = str(item.get("content", "")).strip()
        if kind not in VALID_KINDS or not content:
            return None
        return MemoryCandidate(
            kind=kind,
            content=content,
            importance=clamp_float(item.get("importance"), default=0.55),
            confidence=clamp_float(item.get("confidence"), default=0.6),
            reason=str(item.get("reason", "llm candidate")).strip() or "llm candidate",
            method=method,
        )


def normalize_memory_content(kind: str, text: str) -> str:
    content = " ".join(text.strip().split())
    if kind == "event":
        return content
    if kind == "preference":
        return content
    if kind == "relationship":
        return content
    return content


def clamp_float(value: Any, *, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, numeric))


def validate_candidate(candidate: MemoryCandidate) -> tuple[bool, str]:
    content = candidate.content.strip()
    if candidate.kind not in VALID_KINDS:
        return False, "invalid kind"
    if len(content) < 4:
        return False, "content too short"
    if len(content) > 240:
        return False, "content too long"
    if candidate.confidence < 0.55:
        return False, "confidence below threshold"
    return True, "accepted"
