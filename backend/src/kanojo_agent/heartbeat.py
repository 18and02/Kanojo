from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from kanojo_agent.memory import parse_time


@dataclass(frozen=True)
class HeartbeatDecision:
    fired: bool
    reason: str
    message: str | None = None


def in_quiet_hours(now: datetime, start_hour: int, end_hour: int) -> bool:
    hour = now.hour
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def evaluate_heartbeat(
    *,
    last_user_at: str | None,
    last_agent_at: str | None,
    last_activity_at: str | None = None,
    now: datetime | None = None,
    enabled: bool = True,
    force: bool = False,
    quiet_start: int = 23,
    quiet_end: int = 8,
    cooldown_minutes: int = 120,
    activity_grace_minutes: int = 10,
) -> HeartbeatDecision:
    current = now or datetime.now(UTC)
    if not enabled:
        return HeartbeatDecision(False, "proactive interaction disabled")
    if force:
        return HeartbeatDecision(
            True,
            "forced heartbeat",
            "这是一条主动心跳测试通知。后台调度链路已经接通。",
        )
    if in_quiet_hours(current, quiet_start, quiet_end):
        return HeartbeatDecision(False, "quiet hours")
    if last_activity_at:
        activity_time = parse_time(last_activity_at)
        minutes_since_activity = (current - activity_time).total_seconds() / 60
        if minutes_since_activity < activity_grace_minutes:
            return HeartbeatDecision(False, "recent desktop activity")
    if not last_user_at:
        return HeartbeatDecision(False, "no user history")

    user_time = parse_time(last_user_at)
    minutes_since_user = (current - user_time).total_seconds() / 60
    if minutes_since_user < cooldown_minutes:
        return HeartbeatDecision(False, "cooldown after user message")

    if last_agent_at:
        agent_time = parse_time(last_agent_at)
        minutes_since_agent = (current - agent_time).total_seconds() / 60
        if minutes_since_agent < cooldown_minutes:
            return HeartbeatDecision(False, "cooldown after agent message")

    return HeartbeatDecision(
        True,
        "idle interval exceeded cooldown",
        "你刚才离开了一阵子。要不要简单告诉我现在进展到哪一步了?",
    )
