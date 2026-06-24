# P1 API Contract

后端默认监听 `http://127.0.0.1:8787`。

## `GET /health`

返回服务状态。

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

## `GET /node/status`

P5.1 节点身份与拓扑健康接口。用于双机常驻前的节点可观测性,不迁移数据、不做同步。

```json
{
  "node": {
    "name": "local",
    "role": "standalone",
    "db_path": "data/kanojo.db",
    "peer_base_url": null,
    "llm_configured": false,
    "tts_configured": false,
    "stt_configured": false
  },
  "memory_write_policy": {
    "primary": "local",
    "offline_behavior": "local_only",
    "local_writes_enabled": true,
    "peer_writes_configured": false,
    "peer_base_url": null,
    "migration_ready": false,
    "note": "local SQLite remains the memory write target"
  },
  "inference_route_policy": {
    "primary": "auto",
    "node_role": "standalone",
    "local_llm_configured": false,
    "peer_base_url": null,
    "peer_inference_configured": false,
    "auto_delegates_chat": false,
    "note": "auto mode keeps inference local for standalone and pc_inference nodes"
  },
  "peer": {
    "configured": false,
    "available": false,
    "base_url": null,
    "error": "peer is not configured"
  }
}
```

`KANOJO_NODE_ROLE` 支持 `standalone / mac_home / pc_inference`。`KANOJO_PEER_BASE_URL` 配置后,接口会检查对端 `/health`;对端不可用只返回 `available: false`,不影响单机链路。

## `GET /node/memory-write-policy`

P5.3 写入迁移策略接口。P5.3b 起,聊天抽取记忆和手动 `/memories` 写入会按该策略选择本地或 peer。

```json
{
  "primary": "local",
  "offline_behavior": "local_only",
  "local_writes_enabled": true,
  "peer_writes_configured": false,
  "peer_base_url": null,
  "migration_ready": false,
  "note": "local SQLite remains the memory write target"
}
```

`KANOJO_MEMORY_PRIMARY` 支持 `local / peer`。`KANOJO_OFFLINE_WRITE_BEHAVIOR` 支持 `local_only / reject / queue`,其中 `queue` 只是预留协议,当前不实现离线队列和冲突合并。只有 `peer + reject + KANOJO_PEER_BASE_URL` 会进入迁移就绪状态;peer 不可用时拒绝写入,不会静默回退本地。

## `GET /node/inference-route-policy`

P5.4 推理路由策略接口。用于观察当前聊天回复会由本地还是 peer 推理。

```json
{
  "primary": "auto",
  "node_role": "mac_home",
  "local_llm_configured": false,
  "peer_base_url": "http://pc.local:8787",
  "peer_inference_configured": true,
  "auto_delegates_chat": true,
  "note": "auto mode delegates chat replies from mac_home to peer inference"
}
```

## `GET /node/peer/memory-card?session_id=default`

P5.2 只读远端记忆名片代理。读取 `KANOJO_PEER_BASE_URL` 指向节点的 `/memory-card`,不写入远端或本地数据库。

```json
{
  "configured": true,
  "available": true,
  "base_url": "http://mac-mini.local:8787",
  "url": "http://mac-mini.local:8787/memory-card?session_id=default",
  "payload": {
    "title": "AI 记忆名片",
    "memory_count": 9
  }
}
```

## `GET /node/peer/memory-card/reflection?session_id=default`

P5.2 只读远端反思摘要代理。读取 peer 的 `/memory-card/reflection`,响应外层与 `/node/peer/memory-card` 一致。

## `POST /node/inference/chat`

P5.4 peer 推理落点。该接口只使用接收节点本地 LLM/mock 生成回复,不会再次转发。

请求:

```json
{
  "text": "你好",
  "memories": []
}
```

响应:

```json
{
  "reply": "我先把这句话认真接住:你好",
  "latency_ms": 25,
  "route": {
    "selected": "local",
    "task_type": "chat_reply",
    "reason": "local node inference endpoint",
    "llm_model": "qwen3-14b",
    "llm_configured": false
  }
}
```

## `POST /node/inference/prewarm`

PC 推理节点预热接口。用于后端启动后主动触发一次极短本地 LLM 调用,避免 Mac 第一次委托推理时遇到模型冷启动超时。

请求:

```json
{
  "text": "预热 PC 推理节点"
}
```

响应:

```json
{
  "ok": true,
  "reply": "预热完成。",
  "latency_ms": 1200,
  "llm_model": "qwen2.5:14b",
  "llm_configured": true
}
```

## `POST /node/memory-writes`

P5.3b peer 写入落点。该接口只在接收节点本地 SQLite 落库,不会再次按写入策略转发,用于避免双节点递归和双写。

请求:

```json
{
  "kind": "event",
  "content": "用户周五有英语口语考试",
  "importance": 0.8,
  "confidence": 0.9,
  "source_message_id": null,
  "deduplicate": true,
  "source_node": "pc"
}
```

响应:

```json
{
  "accepted": true,
  "target": "local",
  "id": 42,
  "reason": "written to local SQLite",
  "source_node": "pc"
}
```

## `POST /chat`

请求:

```json
{
  "text": "我明天有考试",
  "session_id": "default"
}
```

响应:

```json
{
  "reply": "记下来了。明天考试前我会提醒你早点休息。",
  "memories": [
    {
      "id": 1,
      "kind": "event",
      "content": "用户明天有考试",
      "score": 0.82
    }
  ],
  "memory_extraction": {
    "method": "heuristic",
    "error": null,
    "decisions": [
      {
        "candidate": {
          "kind": "event",
          "content": "我明天有考试",
          "importance": 0.65,
          "confidence": 0.65,
          "reason": "heuristic marker matched",
          "method": "heuristic"
        },
        "accepted": true,
        "reason": "accepted",
        "memory_id": 1,
        "audit_id": 1
      }
    ]
  },
  "created_memory_ids": [1],
  "evaluation_event_id": 1,
  "inference_route": {
    "selected": "local",
    "task_type": "chat_reply",
    "reason": "local inference route selected",
    "llm_model": "qwen3-14b",
    "llm_configured": false,
    "latency_ms": 320
  },
  "latency_ms": 1200
}
```

## `POST /chat/stream`

P2.1 文本流式聊天接口。请求体与 `/chat` 一致,响应为 `text/event-stream`。

事件顺序:

```text
event: meta
data: {"message_ids":{"user":1},"memories":[]}

event: delta
data: {"text":"我"}

event: delta
data: {"text":"记下来了"}

event: done
data: {"reply":"我记下来了。","latency_ms":1200,"first_delta_ms":320,"inference_route":{"selected":"local"}}
```

事件说明:

- `meta`:用户消息已落库,并返回本轮检索到的已有记忆。
- `delta`:LLM 增量文本片段,桌面端应追加到同一条 assistant 消息。
- `done`:完整回复、记忆抽取审计、评测事件 ID、总延迟和首片段延迟。
- `error`:流式过程中出现错误时返回错误消息。

流式接口为了降低首字延迟,会先基于已有记忆生成回复,回复结束后再执行本轮记忆抽取和审计。非流式 `/chat` 保持 P1 行为不变。

## `POST /memories`

手动写入记忆,用于调试和评测。默认 `local + local_only` 时写入本机 SQLite;当 `KANOJO_MEMORY_PRIMARY=peer`、`KANOJO_OFFLINE_WRITE_BEHAVIOR=reject` 且配置了 `KANOJO_PEER_BASE_URL` 时,后端会写入 peer 的 `/node/memory-writes`。

响应:

```json
{
  "accepted": true,
  "target": "local",
  "id": 1,
  "reason": "written to local SQLite"
}
```

peer 未配置或不可用时返回 `503`,响应 `detail.reason` 解释拒绝原因。

## `DELETE /memories/{memory_id}`

软删除本地长期记忆。该接口不会物理删除 SQLite 行,只把 `memories.status` 改为 `inactive`,因此名片、检索和反思摘要不再使用该记忆。

响应:

```json
{
  "id": 2,
  "deactivated": true,
  "reason": "memory soft-deactivated",
  "memory": {
    "id": 2,
    "status": "inactive"
  }
}
```

## `POST /maintenance/cleanup-test-memories`

维护接口,用于清理联调/冒烟/链路验证过程中写入的测试记忆。默认 `dry_run=true`,只返回匹配项,不修改数据库。正式执行时设置 `dry_run=false`。

请求:

```json
{
  "dry_run": true,
  "patterns": [
    "联调测试",
    "真实双机联调",
    "双机联调",
    "链路验证",
    "PC 长期记忆写回 Mac mini"
  ]
}
```

响应:

```json
{
  "dry_run": true,
  "matched_count": 2,
  "deactivated_count": 0,
  "remaining_matches": 2,
  "items": [
    {
      "id": 1,
      "kind": "event",
      "content": "联调测试：PC 长期记忆写回 Mac mini"
    }
  ]
}
```

## `POST /stt/transcribe`

P2.2 语音输入转写接口。桌面端直接把录音 Blob 作为请求体发送,后端再转发到 OpenAI-compatible audio transcription 服务。

请求头:

```text
Content-Type: audio/webm
X-Filename: recording.webm
```

未配置 `KANOJO_STT_BASE_URL` 时不会影响文字聊天,返回:

```json
{
  "configured": false,
  "text": "",
  "error": "STT service is not configured."
}
```

配置后返回:

```json
{
  "configured": true,
  "text": "转写出来的文字",
  "model": "base",
  "language": "zh",
  "duration": 11.0,
  "latency_ms": 767
}
```

若 STT 服务已配置但不可用,返回 `configured: true`、空文本和 `error`,桌面端会直接显示错误。

## `GET /stt/status`

P2.2 本地 STT 可用性检查。桌面端录音前会调用一次,避免麦克风录完后才发现服务没有启动。

```json
{
  "configured": true,
  "available": true,
  "base_url": "http://127.0.0.1:9000/v1",
  "model": "whisper-1",
  "health_url": "http://127.0.0.1:9000/health",
  "detail": {
    "status": "ok",
    "model": "base",
    "device": "cpu",
    "compute_type": "int8",
    "language": "zh",
    "model_loaded": true
  }
}
```

## `GET /memories?query=考试`

按查询词检索记忆,返回分数、来源和更新时间。

## `GET /memory-card?session_id=default`

P4.1 记忆名片接口。后端从 active memories 生成确定性 artifact,按关系状态、偏好、事件和反思分组,同时返回 Markdown 版本供后续导出。

```json
{
  "title": "AI 记忆名片",
  "session_id": "default",
  "generated_at": "2026-06-24T10:00:00+00:00",
  "memory_count": 3,
  "conversation_count": 24,
  "latest_message_at": "2026-06-24T09:58:00+00:00",
  "summary": "已沉淀 3 条长期记忆,覆盖 关系状态、偏好、事件。",
  "sections": [
    {
      "kind": "preference",
      "title": "偏好",
      "items": [
        {
          "id": 1,
          "kind": "preference",
          "content": "用户喜欢普通话音色",
          "importance": 0.8,
          "confidence": 0.9,
          "source_message_id": 12,
          "created_at": "2026-06-24T09:00:00+00:00",
          "updated_at": "2026-06-24T09:00:00+00:00"
        }
      ]
    }
  ],
  "markdown": "# AI 记忆名片\n..."
}
```

## `GET /memory-card/export?session_id=default&format=markdown`

P4.2 记忆名片导出接口。`format` 支持 `markdown` / `md` / `json`。

Markdown 响应:

```text
Content-Type: text/markdown; charset=utf-8
Content-Disposition: attachment; filename="kanojo_memory_card_default.md"

# AI 记忆名片
...
```

JSON 响应:

```text
Content-Type: application/json; charset=utf-8
Content-Disposition: attachment; filename="kanojo_memory_card_default.json"
```

JSON 内容与 `/memory-card` 返回的名片对象一致,用于演示留档、论文材料和后续版本快照。

## `GET /memory-card/reflection?session_id=default`

P4.4 反思摘要接口。后端从当前记忆名片确定性生成摘要,返回样本就绪度、分组主题、证据和后续关注点。

```json
{
  "title": "AI 反思摘要",
  "session_id": "default",
  "generated_at": "2026-06-24T10:05:00+00:00",
  "memory_count": 4,
  "conversation_count": 24,
  "sample_ready": true,
  "readiness": "样本充足",
  "summary": "当前长期记忆已覆盖 关系状态、偏好,可以作为阶段性反思摘要。",
  "themes": [
    {
      "kind": "preference",
      "title": "偏好",
      "count": 2,
      "headline": "偏好线索: 用户喜欢普通话音色",
      "evidence": ["用户喜欢普通话音色"],
      "next_focus": "用后续反馈校验偏好是否稳定,避免把一次性选择当成长期偏好。"
    }
  ],
  "next_questions": ["事件还缺少样本。"],
  "markdown": "# AI 反思摘要\n..."
}
```

## `POST /memory-card/snapshots`

P4.3 创建当前记忆名片快照。后端会调用同一份 `/memory-card` 生成逻辑,并把完整 JSON、Markdown 和摘要写入 SQLite。

请求:

```json
{
  "session_id": "default",
  "label": "答辩演示前"
}
```

响应:

```json
{
  "id": 1,
  "session_id": "default",
  "label": "答辩演示前",
  "memory_count": 9,
  "conversation_count": 24,
  "summary": "已沉淀 9 条长期记忆,覆盖 关系状态、偏好、事件。",
  "generated_at": "2026-06-24T10:00:00+00:00",
  "created_at": "2026-06-24T10:00:01+00:00",
  "card": {
    "title": "AI 记忆名片"
  },
  "markdown": "# AI 记忆名片\n..."
}
```

## `GET /memory-card/snapshots?session_id=default`

返回最近的名片快照摘要列表,默认最多 20 条。

```json
{
  "items": [
    {
      "id": 1,
      "session_id": "default",
      "label": "答辩演示前",
      "memory_count": 9,
      "conversation_count": 24,
      "summary": "已沉淀 9 条长期记忆,覆盖 关系状态、偏好、事件。",
      "generated_at": "2026-06-24T10:00:00+00:00",
      "created_at": "2026-06-24T10:00:01+00:00"
    }
  ]
}
```

## `GET /memory-card/snapshots/{snapshot_id}`

返回单个快照详情,包含完整 `card` 和 `markdown`。

## `GET /memory-card/snapshots/{snapshot_id}/compare`

把指定快照与当前记忆名片对比。`added` 表示当前名片相对快照新增的记忆,`removed` 表示快照中有但当前名片没有的记忆。

```json
{
  "snapshot": {
    "id": 1,
    "card": {}
  },
  "current": {
    "title": "AI 记忆名片"
  },
  "diff": {
    "added_count": 1,
    "removed_count": 0,
    "unchanged_count": 8,
    "sections": [
      {
        "kind": "event",
        "title": "事件",
        "added": [
          {
            "kind": "event",
            "content": "用户周五有英语口语考试",
            "id": 12
          }
        ],
        "removed": []
      }
    ]
  }
}
```

## `GET /memory-audits`

返回最近的记忆抽取审计记录,用于检查"为什么存 / 为什么没存"。

查询参数:

- `limit`:返回条数,默认 20,最大 100。
- `offset`:分页偏移,默认 0。
- `decision`:可选,`accepted` / `pending` / `rejected`。
- `q`:可选搜索词,匹配原文、候选内容、方法和原因。

## `POST /memory-audits/{audit_id}/approve`

人工批准一条待确认候选记忆。请求体可省略;如果需要批准前编辑候选内容,传入 `candidate`。

```json
{
  "candidate": {
    "kind": "preference",
    "content": "用户喜欢柔和普通话女声",
    "importance": 0.6,
    "confidence": 0.75
  }
}
```

## `POST /memory-audits/{audit_id}/reject`

人工拒绝一条待确认候选记忆。

```json
{
  "reason": "rejected manually"
}
```

## `POST /memory-audits/batch`

批量批准或拒绝多条候选记忆。批量批准使用候选原文;需要编辑时先使用单条批准接口。

```json
{
  "audit_ids": [12, 13],
  "action": "reject",
  "reason": "batch rejected manually"
}
```

## `POST /heartbeat/tick`

触发一次心跳评估。P1 由桌面端或后台定时器调用。P5.5 起,最近桌面活动会作为主动心跳抑制条件,但不会直接触发通知。

请求:

```json
{
  "enabled": true,
  "force": false,
  "source": "scheduler"
}
```

字段:

- `enabled`:主动心跳总开关。
- `force`:仅用于测试通知链路,会绕过冷却、免打扰和活动抑制。
- `source`:调用来源,例如 `scheduler`、`manual`、`forced`。

响应包含是否触发、理由、来源、最近活动时间和可选主动消息。

```json
{
  "id": 12,
  "evaluation_event_id": 34,
  "fired": false,
  "reason": "scheduler: recent desktop activity",
  "message": null,
  "source": "scheduler",
  "last_activity_at": "2026-06-24T08:00:00+00:00"
}
```

## `POST /activity/events`

P5.5 低频活动信号写入接口。活动只进入主动心跳判断,不会直接触发通知。

请求:

```json
{
  "activity_type": "user_input",
  "source": "desktop",
  "intensity": 0.8,
  "note": "visible"
}
```

响应:

```json
{
  "id": 1
}
```

## `GET /activity/status`

返回最近 active 类活动时间、活动抑制窗口和最近 5 条活动事件。

```json
{
  "last_activity_at": "2026-06-24T08:00:00+00:00",
  "grace_minutes": 10,
  "recent": []
}
```

## `GET /activity/events?limit=20`

返回最近活动事件,用于调试活动感知是否正常上报。

## `GET /evaluation/summary`

返回评测埋点摘要,用于 demo 观察和后续实验数据导出前检查。

```json
{
  "chat": {
    "count": 10,
    "avg_latency_ms": 1320,
    "p95_latency_ms": 2200,
    "memory_hit_rate": 0.6,
    "avg_memory_hits": 1.2
  },
  "heartbeat": {
    "count": 20,
    "fired_count": 3,
    "blocked_count": 17,
    "fired_rate": 0.15,
    "latest_reason": "scheduler: cooldown after user message"
  },
  "avatar": {
    "count": 12,
    "voice_start_count": 4,
    "avg_first_play_ms": 230,
    "lip_sync_count": 4,
    "avg_mouth_active_ms": 900,
    "avg_mouth_active_ratio": 0.75,
    "interrupt_count": 1,
    "avg_interrupt_to_silent_ms": 12
  },
  "recent_events": []
}
```

## `POST /evaluation/events`

写入通用评测事件。P3.4 桌面端用它记录形象侧时序指标,也可继续用于后续实验脚本补充事件。

请求:

```json
{
  "event_type": "avatar_lip_sync",
  "session_id": "default",
  "source": "desktop_live2d",
  "latency_ms": 1200,
  "reason": "system_speech_ended",
  "payload": {
    "run_id": 7,
    "mode": "reply",
    "channel": "system",
    "source": "text",
    "active_ms": 900,
    "active_ratio": 0.75,
    "max_mouth_level": 3,
    "avatar_mode": "speaking",
    "live2d_status": "ready"
  }
}
```

响应:

```json
{
  "id": 35
}
```

当前形象事件:

- `avatar_voice_start`:语音实际首播,`latency_ms` 为首播耗时。
- `avatar_lip_sync`:一次口型同步结束,`payload.active_ms` 和 `payload.active_ratio` 为嘴型活动估算。
- `avatar_interrupt`:打断完成,`latency_ms` 为打断入口到播放清理和闭嘴归零的耗时。

## `GET /evaluation/events?limit=50&event_type=chat`

返回最近评测事件。`event_type` 可选,当前写入 `chat`、`heartbeat` 和 `avatar_*`:

- `chat`:记录端到端延迟、命中记忆 ID、新增记忆 ID、记忆抽取方法、消息 ID、LLM 模型和 P5.4 推理路由。
- `heartbeat`:记录主动心跳来源、是否触发、触发/未触发理由、关联心跳事件 ID 和最近活动时间。
- `avatar_*`:记录 Live2D/口型链路的首播、活动和打断闭嘴时序。

## `GET /evaluation/export?format=json`

导出全部评测事件。`format` 支持 `json` 和 `csv`;`event_type` 可选。

JSON 响应:

```json
{
  "items": []
}
```

CSV 响应字段:

```text
id,event_type,session_id,source,latency_ms,memory_hit_count,memory_hit_ids,created_memory_ids,heartbeat_event_id,fired,reason,created_at,payload
```

## `GET /config`

返回当前 LLM、记忆抽取模式和数据库路径。不会返回 API key。

TTS 字段:

```json
{
  "tts": {
    "configured": true,
    "base_url": "http://127.0.0.1:9880",
    "mode": "external",
    "synthesize_url": "http://127.0.0.1:9880/synthesize",
    "health_url": "http://127.0.0.1:9880/health"
  },
  "stt": {
    "configured": false,
    "base_url": null,
    "model": "whisper-1",
    "transcriptions_url": null
  }
}
```

## `GET /tts/status`

P2.4 外部 TTS 可用性检查。未配置时返回桌面系统语音兜底模式;配置后会检查外部服务的 `/health`。若服务没有 `/health` 但 `/synthesize` 可用,仍可直接合成。

```json
{
  "configured": true,
  "available": true,
  "base_url": "http://127.0.0.1:9880",
  "mode": "external",
  "synthesize_url": "http://127.0.0.1:9880/synthesize",
  "health_url": "http://127.0.0.1:9880/health"
}
```

## `POST /tts/synthesize`

桌面端通过后端代理请求外部 TTS。后端接受外部服务返回:

- `audio/*` 或 `application/octet-stream` 原始音频字节;
- JSON `audio_base64`;
- JSON `audio_url`。

请求:

```json
{
  "text": "要合成的句子"
}
```

响应示例:

```json
{
  "configured": true,
  "status": "ok",
  "text": "要合成的句子",
  "content_type": "audio/wav",
  "audio_base64": "...",
  "latency_ms": 420
}
```

P2.4 默认优先播放外部 TTS 音频。外部 TTS 不可用或单句合成失败时,桌面端回退系统 `speechSynthesis`。输入、录音、提交新消息和停止按钮共用同一个打断控制位。
