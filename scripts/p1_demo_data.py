from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from kanojo_agent.storage import MemoryStore  # noqa: E402


TABLES = ["evaluation_events", "memory_audits", "heartbeat_events", "memories", "messages"]


def main() -> None:
    parser = argparse.ArgumentParser(description="P1 demo data utility.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("reset-seed", help="Reset local demo tables and seed reproducible data.")
    subparsers.add_parser("status", help="Print current P1 demo data counts and summary.")

    export_parser = subparsers.add_parser("export", help="Export evaluation events.")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json")
    export_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    store = MemoryStore(resolve_db_path())

    if args.command == "reset-seed":
        reset_demo_data(store)
        seed_demo_data(store)
        print(f"Seeded P1 demo data into {store.db_path}")
        print_status(store)
        return

    if args.command == "status":
        print_status(store)
        return

    if args.command == "export":
        output = export_events(store, args.format, args.output)
        print(f"Exported evaluation events to {output}")
        return


def resolve_db_path() -> Path:
    env_path = os.getenv("KANOJO_DB_PATH")
    if env_path:
        return normalize_db_path(env_path)

    env_file = ROOT / "backend" / ".env"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("KANOJO_DB_PATH="):
                return normalize_db_path(line.split("=", 1)[1].strip())

    return ROOT / "backend" / "data" / "kanojo.db"


def normalize_db_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT / "backend" / path


def reset_demo_data(store: MemoryStore) -> None:
    with store.connect() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
        placeholders = ",".join("?" for _ in TABLES)
        conn.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})", TABLES)
        conn.execute("PRAGMA foreign_keys = ON")


def seed_demo_data(store: MemoryStore) -> None:
    user_message_id = store.add_message(
        "default", "user", "我明天上午有数据库系统考试，今晚想早点睡。"
    )
    assistant_message_id = store.add_message(
        "default",
        "assistant",
        "我记下来了。今晚我会尽量少打扰你，明天可以提醒你复盘考试状态。",
    )

    memories = [
        {
            "kind": "event",
            "content": "用户明天上午有数据库系统考试，需要今晚早点休息",
            "importance": 0.86,
            "confidence": 0.9,
        },
        {
            "kind": "preference",
            "content": "用户喜欢普通话偏温柔、语速稍慢的系统语音",
            "importance": 0.72,
            "confidence": 0.82,
        },
        {
            "kind": "relationship",
            "content": "用户希望被称呼为吉川君",
            "importance": 0.68,
            "confidence": 0.8,
        },
    ]

    memory_ids: list[int] = []
    for memory in memories:
        memory_id = store.add_memory(
            kind=memory["kind"],
            content=memory["content"],
            source_message_id=user_message_id,
            importance=memory["importance"],
            confidence=memory["confidence"],
        )
        memory_ids.append(memory_id)
        store.add_memory_audit(
            source_message_id=user_message_id,
            method="demo_seed",
            raw_text="P1 demo seed data",
            candidate={
                **memory,
                "method": "demo_seed",
                "reason": "seeded for reproducible P1 demo",
            },
            accepted=True,
            reason="accepted by demo seed",
            memory_id=memory_id,
        )

    store.record_evaluation_event(
        event_type="chat",
        session_id="default",
        source="demo_seed",
        latency_ms=1180,
        memory_hit_ids=[memory_ids[0]],
        created_memory_ids=memory_ids,
        payload={
            "message_ids": {"user": user_message_id, "assistant": assistant_message_id},
            "memory_extraction_method": "demo_seed",
            "accepted_memory_count": len(memory_ids),
            "llm_model": "demo",
        },
    )
    heartbeat_id = store.record_heartbeat(
        True,
        "demo_seed: forced heartbeat",
        "吉川君，明天考试前记得早点休息。我会安静一点。",
    )
    store.record_evaluation_event(
        event_type="heartbeat",
        source="demo_seed",
        heartbeat_event_id=heartbeat_id,
        fired=True,
        reason="demo_seed: forced heartbeat",
        payload={
            "message": "吉川君，明天考试前记得早点休息。我会安静一点。",
            "force": True,
            "purpose": "P1 reproducible demo",
        },
    )


def print_status(store: MemoryStore) -> None:
    with store.connect() as conn:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in TABLES
        }
    print(json.dumps({"db_path": str(store.db_path), "counts": counts}, ensure_ascii=False, indent=2))
    print(json.dumps(store.evaluation_summary(), ensure_ascii=False, indent=2))


def export_events(store: MemoryStore, export_format: str, output: Path | None) -> Path:
    events = store.evaluation_events_for_export()
    output = output or default_export_path(export_format)
    output.parent.mkdir(parents=True, exist_ok=True)

    if export_format == "json":
        payload = {"summary": store.evaluation_summary(), "items": events}
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    import csv

    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "id",
                "event_type",
                "session_id",
                "source",
                "latency_ms",
                "memory_hit_count",
                "memory_hit_ids",
                "created_memory_ids",
                "heartbeat_event_id",
                "fired",
                "reason",
                "created_at",
                "payload",
            ],
        )
        writer.writeheader()
        for event in events:
            writer.writerow(flatten_event(event))
    return output


def default_export_path(export_format: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return ROOT / "exports" / f"p1_evaluation_events_{stamp}.{export_format}"


def flatten_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event["id"],
        "event_type": event["event_type"],
        "session_id": event.get("session_id"),
        "source": event.get("source"),
        "latency_ms": event.get("latency_ms"),
        "memory_hit_count": event.get("memory_hit_count"),
        "memory_hit_ids": ",".join(str(item) for item in event.get("memory_hit_ids", [])),
        "created_memory_ids": ",".join(str(item) for item in event.get("created_memory_ids", [])),
        "heartbeat_event_id": event.get("heartbeat_event_id"),
        "fired": event.get("fired"),
        "reason": event.get("reason"),
        "created_at": event["created_at"],
        "payload": json.dumps(event.get("payload", {}), ensure_ascii=False),
    }


if __name__ == "__main__":
    main()
