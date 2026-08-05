from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib import error, request


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Kanojo dual-node demo checks.")
    parser.add_argument(
        "--pc-base",
        default=os.environ.get("KANOJO_PC_BASE_URL", "http://kanojo-pc.local:8787"),
    )
    parser.add_argument(
        "--mac-base",
        default=os.environ.get("KANOJO_MAC_BASE_URL", "http://kanojo-mac.local:8787"),
    )
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--writeback-test", action="store_true")
    parser.add_argument("--cleanup-after-write", action="store_true")
    args = parser.parse_args()

    pc_base = args.pc_base.rstrip("/")
    mac_base = args.mac_base.rstrip("/")
    summary: dict[str, Any] = {
        "pc_base": pc_base,
        "mac_base": mac_base,
        "checks": {},
    }

    summary["checks"]["pc_health"] = get_json(f"{pc_base}/health", timeout=args.timeout)
    summary["checks"]["mac_health"] = get_json(f"{mac_base}/health", timeout=args.timeout)
    pc_status = get_json(f"{pc_base}/node/status", timeout=args.timeout)
    mac_status = get_json(f"{mac_base}/node/status", timeout=args.timeout)
    summary["checks"]["pc_status"] = compact_node_status(pc_status)
    summary["checks"]["mac_status"] = compact_node_status(mac_status)

    summary["checks"]["pc_prewarm"] = post_json(
        f"{pc_base}/node/inference/prewarm",
        {"text": "prewarm pc inference node"},
        timeout=args.timeout,
    )
    summary["checks"]["pc_peer_memory_card"] = compact_peer_card(
        get_json(f"{pc_base}/node/peer/memory-card", timeout=args.timeout)
    )

    if not args.skip_chat:
        started = time.perf_counter()
        mac_chat = post_json(
            f"{mac_base}/chat",
            {
                "text": "Please answer in one short Chinese sentence: dual node route check.",
                "session_id": "dual_node_demo",
                "speak": False,
            },
            timeout=args.timeout,
        )
        mac_chat["client_elapsed_ms"] = int((time.perf_counter() - started) * 1000)
        summary["checks"]["mac_chat_delegates_to_pc"] = compact_chat(mac_chat)

    if args.writeback_test:
        write = post_json(
            f"{pc_base}/memories",
            {
                "kind": "event",
                "content": "联调测试：演示脚本验证 PC 写回 Mac，可清理",
                "importance": 0.2,
                "confidence": 0.9,
            },
            timeout=args.timeout,
        )
        summary["checks"]["pc_writeback_to_mac"] = write
        if args.cleanup_after_write:
            cleanup = post_json(
                f"{mac_base}/maintenance/cleanup-test-memories",
                {"dry_run": False},
                timeout=args.timeout,
            )
            summary["checks"]["mac_cleanup_after_write"] = cleanup

    summary["passed"] = evaluate_summary(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


def get_json(url: str, *, timeout: float) -> dict[str, Any]:
    return send_json("GET", url, None, timeout=timeout)


def post_json(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    return send_json("POST", url, payload, timeout=timeout)


def send_json(
    method: str, url: str, payload: dict[str, Any] | None, *, timeout: float
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {exc.code}", "body": raw, "url": url}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "url": url}


def compact_node_status(payload: dict[str, Any]) -> dict[str, Any]:
    node = payload.get("node") if isinstance(payload, dict) else {}
    peer = payload.get("peer") if isinstance(payload, dict) else {}
    memory_policy = payload.get("memory_write_policy") if isinstance(payload, dict) else {}
    route_policy = payload.get("inference_route_policy") if isinstance(payload, dict) else {}
    return {
        "error": payload.get("error"),
        "node_name": node.get("name") if isinstance(node, dict) else None,
        "role": node.get("role") if isinstance(node, dict) else None,
        "llm_configured": node.get("llm_configured") if isinstance(node, dict) else None,
        "peer_available": peer.get("available") if isinstance(peer, dict) else None,
        "peer_base_url": peer.get("base_url") if isinstance(peer, dict) else None,
        "memory_primary": memory_policy.get("primary") if isinstance(memory_policy, dict) else None,
        "inference_primary": route_policy.get("primary") if isinstance(route_policy, dict) else None,
    }


def compact_peer_card(payload: dict[str, Any]) -> dict[str, Any]:
    card = payload.get("payload") if isinstance(payload, dict) else {}
    return {
        "error": payload.get("error"),
        "configured": payload.get("configured"),
        "available": payload.get("available"),
        "base_url": payload.get("base_url"),
        "memory_count": card.get("memory_count") if isinstance(card, dict) else None,
        "summary": card.get("summary") if isinstance(card, dict) else None,
    }


def compact_chat(payload: dict[str, Any]) -> dict[str, Any]:
    route = payload.get("inference_route") if isinstance(payload, dict) else {}
    return {
        "error": payload.get("error"),
        "route_selected": route.get("selected") if isinstance(route, dict) else None,
        "llm_model": route.get("llm_model") if isinstance(route, dict) else None,
        "llm_configured": route.get("llm_configured") if isinstance(route, dict) else None,
        "latency_ms": payload.get("latency_ms"),
        "client_elapsed_ms": payload.get("client_elapsed_ms"),
        "reply_preview": str(payload.get("reply", ""))[:120],
    }


def evaluate_summary(summary: dict[str, Any]) -> bool:
    checks = summary["checks"]
    pc_status = checks.get("pc_status", {})
    mac_status = checks.get("mac_status", {})
    peer_card = checks.get("pc_peer_memory_card", {})
    chat = checks.get("mac_chat_delegates_to_pc", {})
    required = [
        checks.get("pc_health", {}).get("status") == "ok",
        checks.get("mac_health", {}).get("status") == "ok",
        pc_status.get("role") == "pc_inference",
        pc_status.get("llm_configured") is True,
        pc_status.get("memory_primary") == "peer",
        mac_status.get("role") == "mac_home",
        mac_status.get("peer_available") is True,
        peer_card.get("configured") is True,
        peer_card.get("available") is True,
    ]
    if chat:
        required.append(chat.get("route_selected") == "peer")
        required.append(chat.get("llm_configured") is True)
    return all(required)


if __name__ == "__main__":
    sys.exit(main())
