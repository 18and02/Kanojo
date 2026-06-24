from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from kanojo_agent.llm import LLMClient
from kanojo_agent.memory import infer_memory_kind
from kanojo_agent.settings import Settings


VALID_KINDS = {"event", "preference", "relationship", "reflection"}
OPERATIONAL_TEST_MARKERS = ("联调", "冒烟", "自检", "链路验证")


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

        if is_operational_test_text(text):
            return "filtered", [], "operational test text is not durable user memory"

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
            if candidate and candidate_supported_by_source(candidate, text):
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


def is_operational_test_text(text: str) -> bool:
    return any(marker in text for marker in OPERATIONAL_TEST_MARKERS)


def candidate_supported_by_source(candidate: MemoryCandidate, source_text: str) -> bool:
    content = normalize_for_support_check(candidate.content)
    source = normalize_for_support_check(source_text)
    if not content or not source:
        return False
    if content in source or source in content:
        return True

    content_bigrams = character_bigrams(content)
    if not content_bigrams:
        return content in source
    source_bigrams = character_bigrams(source)
    overlap_ratio = len(content_bigrams & source_bigrams) / len(content_bigrams)
    return overlap_ratio >= 0.55


def normalize_for_support_check(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower(), flags=re.UNICODE)


def character_bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text} if text else set()
    return {text[index : index + 2] for index in range(len(text) - 1)}


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
