from __future__ import annotations

from datetime import UTC, datetime, timedelta
import asyncio

from fastapi.testclient import TestClient

from kanojo_agent.heartbeat import evaluate_heartbeat, in_quiet_hours
from kanojo_agent.extractor import MemoryCandidate, validate_candidate
from kanojo_agent.extractor import MemoryExtractor
from kanojo_agent.llm import LLMClient, _parse_json_array, chunk_text
from kanojo_agent.memory import infer_memory_kind, score_memory
from kanojo_agent.node import (
    inference_route_policy,
    memory_write_policy,
    node_config_summary,
    normalized_node_role,
    select_inference_route,
)
from kanojo_agent.settings import Settings
from kanojo_agent.stt import STTClient
from kanojo_agent.storage import MemoryStore
from kanojo_agent.tts import TTSClient


def make_settings(tmp_path, **overrides) -> Settings:
    values = {
        "db_path": tmp_path / "test.db",
        "llm_base_url": None,
        "llm_api_key": None,
        "llm_model": "mock",
        "llm_timeout_seconds": 60,
        "memory_extraction_mode": "heuristic",
        "tts_base_url": None,
        "stt_base_url": None,
        "stt_api_key": None,
        "stt_model": "whisper-1",
        "stt_timeout_seconds": 120,
        "quiet_hours_start": 23,
        "quiet_hours_end": 8,
        "proactive_cooldown_minutes": 120,
    }
    values.update(overrides)
    return Settings(**values)


def test_score_memory_prefers_relevant_memory() -> None:
    now = datetime(2026, 6, 23, 12, tzinfo=UTC)
    relevant = {
        "content": "用户明天有考试,需要早点休息",
        "importance": 0.8,
        "created_at": now.isoformat(),
    }
    irrelevant = {
        "content": "用户喜欢吃甜点",
        "importance": 0.8,
        "created_at": now.isoformat(),
    }

    assert score_memory(relevant, "明天考试", now=now) > score_memory(
        irrelevant, "明天考试", now=now
    )


def test_infer_memory_kind() -> None:
    assert infer_memory_kind("我明天有考试") == "event"
    assert infer_memory_kind("我喜欢普通话音色") == "preference"
    assert infer_memory_kind("以后可以叫我吉川") == "relationship"
    assert infer_memory_kind("嗯,我知道了") is None


def test_quiet_hours_cross_midnight() -> None:
    assert in_quiet_hours(datetime(2026, 6, 23, 23, tzinfo=UTC), 23, 8)
    assert in_quiet_hours(datetime(2026, 6, 24, 7, tzinfo=UTC), 23, 8)
    assert not in_quiet_hours(datetime(2026, 6, 24, 12, tzinfo=UTC), 23, 8)


def test_heartbeat_cooldown() -> None:
    now = datetime(2026, 6, 23, 12, tzinfo=UTC)
    recent = (now - timedelta(minutes=30)).isoformat()
    old = (now - timedelta(hours=5)).isoformat()

    assert not evaluate_heartbeat(
        last_user_at=recent,
        last_agent_at=None,
        now=now,
        quiet_start=23,
        quiet_end=8,
        cooldown_minutes=120,
    ).fired
    assert evaluate_heartbeat(
        last_user_at=old,
        last_agent_at=None,
        now=now,
        quiet_start=23,
        quiet_end=8,
        cooldown_minutes=120,
    ).fired


def test_heartbeat_recent_activity_blocks_proactive_tick() -> None:
    now = datetime(2026, 6, 23, 12, tzinfo=UTC)
    old_user = (now - timedelta(hours=5)).isoformat()
    recent_activity = (now - timedelta(minutes=2)).isoformat()

    decision = evaluate_heartbeat(
        last_user_at=old_user,
        last_agent_at=None,
        last_activity_at=recent_activity,
        now=now,
        quiet_start=23,
        quiet_end=8,
        cooldown_minutes=120,
        activity_grace_minutes=10,
    )

    assert not decision.fired
    assert decision.reason == "recent desktop activity"


def test_forced_heartbeat_bypasses_cooldown() -> None:
    now = datetime(2026, 6, 23, 12, tzinfo=UTC)
    recent = (now - timedelta(minutes=1)).isoformat()
    decision = evaluate_heartbeat(
        last_user_at=recent,
        last_agent_at=recent,
        now=now,
        force=True,
        quiet_start=23,
        quiet_end=8,
        cooldown_minutes=120,
    )
    assert decision.fired
    assert decision.reason == "forced heartbeat"


def test_validate_candidate_rejects_low_confidence() -> None:
    candidate = MemoryCandidate(
        kind="event",
        content="我可能明天有考试",
        importance=0.6,
        confidence=0.4,
        reason="uncertain",
        method="heuristic",
    )
    accepted, reason = validate_candidate(candidate)
    assert not accepted
    assert reason == "confidence below threshold"


def test_parse_json_array_from_fenced_output() -> None:
    parsed = _parse_json_array(
        '```json\n[{"kind":"event","content":"用户明天有考试","importance":0.7,"confidence":0.8}]\n```'
    )
    assert parsed[0]["kind"] == "event"


def test_llm_url_normalization(tmp_path) -> None:
    settings = Settings(
        db_path=tmp_path / "test.db",
        llm_base_url="http://127.0.0.1:1234/v1",
        llm_api_key=None,
        llm_model="qwen3",
        llm_timeout_seconds=60,
        memory_extraction_mode="hybrid",
        tts_base_url=None,
        stt_base_url=None,
        stt_api_key=None,
        stt_model="whisper-1",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
    )
    assert LLMClient(settings).chat_completions_url() == (
        "http://127.0.0.1:1234/v1/chat/completions"
    )


def test_node_config_summary(tmp_path) -> None:
    settings = Settings(
        db_path=tmp_path / "test.db",
        llm_base_url="http://127.0.0.1:1234/v1",
        llm_api_key=None,
        llm_model="qwen3",
        llm_timeout_seconds=60,
        memory_extraction_mode="hybrid",
        tts_base_url=None,
        stt_base_url=None,
        stt_api_key=None,
        stt_model="whisper-1",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
        node_name="pc",
        node_role="pc_inference",
        peer_base_url="http://mac-mini.local:8787/",
    )
    summary = node_config_summary(settings)

    assert normalized_node_role("unknown") == "standalone"
    assert summary["name"] == "pc"
    assert summary["role"] == "pc_inference"
    assert summary["peer_base_url"] == "http://mac-mini.local:8787"
    assert summary["llm_configured"] is True


def test_inference_route_policy_auto_delegates_mac_home_to_peer(tmp_path) -> None:
    settings = make_settings(
        tmp_path,
        node_role="mac_home",
        peer_base_url="http://pc.local:8787",
        inference_primary="auto",
    )

    policy = inference_route_policy(settings)
    route = select_inference_route(settings, "chat_reply")

    assert policy["primary"] == "auto"
    assert policy["auto_delegates_chat"] is True
    assert route["selected"] == "peer"
    assert "delegates chat replies" in route["reason"]


def test_inference_route_policy_standalone_keeps_local(tmp_path) -> None:
    settings = make_settings(tmp_path, inference_primary="auto")

    route = select_inference_route(settings, "chat_reply")

    assert route["selected"] == "local"
    assert route["reason"] == "local inference route selected"


def test_memory_write_policy_defaults_to_local(tmp_path) -> None:
    settings = Settings(
        db_path=tmp_path / "test.db",
        llm_base_url=None,
        llm_api_key=None,
        llm_model="mock",
        llm_timeout_seconds=60,
        memory_extraction_mode="heuristic",
        tts_base_url=None,
        stt_base_url=None,
        stt_api_key=None,
        stt_model="whisper-1",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
    )

    policy = memory_write_policy(settings)

    assert policy["primary"] == "local"
    assert policy["local_writes_enabled"] is True
    assert policy["migration_ready"] is False


def test_memory_write_policy_peer_requires_peer_url(tmp_path) -> None:
    settings = Settings(
        db_path=tmp_path / "test.db",
        llm_base_url=None,
        llm_api_key=None,
        llm_model="mock",
        llm_timeout_seconds=60,
        memory_extraction_mode="heuristic",
        tts_base_url=None,
        stt_base_url=None,
        stt_api_key=None,
        stt_model="whisper-1",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
        memory_primary="peer",
        offline_write_behavior="reject",
    )

    policy = memory_write_policy(settings)

    assert policy["primary"] == "peer"
    assert policy["peer_writes_configured"] is False
    assert policy["migration_ready"] is False


def test_memory_write_policy_peer_local_only_is_not_ready(tmp_path) -> None:
    settings = make_settings(
        tmp_path,
        memory_primary="peer",
        offline_write_behavior="local_only",
        peer_base_url="http://mac-mini.local:8787",
    )

    policy = memory_write_policy(settings)

    assert policy["primary"] == "peer"
    assert policy["peer_writes_configured"] is True
    assert policy["migration_ready"] is False
    assert "single-writer" in policy["note"]


def test_hybrid_empty_llm_falls_back_to_heuristic(tmp_path) -> None:
    settings = Settings(
        db_path=tmp_path / "test.db",
        llm_base_url=None,
        llm_api_key=None,
        llm_model="qwen3",
        llm_timeout_seconds=60,
        memory_extraction_mode="hybrid",
        tts_base_url=None,
        stt_base_url=None,
        stt_api_key=None,
        stt_model="whisper-1",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
    )

    class EmptyLLM(LLMClient):
        @property
        def configured(self) -> bool:
            return True

        async def extract_memory_json(self, user_text: str):
            return []

    method, candidates, error = asyncio.run(
        MemoryExtractor(settings, EmptyLLM(settings)).extract("我喜欢普通话音色")
    )
    assert method == "heuristic_fallback"
    assert candidates[0].kind == "preference"
    assert error == "llm returned no durable candidates"


def test_operational_test_text_is_not_extracted(tmp_path) -> None:
    settings = make_settings(
        tmp_path,
        llm_base_url="http://127.0.0.1:1234/v1",
        memory_extraction_mode="hybrid",
    )

    class HallucinatingLLM(LLMClient):
        @property
        def configured(self) -> bool:
            return True

        async def extract_memory_json(self, user_text: str):
            return [
                {
                    "kind": "preference",
                    "content": "用户计划购买 Mac mini",
                    "importance": 1,
                    "confidence": 1,
                    "reason": "hallucinated",
                }
            ]

    method, candidates, error = asyncio.run(
        MemoryExtractor(settings, HallucinatingLLM(settings)).extract(
            "真实双机联调：我在2026年6月24日完成 PC 推理节点和 Mac mini 常驻记忆节点的联调验证。"
        )
    )

    assert method == "filtered"
    assert candidates == []
    assert error == "operational test text is not durable user memory"


def test_hybrid_rejects_unsupported_llm_candidate_and_falls_back(tmp_path) -> None:
    settings = make_settings(
        tmp_path,
        llm_base_url="http://127.0.0.1:1234/v1",
        memory_extraction_mode="hybrid",
    )

    class UnsupportedLLM(LLMClient):
        @property
        def configured(self) -> bool:
            return True

        async def extract_memory_json(self, user_text: str):
            return [
                {
                    "kind": "preference",
                    "content": "用户计划购买 Mac mini",
                    "importance": 1,
                    "confidence": 1,
                    "reason": "hallucinated",
                }
            ]

    method, candidates, error = asyncio.run(
        MemoryExtractor(settings, UnsupportedLLM(settings)).extract("我明天有英语考试")
    )

    assert method == "heuristic_fallback"
    assert candidates[0].kind == "event"
    assert candidates[0].content == "我明天有英语考试"
    assert error == "llm returned no durable candidates"


def test_mock_reply_stream(tmp_path) -> None:
    settings = Settings(
        db_path=tmp_path / "test.db",
        llm_base_url=None,
        llm_api_key=None,
        llm_model="mock",
        llm_timeout_seconds=60,
        memory_extraction_mode="heuristic",
        tts_base_url=None,
        stt_base_url=None,
        stt_api_key=None,
        stt_model="whisper-1",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
    )

    async def collect_chunks() -> list[str]:
        return [chunk async for chunk in LLMClient(settings).generate_reply_stream("你好", [])]

    chunks = asyncio.run(collect_chunks())
    assert chunks == chunk_text("我先把这句话认真接住:你好")
    assert "".join(chunks) == "我先把这句话认真接住:你好"


def test_stt_url_normalization(tmp_path) -> None:
    settings = Settings(
        db_path=tmp_path / "test.db",
        llm_base_url=None,
        llm_api_key=None,
        llm_model="mock",
        llm_timeout_seconds=60,
        memory_extraction_mode="heuristic",
        tts_base_url=None,
        stt_base_url="http://127.0.0.1:9000/v1",
        stt_api_key=None,
        stt_model="whisper-large-v3",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
    )
    assert STTClient(settings).transcriptions_url() == (
        "http://127.0.0.1:9000/v1/audio/transcriptions"
    )
    assert STTClient(settings).health_url() == "http://127.0.0.1:9000/health"


def test_tts_url_normalization(tmp_path) -> None:
    settings = Settings(
        db_path=tmp_path / "test.db",
        llm_base_url=None,
        llm_api_key=None,
        llm_model="mock",
        llm_timeout_seconds=60,
        memory_extraction_mode="heuristic",
        tts_base_url="http://127.0.0.1:9880",
        stt_base_url=None,
        stt_api_key=None,
        stt_model="whisper-1",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
    )
    client = TTSClient(settings)
    assert client.synthesize_url() == "http://127.0.0.1:9880/synthesize"
    assert client.health_url() == "http://127.0.0.1:9880/health"


def test_memory_card_groups_active_memories(tmp_path) -> None:
    store = MemoryStore(tmp_path / "card.db")
    user_message_id = store.add_message("default", "user", "我喜欢普通话音色")
    store.add_memory(
        "preference",
        "用户喜欢普通话音色",
        source_message_id=user_message_id,
        importance=0.8,
        confidence=0.9,
    )
    store.add_memory(
        "relationship",
        "用户希望被叫作吉川",
        source_message_id=user_message_id,
        importance=0.7,
        confidence=0.8,
    )
    store.add_memory(
        "event",
        "用户明天有考试",
        source_message_id=user_message_id,
        importance=0.9,
        confidence=0.85,
    )

    card = store.memory_card()
    sections = {section["kind"]: section for section in card["sections"]}

    assert card["title"] == "AI 记忆名片"
    assert card["memory_count"] == 3
    assert card["conversation_count"] == 1
    assert card["latest_message_at"] is not None
    assert sections["relationship"]["items"][0]["content"] == "用户希望被叫作吉川"
    assert sections["preference"]["items"][0]["content"] == "用户喜欢普通话音色"
    assert sections["event"]["items"][0]["importance"] == 0.9
    assert "## 关系状态" in card["markdown"]
    assert "用户明天有考试" in card["markdown"]


def test_memory_reflection_summary_is_deterministic(tmp_path) -> None:
    store = MemoryStore(tmp_path / "reflection.db")
    user_message_id = store.add_message("default", "user", "以后叫我吉川,我喜欢普通话音色")
    store.add_memory(
        "relationship",
        "用户希望被叫作吉川",
        source_message_id=user_message_id,
        importance=0.8,
        confidence=0.9,
    )
    store.add_memory(
        "preference",
        "用户喜欢普通话音色",
        source_message_id=user_message_id,
        importance=0.7,
        confidence=0.8,
    )

    summary = store.memory_reflection_summary()
    themes = {theme["kind"]: theme for theme in summary["themes"]}

    assert summary["title"] == "AI 反思摘要"
    assert summary["sample_ready"] is False
    assert summary["memory_count"] == 2
    assert themes["relationship"]["headline"].startswith("关系线索")
    assert themes["preference"]["evidence"] == ["用户喜欢普通话音色"]
    assert themes["event"]["headline"] == "暂无稳定线索"
    assert "## 待验证问题" in summary["markdown"]


def test_memory_card_export_endpoint(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    store = MemoryStore(tmp_path / "export.db")
    message_id = store.add_message("default", "user", "我喜欢普通话音色")
    store.add_memory(
        "preference",
        "用户喜欢普通话音色",
        source_message_id=message_id,
        importance=0.8,
        confidence=0.9,
    )
    monkeypatch.setattr(main, "store", store)
    client = TestClient(main.app)

    markdown_response = client.get("/memory-card/export?session_id=default&format=markdown")
    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-type"].startswith("text/markdown")
    assert (
        'attachment; filename="kanojo_memory_card_default.md"'
        == markdown_response.headers["content-disposition"]
    )
    assert "# AI 记忆名片" in markdown_response.text
    assert "用户喜欢普通话音色" in markdown_response.text

    json_response = client.get("/memory-card/export?session_id=default&format=json")
    assert json_response.status_code == 200
    assert json_response.headers["content-type"].startswith("application/json")
    assert json_response.json()["sections"][1]["items"][0]["content"] == "用户喜欢普通话音色"

    bad_response = client.get("/memory-card/export?format=txt")
    assert bad_response.status_code == 400


def test_memory_reflection_endpoint(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    store = MemoryStore(tmp_path / "reflection-api.db")
    message_id = store.add_message("default", "user", "我周五有英语口语考试")
    store.add_memory(
        "event",
        "用户周五有英语口语考试",
        source_message_id=message_id,
        importance=0.8,
        confidence=0.9,
    )
    monkeypatch.setattr(main, "store", store)
    client = TestClient(main.app)

    response = client.get("/memory-card/reflection?session_id=default")

    assert response.status_code == 200
    payload = response.json()
    assert payload["memory_count"] == 1
    assert payload["themes"][2]["kind"] == "event"
    assert payload["themes"][2]["evidence"] == ["用户周五有英语口语考试"]


def test_node_status_endpoint_without_peer(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    settings = Settings(
        db_path=tmp_path / "node.db",
        llm_base_url=None,
        llm_api_key=None,
        llm_model="mock",
        llm_timeout_seconds=60,
        memory_extraction_mode="heuristic",
        tts_base_url=None,
        stt_base_url=None,
        stt_api_key=None,
        stt_model="whisper-1",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
        node_name="local-test",
        node_role="standalone",
    )
    monkeypatch.setattr(main, "settings", settings)
    client = TestClient(main.app)

    response = client.get("/node/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["node"]["name"] == "local-test"
    assert payload["node"]["role"] == "standalone"
    assert payload["node"]["peer_timeout_seconds"] == 3
    assert payload["memory_write_policy"]["primary"] == "local"
    assert payload["peer"]["configured"] is False
    assert payload["peer"]["available"] is False


def test_peer_memory_card_without_peer(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    settings = Settings(
        db_path=tmp_path / "node.db",
        llm_base_url=None,
        llm_api_key=None,
        llm_model="mock",
        llm_timeout_seconds=60,
        memory_extraction_mode="heuristic",
        tts_base_url=None,
        stt_base_url=None,
        stt_api_key=None,
        stt_model="whisper-1",
        stt_timeout_seconds=120,
        quiet_hours_start=23,
        quiet_hours_end=8,
        proactive_cooldown_minutes=120,
    )
    monkeypatch.setattr(main, "settings", settings)
    client = TestClient(main.app)

    response = client.get("/node/peer/memory-card")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["available"] is False


def test_peer_memory_card_endpoint_uses_read_only_proxy(monkeypatch) -> None:
    from kanojo_agent import main

    async def fake_peer_json(settings, path, params=None):
        return {
            "configured": True,
            "available": True,
            "base_url": "http://mac-mini.local:8787",
            "url": f"http://mac-mini.local:8787{path}",
            "payload": {"session_id": params["session_id"], "memory_count": 2},
        }

    monkeypatch.setattr(main, "peer_json", fake_peer_json)
    client = TestClient(main.app)

    response = client.get("/node/peer/memory-card?session_id=demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["payload"]["session_id"] == "demo"
    assert payload["payload"]["memory_count"] == 2


def test_local_inference_endpoint_uses_local_llm(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    monkeypatch.setattr(main, "settings", make_settings(tmp_path))
    client = TestClient(main.app)

    response = client.post(
        "/node/inference/chat",
        json={"text": "你好", "memories": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "我先把这句话认真接住:你好"
    assert payload["route"]["selected"] == "local"
    assert payload["route"]["task_type"] == "chat_reply"


def test_local_inference_prewarm_endpoint_uses_local_llm(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    monkeypatch.setattr(main, "settings", make_settings(tmp_path))
    client = TestClient(main.app)

    response = client.post("/node/inference/prewarm", json={"text": "预热"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["llm_configured"] is False
    assert payload["reply"] == "我先把这句话认真接住:预热"


def test_chat_routes_inference_to_peer_when_auto_mac_home(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    async def fake_peer_post_json(settings, path, payload):
        assert path == "/node/inference/chat"
        assert payload["text"] == "你好"
        return {
            "configured": True,
            "available": True,
            "base_url": "http://pc.local:8787",
            "url": "http://pc.local:8787/node/inference/chat",
            "payload": {
                "reply": "peer reply",
                "latency_ms": 25,
                "route": {
                    "selected": "local",
                    "task_type": "chat_reply",
                    "llm_model": "qwen-heavy",
                    "llm_configured": True,
                },
            },
        }

    store = MemoryStore(tmp_path / "peer-inference.db")
    settings = make_settings(
        tmp_path,
        node_role="mac_home",
        peer_base_url="http://pc.local:8787",
        inference_primary="auto",
    )
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "peer_post_json", fake_peer_post_json)
    client = TestClient(main.app)

    response = client.post("/chat", json={"text": "你好", "session_id": "default"})

    assert response.status_code == 200
    payload = response.json()
    events = store.recent_evaluation_events(limit=1)
    assert payload["reply"] == "peer reply"
    assert payload["inference_route"]["selected"] == "peer"
    assert payload["inference_route"]["remote_latency_ms"] == 25
    assert payload["inference_route"]["llm_model"] == "qwen-heavy"
    assert events[0]["payload"]["inference_route"]["selected"] == "peer"


def test_chat_falls_back_local_when_peer_inference_fails(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    async def unavailable_peer_post_json(settings, path, payload):
        return {
            "configured": True,
            "available": False,
            "base_url": "http://pc.local:8787",
            "url": "http://pc.local:8787/node/inference/chat",
            "error": "connection refused",
        }

    store = MemoryStore(tmp_path / "peer-inference-fallback.db")
    settings = make_settings(
        tmp_path,
        node_role="mac_home",
        peer_base_url="http://pc.local:8787",
        inference_primary="auto",
    )
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "peer_post_json", unavailable_peer_post_json)
    client = TestClient(main.app)

    response = client.post("/chat", json={"text": "你好", "session_id": "default"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "我先把这句话认真接住:你好"
    assert payload["inference_route"]["selected"] == "local"
    assert payload["inference_route"]["requested"] == "peer"
    assert payload["inference_route"]["fallback"] is True


def test_manual_memory_write_defaults_to_local(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    store = MemoryStore(tmp_path / "manual-local.db")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "settings", make_settings(tmp_path))
    client = TestClient(main.app)

    response = client.post(
        "/memories",
        json={
            "kind": "preference",
            "content": "用户喜欢普通话音色",
            "importance": 0.8,
            "confidence": 0.9,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["target"] == "local"
    assert payload["id"] == 1
    assert store.search_memories("普通话")[0]["content"] == "用户喜欢普通话音色"


def test_delete_memory_soft_deactivates_local_memory(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    store = MemoryStore(tmp_path / "delete-memory.db")
    memory_id = store.add_memory("event", "联调测试：需要被删除")
    monkeypatch.setattr(main, "store", store)
    client = TestClient(main.app)

    response = client.delete(f"/memories/{memory_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["deactivated"] is True
    assert store.memory_by_id(memory_id)["status"] == "inactive"
    assert store.memory_card()["memory_count"] == 0


def test_update_memory_edits_content_and_weight(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    store = MemoryStore(tmp_path / "update-memory.db")
    memory_id = store.add_memory("preference", "用户喜欢旧音色", importance=0.8, confidence=0.9)
    monkeypatch.setattr(main, "store", store)
    client = TestClient(main.app)

    response = client.patch(
        f"/memories/{memory_id}",
        json={
            "content": "用户喜欢柔和普通话音色",
            "importance": 0.4,
            "confidence": 0.6,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"] is True
    updated = store.memory_by_id(memory_id)
    assert updated["content"] == "用户喜欢柔和普通话音色"
    assert updated["importance"] == 0.4
    assert updated["confidence"] == 0.6
    assert updated["status"] == "active"


def test_approve_memory_audit_writes_candidate(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    store = MemoryStore(tmp_path / "approve-audit.db")
    message_id = store.add_message("default", "user", "我喜欢柔和女声")
    audit_id = store.add_memory_audit(
        source_message_id=message_id,
        method="manual_test",
        raw_text="我喜欢柔和女声",
        candidate={
            "kind": "preference",
            "content": "用户喜欢柔和女声",
            "importance": 0.7,
            "confidence": 0.8,
            "method": "manual_test",
            "reason": "test candidate",
        },
        accepted=False,
        reason="pending manual review",
        memory_id=None,
    )
    monkeypatch.setattr(main, "store", store)
    client = TestClient(main.app)

    response = client.post(f"/memory-audits/{audit_id}/approve")

    assert response.status_code == 200
    payload = response.json()
    assert payload["approved"] is True
    memory_id = payload["memory_id"]
    assert store.memory_by_id(memory_id)["content"] == "用户喜欢柔和女声"
    audit = store.memory_audit_by_id(audit_id)
    assert audit["accepted"] is True
    assert audit["memory_id"] == memory_id


def test_cleanup_test_memories_dry_run_and_apply(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    store = MemoryStore(tmp_path / "cleanup-test-memories.db")
    test_memory_id = store.add_memory("event", "联调测试：PC 长期记忆写回 Mac mini")
    real_memory_id = store.add_memory("event", "用户周五有英语考试")
    monkeypatch.setattr(main, "store", store)
    client = TestClient(main.app)

    dry_run = client.post("/maintenance/cleanup-test-memories", json={"dry_run": True})

    assert dry_run.status_code == 200
    assert dry_run.json()["matched_count"] == 1
    assert dry_run.json()["items"][0]["id"] == test_memory_id
    assert store.memory_card()["memory_count"] == 2

    applied = client.post("/maintenance/cleanup-test-memories", json={"dry_run": False})

    assert applied.status_code == 200
    assert applied.json()["deactivated_count"] == 1
    assert applied.json()["remaining_matches"] == 0
    assert store.memory_by_id(test_memory_id)["status"] == "inactive"
    assert store.memory_by_id(real_memory_id)["status"] == "active"
    assert store.memory_card()["memory_count"] == 1


def test_manual_memory_write_routes_to_peer_when_ready(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    captured: dict[str, object] = {}

    async def fake_peer_post_json(settings, path, payload):
        captured["settings"] = settings
        captured["path"] = path
        captured["payload"] = payload
        return {
            "configured": True,
            "available": True,
            "base_url": "http://mac-mini.local:8787",
            "url": "http://mac-mini.local:8787/node/memory-writes",
            "payload": {
                "accepted": True,
                "target": "local",
                "id": 42,
                "reason": "written to local SQLite",
            },
        }

    store = MemoryStore(tmp_path / "manual-peer.db")
    settings = make_settings(
        tmp_path,
        memory_primary="peer",
        offline_write_behavior="reject",
        peer_base_url="http://mac-mini.local:8787",
        node_name="pc",
    )
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "peer_post_json", fake_peer_post_json)
    client = TestClient(main.app)

    response = client.post(
        "/memories",
        json={
            "kind": "event",
            "content": "用户周五有英语口语考试",
            "importance": 0.8,
            "confidence": 0.9,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["target"] == "peer"
    assert payload["id"] == 42
    assert captured["path"] == "/node/memory-writes"
    peer_payload = captured["payload"]
    assert isinstance(peer_payload, dict)
    assert peer_payload["source_message_id"] is None
    assert peer_payload["source_node"] == "pc"
    assert store.search_memories("英语") == []


def test_chat_memory_candidate_rejects_when_peer_write_fails(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    async def unavailable_peer_post_json(settings, path, payload):
        return {
            "configured": True,
            "available": False,
            "base_url": "http://mac-mini.local:8787",
            "url": "http://mac-mini.local:8787/node/memory-writes",
            "error": "connection refused",
        }

    store = MemoryStore(tmp_path / "peer-fail.db")
    settings = make_settings(
        tmp_path,
        memory_primary="peer",
        offline_write_behavior="reject",
        peer_base_url="http://mac-mini.local:8787",
    )
    message_id = store.add_message("default", "user", "我喜欢普通话音色")
    candidate = MemoryCandidate(
        kind="preference",
        content="用户喜欢普通话音色",
        importance=0.8,
        confidence=0.9,
        reason="explicit preference",
        method="heuristic",
    )
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "peer_post_json", unavailable_peer_post_json)

    decisions = asyncio.run(
        main.apply_memory_candidates(
            user_message_id=message_id,
            raw_text="我喜欢普通话音色",
            method="heuristic",
            candidates=[candidate],
        )
    )
    audits = store.recent_memory_audits(limit=1)

    assert decisions[0].accepted is False
    assert decisions[0].memory_id is None
    assert decisions[0].reason.startswith("peer memory write failed")
    assert audits[0]["accepted"] is False
    assert audits[0]["reason"].startswith("peer memory write failed")
    assert store.search_memories("普通话") == []


def test_chat_memory_candidate_routes_to_peer_when_ready(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    async def fake_peer_post_json(settings, path, payload):
        return {
            "configured": True,
            "available": True,
            "base_url": "http://mac-mini.local:8787",
            "url": "http://mac-mini.local:8787/node/memory-writes",
            "payload": {
                "accepted": True,
                "target": "local",
                "id": 77,
                "reason": "written to local SQLite",
            },
        }

    store = MemoryStore(tmp_path / "peer-chat.db")
    settings = make_settings(
        tmp_path,
        memory_primary="peer",
        offline_write_behavior="reject",
        peer_base_url="http://mac-mini.local:8787",
    )
    message_id = store.add_message("default", "user", "我周五有英语口语考试")
    candidate = MemoryCandidate(
        kind="event",
        content="用户周五有英语口语考试",
        importance=0.8,
        confidence=0.9,
        reason="explicit event",
        method="heuristic",
    )
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "peer_post_json", fake_peer_post_json)

    decisions = asyncio.run(
        main.apply_memory_candidates(
            user_message_id=message_id,
            raw_text="我周五有英语口语考试",
            method="heuristic",
            candidates=[candidate],
        )
    )

    assert decisions[0].accepted is True
    assert decisions[0].memory_id == 77
    assert store.search_memories("英语") == []


def test_memory_card_snapshots_compare_current(tmp_path) -> None:
    store = MemoryStore(tmp_path / "snapshot.db")
    message_id = store.add_message("default", "user", "我喜欢普通话音色")
    store.add_memory(
        "preference",
        "用户喜欢普通话音色",
        source_message_id=message_id,
        importance=0.8,
        confidence=0.9,
    )

    snapshot = store.create_memory_card_snapshot(label="初始快照")
    store.add_memory(
        "event",
        "用户周五有英语口语考试",
        source_message_id=message_id,
        importance=0.9,
        confidence=0.9,
    )
    comparison = store.compare_memory_card_snapshot(snapshot["id"])
    snapshots = store.memory_card_snapshots()

    assert snapshot["label"] == "初始快照"
    assert snapshot["memory_count"] == 1
    assert snapshot["card"]["sections"][1]["items"][0]["content"] == "用户喜欢普通话音色"
    assert snapshots[0]["id"] == snapshot["id"]
    assert comparison is not None
    assert comparison["current"]["memory_count"] == 2
    assert comparison["diff"]["added_count"] == 1
    assert comparison["diff"]["removed_count"] == 0
    event_diff = comparison["diff"]["sections"][2]
    assert event_diff["kind"] == "event"
    assert event_diff["added"][0]["content"] == "用户周五有英语口语考试"


def test_memory_card_snapshot_endpoints(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    store = MemoryStore(tmp_path / "snapshot-api.db")
    message_id = store.add_message("default", "user", "我喜欢普通话音色")
    store.add_memory(
        "preference",
        "用户喜欢普通话音色",
        source_message_id=message_id,
        importance=0.8,
        confidence=0.9,
    )
    monkeypatch.setattr(main, "store", store)
    client = TestClient(main.app)

    create_response = client.post(
        "/memory-card/snapshots",
        json={"session_id": "default", "label": "演示节点"},
    )
    assert create_response.status_code == 200
    snapshot_id = create_response.json()["id"]
    assert create_response.json()["label"] == "演示节点"

    list_response = client.get("/memory-card/snapshots?session_id=default")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == snapshot_id

    detail_response = client.get(f"/memory-card/snapshots/{snapshot_id}")
    assert detail_response.status_code == 200
    assert "# AI 记忆名片" in detail_response.json()["markdown"]

    compare_response = client.get(f"/memory-card/snapshots/{snapshot_id}/compare")
    assert compare_response.status_code == 200
    assert compare_response.json()["diff"]["unchanged_count"] == 1

    missing_response = client.get("/memory-card/snapshots/999/compare")
    assert missing_response.status_code == 404


def test_evaluation_events_summary(tmp_path) -> None:
    store = MemoryStore(tmp_path / "eval.db")
    chat_event_id = store.record_evaluation_event(
        event_type="chat",
        session_id="default",
        source="desktop",
        latency_ms=1200,
        memory_hit_ids=[1, 2],
        created_memory_ids=[3],
        payload={"memory_extraction_method": "heuristic"},
    )
    heartbeat_id = store.record_heartbeat(False, "scheduler: cooldown after user message", None)
    heartbeat_event_id = store.record_evaluation_event(
        event_type="heartbeat",
        source="scheduler",
        heartbeat_event_id=heartbeat_id,
        fired=False,
        reason="scheduler: cooldown after user message",
    )
    voice_event_id = store.record_evaluation_event(
        event_type="avatar_voice_start",
        source="desktop_live2d",
        latency_ms=230,
        payload={"mode": "reply", "channel": "system"},
    )
    lip_event_id = store.record_evaluation_event(
        event_type="avatar_lip_sync",
        source="desktop_live2d",
        payload={
            "source": "text",
            "duration_ms": 1200,
            "active_ms": 900,
            "active_ratio": 0.75,
            "max_mouth_level": 3,
        },
    )
    interrupt_event_id = store.record_evaluation_event(
        event_type="avatar_interrupt",
        source="desktop_live2d",
        latency_ms=12,
        reason="input interrupted speech",
    )

    events = store.recent_evaluation_events(limit=10)
    exported = store.evaluation_events_for_export()
    summary = store.evaluation_summary()

    assert events[0]["id"] == interrupt_event_id
    assert events[1]["id"] == lip_event_id
    assert events[2]["id"] == voice_event_id
    assert [event["id"] for event in exported] == [
        chat_event_id,
        heartbeat_event_id,
        voice_event_id,
        lip_event_id,
        interrupt_event_id,
    ]
    assert events[4]["memory_hit_ids"] == [1, 2]
    assert summary["chat"]["count"] == 1
    assert summary["chat"]["avg_latency_ms"] == 1200
    assert summary["chat"]["memory_hit_rate"] == 1
    assert summary["heartbeat"]["count"] == 1
    assert summary["heartbeat"]["blocked_count"] == 1
    assert summary["heartbeat"]["latest_reason"] == "scheduler: cooldown after user message"
    assert summary["avatar"]["count"] == 3
    assert summary["avatar"]["voice_start_count"] == 1
    assert summary["avatar"]["avg_first_play_ms"] == 230
    assert summary["avatar"]["lip_sync_count"] == 1
    assert summary["avatar"]["avg_mouth_active_ms"] == 900
    assert summary["avatar"]["avg_mouth_active_ratio"] == 0.75
    assert summary["avatar"]["interrupt_count"] == 1
    assert summary["avatar"]["avg_interrupt_to_silent_ms"] == 12


def test_activity_events_status_and_heartbeat_gate(tmp_path, monkeypatch) -> None:
    from kanojo_agent import main

    store = MemoryStore(tmp_path / "activity.db")
    old_message_time = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(
        main,
        "settings",
        make_settings(tmp_path, activity_grace_minutes=10, quiet_hours_start=0, quiet_hours_end=0),
    )
    message_id = store.add_message("default", "user", "我先离开一下")
    with store.connect() as conn:
        conn.execute("UPDATE messages SET created_at = ? WHERE id = ?", (old_message_time, message_id))
    client = TestClient(main.app)

    activity_response = client.post(
        "/activity/events",
        json={"activity_type": "user_input", "source": "desktop", "intensity": 0.8},
    )
    status_response = client.get("/activity/status")
    heartbeat_response = client.post(
        "/heartbeat/tick",
        json={"enabled": True, "force": False, "source": "scheduler"},
    )

    assert activity_response.status_code == 200
    assert status_response.status_code == 200
    assert status_response.json()["last_activity_at"] is not None
    assert status_response.json()["recent"][0]["activity_type"] == "user_input"
    assert heartbeat_response.status_code == 200
    assert heartbeat_response.json()["fired"] is False
    assert heartbeat_response.json()["reason"] == "scheduler: recent desktop activity"
