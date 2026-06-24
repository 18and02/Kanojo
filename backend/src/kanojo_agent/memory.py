from __future__ import annotations

from datetime import UTC, datetime
import math
import re
from typing import Any


WORD_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> set[str]:
    return {match.group(0).lower() for match in WORD_RE.finditer(text)}


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def recency_score(created_at: str | None, now: datetime | None = None) -> float:
    current = now or datetime.now(UTC)
    created = parse_time(created_at)
    age_hours = max((current - created).total_seconds() / 3600, 0)
    return math.exp(-age_hours / (24 * 14))


def relevance_score(query: str, content: str) -> float:
    query_tokens = tokenize(query)
    content_tokens = tokenize(content)
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = query_tokens & content_tokens
    return len(overlap) / len(query_tokens)


def score_memory(memory: dict[str, Any], query: str, now: datetime | None = None) -> float:
    relevance = relevance_score(query, str(memory.get("content", "")))
    importance = float(memory.get("importance") or 0.5)
    recency = recency_score(memory.get("created_at"), now=now)
    return round(0.55 * relevance + 0.25 * importance + 0.20 * recency, 4)


def infer_memory_kind(text: str) -> str | None:
    event_markers = ("今天", "明天", "昨天", "考试", "计划", "约", "要去", "准备")
    preference_markers = ("喜欢", "不喜欢", "讨厌", "偏好", "习惯", "想要")
    relationship_markers = ("叫我", "称呼", "名字", "关系", "边界")

    if any(marker in text for marker in relationship_markers):
        return "relationship"
    if any(marker in text for marker in preference_markers):
        return "preference"
    if any(marker in text for marker in event_markers):
        return "event"
    return None
