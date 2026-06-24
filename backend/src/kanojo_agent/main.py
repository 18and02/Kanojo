from __future__ import annotations

import csv
from datetime import UTC, datetime
import io
import json
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kanojo_agent import __version__
from kanojo_agent.extractor import MemoryCandidate, MemoryDecision, MemoryExtractor, validate_candidate
from kanojo_agent.heartbeat import evaluate_heartbeat
from kanojo_agent.llm import LLMClient, chunk_text
from kanojo_agent.node import (
    inference_route_policy,
    memory_write_policy,
    node_config_summary,
    peer_health,
    peer_json,
    peer_post_json,
    select_inference_route,
)
from kanojo_agent.settings import Settings
from kanojo_agent.stt import STTClient, STTNotConfiguredError, STTTranscriptionError
from kanojo_agent.storage import MemoryStore
from kanojo_agent.tts import TTSClient, TTSError


settings = Settings.from_env()
store = MemoryStore(settings.db_path)
llm = LLMClient(settings)
tts = TTSClient(settings)
stt = STTClient(settings)
extractor = MemoryExtractor(settings, llm)
DEFAULT_TEST_MEMORY_PATTERNS = (
    "联调测试",
    "真实双机联调",
    "双机联调",
    "链路验证",
    "PC 长期记忆写回 Mac mini",
    "PC 长期记忆写回 Mac",
    "计划在2026年6月24日购买Mac mini作为PC",
)

app = FastAPI(title="Kanojo Agent Backend", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    text: str = Field(min_length=1)
    session_id: str = "default"
    speak: bool = False


class MemoryCreateRequest(BaseModel):
    kind: str = Field(pattern="^(event|preference|relationship|reflection)$")
    content: str = Field(min_length=1)
    importance: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.7, ge=0, le=1)


class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    importance: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)


class RoutedMemoryWriteRequest(MemoryCreateRequest):
    source_message_id: int | None = Field(default=None, ge=1)
    deduplicate: bool = False
    source_node: str | None = Field(default=None, max_length=80)


class InferenceChatRequest(BaseModel):
    text: str = Field(min_length=1)
    memories: list[dict[str, Any]] = Field(default_factory=list)


class InferencePrewarmRequest(BaseModel):
    text: str = "预热 PC 推理节点"


class MemoryCleanupRequest(BaseModel):
    patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_TEST_MEMORY_PATTERNS))
    dry_run: bool = True
    limit: int = Field(default=100, ge=1, le=500)


class MemoryCardSnapshotRequest(BaseModel):
    session_id: str = Field(default="default", max_length=64)
    label: str | None = Field(default=None, max_length=80)


class MemoryAuditApproveRequest(BaseModel):
    candidate: MemoryCreateRequest | None = None


class MemoryAuditRejectRequest(BaseModel):
    reason: str = Field(default="rejected manually", min_length=1, max_length=200)


class MemoryAuditBatchRequest(BaseModel):
    audit_ids: list[int] = Field(min_length=1, max_length=50)
    action: str = Field(pattern="^(approve|reject)$")
    reason: str | None = Field(default=None, max_length=200)


class HeartbeatRequest(BaseModel):
    enabled: bool = True
    force: bool = False
    source: str = Field(default="manual", max_length=32)


class ActivityEventRequest(BaseModel):
    activity_type: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    source: str | None = Field(default=None, max_length=64)
    intensity: float = Field(default=1.0, ge=0, le=1)
    note: str | None = Field(default=None, max_length=256)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)


class EvaluationEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    session_id: str | None = Field(default=None, max_length=64)
    source: str | None = Field(default=None, max_length=64)
    latency_ms: int | None = Field(default=None, ge=0)
    memory_hit_ids: list[int] = Field(default_factory=list)
    created_memory_ids: list[int] = Field(default_factory=list)
    heartbeat_event_id: int | None = Field(default=None, ge=1)
    fired: bool | None = None
    reason: str | None = Field(default=None, max_length=256)
    payload: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/node/status")
async def node_status() -> dict[str, Any]:
    return {
        "node": node_config_summary(settings),
        "memory_write_policy": memory_write_policy(settings),
        "inference_route_policy": inference_route_policy(settings),
        "peer": await peer_health(settings),
    }


@app.get("/node/memory-write-policy")
def node_memory_write_policy() -> dict[str, Any]:
    return memory_write_policy(settings)


@app.get("/node/inference-route-policy")
def node_inference_route_policy() -> dict[str, Any]:
    return inference_route_policy(settings)


@app.get("/node/peer/memory-card")
async def peer_memory_card(session_id: str = "default") -> dict[str, Any]:
    return await peer_json(settings, "/memory-card", params={"session_id": session_id})


@app.get("/node/peer/memory-card/reflection")
async def peer_memory_card_reflection(session_id: str = "default") -> dict[str, Any]:
    return await peer_json(settings, "/memory-card/reflection", params={"session_id": session_id})


@app.post("/node/inference/chat")
async def local_inference_chat(request: InferenceChatRequest) -> dict[str, Any]:
    started = perf_counter()
    reply = await llm.generate_reply(request.text, request.memories)
    latency_ms = int((perf_counter() - started) * 1000)
    return {
        "reply": reply,
        "latency_ms": latency_ms,
        "route": {
            "selected": "local",
            "task_type": "chat_reply",
            "reason": "local node inference endpoint",
            "llm_model": settings.llm_model,
            "llm_configured": llm.configured,
        },
    }


@app.post("/node/inference/prewarm")
async def prewarm_local_inference(request: InferencePrewarmRequest) -> dict[str, Any]:
    started = perf_counter()
    if llm.configured:
        reply = await llm.chat_completion(
            [
                {
                    "role": "system",
                    "content": "你是 Kanojo 的 PC 推理节点。请用一句极短中文确认预热完成。",
                },
                {"role": "user", "content": request.text},
            ],
            temperature=0.0,
            max_tokens=32,
        )
    else:
        reply = await llm.generate_reply(request.text, [])
    return {
        "ok": True,
        "reply": reply,
        "latency_ms": int((perf_counter() - started) * 1000),
        "llm_model": settings.llm_model,
        "llm_configured": llm.configured,
    }


@app.post("/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    started = perf_counter()
    user_message_id = store.add_message(request.session_id, "user", request.text)

    extraction_method, candidates, extraction_error = await extractor.extract(request.text)
    memory_decisions = await apply_memory_candidates(
        user_message_id=user_message_id,
        raw_text=request.text,
        method=extraction_method,
        candidates=candidates,
        no_candidate_reason=extraction_error or "no durable memory candidate",
    )

    memories = store.search_memories(request.text)
    reply_result = await generate_reply_by_inference_route(request.text, memories)
    reply = str(reply_result["reply"])
    inference_route = reply_result["route"]
    assistant_message_id = store.add_message(request.session_id, "assistant", reply)

    audio = await tts.synthesize(reply) if request.speak else None
    latency_ms = int((perf_counter() - started) * 1000)
    created_memory_ids = [
        decision.memory_id for decision in memory_decisions if decision.accepted and decision.memory_id
    ]
    message_ids = {"user": user_message_id, "assistant": assistant_message_id}
    evaluation_event_id = store.record_evaluation_event(
        event_type="chat",
        session_id=request.session_id,
        source="desktop",
        latency_ms=latency_ms,
        memory_hit_ids=[int(memory["id"]) for memory in memories],
        created_memory_ids=created_memory_ids,
        payload={
            "message_ids": message_ids,
            "memory_extraction_method": extraction_method,
            "memory_extraction_error": extraction_error,
            "memory_decision_count": len(memory_decisions),
            "accepted_memory_count": len(created_memory_ids),
            "speak_requested": request.speak,
            "llm_model": inference_route.get("llm_model", settings.llm_model),
            "inference_route": inference_route,
        },
    )
    return {
        "reply": reply,
        "memories": memories,
        "memory_extraction": {
            "method": extraction_method,
            "error": extraction_error,
            "decisions": [decision.to_dict() for decision in memory_decisions],
        },
        "created_memory_ids": created_memory_ids,
        "message_ids": message_ids,
        "evaluation_event_id": evaluation_event_id,
        "inference_route": inference_route,
        "audio": audio,
        "latency_ms": latency_ms,
    }


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def event_stream() -> Any:
        started = perf_counter()
        first_delta_ms: int | None = None
        reply_parts: list[str] = []

        try:
            user_message_id = store.add_message(request.session_id, "user", request.text)
            memories = store.search_memories(request.text)
            yield sse_event(
                "meta",
                {
                    "message_ids": {"user": user_message_id},
                    "memories": memories,
                },
            )

            inference_route = select_inference_route(settings, "chat_reply")
            if inference_route["selected"] == "peer":
                reply_result = await generate_reply_by_inference_route(request.text, memories)
                inference_route = reply_result["route"]
                for chunk in chunk_text(str(reply_result["reply"])):
                    if first_delta_ms is None:
                        first_delta_ms = int((perf_counter() - started) * 1000)
                    reply_parts.append(chunk)
                    yield sse_event("delta", {"text": chunk})
            else:
                route_started = perf_counter()
                async for chunk in llm.generate_reply_stream(request.text, memories):
                    if not chunk:
                        continue
                    if first_delta_ms is None:
                        first_delta_ms = int((perf_counter() - started) * 1000)
                    reply_parts.append(chunk)
                    yield sse_event("delta", {"text": chunk})
                inference_route = {
                    **inference_route,
                    "latency_ms": int((perf_counter() - route_started) * 1000),
                    "llm_model": settings.llm_model,
                    "llm_configured": llm.configured,
                }

            reply = "".join(reply_parts)
            assistant_message_id = store.add_message(request.session_id, "assistant", reply)

            extraction_method, candidates, extraction_error = await extractor.extract(request.text)
            memory_decisions = await apply_memory_candidates(
                user_message_id=user_message_id,
                raw_text=request.text,
                method=extraction_method,
                candidates=candidates,
                no_candidate_reason=extraction_error or "no durable memory candidate",
            )

            latency_ms = int((perf_counter() - started) * 1000)
            created_memory_ids = [
                decision.memory_id
                for decision in memory_decisions
                if decision.accepted and decision.memory_id
            ]
            message_ids = {"user": user_message_id, "assistant": assistant_message_id}
            evaluation_event_id = store.record_evaluation_event(
                event_type="chat",
                session_id=request.session_id,
                source="desktop_stream",
                latency_ms=latency_ms,
                memory_hit_ids=[int(memory["id"]) for memory in memories],
                created_memory_ids=created_memory_ids,
                payload={
                    "message_ids": message_ids,
                    "memory_extraction_method": extraction_method,
                    "memory_extraction_error": extraction_error,
                    "memory_decision_count": len(memory_decisions),
                    "accepted_memory_count": len(created_memory_ids),
                    "first_delta_ms": first_delta_ms,
                    "streamed": True,
                    "speak_requested": request.speak,
                    "llm_model": inference_route.get("llm_model", settings.llm_model),
                    "inference_route": inference_route,
                },
            )
            yield sse_event(
                "done",
                {
                    "reply": reply,
                    "memories": memories,
                    "memory_extraction": {
                        "method": extraction_method,
                        "error": extraction_error,
                        "decisions": [decision.to_dict() for decision in memory_decisions],
                    },
                    "created_memory_ids": created_memory_ids,
                    "message_ids": message_ids,
                    "evaluation_event_id": evaluation_event_id,
                    "first_delta_ms": first_delta_ms,
                    "inference_route": inference_route,
                    "latency_ms": latency_ms,
                },
            )
        except Exception as error:  # pragma: no cover - exercised through manual streaming.
            yield sse_event("error", {"message": str(error)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/memories")
async def create_memory(request: MemoryCreateRequest) -> dict[str, Any]:
    result = await write_memory_by_policy(
        kind=request.kind,
        content=request.content,
        importance=request.importance,
        confidence=request.confidence,
        source_message_id=None,
        deduplicate=False,
    )
    if not result["accepted"]:
        raise HTTPException(status_code=503, detail=result)
    return result


@app.delete("/memories/{memory_id}")
def deactivate_memory(memory_id: int) -> dict[str, Any]:
    memory = store.memory_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    if memory["status"] != "active":
        return {
            "id": memory_id,
            "deactivated": False,
            "reason": f"memory is already {memory['status']}",
            "memory": memory,
        }
    deactivated = store.deactivate_memories([memory_id])
    updated = store.memory_by_id(memory_id)
    return {
        "id": memory_id,
        "deactivated": deactivated == 1,
        "reason": "memory soft-deactivated",
        "memory": updated,
    }


@app.patch("/memories/{memory_id}")
def update_memory(memory_id: int, request: MemoryUpdateRequest) -> dict[str, Any]:
    memory = store.memory_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        return {
            "id": memory_id,
            "updated": False,
            "reason": "no update fields provided",
            "memory": memory,
        }
    updated = store.update_memory(memory_id, **update_data)
    return {
        "id": memory_id,
        "updated": True,
        "reason": "memory updated",
        "memory": updated,
    }


@app.post("/node/memory-writes")
def create_local_memory_from_node(request: RoutedMemoryWriteRequest) -> dict[str, Any]:
    return write_memory_locally(
        kind=request.kind,
        content=request.content,
        source_message_id=request.source_message_id,
        importance=request.importance,
        confidence=request.confidence,
        deduplicate=request.deduplicate,
        source_node=request.source_node,
    )


@app.post("/stt/transcribe")
async def transcribe_audio(request: Request) -> dict[str, Any]:
    audio = await request.body()
    filename = request.headers.get("x-filename", "recording.webm")
    content_type = request.headers.get("content-type", "application/octet-stream")
    if not stt.configured:
        return {
            "configured": False,
            "text": "",
            "error": "STT service is not configured.",
        }
    try:
        result = await stt.transcribe_with_metadata(
            audio,
            filename=filename,
            content_type=content_type,
        )
    except STTNotConfiguredError as error:
        return {"configured": False, "text": "", "error": str(error)}
    except STTTranscriptionError as error:
        return {
            "configured": True,
            "text": "",
            "model": settings.stt_model,
            "error": str(error),
            "status_code": error.status_code,
        }
    return {
        "configured": True,
        "text": result.text,
        "model": result.model,
        "language": result.language,
        "duration": result.duration,
        "latency_ms": result.latency_ms,
    }


@app.get("/stt/status")
async def stt_status() -> dict[str, Any]:
    if not stt.configured:
        return {
            "configured": False,
            "available": False,
            "error": "STT service is not configured.",
        }
    health = await stt.health()
    return {
        "configured": True,
        "available": bool(health.get("available")),
        "base_url": settings.stt_base_url,
        "model": settings.stt_model,
        **health,
    }


@app.get("/tts/status")
async def tts_status() -> dict[str, Any]:
    health = await tts.health()
    return {
        "configured": tts.configured,
        "available": bool(health.get("available")),
        "base_url": settings.tts_base_url,
        "mode": "external" if tts.configured else "desktop_speech_fallback",
        "synthesize_url": tts.synthesize_url() if tts.configured else None,
        **health,
    }


@app.post("/tts/synthesize")
async def synthesize_tts(request: TTSRequest) -> dict[str, Any]:
    if not tts.configured:
        return {
            "configured": False,
            "status": "desktop_speech_fallback",
            "text": request.text,
            "audio_url": None,
        }
    try:
        return await tts.synthesize(request.text)
    except TTSError as error:
        return {
            "configured": True,
            "status": "error",
            "text": request.text,
            "error": str(error),
            "status_code": error.status_code,
        }


@app.get("/memories")
def search_memories(query: str = "", limit: int = 5) -> dict[str, Any]:
    return {"items": store.search_memories(query, limit=limit)}


@app.post("/maintenance/cleanup-test-memories")
def cleanup_test_memories(request: MemoryCleanupRequest) -> dict[str, Any]:
    patterns = [pattern.strip() for pattern in request.patterns if pattern.strip()]
    if not patterns:
        raise HTTPException(status_code=400, detail="patterns must not be empty")
    matches = store.active_memories_matching_content(patterns, limit=request.limit)
    deactivated_count = 0
    if not request.dry_run and matches:
        deactivated_count = store.deactivate_memories([int(item["id"]) for item in matches])
        matches = store.active_memories_matching_content(patterns, limit=request.limit)
    return {
        "dry_run": request.dry_run,
        "patterns": patterns,
        "matched_count": len(matches) if request.dry_run else deactivated_count,
        "deactivated_count": deactivated_count,
        "remaining_matches": len(matches),
        "items": matches,
    }


@app.get("/memory-card")
def memory_card(session_id: str = "default") -> dict[str, Any]:
    return store.memory_card(session_id=session_id)


@app.get("/memory-card/reflection")
def memory_card_reflection(session_id: str = "default") -> dict[str, Any]:
    return store.memory_reflection_summary(session_id=session_id)


@app.get("/memory-card/export", response_model=None)
def export_memory_card(session_id: str = "default", format: str = "markdown") -> Any:
    export_format = format.lower()
    card = store.memory_card(session_id=session_id)
    if export_format in ("markdown", "md"):
        filename = memory_card_export_filename(session_id, "md")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(
            card["markdown"],
            media_type="text/markdown; charset=utf-8",
            headers=headers,
        )
    if export_format == "json":
        filename = memory_card_export_filename(session_id, "json")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(
            json.dumps(card, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers=headers,
        )
    raise HTTPException(status_code=400, detail="format must be markdown or json")


@app.post("/memory-card/snapshots")
def create_memory_card_snapshot(request: MemoryCardSnapshotRequest) -> dict[str, Any]:
    return store.create_memory_card_snapshot(session_id=request.session_id, label=request.label)


@app.get("/memory-card/snapshots")
def memory_card_snapshots(session_id: str = "default", limit: int = 20) -> dict[str, Any]:
    return {"items": store.memory_card_snapshots(session_id=session_id, limit=limit)}


@app.get("/memory-card/snapshots/{snapshot_id}")
def memory_card_snapshot(snapshot_id: int) -> dict[str, Any]:
    snapshot = store.memory_card_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="memory card snapshot not found")
    return snapshot


@app.get("/memory-card/snapshots/{snapshot_id}/compare")
def compare_memory_card_snapshot(snapshot_id: int) -> dict[str, Any]:
    comparison = store.compare_memory_card_snapshot(snapshot_id)
    if comparison is None:
        raise HTTPException(status_code=404, detail="memory card snapshot not found")
    return comparison


@app.get("/memory-audits")
def recent_memory_audits(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    accepted: bool | None = None,
    decision: str | None = Query(default=None, pattern="^(accepted|pending|rejected)$"),
    q: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    return {
        "items": store.recent_memory_audits(
            limit=limit,
            offset=offset,
            accepted=accepted,
            decision=decision,
            query=q,
        ),
        "limit": limit,
        "offset": offset,
        "accepted": accepted,
        "decision": decision,
        "q": q,
    }


def memory_audit_candidate_payload(
    audit: dict[str, Any],
    override: MemoryCreateRequest | None = None,
) -> dict[str, Any]:
    if override is None:
        candidate = audit.get("candidate")
        if not isinstance(candidate, dict):
            raise HTTPException(status_code=400, detail="audit has no memory candidate")
        try:
            normalized = MemoryCreateRequest(
                kind=str(candidate["kind"]),
                content=str(candidate["content"]),
                importance=float(candidate.get("importance", 0.5)),
                confidence=float(candidate.get("confidence", 0.7)),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid memory candidate: {exc}") from exc
        payload = normalized.model_dump()
        payload["method"] = str(candidate.get("method") or audit.get("method") or "manual_review")
        payload["reason"] = str(candidate.get("reason") or "approved manually")
        return payload

    payload = override.model_dump()
    payload["method"] = str(audit.get("method") or "manual_review")
    payload["reason"] = "edited manually before approval"
    return payload


async def approve_memory_audit_candidate(
    audit_id: int,
    override: MemoryCreateRequest | None = None,
) -> dict[str, Any]:
    audit = store.memory_audit_by_id(audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="memory audit not found")
    if audit.get("memory_id"):
        return {
            "approved": False,
            "reason": "audit already has memory_id",
            "audit": audit,
        }
    candidate = memory_audit_candidate_payload(audit, override)
    write_result = await write_memory_by_policy(
        kind=str(candidate["kind"]),
        content=str(candidate["content"]),
        source_message_id=int(audit["source_message_id"]),
        importance=float(candidate.get("importance", 0.5)),
        confidence=float(candidate.get("confidence", 0.7)),
        deduplicate=True,
    )
    if not write_result.get("accepted"):
        updated = store.update_memory_audit_decision(
            audit_id,
            accepted=False,
            reason=str(write_result.get("reason") or "manual approval write failed"),
            memory_id=None,
            candidate=candidate,
        )
        raise HTTPException(status_code=503, detail={"write": write_result, "audit": updated})
    memory_id = int(write_result["id"]) if write_result.get("id") is not None else None
    updated = store.update_memory_audit_decision(
        audit_id,
        accepted=True,
        reason="approved manually",
        memory_id=memory_id,
        candidate=candidate,
    )
    return {
        "approved": True,
        "memory_id": memory_id,
        "write": write_result,
        "audit": updated,
    }


def reject_memory_audit_candidate(audit_id: int, reason: str) -> dict[str, Any]:
    audit = store.memory_audit_by_id(audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="memory audit not found")
    if audit.get("memory_id"):
        return {
            "rejected": False,
            "reason": "audit already has memory_id",
            "audit": audit,
        }
    updated = store.update_memory_audit_decision(
        audit_id,
        accepted=False,
        reason=reason,
        memory_id=None,
    )
    return {
        "rejected": True,
        "audit": updated,
    }


@app.post("/memory-audits/batch")
async def batch_memory_audits(request: MemoryAuditBatchRequest) -> dict[str, Any]:
    items = []
    for audit_id in request.audit_ids:
        try:
            if request.action == "approve":
                result = await approve_memory_audit_candidate(audit_id)
                ok = bool(result.get("approved"))
            else:
                result = reject_memory_audit_candidate(
                    audit_id,
                    request.reason or "rejected manually",
                )
                ok = bool(result.get("rejected"))
            items.append({"audit_id": audit_id, "ok": ok, "result": result})
        except HTTPException as exc:
            items.append(
                {
                    "audit_id": audit_id,
                    "ok": False,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                }
            )
    return {
        "action": request.action,
        "requested_count": len(request.audit_ids),
        "ok_count": sum(1 for item in items if item["ok"]),
        "items": items,
    }


@app.post("/memory-audits/{audit_id}/approve")
async def approve_memory_audit(
    audit_id: int,
    request: MemoryAuditApproveRequest | None = None,
) -> dict[str, Any]:
    return await approve_memory_audit_candidate(audit_id, request.candidate if request else None)


@app.post("/memory-audits/{audit_id}/reject")
def reject_memory_audit(
    audit_id: int,
    request: MemoryAuditRejectRequest | None = None,
) -> dict[str, Any]:
    return reject_memory_audit_candidate(audit_id, request.reason if request else "rejected manually")


@app.get("/evaluation/summary")
def evaluation_summary() -> dict[str, Any]:
    return store.evaluation_summary()


@app.get("/evaluation/events")
def recent_evaluation_events(limit: int = 50, event_type: str | None = None) -> dict[str, Any]:
    return {"items": store.recent_evaluation_events(limit=limit, event_type=event_type)}


@app.post("/evaluation/events")
def record_evaluation_event(request: EvaluationEventRequest) -> dict[str, int]:
    event_id = store.record_evaluation_event(
        event_type=request.event_type,
        session_id=request.session_id,
        source=request.source,
        latency_ms=request.latency_ms,
        memory_hit_ids=request.memory_hit_ids,
        created_memory_ids=request.created_memory_ids,
        heartbeat_event_id=request.heartbeat_event_id,
        fired=request.fired,
        reason=request.reason,
        payload=request.payload,
    )
    return {"id": event_id}


@app.get("/evaluation/export", response_model=None)
def export_evaluation_events(
    event_type: str | None = None, format: str = "json"
) -> Any:
    events = store.evaluation_events_for_export(event_type=event_type)
    if format == "json":
        return {"items": events}
    if format != "csv":
        raise HTTPException(status_code=400, detail="format must be json or csv")

    output = io.StringIO()
    fieldnames = [
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
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for event in events:
        writer.writerow(flatten_evaluation_event(event))
    filename = "kanojo_evaluation_events.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)


@app.get("/config")
def config() -> dict[str, Any]:
    return {
        "version": __version__,
        "node": node_config_summary(settings),
        "llm": {
            "configured": llm.configured,
            "base_url": settings.llm_base_url,
            "model": settings.llm_model,
            "chat_completions_url": llm.chat_completions_url() if llm.configured else None,
        },
        "memory_extraction_mode": settings.memory_extraction_mode,
        "inference_route_policy": inference_route_policy(settings),
        "tts": {
            "configured": tts.configured,
            "base_url": settings.tts_base_url,
            "mode": "external" if tts.configured else "desktop_speech_fallback",
            "synthesize_url": tts.synthesize_url() if tts.configured else None,
            "health_url": tts.health_url() if tts.configured else None,
        },
        "stt": {
            "configured": stt.configured,
            "base_url": settings.stt_base_url,
            "model": settings.stt_model,
            "transcriptions_url": stt.transcriptions_url() if stt.configured else None,
            "health_url": stt.health_url() if stt.configured else None,
        },
        "heartbeat": {
            "quiet_hours_start": settings.quiet_hours_start,
            "quiet_hours_end": settings.quiet_hours_end,
            "cooldown_minutes": settings.proactive_cooldown_minutes,
            "activity_grace_minutes": settings.activity_grace_minutes,
        },
        "db_path": str(settings.db_path),
    }


@app.post("/heartbeat/tick")
def heartbeat_tick(request: HeartbeatRequest) -> dict[str, Any]:
    last_activity_at = store.last_activity_time()
    decision = evaluate_heartbeat(
        last_user_at=store.last_message_time("user"),
        last_agent_at=store.last_message_time("assistant"),
        last_activity_at=last_activity_at,
        now=datetime.now(UTC),
        enabled=request.enabled,
        force=request.force,
        quiet_start=settings.quiet_hours_start,
        quiet_end=settings.quiet_hours_end,
        cooldown_minutes=settings.proactive_cooldown_minutes,
        activity_grace_minutes=settings.activity_grace_minutes,
    )
    reason = f"{request.source}: {decision.reason}"
    event_id = store.record_heartbeat(decision.fired, reason, decision.message)
    evaluation_event_id = store.record_evaluation_event(
        event_type="heartbeat",
        source=request.source,
        heartbeat_event_id=event_id,
        fired=decision.fired,
        reason=reason,
        payload={
            "message": decision.message,
            "enabled": request.enabled,
            "force": request.force,
            "quiet_hours_start": settings.quiet_hours_start,
            "quiet_hours_end": settings.quiet_hours_end,
            "cooldown_minutes": settings.proactive_cooldown_minutes,
            "activity_grace_minutes": settings.activity_grace_minutes,
            "last_activity_at": last_activity_at,
        },
    )
    return {
        "id": event_id,
        "evaluation_event_id": evaluation_event_id,
        "fired": decision.fired,
        "reason": reason,
        "message": decision.message,
        "source": request.source,
        "last_activity_at": last_activity_at,
    }


@app.post("/activity/events")
def record_activity_event(request: ActivityEventRequest) -> dict[str, int]:
    event_id = store.record_activity_event(
        activity_type=request.activity_type,
        source=request.source,
        intensity=request.intensity,
        note=request.note,
    )
    return {"id": event_id}


@app.get("/activity/events")
def recent_activity_events(limit: int = 20) -> dict[str, Any]:
    return {"items": store.recent_activity_events(limit=limit)}


@app.get("/activity/status")
def activity_status() -> dict[str, Any]:
    return {
        "last_activity_at": store.last_activity_time(),
        "grace_minutes": settings.activity_grace_minutes,
        "recent": store.recent_activity_events(limit=5),
    }


def write_memory_locally(
    *,
    kind: str,
    content: str,
    source_message_id: int | None = None,
    importance: float = 0.5,
    confidence: float = 0.7,
    deduplicate: bool = False,
    source_node: str | None = None,
) -> dict[str, Any]:
    if deduplicate:
        duplicate = store.find_duplicate_memory(kind, content)
        if duplicate:
            return {
                "accepted": False,
                "target": "local",
                "id": None,
                "duplicate_id": duplicate["id"],
                "reason": f"duplicate memory #{duplicate['id']}",
            }
    memory_id = store.add_memory(
        kind=kind,
        content=content,
        source_message_id=source_message_id,
        importance=importance,
        confidence=confidence,
    )
    result: dict[str, Any] = {
        "accepted": True,
        "target": "local",
        "id": memory_id,
        "reason": "written to local SQLite",
    }
    if source_node:
        result["source_node"] = source_node
    return result


async def write_memory_by_policy(
    *,
    kind: str,
    content: str,
    source_message_id: int | None = None,
    importance: float = 0.5,
    confidence: float = 0.7,
    deduplicate: bool = False,
) -> dict[str, Any]:
    policy = memory_write_policy(settings)
    if policy["primary"] == "local":
        return write_memory_locally(
            kind=kind,
            content=content,
            source_message_id=source_message_id,
            importance=importance,
            confidence=confidence,
            deduplicate=deduplicate,
        )

    if not policy["migration_ready"]:
        return {
            "accepted": False,
            "target": "peer",
            "id": None,
            "policy": policy,
            "reason": policy["note"],
        }

    peer_result = await peer_post_json(
        settings,
        "/node/memory-writes",
        {
            "kind": kind,
            "content": content,
            "importance": importance,
            "confidence": confidence,
            "source_message_id": None,
            "deduplicate": deduplicate,
            "source_node": (settings.node_name.strip() or "local"),
        },
    )
    if not peer_result.get("available"):
        return {
            "accepted": False,
            "target": "peer",
            "id": None,
            "policy": policy,
            "remote": peer_result,
            "reason": f"peer memory write failed: {peer_result.get('error', 'unavailable')}",
        }

    payload = peer_result.get("payload")
    if not isinstance(payload, dict):
        return {
            "accepted": False,
            "target": "peer",
            "id": None,
            "policy": policy,
            "remote": peer_result,
            "reason": "peer memory write returned invalid payload",
        }

    return {
        **payload,
        "target": "peer",
        "remote": peer_result,
        "reason": payload.get("reason", "written to peer memory source"),
    }


async def apply_memory_candidates(
    *,
    user_message_id: int,
    raw_text: str,
    method: str,
    candidates: list[MemoryCandidate],
    no_candidate_reason: str = "no durable memory candidate",
) -> list[MemoryDecision]:
    decisions: list[MemoryDecision] = []
    for candidate in candidates:
        accepted, reason = validate_candidate(candidate)
        memory_id = None
        if accepted:
            write_result = await write_memory_by_policy(
                kind=candidate.kind,
                content=candidate.content,
                source_message_id=user_message_id,
                importance=candidate.importance,
                confidence=candidate.confidence,
                deduplicate=True,
            )
            accepted = bool(write_result["accepted"])
            reason = str(write_result.get("reason") or reason)
            if accepted and write_result.get("id") is not None:
                memory_id = int(write_result["id"])
        audit_id = store.add_memory_audit(
            source_message_id=user_message_id,
            method=method,
            raw_text=raw_text,
            candidate=candidate.to_dict(),
            accepted=accepted,
            reason=reason,
            memory_id=memory_id,
        )
        decisions.append(
            MemoryDecision(
                candidate=candidate,
                accepted=accepted,
                reason=reason,
                memory_id=memory_id,
                audit_id=audit_id,
            )
        )

    if not candidates:
        audit_id = store.add_memory_audit(
            source_message_id=user_message_id,
            method=method,
            raw_text=raw_text,
            candidate=None,
            accepted=False,
            reason=no_candidate_reason,
            memory_id=None,
        )
        # No candidate means nothing should appear as an accepted or rejected extracted memory.
        # The audit row still makes the extraction decision traceable.
        _ = audit_id

    return decisions


def flatten_evaluation_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event["id"],
        "event_type": event["event_type"],
        "session_id": event.get("session_id"),
        "source": event.get("source"),
        "latency_ms": event.get("latency_ms"),
        "memory_hit_count": event.get("memory_hit_count"),
        "memory_hit_ids": ",".join(str(item) for item in event.get("memory_hit_ids", [])),
        "created_memory_ids": ",".join(
            str(item) for item in event.get("created_memory_ids", [])
        ),
        "heartbeat_event_id": event.get("heartbeat_event_id"),
        "fired": event.get("fired"),
        "reason": event.get("reason"),
        "created_at": event["created_at"],
        "payload": json.dumps(event.get("payload", {}), ensure_ascii=False),
    }


def memory_card_export_filename(session_id: str, extension: str) -> str:
    safe_session_id = "".join(
        char if char.isascii() and (char.isalnum() or char in "-_") else "_"
        for char in session_id.strip()
    ).strip("_")
    return f"kanojo_memory_card_{safe_session_id or 'default'}.{extension}"


async def generate_reply_by_inference_route(
    user_text: str, memories: list[dict[str, Any]]
) -> dict[str, Any]:
    route = select_inference_route(settings, "chat_reply")
    route_started = perf_counter()
    if route["selected"] == "peer":
        peer_result = await peer_post_json(
            settings,
            "/node/inference/chat",
            {
                "text": user_text,
                "memories": memories,
            },
        )
        payload = peer_result.get("payload")
        if peer_result.get("available") and isinstance(payload, dict) and payload.get("reply"):
            remote_route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
            return {
                "reply": str(payload["reply"]),
                "route": {
                    **route,
                    "latency_ms": int((perf_counter() - route_started) * 1000),
                    "remote_latency_ms": payload.get("latency_ms"),
                    "llm_model": remote_route.get("llm_model", settings.llm_model),
                    "llm_configured": remote_route.get("llm_configured"),
                    "remote": peer_result,
                },
            }
        route = {
            **route,
            "selected": "local",
            "requested": "peer",
            "fallback": True,
            "reason": f"peer inference failed: {peer_result.get('error', 'invalid payload')}",
            "remote": peer_result,
        }

    reply = await llm.generate_reply(user_text, memories)
    route["latency_ms"] = int((perf_counter() - route_started) * 1000)
    route["llm_model"] = settings.llm_model
    route["llm_configured"] = llm.configured
    return {"reply": reply, "route": route}


def sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
