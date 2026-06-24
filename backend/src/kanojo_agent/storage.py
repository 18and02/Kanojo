from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

from kanojo_agent.memory import score_memory


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


MEMORY_CARD_KIND_ORDER = ("relationship", "preference", "event", "reflection")
MEMORY_CARD_KIND_LABELS = {
    "relationship": "关系状态",
    "preference": "偏好",
    "event": "事件",
    "reflection": "反思",
}


class MemoryStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_message_id INTEGER,
                    importance REAL NOT NULL DEFAULT 0.5,
                    confidence REAL NOT NULL DEFAULT 0.7,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(source_message_id) REFERENCES messages(id)
                );

                CREATE TABLE IF NOT EXISTS heartbeat_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fired INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_message_id INTEGER NOT NULL,
                    method TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    candidate_json TEXT,
                    accepted INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    memory_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_message_id) REFERENCES messages(id),
                    FOREIGN KEY(memory_id) REFERENCES memories(id)
                );

                CREATE TABLE IF NOT EXISTS evaluation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    session_id TEXT,
                    source TEXT,
                    latency_ms INTEGER,
                    memory_hit_count INTEGER NOT NULL DEFAULT 0,
                    memory_hit_ids TEXT NOT NULL DEFAULT '[]',
                    created_memory_ids TEXT NOT NULL DEFAULT '[]',
                    heartbeat_event_id INTEGER,
                    fired INTEGER,
                    reason TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(heartbeat_event_id) REFERENCES heartbeat_events(id)
                );

                CREATE TABLE IF NOT EXISTS memory_card_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    label TEXT,
                    card_json TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    memory_count INTEGER NOT NULL,
                    conversation_count INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS activity_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    activity_type TEXT NOT NULL,
                    source TEXT,
                    intensity REAL NOT NULL DEFAULT 1.0,
                    note TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    def add_message(self, session_id: str, role: str, content: str) -> int:
        now = utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages(session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, now),
            )
            return int(cur.lastrowid)

    def add_memory(
        self,
        kind: str,
        content: str,
        source_message_id: int | None = None,
        importance: float = 0.5,
        confidence: float = 0.7,
    ) -> int:
        now = utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO memories(
                    kind, content, source_message_id, importance, confidence, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (kind, content, source_message_id, importance, confidence, now, now),
            )
            return int(cur.lastrowid)

    def find_duplicate_memory(self, kind: str, content: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, kind, content, source_message_id, importance, confidence, created_at, updated_at
                FROM memories
                WHERE status = 'active' AND kind = ? AND content = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (kind, content),
            ).fetchone()
        return dict(row) if row else None

    def memory_by_id(self, memory_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, kind, content, source_message_id, importance, confidence,
                       status, created_at, updated_at
                FROM memories
                WHERE id = ?
                """,
                (memory_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_memory(
        self,
        memory_id: int,
        *,
        content: str | None = None,
        importance: float | None = None,
        confidence: float | None = None,
    ) -> dict[str, Any] | None:
        updates: list[str] = []
        params: list[Any] = []
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)
        if confidence is not None:
            updates.append("confidence = ?")
            params.append(confidence)
        if not updates:
            return self.memory_by_id(memory_id)

        updates.append("updated_at = ?")
        params.append(utc_now())
        params.append(memory_id)
        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE memories
                SET {", ".join(updates)}
                WHERE id = ?
                """,
                tuple(params),
            )
        return self.memory_by_id(memory_id)

    def active_memories_matching_content(
        self, patterns: list[str], limit: int = 100
    ) -> list[dict[str, Any]]:
        clean_patterns = [pattern.strip() for pattern in patterns if pattern.strip()]
        if not clean_patterns:
            return []
        limit = max(1, min(limit, 500))
        where_clause = " OR ".join("content LIKE ?" for _ in clean_patterns)
        params: list[Any] = [f"%{pattern}%" for pattern in clean_patterns]
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, kind, content, source_message_id, importance, confidence,
                       status, created_at, updated_at
                FROM memories
                WHERE status = 'active' AND ({where_clause})
                ORDER BY id ASC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def deactivate_memories(self, memory_ids: list[int]) -> int:
        unique_ids = sorted({int(memory_id) for memory_id in memory_ids if int(memory_id) > 0})
        if not unique_ids:
            return 0
        placeholders = ", ".join("?" for _ in unique_ids)
        params: list[Any] = ["inactive", utc_now(), *unique_ids]
        with self.connect() as conn:
            cur = conn.execute(
                f"""
                UPDATE memories
                SET status = ?, updated_at = ?
                WHERE status = 'active' AND id IN ({placeholders})
                """,
                tuple(params),
            )
            return int(cur.rowcount)

    def add_memory_audit(
        self,
        *,
        source_message_id: int,
        method: str,
        raw_text: str,
        candidate: dict[str, Any] | None,
        accepted: bool,
        reason: str,
        memory_id: int | None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO memory_audits(
                    source_message_id, method, raw_text, candidate_json,
                    accepted, reason, memory_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_message_id,
                    method,
                    raw_text,
                    json.dumps(candidate, ensure_ascii=False) if candidate else None,
                    1 if accepted else 0,
                    reason,
                    memory_id,
                    utc_now(),
                ),
            )
            return int(cur.lastrowid)

    def memory_audit_by_id(self, audit_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, source_message_id, method, raw_text, candidate_json,
                       accepted, reason, memory_id, created_at
                FROM memory_audits
                WHERE id = ?
                """,
                (audit_id,),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["accepted"] = bool(item["accepted"])
        item["candidate"] = json.loads(item["candidate_json"]) if item.get("candidate_json") else None
        del item["candidate_json"]
        item["decision"] = self._memory_audit_decision(item)
        return item

    def update_memory_audit_decision(
        self,
        audit_id: int,
        *,
        accepted: bool,
        reason: str,
        memory_id: int | None,
        candidate: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self.connect() as conn:
            if candidate is None:
                conn.execute(
                    """
                    UPDATE memory_audits
                    SET accepted = ?, reason = ?, memory_id = ?
                    WHERE id = ?
                    """,
                    (1 if accepted else 0, reason, memory_id, audit_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE memory_audits
                    SET accepted = ?, reason = ?, memory_id = ?, candidate_json = ?
                    WHERE id = ?
                    """,
                    (
                        1 if accepted else 0,
                        reason,
                        memory_id,
                        json.dumps(candidate, ensure_ascii=False),
                        audit_id,
                    ),
                )
        return self.memory_audit_by_id(audit_id)

    def search_memories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, kind, content, source_message_id, importance, confidence, created_at, updated_at
                FROM memories
                WHERE status = 'active'
                ORDER BY updated_at DESC
                LIMIT 200
                """
            ).fetchall()

        memories = [dict(row) for row in rows]
        for memory in memories:
            memory["score"] = score_memory(memory, query)
        memories.sort(key=lambda item: item["score"], reverse=True)
        return memories[:limit]

    def memory_card(self, session_id: str = "default", limit_per_kind: int = 6) -> dict[str, Any]:
        with self.connect() as conn:
            memory_rows = conn.execute(
                """
                SELECT id, kind, content, source_message_id, importance, confidence,
                       created_at, updated_at
                FROM memories
                WHERE status = 'active'
                ORDER BY importance DESC, confidence DESC, updated_at DESC, id DESC
                """
            ).fetchall()
            conversation_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM messages
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()["count"]
            )
            latest_message = conn.execute(
                """
                SELECT created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()

        memories = [dict(row) for row in memory_rows]
        grouped: dict[str, list[dict[str, Any]]] = {kind: [] for kind in MEMORY_CARD_KIND_ORDER}
        for memory in memories:
            grouped.setdefault(str(memory["kind"]), []).append(memory)

        sections = []
        for kind in MEMORY_CARD_KIND_ORDER:
            items = grouped.get(kind, [])[:limit_per_kind]
            sections.append(
                {
                    "kind": kind,
                    "title": MEMORY_CARD_KIND_LABELS[kind],
                    "items": [memory_card_item(item) for item in items],
                }
            )

        memory_count = len(memories)
        non_empty_titles = [section["title"] for section in sections if section["items"]]
        summary = (
            f"已沉淀 {memory_count} 条长期记忆,覆盖 {'、'.join(non_empty_titles)}。"
            if memory_count
            else "暂无长期记忆,需要通过对话先沉淀事件、偏好或关系状态。"
        )
        card = {
            "title": "AI 记忆名片",
            "session_id": session_id,
            "generated_at": utc_now(),
            "memory_count": memory_count,
            "conversation_count": conversation_count,
            "latest_message_at": latest_message["created_at"] if latest_message else None,
            "summary": summary,
            "sections": sections,
        }
        card["markdown"] = memory_card_markdown(card)
        return card

    def create_memory_card_snapshot(
        self, session_id: str = "default", label: str | None = None
    ) -> dict[str, Any]:
        card = self.memory_card(session_id=session_id)
        created_at = utc_now()
        clean_label = label.strip() if label and label.strip() else None
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO memory_card_snapshots(
                    session_id, label, card_json, markdown, memory_count,
                    conversation_count, summary, generated_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    clean_label,
                    json.dumps(card, ensure_ascii=False),
                    card["markdown"],
                    int(card["memory_count"]),
                    int(card["conversation_count"]),
                    str(card["summary"]),
                    str(card["generated_at"]),
                    created_at,
                ),
            )
            snapshot_id = int(cur.lastrowid)
        snapshot = self.memory_card_snapshot(snapshot_id)
        if snapshot is None:  # pragma: no cover - defensive guard for SQLite write failure.
            raise RuntimeError("memory card snapshot was not persisted")
        return snapshot

    def memory_card_snapshots(
        self, session_id: str = "default", limit: int = 20
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, label, memory_count, conversation_count,
                       summary, generated_at, created_at
                FROM memory_card_snapshots
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [memory_card_snapshot_summary(row) for row in rows]

    def memory_card_snapshot(self, snapshot_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, session_id, label, card_json, markdown, memory_count,
                       conversation_count, summary, generated_at, created_at
                FROM memory_card_snapshots
                WHERE id = ?
                """,
                (snapshot_id,),
            ).fetchone()
        return memory_card_snapshot_from_row(row) if row else None

    def compare_memory_card_snapshot(self, snapshot_id: int) -> dict[str, Any] | None:
        snapshot = self.memory_card_snapshot(snapshot_id)
        if snapshot is None:
            return None
        current = self.memory_card(session_id=str(snapshot["session_id"]))
        return {
            "snapshot": snapshot,
            "current": current,
            "diff": memory_card_diff(snapshot["card"], current),
        }

    def memory_reflection_summary(self, session_id: str = "default") -> dict[str, Any]:
        card = self.memory_card(session_id=session_id)
        themes = memory_reflection_themes(card)
        non_empty_themes = [theme for theme in themes if theme["count"] > 0]
        sample_ready = card["memory_count"] >= 4 and len(non_empty_themes) >= 2
        readiness = "样本充足" if sample_ready else "样本不足"
        if card["memory_count"] == 0:
            summary = "暂无长期记忆,还不能形成可靠反思。"
        elif sample_ready:
            covered = "、".join(theme["title"] for theme in non_empty_themes)
            summary = f"当前长期记忆已覆盖 {covered},可以作为阶段性反思摘要。"
        else:
            summary = "当前长期记忆仍偏少,先作为草稿反思,后续需要更多对话样本校准。"
        result = {
            "title": "AI 反思摘要",
            "session_id": session_id,
            "generated_at": utc_now(),
            "memory_count": card["memory_count"],
            "conversation_count": card["conversation_count"],
            "sample_ready": sample_ready,
            "readiness": readiness,
            "summary": summary,
            "themes": themes,
            "next_questions": memory_reflection_next_questions(themes),
        }
        result["markdown"] = memory_reflection_markdown(result)
        return result

    def recent_memory_audits(
        self,
        limit: int = 20,
        *,
        offset: int = 0,
        accepted: bool | None = None,
        decision: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if accepted is not None:
            where.append("accepted = ?")
            params.append(1 if accepted else 0)
        if decision == "accepted":
            where.append("(accepted = 1 OR memory_id IS NOT NULL)")
        elif decision == "pending":
            where.append("accepted = 0 AND memory_id IS NULL AND reason LIKE 'pending%'")
        elif decision == "rejected":
            where.append("accepted = 0 AND memory_id IS NULL AND reason NOT LIKE 'pending%'")
        if query:
            where.append("(raw_text LIKE ? OR candidate_json LIKE ? OR reason LIKE ? OR method LIKE ?)")
            pattern = f"%{query}%"
            params.extend([pattern, pattern, pattern, pattern])
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        params.extend([limit, offset])
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, source_message_id, method, raw_text, candidate_json,
                       accepted, reason, memory_id, created_at
                FROM memory_audits
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params),
            ).fetchall()
        audits = []
        for row in rows:
            item = dict(row)
            item["accepted"] = bool(item["accepted"])
            if item.get("candidate_json"):
                item["candidate"] = json.loads(item["candidate_json"])
            else:
                item["candidate"] = None
            del item["candidate_json"]
            item["decision"] = self._memory_audit_decision(item)
            audits.append(item)
        return audits

    @staticmethod
    def _memory_audit_decision(item: dict[str, Any]) -> str:
        if item.get("accepted") or item.get("memory_id"):
            return "accepted"
        reason = str(item.get("reason") or "").lower()
        if reason.startswith("pending"):
            return "pending"
        return "rejected"

    def recent_messages(self, session_id: str, limit: int = 12) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def record_heartbeat(self, fired: bool, reason: str, message: str | None) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO heartbeat_events(fired, reason, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (1 if fired else 0, reason, message, utc_now()),
            )
            return int(cur.lastrowid)

    def record_evaluation_event(
        self,
        *,
        event_type: str,
        session_id: str | None = None,
        source: str | None = None,
        latency_ms: int | None = None,
        memory_hit_ids: list[int] | None = None,
        created_memory_ids: list[int] | None = None,
        heartbeat_event_id: int | None = None,
        fired: bool | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        memory_hit_ids = memory_hit_ids or []
        created_memory_ids = created_memory_ids or []
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO evaluation_events(
                    event_type, session_id, source, latency_ms, memory_hit_count,
                    memory_hit_ids, created_memory_ids, heartbeat_event_id, fired,
                    reason, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    session_id,
                    source,
                    latency_ms,
                    len(memory_hit_ids),
                    json.dumps(memory_hit_ids, ensure_ascii=False),
                    json.dumps(created_memory_ids, ensure_ascii=False),
                    heartbeat_event_id,
                    None if fired is None else 1 if fired else 0,
                    reason,
                    json.dumps(payload or {}, ensure_ascii=False),
                    utc_now(),
                ),
            )
            return int(cur.lastrowid)

    def record_activity_event(
        self,
        *,
        activity_type: str,
        source: str | None = None,
        intensity: float = 1.0,
        note: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO activity_events(activity_type, source, intensity, note, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (activity_type, source, intensity, note, utc_now()),
            )
            return int(cur.lastrowid)

    def recent_activity_events(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, activity_type, source, intensity, note, created_at
                FROM activity_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def last_activity_time(
        self,
        activity_types: tuple[str, ...] = (
            "active",
            "user_input",
            "app_visible",
            "screen_unlocked",
        ),
    ) -> str | None:
        placeholders = ", ".join("?" for _ in activity_types)
        with self.connect() as conn:
            row = conn.execute(
                f"""
                SELECT created_at
                FROM activity_events
                WHERE activity_type IN ({placeholders})
                ORDER BY id DESC
                LIMIT 1
                """,
                activity_types,
            ).fetchone()
        return str(row["created_at"]) if row else None

    def recent_evaluation_events(
        self, limit: int = 50, event_type: str | None = None
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        params: tuple[Any, ...]
        where_clause = ""
        if event_type:
            where_clause = "WHERE event_type = ?"
            params = (event_type, limit)
        else:
            params = (limit,)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, event_type, session_id, source, latency_ms, memory_hit_count,
                       memory_hit_ids, created_memory_ids, heartbeat_event_id, fired,
                       reason, payload_json, created_at
                FROM evaluation_events
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._evaluation_event_from_row(row) for row in rows]

    def evaluation_events_for_export(self, event_type: str | None = None) -> list[dict[str, Any]]:
        params: tuple[Any, ...]
        where_clause = ""
        if event_type:
            where_clause = "WHERE event_type = ?"
            params = (event_type,)
        else:
            params = ()
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, event_type, session_id, source, latency_ms, memory_hit_count,
                       memory_hit_ids, created_memory_ids, heartbeat_event_id, fired,
                       reason, payload_json, created_at
                FROM evaluation_events
                {where_clause}
                ORDER BY id ASC
                """,
                params,
            ).fetchall()
        return [self._evaluation_event_from_row(row) for row in rows]

    def evaluation_summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            chat_rows = conn.execute(
                """
                SELECT latency_ms, memory_hit_count
                FROM evaluation_events
                WHERE event_type = 'chat'
                ORDER BY id ASC
                """
            ).fetchall()
            heartbeat_rows = conn.execute(
                """
                SELECT fired, reason
                FROM evaluation_events
                WHERE event_type = 'heartbeat'
                ORDER BY id ASC
                """
            ).fetchall()
            avatar_rows = conn.execute(
                """
                SELECT event_type, latency_ms, payload_json
                FROM evaluation_events
                WHERE event_type LIKE 'avatar_%'
                ORDER BY id ASC
                """
            ).fetchall()

        latencies = [
            int(row["latency_ms"]) for row in chat_rows if row["latency_ms"] is not None
        ]
        memory_hit_counts = [int(row["memory_hit_count"]) for row in chat_rows]
        chat_count = len(chat_rows)
        heartbeat_count = len(heartbeat_rows)
        heartbeat_fired_count = sum(1 for row in heartbeat_rows if row["fired"] == 1)
        avatar_payloads = [json.loads(row["payload_json"]) for row in avatar_rows]
        avatar_first_play_latencies = [
            int(row["latency_ms"])
            for row in avatar_rows
            if row["event_type"] == "avatar_voice_start" and row["latency_ms"] is not None
        ]
        avatar_interrupt_latencies = [
            int(row["latency_ms"])
            for row in avatar_rows
            if row["event_type"] == "avatar_interrupt" and row["latency_ms"] is not None
        ]
        avatar_active_ms = [
            round(float(payload["active_ms"]))
            for row, payload in zip(avatar_rows, avatar_payloads, strict=False)
            if row["event_type"] == "avatar_lip_sync" and is_number(payload.get("active_ms"))
        ]
        avatar_active_ratios = [
            float(payload["active_ratio"])
            for row, payload in zip(avatar_rows, avatar_payloads, strict=False)
            if row["event_type"] == "avatar_lip_sync" and is_number(payload.get("active_ratio"))
        ]
        avatar_voice_start_count = sum(
            1 for row in avatar_rows if row["event_type"] == "avatar_voice_start"
        )
        avatar_lip_sync_count = sum(
            1 for row in avatar_rows if row["event_type"] == "avatar_lip_sync"
        )
        avatar_interrupt_count = sum(
            1 for row in avatar_rows if row["event_type"] == "avatar_interrupt"
        )

        return {
            "chat": {
                "count": chat_count,
                "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
                "p95_latency_ms": percentile_nearest_rank(latencies, 0.95),
                "memory_hit_rate": ratio(
                    sum(1 for count in memory_hit_counts if count > 0), chat_count
                ),
                "avg_memory_hits": round(sum(memory_hit_counts) / chat_count, 2)
                if chat_count
                else None,
            },
            "heartbeat": {
                "count": heartbeat_count,
                "fired_count": heartbeat_fired_count,
                "blocked_count": heartbeat_count - heartbeat_fired_count,
                "fired_rate": ratio(heartbeat_fired_count, heartbeat_count),
                "latest_reason": heartbeat_rows[-1]["reason"] if heartbeat_rows else None,
            },
            "avatar": {
                "count": len(avatar_rows),
                "voice_start_count": avatar_voice_start_count,
                "avg_first_play_ms": average_int(avatar_first_play_latencies),
                "lip_sync_count": avatar_lip_sync_count,
                "avg_mouth_active_ms": average_int(avatar_active_ms),
                "avg_mouth_active_ratio": average_float(avatar_active_ratios),
                "interrupt_count": avatar_interrupt_count,
                "avg_interrupt_to_silent_ms": average_int(avatar_interrupt_latencies),
            },
            "recent_events": self.recent_evaluation_events(limit=10),
        }

    def _evaluation_event_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["memory_hit_ids"] = json.loads(item["memory_hit_ids"])
        item["created_memory_ids"] = json.loads(item["created_memory_ids"])
        item["payload"] = json.loads(item["payload_json"])
        item["fired"] = None if item["fired"] is None else bool(item["fired"])
        del item["payload_json"]
        return item

    def last_message_time(self, role: str | None = None) -> str | None:
        query = "SELECT created_at FROM messages"
        params: tuple[Any, ...] = ()
        if role:
            query += " WHERE role = ?"
            params = (role,)
        query += " ORDER BY id DESC LIMIT 1"
        with self.connect() as conn:
            row = conn.execute(query, params).fetchone()
        return str(row["created_at"]) if row else None


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 3)


def average_int(values: list[int]) -> int | None:
    if not values:
        return None
    return round(sum(values) / len(values))


def average_float(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def memory_card_item(memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(memory["id"]),
        "kind": str(memory["kind"]),
        "content": str(memory["content"]),
        "importance": float(memory["importance"]),
        "confidence": float(memory["confidence"]),
        "source_message_id": memory["source_message_id"],
        "created_at": memory["created_at"],
        "updated_at": memory["updated_at"],
    }


def memory_card_snapshot_summary(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    return {
        "id": int(item["id"]),
        "session_id": str(item["session_id"]),
        "label": item["label"],
        "memory_count": int(item["memory_count"]),
        "conversation_count": int(item["conversation_count"]),
        "summary": str(item["summary"]),
        "generated_at": str(item["generated_at"]),
        "created_at": str(item["created_at"]),
    }


def memory_card_snapshot_from_row(row: sqlite3.Row) -> dict[str, Any]:
    summary = memory_card_snapshot_summary(row)
    card = json.loads(row["card_json"])
    return {
        **summary,
        "card": card,
        "markdown": str(row["markdown"]),
    }


def memory_card_diff(base: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    base_items = memory_card_items_by_key(base)
    target_items = memory_card_items_by_key(target)
    added_keys = sorted(set(target_items) - set(base_items))
    removed_keys = sorted(set(base_items) - set(target_items))
    section_diffs = []
    for kind in MEMORY_CARD_KIND_ORDER:
        added = [target_items[key] for key in added_keys if target_items[key]["kind"] == kind]
        removed = [base_items[key] for key in removed_keys if base_items[key]["kind"] == kind]
        section_diffs.append(
            {
                "kind": kind,
                "title": MEMORY_CARD_KIND_LABELS[kind],
                "added": added,
                "removed": removed,
            }
        )
    return {
        "added_count": len(added_keys),
        "removed_count": len(removed_keys),
        "unchanged_count": len(set(base_items) & set(target_items)),
        "sections": section_diffs,
    }


def memory_card_items_by_key(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for section in card.get("sections", []):
        kind = str(section.get("kind", ""))
        for item in section.get("items", []):
            content = str(item.get("content", ""))
            key = f"{kind}\0{content}"
            items[key] = {
                "kind": kind,
                "content": content,
                "id": item.get("id"),
            }
    return items


def memory_reflection_themes(card: dict[str, Any]) -> list[dict[str, Any]]:
    themes = []
    for section in card["sections"]:
        kind = str(section["kind"])
        items = section["items"]
        count = len(items)
        evidence = [str(item["content"]) for item in items[:3]]
        themes.append(
            {
                "kind": kind,
                "title": str(section["title"]),
                "count": count,
                "headline": memory_reflection_headline(kind, evidence),
                "evidence": evidence,
                "next_focus": memory_reflection_next_focus(kind, count),
            }
        )
    return themes


def memory_reflection_headline(kind: str, evidence: list[str]) -> str:
    if not evidence:
        return "暂无稳定线索"
    first = evidence[0]
    prefixes = {
        "relationship": "关系线索",
        "preference": "偏好线索",
        "event": "事件线索",
        "reflection": "自我反思线索",
    }
    return f"{prefixes.get(kind, '记忆线索')}: {first}"


def memory_reflection_next_focus(kind: str, count: int) -> str:
    if count == 0:
        missing = {
            "relationship": "继续观察用户希望怎样被称呼、回应和陪伴。",
            "preference": "继续沉淀语音、表达风格、学习和生活偏好。",
            "event": "继续记录有明确时间或任务属性的事件。",
            "reflection": "继续收集能体现情绪、压力和自我评价的表达。",
        }
        return missing.get(kind, "继续补充该类长期记忆。")
    followups = {
        "relationship": "确认这些关系线索是否仍然适合当前互动边界。",
        "preference": "用后续反馈校验偏好是否稳定,避免把一次性选择当成长期偏好。",
        "event": "关注事件是否已过期、完成或需要主动提醒。",
        "reflection": "结合更多样本判断反思是否可沉淀为更高层主题。",
    }
    return followups.get(kind, "结合后续对话继续校准。")


def memory_reflection_next_questions(themes: list[dict[str, Any]]) -> list[str]:
    questions = []
    for theme in themes:
        if theme["count"] == 0:
            questions.append(f"{theme['title']}还缺少样本。")
        elif theme["count"] < 2:
            questions.append(f"{theme['title']}只有 {theme['count']} 条线索,需要继续验证。")
    if not questions:
        questions.append("下一步可以对比新旧快照,确认关系、偏好和事件是否发生变化。")
    return questions[:4]


def memory_reflection_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# {summary['title']}",
        "",
        f"- 会话: {summary['session_id']}",
        f"- 生成时间: {summary['generated_at']}",
        f"- 样本状态: {summary['readiness']}",
        f"- 长期记忆: {summary['memory_count']} 条",
        f"- 对话消息: {summary['conversation_count']} 条",
        "",
        summary["summary"],
        "",
    ]
    for theme in summary["themes"]:
        lines.append(f"## {theme['title']}")
        lines.append(f"- 线索数: {theme['count']}")
        lines.append(f"- 摘要: {theme['headline']}")
        lines.append(f"- 后续关注: {theme['next_focus']}")
        if theme["evidence"]:
            lines.append("- 证据:")
            for item in theme["evidence"]:
                lines.append(f"  - {item}")
        lines.append("")
    lines.append("## 待验证问题")
    for question in summary["next_questions"]:
        lines.append(f"- {question}")
    return "\n".join(lines).strip() + "\n"


def memory_card_markdown(card: dict[str, Any]) -> str:
    lines = [
        f"# {card['title']}",
        "",
        f"- 会话: {card['session_id']}",
        f"- 生成时间: {card['generated_at']}",
        f"- 长期记忆: {card['memory_count']} 条",
        f"- 对话消息: {card['conversation_count']} 条",
        "",
        card["summary"],
        "",
    ]
    for section in card["sections"]:
        lines.append(f"## {section['title']}")
        if not section["items"]:
            lines.append("- 暂无")
        else:
            for item in section["items"]:
                lines.append(f"- {item['content']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def percentile_nearest_rank(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, round(percentile * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]
