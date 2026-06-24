# P2 实施计划

P2 目标是在 P1 MVP 上补齐语音交互的实时性基础,顺序固定为:

1. 文本流式输出;
2. STT 语音输入;
3. TTS 打断;
4. 外部 TTS 音频接入。

## 里程碑

| 编号 | 交付 | 验收 |
| --- | --- | --- |
| P2.1 | 文本流式输出 | `/chat/stream` 返回 SSE;桌面端逐段更新 assistant 消息;`/chat` 仍可兜底 |
| P2.2 | STT 语音输入 | 桌面端可录音并转文字;转写文本可直接送入聊天输入 |
| P2.3 | TTS 打断 | 用户新输入或停止操作能立即取消当前语音播放;后续流式 TTS 可接入同一控制位 |
| P2.4 | 外部 TTS 音频接入 | 配置 `KANOJO_TTS_BASE_URL` 后后端可代理合成音频;桌面端优先播放外部音频,失败时回退系统语音 |

## 当前状态

- P2.1 已实现:
  - 后端新增 `/chat/stream`;
  - OpenAI-compatible / Ollama 使用 `stream=true`;
  - mock LLM 支持分片输出;
  - 桌面端增量渲染同一条 assistant 消息;
  - 流式不可用时自动退回 `/chat`;
  - 评测 payload 记录 `first_delta_ms` 和 `streamed=true`。
- P2.2 已实现:
  - 桌面端使用 `MediaRecorder` 录音;
  - 录音结束后发送 Blob 到 `/stt/transcribe`;
  - 后端支持 OpenAI-compatible `/audio/transcriptions` STT 服务;
  - 仓库内置本地 `faster-whisper` STT 服务,可通过 `scripts/start_stt.ps1` 启动;
  - 后端新增 `/stt/status`,桌面端录音前会检查本地 STT 是否真的可连接;
  - `scripts/test_stt.ps1` 可用真实音频验证本地 STT 与后端代理链路;
  - 未配置 STT 时 UI 明确显示“STT 未配置”,文字输入不受影响;
  - 转写成功后自动回填输入框,由用户确认后发送。
- P2.3 已实现:
  - 流式回复过程中按完整句子入队播放,不再等整段回复结束后才开始朗读;
  - 用户输入、录音开始、提交新消息或停止操作都会走同一个 `interruptSpeech` 控制位;
  - `interruptSpeech` 会同时取消当前 `SpeechSynthesisUtterance`、清空待播放队列和流式语音缓冲;
  - 每次播放都有独立 `runId`,旧 utterance 的 `onend/onerror` 不会覆盖新状态;
  - TTS 面板显示播放状态、首音延迟、播放模式、已播段数、队列长度和打断次数。
- P2.4 已实现:
  - 后端新增 `/tts/status` 和 `/tts/synthesize`;
  - `TTSClient` 支持本地服务返回直接音频字节、`audio_base64` 或 `audio_url`;
  - 仓库内置 Windows SAPI 本地 TTS 服务,可通过 `scripts/start_tts.ps1` 启动;
  - 桌面端播放队列优先请求外部 TTS 音频,不可用时自动回退系统 `speechSynthesis`;
  - 打断会 abort 正在进行的 TTS 合成请求、暂停当前 audio、释放 blob URL 并清空队列;
  - `scripts/test_tts.ps1` 可用真实 wav 音频验证本地 TTS 与后端代理链路。

## P2.2 配置

后端通过以下环境变量接入本地 STT 服务:

```powershell
$env:KANOJO_STT_BASE_URL="http://127.0.0.1:9000/v1"
$env:KANOJO_STT_MODEL="whisper-1"
```

本地验证:

```powershell
.\scripts\start_stt.ps1 -Restart -Warmup
.\scripts\start_backend.ps1 -Restart
.\scripts\test_stt.ps1
```

接口约定兼容 OpenAI audio transcription 风格:

```text
POST /v1/audio/transcriptions
multipart form: file, model
```

## P2.3 方案

P2.3 先完成系统语音层面的打断和分句播放:

- 流式回复按句子边生成边朗读,降低“等完整回答”的体感延迟;
- 用户输入、录音开始、提交新消息时自动 `speechSynthesis.cancel()`;
- 点击停止时同时取消正在播放、待播放队列和流式语音缓冲;
- 后续外部 TTS / 流式 TTS 接入时复用同一 interrupt 控制。

## P2.4 配置

后端通过以下环境变量接入外部 TTS 服务。仓库内置的本地 Windows SAPI 服务默认监听 `9880`:

```powershell
$env:KANOJO_TTS_BASE_URL="http://127.0.0.1:9880"
```

本地验证:

```powershell
.\scripts\start_tts.ps1 -Restart
.\scripts\start_backend.ps1 -Restart
.\scripts\test_tts.ps1
```

接口约定:

```text
POST /synthesize
JSON: {"text": "..."}
Response: audio/* bytes, or JSON with audio_base64/audio_url
```

## 非目标

- P2 不做 Live2D;
- P2 不做双机常驻;
- P2 不做屏幕活动感知;
- P2 不追求完整端到端语音流式大闭环,先让文本流式和语音输入各自稳定。
