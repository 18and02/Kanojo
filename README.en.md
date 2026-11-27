# AI Memory Card Desktop Agent

This repository is the project workspace for the graduation project “Design, Implementation, and Evaluation of a Memory-Driven Proactive Interactive Desktop Agent for Long-Term Companionship.” The original Chinese README remains the primary source; this English version preserves its stated implementation status and constraints.

## Current status

**P5 dual-machine always-on loop is complete.** The Windows single-machine system includes text and voice input, LLM replies, persistent memory, proactive heartbeat, TTS output, barge-in, a Live2D character, character-side evaluation instrumentation, a reviewable memory-card view, Markdown/JSON export, version snapshots, and reflection summaries.

The Mac persistent-memory source and PC inference node support node identity, peer health checks, read-only remote memory artifacts, policy-based memory-write routing, chat inference routing, and low-frequency activity awareness. See `docs/P5_CLOSEOUT.md` for P5 closeout.

The current two-machine demo baseline is in `docs/DEMO_RUNBOOK.md`: a Mac mini runs the persistent SQLite memory source; the PC runs local `qwen2.5:14b` inference. Long-term memories from the PC are written back to the Mac, and the Mac `/chat` endpoint delegates inference to the PC automatically.

Defense and finalization materials:

- `docs/DEFENSE_MATERIALS.md`: thesis and defense materials, including contributions, architecture narrative, demo sequence, and risk responses.
- `docs/FINAL_SELF_CHECK.md`: final checks and follow-up optimization list, including completed five-round cycles, verification commands, and remaining priorities.
- `docs/SHOWCASE_PACKAGE.md`: showcase packaging, startup sequence, and release packaging.

## Main contribution

Memory-driven proactive interaction:

- Layered persistent memory: raw conversations, event memories, facts and preferences, and relationship state.
- Retrieval scoring by relevance, recency, and importance.
- Proactive engine with cooldowns, do-not-disturb periods, trigger reasons, and interruption suppression.
- Evaluatable loop measuring memory recall, false-memory rate, appropriateness of proactive interactions, and interruption rate.

## Project structure

```text
backend/          Python orchestration service for chat, memory, heartbeat, and TTS/LLM adapters
desktop/          Electron desktop client skeleton
docs/             Startup, architecture, API, and P1 planning documents
*.md              PRD, proposal, recording specifications, and graduation-project documents
```

## P1 architecture

```text
Electron Desktop
  -> FastAPI backend
    -> LLM adapter (OpenAI-compatible / local fallback)
    -> SQLite memory store
    -> Memory scoring
    -> Heartbeat scheduler
    -> TTS adapter
```

## Local startup and common scripts

The recommended Windows launcher prefers local `pnpm` and falls back to the Codex bundled runtime:

```powershell
cd "G:\Codex env\Kanojo"
.\scripts\dev.ps1
```

Other launch and packaging scripts:

```powershell
.\scripts\start_backend.ps1
.\scripts\start_desktop.ps1
.\scripts\start_backend.ps1 -Restart
.\scripts\dual_node_demo.ps1
.\scripts\start_demo_stack.ps1 -Restart
.\scripts\export_evaluation_snapshot.ps1
.\scripts\build_release.ps1
.\scripts\install_windows_desktop_portable.ps1
.\scripts\build_showcase_package.ps1 -OutDir exports-showcase-package
```

The showcase package includes `SHOWCASE_INDEX.md`, `demo-talk-track.md`, `recording-plan.md`, an evaluation report, key screenshots, a screenshot-composite MP4, and release verification information. If the desktop still shows old state, restart it with `scripts/start_desktop.ps1 -Restart`. To start the desktop while ensuring the backend is running, use `scripts/start_desktop.ps1 -EnsureBackend -Restart`. Register the PC backend to start at user login with `scripts/install_windows_backend_startup.ps1 -RunNow`.

P1 acceptance, demo scripts, and evaluation exports are documented in `docs/P1_CLOSEOUT.md`. Common demo data commands:

```powershell
.\scripts\p1_demo.ps1 reset-seed
.\scripts\p1_demo.ps1 status
.\scripts\p1_demo.ps1 export-csv
```

## LLM configuration

The P1 backend supports the OpenAI-compatible Chat Completions API. If no provider is configured, it uses a mock LLM for offline demos and frontend integration.

```powershell
# LM Studio
$env:KANOJO_LLM_BASE_URL="http://127.0.0.1:1234/v1"
$env:KANOJO_LLM_MODEL="qwen3-14b"

# Ollama OpenAI-compatible endpoint
$env:KANOJO_LLM_BASE_URL="http://127.0.0.1:11434/v1"
$env:KANOJO_LLM_MODEL="qwen3:14b"

# llama.cpp server
$env:KANOJO_LLM_BASE_URL="http://127.0.0.1:8080/v1"
$env:KANOJO_LLM_MODEL="local-model"
```

Memory extraction mode is controlled by `KANOJO_MEMORY_EXTRACTION`: `hybrid` uses an LLM to extract JSON when available and falls back to heuristics on failure; `heuristic` is fully offline and uses rules only.

## Speech-to-text (STT)

P2.2 supports an OpenAI-compatible audio transcription service. If it is not configured, desktop recording remains available but displays `STT service is not configured.` Text input is unaffected.

```powershell
$env:KANOJO_STT_BASE_URL="http://127.0.0.1:9000/v1"
$env:KANOJO_STT_MODEL="whisper-1"
```

A local `faster-whisper` service can be started with the repository scripts. `backend\.env` configures `127.0.0.1:9000`, so `dev.ps1` starts STT automatically; use `-SkipStt` when voice is not needed.

```powershell
.\scripts\dev.ps1 -Restart
.\scripts\start_stt.ps1 -Restart -Warmup
.\scripts\test_stt.ps1
```

The STT test uses `backend\data\stt-test-zh.wav` to verify local STT → backend proxy → transcription text. To start the backend manually:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,stt]"
uvicorn kanojo_agent.main:app --reload
```

Start the desktop client with `cd desktop`, `pnpm install`, and `pnpm dev`.

## TTS and interruption

In P2.3, the desktop uses the system `speechSynthesis` as its current speech output layer. With speech output enabled, streamed replies are queued and played sentence by sentence. User input, starting a recording, submitting a new message, or clicking Stop immediately cancels playback and clears the queue. External GPT-SoVITS/CosyVoice integrations reuse the same interruption control.

In P2.4, setting `KANOJO_TTS_BASE_URL` makes the backend proxy requests through `/tts/synthesize`. The desktop prefers external TTS audio and falls back to system speech if synthesis fails or is not configured. A Windows SAPI local TTS service is included for a real WAV audio path:

```powershell
$env:KANOJO_TTS_BASE_URL="http://127.0.0.1:9880"
.\scripts\start_tts.ps1 -Restart
.\scripts\start_backend.ps1 -Restart
.\scripts\test_tts.ps1
```

## Live2D evaluation (P3.4)

The CSS character has been replaced with a real Live2D rendering layer. The default is the official Haru Greeter sample model. Recording, generation, TTS synthesis/playback, and interruption drive the model's pose; while speech is playing, the P3.2 lip-sync signal is written to `ParamMouthOpenY`. If Live2D initialization fails, the client falls back to the CSS character.

The character layer sends first-speech latency, lip activity, and interruption-to-mouth-closed duration to `POST /evaluation/events`. The debug panel shows first-speech latency, average lip-active duration, average activity rate, and interruption-to-silence/mouth-closed duration.

## Memory cards and reflection (P4.4)

`GET /memory-card` deterministically organizes active memories into relationship state, preferences, events, and reflections, and returns a Markdown artifact. `GET /memory-card/export?format=markdown|json` exports the current card as Markdown or JSON. P4.3 added the `memory_card_snapshots` table and snapshot endpoints: `POST /memory-card/snapshots` saves a version; `GET /memory-card/snapshots/{id}/compare` compares it with the current card and reports added, removed, and unchanged counts by group.

P4.4 added `GET /memory-card/reflection`, which deterministically generates a reflection summary from the current card, including sample readiness, group themes, evidence, follow-up points, and Markdown. The desktop Memory page has five views: card, reflection, hits, audit, and versions. The card view supports copying/export; the versions view supports saving a snapshot, refreshing the list, and comparing changes.

## Dual-node memory writes (P5.3)

`GET /node/status` returns node identity, peer health, and `memory_write_policy`. Defaults remain `KANOJO_MEMORY_PRIMARY=local` and `KANOJO_OFFLINE_WRITE_BEHAVIOR=local_only`; single-machine chat, extraction, and manual memory writes are unchanged.

With `peer + reject` and `KANOJO_PEER_BASE_URL` configured, long-term memories extracted from chat and `POST /memories` are sent to the peer's `/node/memory-writes`. The receiving node stores them only in its local SQLite database and does not forward them again. If the peer is unavailable, unconfigured, or the policy is not ready, that memory write is rejected and recorded in the memory audit; it does not silently fall back to local storage and create a dual write.

```powershell
$env:KANOJO_NODE_NAME="pc"
$env:KANOJO_NODE_ROLE="pc_inference"
$env:KANOJO_PEER_BASE_URL="http://mac-mini.local:8787"
$env:KANOJO_MEMORY_PRIMARY="peer"
$env:KANOJO_OFFLINE_WRITE_BEHAVIOR="reject"
```

## Inference routing (P5.4)

`GET /node/inference-route-policy` returns the active inference routing policy. `KANOJO_INFERENCE_PRIMARY` accepts `auto`, `local`, or `peer`. With the default `auto`, a `mac_home` node configured with a peer delegates chat response generation to the peer's `/node/inference/chat`; `standalone` and `pc_inference` use local inference by default.

Both `/chat` and `/chat/stream` record `inference_route` in evaluation event payloads, including selection, reason, model, peer latency, and fallback reason. If peer inference fails, the backend falls back to the local LLM/mock, so the current conversation can finish.

```powershell
$env:KANOJO_NODE_ROLE="mac_home"
$env:KANOJO_PEER_BASE_URL="http://pc.local:8787"
$env:KANOJO_INFERENCE_PRIMARY="auto"
```

## Activity awareness (P5.5)

The backend provides `POST /activity/events`, `GET /activity/status`, and `GET /activity/events`. The desktop reports window visibility, focus/blur, and low-frequency input activity. These signals only suppress proactive heartbeat notifications; they do not trigger notifications directly.

`KANOJO_ACTIVITY_GRACE_MINUTES` defaults to `10`. If recent activity is within this window, `/heartbeat/tick` returns `recent desktop activity` to avoid interrupting someone actively using the desktop. `force=true` remains available for manually testing the notification path.

```powershell
$env:KANOJO_ACTIVITY_GRACE_MINUTES="10"
```

## Current constraints

- P2.2 includes local STT; text input is unaffected when the STT service is stopped.
- P5.3 keeps single-machine local writes by default. Peer writes require `peer + reject + KANOJO_PEER_BASE_URL`.
- SQLite is the sole source of truth; a vector database is planned only as an index layer.
- The public defense version avoids strongly romanticized language and emphasizes long-term memory, proactive interaction, privacy, and healthy boundaries.
- The desktop calls the backend periodically for proactive heartbeat decisions. Test notifications use `force`; background scheduling does not bypass cooldowns or do-not-disturb.
- P2.4 prefers external TTS by default and falls back to desktop system speech when unavailable. `KANOJO_TTS_BASE_URL` can later point to GPT-SoVITS/CosyVoice.
- P3.4 validates the real Live2D path and evaluation instrumentation with the official sample model; it does not include final custom character assets or a transparent floating desktop window.
- P4 implements deterministic memory cards, reflection summaries, local export, and version snapshots; it does not include LLM polishing, automatic privacy redaction, or public sharing.
- P5.3 does not implement an offline write queue, conflict merging, or dual-write synchronization; `queue` is reserved in the protocol.
- P5.4 currently routes chat response generation only. Memory extraction, STT, TTS, and proactive heartbeat run on the current node.
- P5.5 does not capture screenshots, perform OCR, recognize app content, or monitor behavior at high frequency. Activity signals only suppress proactive heartbeat.

## Attribution

qlmeng2023 — collaborator
