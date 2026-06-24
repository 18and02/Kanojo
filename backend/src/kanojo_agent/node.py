from __future__ import annotations

from typing import Any

import httpx

from kanojo_agent.settings import Settings


VALID_NODE_ROLES = {"standalone", "mac_home", "pc_inference"}
VALID_MEMORY_PRIMARY = {"local", "peer"}
VALID_OFFLINE_WRITE_BEHAVIOR = {"local_only", "reject", "queue"}
VALID_INFERENCE_PRIMARY = {"local", "peer", "auto"}


def normalized_node_role(role: str) -> str:
    value = role.strip().lower()
    return value if value in VALID_NODE_ROLES else "standalone"


def normalized_memory_primary(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in VALID_MEMORY_PRIMARY else "local"


def normalized_offline_write_behavior(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in VALID_OFFLINE_WRITE_BEHAVIOR else "local_only"


def normalized_inference_primary(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in VALID_INFERENCE_PRIMARY else "auto"


def node_config_summary(settings: Settings) -> dict[str, Any]:
    return {
        "name": settings.node_name.strip() or "local",
        "role": normalized_node_role(settings.node_role),
        "db_path": str(settings.db_path),
        "peer_base_url": normalize_base_url(settings.peer_base_url),
        "peer_timeout_seconds": settings.peer_timeout_seconds,
        "llm_configured": bool(settings.llm_base_url),
        "tts_configured": bool(settings.tts_base_url),
        "stt_configured": bool(settings.stt_base_url),
    }


def memory_write_policy(settings: Settings) -> dict[str, Any]:
    primary = normalized_memory_primary(settings.memory_primary)
    offline_behavior = normalized_offline_write_behavior(settings.offline_write_behavior)
    peer_base_url = normalize_base_url(settings.peer_base_url)
    local_writes_enabled = primary == "local"
    peer_writes_configured = primary == "peer" and bool(peer_base_url)
    return {
        "primary": primary,
        "offline_behavior": offline_behavior,
        "local_writes_enabled": local_writes_enabled,
        "peer_writes_configured": peer_writes_configured,
        "peer_base_url": peer_base_url,
        "migration_ready": primary == "peer" and bool(peer_base_url) and offline_behavior == "reject",
        "note": memory_write_policy_note(primary, offline_behavior, peer_base_url),
    }


def inference_route_policy(settings: Settings) -> dict[str, Any]:
    primary = normalized_inference_primary(settings.inference_primary)
    role = normalized_node_role(settings.node_role)
    peer_base_url = normalize_base_url(settings.peer_base_url)
    return {
        "primary": primary,
        "node_role": role,
        "local_llm_configured": bool(settings.llm_base_url),
        "peer_base_url": peer_base_url,
        "peer_inference_configured": bool(peer_base_url),
        "auto_delegates_chat": primary == "auto" and role == "mac_home" and bool(peer_base_url),
        "note": inference_route_policy_note(primary, role, peer_base_url),
    }


def select_inference_route(settings: Settings, task_type: str) -> dict[str, Any]:
    policy = inference_route_policy(settings)
    primary = str(policy["primary"])
    if primary == "peer":
        if policy["peer_inference_configured"]:
            return {
                **policy,
                "task_type": task_type,
                "selected": "peer",
                "reason": "peer inference primary is configured",
            }
        return {
            **policy,
            "task_type": task_type,
            "selected": "local",
            "fallback": True,
            "reason": "peer inference primary requested but peer is not configured",
        }
    if primary == "auto" and policy["auto_delegates_chat"] and task_type == "chat_reply":
        return {
            **policy,
            "task_type": task_type,
            "selected": "peer",
            "reason": "mac_home auto route delegates chat replies to peer inference",
        }
    return {
        **policy,
        "task_type": task_type,
        "selected": "local",
        "reason": "local inference route selected",
    }


def inference_route_policy_note(primary: str, role: str, peer_base_url: str | None) -> str:
    if primary == "local":
        return "local LLM/mock handles inference"
    if primary == "peer":
        return (
            "peer inference handles chat replies"
            if peer_base_url
            else "peer inference requested but KANOJO_PEER_BASE_URL is not configured"
        )
    if role == "mac_home" and peer_base_url:
        return "auto mode delegates chat replies from mac_home to peer inference"
    return "auto mode keeps inference local for standalone and pc_inference nodes"


def memory_write_policy_note(
    primary: str, offline_behavior: str, peer_base_url: str | None
) -> str:
    if primary == "local":
        return "local SQLite remains the memory write target"
    if not peer_base_url:
        return "peer primary requested but KANOJO_PEER_BASE_URL is not configured"
    if offline_behavior == "queue":
        return "queued writes are not implemented yet; use reject before enabling peer primary"
    if offline_behavior == "reject":
        return "peer primary can reject writes while peer is offline"
    return "peer primary configured; local fallback would break single-writer semantics"


async def peer_health(settings: Settings) -> dict[str, Any]:
    peer_base_url = normalize_base_url(settings.peer_base_url)
    if not peer_base_url:
        return {
            "configured": False,
            "available": False,
            "base_url": None,
            "error": "peer is not configured",
        }
    health_url = f"{peer_base_url}/health"
    try:
        async with httpx.AsyncClient(timeout=settings.peer_timeout_seconds) as client:
            response = await client.get(health_url)
            response.raise_for_status()
            payload = response.json()
    except Exception as error:
        return {
            "configured": True,
            "available": False,
            "base_url": peer_base_url,
            "health_url": health_url,
            "error": str(error),
        }
    return {
        "configured": True,
        "available": True,
        "base_url": peer_base_url,
        "health_url": health_url,
        "status": payload.get("status"),
        "version": payload.get("version"),
    }


async def peer_json(settings: Settings, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    peer_base_url = normalize_base_url(settings.peer_base_url)
    if not peer_base_url:
        return {
            "configured": False,
            "available": False,
            "base_url": None,
            "error": "peer is not configured",
        }
    target_path = path if path.startswith("/") else f"/{path}"
    url = f"{peer_base_url}{target_path}"
    try:
        async with httpx.AsyncClient(timeout=settings.peer_timeout_seconds) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as error:
        return {
            "configured": True,
            "available": False,
            "base_url": peer_base_url,
            "url": url,
            "error": str(error),
        }
    return {
        "configured": True,
        "available": True,
        "base_url": peer_base_url,
        "url": str(response.url),
        "payload": payload,
    }


async def peer_post_json(settings: Settings, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    peer_base_url = normalize_base_url(settings.peer_base_url)
    if not peer_base_url:
        return {
            "configured": False,
            "available": False,
            "base_url": None,
            "error": "peer is not configured",
        }
    target_path = path if path.startswith("/") else f"/{path}"
    url = f"{peer_base_url}{target_path}"
    try:
        async with httpx.AsyncClient(timeout=settings.peer_timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            response_payload = response.json()
    except Exception as error:
        return {
            "configured": True,
            "available": False,
            "base_url": peer_base_url,
            "url": url,
            "error": str(error),
        }
    return {
        "configured": True,
        "available": True,
        "base_url": peer_base_url,
        "url": str(response.url),
        "payload": response_payload,
    }


def normalize_base_url(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().rstrip("/") or None
