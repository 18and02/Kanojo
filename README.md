# AI Memory Card Desktop Agent

本仓库是毕业设计《面向长期陪伴的记忆驱动主动交互式桌面智能体设计、实现与评测》的项目工作区。

当前技术方案状态为 **P5 双机常驻闭环已完成**: Windows 单机、文字/语音输入、LLM 回复、持久记忆、主动心跳、TTS 输出、barge-in、Live2D 形象、形象侧评测埋点、可回看的记忆名片视图、Markdown / JSON 导出、版本快照和反思摘要已接入。Mac 常驻记忆源 + PC 重推理节点已具备节点身份、peer 健康检查、只读远端记忆 artifact、策略化记忆写入路由、聊天推理路由和低频活动感知。P5 收口见 `docs\P5_CLOSEOUT.md`。

当前双机演示基线见 `docs\DEMO_RUNBOOK.md`:Mac mini 常驻 SQLite 记忆源,PC 作为本地 `qwen2.5:14b` 推理节点,PC 长期记忆写回 Mac,Mac `/chat` 自动委托 PC 推理。

## 主贡献

记忆驱动的主动交互机制:

- 分层持久记忆:原始对话、事件记忆、事实偏好、关系状态;
- 检索打分:相关度、新近度、重要性;
- 主动引擎:冷却时间、免打扰时段、触发理由、打扰抑制;
- 可评测闭环:记忆召回率、假记忆率、主动恰当率、打扰率。

## 项目结构

```text
backend/          Python 编排服务,负责聊天、记忆、心跳和 TTS/LLM 适配
desktop/          Electron 桌面端骨架
docs/             项目启动文档、架构、API 和 P1 计划
*.md              PRD、开题、录音规范等毕业设计文档
```

## P1 技术路线

```text
Electron Desktop
  -> FastAPI backend
    -> LLM adapter(OpenAI-compatible / local fallback)
    -> SQLite memory store
    -> Memory scoring
    -> Heartbeat scheduler
    -> TTS adapter
```

## 本地启动草案

推荐直接用仓库脚本启动,脚本会优先使用本机 `pnpm`,找不到时自动使用 Codex bundled runtime:

```powershell
cd "G:\Codex env\Kanojo"
.\scripts\dev.ps1
```

也可以分开启动:

```powershell
.\scripts\start_backend.ps1
.\scripts\start_desktop.ps1
```

改了 `backend\.env` 后重启后端:

```powershell
.\scripts\start_backend.ps1 -Restart
```

双机演示冒烟:

```powershell
.\scripts\dual_node_demo.ps1
```

如果桌面端还显示旧状态,清理旧 Electron / Vite 进程后重启:

```powershell
.\scripts\start_desktop.ps1 -Restart
```

## P1 收口与演示

P1 验收、演示脚本和评测导出见 `docs\P1_CLOSEOUT.md`。

常用命令:

```powershell
# 重置并写入可复现 demo 数据
.\scripts\p1_demo.ps1 reset-seed

# 查看当前 demo 数据和评测摘要
.\scripts\p1_demo.ps1 status

# 导出评测事件到 exports/
.\scripts\p1_demo.ps1 export-csv
```

## LLM 配置

P1 后端支持 OpenAI-compatible Chat Completions 接口。未配置时使用 mock LLM,用于离线演示和前端联调。

常见本地模型服务:

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

记忆抽取模式:

```powershell
# hybrid:有 LLM 则用 LLM 抽 JSON,失败自动回退启发式
$env:KANOJO_MEMORY_EXTRACTION="hybrid"

# heuristic:完全离线,只用规则抽取
$env:KANOJO_MEMORY_EXTRACTION="heuristic"
```

## STT 配置

P2.2 后端支持 OpenAI-compatible audio transcription 服务。未配置时桌面端仍可录音,但会提示 `STT service is not configured.`,文字输入不受影响。

```powershell
$env:KANOJO_STT_BASE_URL="http://127.0.0.1:9000/v1"
$env:KANOJO_STT_MODEL="whisper-1"
```

本地 `faster-whisper` 服务可用脚本启动。仓库里的 `backend\.env` 已配置为 `127.0.0.1:9000`,所以 `dev.ps1` 会自动先拉起 STT;不需要语音时加 `-SkipStt`。

```powershell
.\scripts\dev.ps1 -Restart

# 只启动或重启 STT,并在启动时预加载模型
.\scripts\start_stt.ps1 -Restart -Warmup

# 用 backend\data\stt-test-zh.wav 验证: 本地 STT -> 后端代理 -> 转写文本
.\scripts\test_stt.ps1
```

后端:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,stt]"
uvicorn kanojo_agent.main:app --reload
```

桌面端:

```powershell
cd desktop
pnpm install
pnpm dev
```

## P2.3 TTS 打断

桌面端使用系统 `speechSynthesis` 作为当前语音输出层。开启语音输出后,流式回复会按完整句子入队播放;用户输入、开始录音、提交新消息或点击停止都会立即取消当前播放并清空待播放队列。外部 GPT-SoVITS / CosyVoice 接入时复用同一打断控制位。

## P2.4 外部 TTS

配置 `KANOJO_TTS_BASE_URL` 后,后端会通过 `/tts/synthesize` 代理外部 TTS。桌面端优先播放外部 TTS 音频;合成失败或未配置时回退系统语音。

仓库内置一个 Windows SAPI 本地 TTS 服务,用于先跑通真实 wav 音频链路:

```powershell
$env:KANOJO_TTS_BASE_URL="http://127.0.0.1:9880"

.\scripts\start_tts.ps1 -Restart
.\scripts\start_backend.ps1 -Restart
.\scripts\test_tts.ps1
```

## P3.4 形象评测

桌面端已把 CSS 形象替换为真实 Live2D 渲染层。当前默认使用官方 Haru Greeter 示例模型;录音、生成、TTS 合成/播放和打断会驱动模型姿态,语音实际播放时会把 P3.2 的口型信号写入 `ParamMouthOpenY`。Live2D 初始化失败时会回退到 CSS 形象。

形象层会把语音首播、口型活动和打断闭嘴耗时写入 `POST /evaluation/events`,调试面板展示首播延迟、平均口型活跃时长、平均活跃率和打断到静音/闭嘴耗时。

## P4.4 记忆名片与反思摘要

后端 `GET /memory-card` 会把 active memories 确定性整理成当前记忆名片,按关系状态、偏好、事件和反思分组,同时返回 Markdown artifact。`GET /memory-card/export?format=markdown|json` 可把当前名片作为 Markdown 或 JSON 文件导出。

P4.3 新增 `memory_card_snapshots` 表和快照接口。`POST /memory-card/snapshots` 会把当前名片保存为版本快照,`GET /memory-card/snapshots/{id}/compare` 会把该快照与当前名片对比,按分组返回新增、移除和不变数量。

P4.4 新增 `GET /memory-card/reflection`,从当前记忆名片确定性生成反思摘要,包含样本就绪度、分组主题、证据、后续关注点和 Markdown。桌面端“记忆”页已拆成名片、反思、命中、审计、版本五个内部视图;名片视图支持复制/导出,版本视图支持保存当前快照、刷新快照列表和对比当前变化。

## P5.3 双机写入迁移

后端 `GET /node/status` 会返回当前节点身份、peer 健康和 `memory_write_policy`。默认仍是 `KANOJO_MEMORY_PRIMARY=local` 与 `KANOJO_OFFLINE_WRITE_BEHAVIOR=local_only`,单机聊天、抽取和手动记忆写入行为不变。

切到 `peer + reject` 并配置 `KANOJO_PEER_BASE_URL` 后,聊天抽取出的长期记忆和 `POST /memories` 会写入 peer 的 `/node/memory-writes`;接收节点只在本地 SQLite 落库,不会再次转发。peer 不可用、未配置或策略未就绪时,本轮记忆写入会被拒绝并进入记忆审计,不会静默回退到本地造成双写。

```powershell
$env:KANOJO_NODE_NAME="pc"
$env:KANOJO_NODE_ROLE="pc_inference"
$env:KANOJO_PEER_BASE_URL="http://mac-mini.local:8787"
$env:KANOJO_MEMORY_PRIMARY="peer"
$env:KANOJO_OFFLINE_WRITE_BEHAVIOR="reject"
```

## P5.4 推理路由

后端 `GET /node/inference-route-policy` 会返回当前推理路由策略。`KANOJO_INFERENCE_PRIMARY` 支持 `auto / local / peer`:默认 `auto` 下,`mac_home` 节点配置 peer 后会把聊天回复生成委托给 peer 的 `/node/inference/chat`;`standalone` 和 `pc_inference` 默认本地推理。

`/chat` 与 `/chat/stream` 都会在评测事件 payload 中记录 `inference_route`,包含选择结果、原因、模型、peer 延迟和失败回退原因。peer 推理失败时会回退本地 LLM/mock,不影响当前对话完成。

```powershell
$env:KANOJO_NODE_ROLE="mac_home"
$env:KANOJO_PEER_BASE_URL="http://pc.local:8787"
$env:KANOJO_INFERENCE_PRIMARY="auto"
```

## P5.5 活动感知

后端新增 `POST /activity/events`、`GET /activity/status` 和 `GET /activity/events`。桌面端会上报窗口显隐、focus/blur 和低频输入活动;这些信号只作为主动心跳的抑制条件,不会直接触发通知。

`KANOJO_ACTIVITY_GRACE_MINUTES` 默认为 10。若最近 active 类活动仍在该窗口内,`/heartbeat/tick` 返回 `recent desktop activity`,避免用户正在桌面前操作时被主动打扰。`force=true` 仍可用于手动测试通知链路。

```powershell
$env:KANOJO_ACTIVITY_GRACE_MINUTES="10"
```

## 当前约束

- P2.2 已接入本地 STT;未启动 STT 服务时文字输入不受影响。
- P5.3 默认仍保持单机本地写入;peer 写入只在 `peer + reject + KANOJO_PEER_BASE_URL` 时启用。
- SQLite 是唯一真相源;向量库后续只作为索引层。
- 公开答辩版避免强恋爱化表达,强调长期记忆、主动交互、隐私与健康边界。
- 主动心跳由桌面端定时调用后端判定;测试通知使用 `force`,后台调度不会绕过冷却和免打扰。
- P2.4 默认优先外部 TTS,不可用时回退桌面端系统语音;`KANOJO_TTS_BASE_URL` 后续可替换为 GPT-SoVITS / CosyVoice 服务。
- P3.4 使用默认官方示例模型跑通真实 Live2D 链路和形象评测埋点,不包含最终自定义角色资产和桌面透明悬浮窗。
- P4 先做确定性记忆名片、反思摘要、本地导出和版本快照,不做 LLM 润色、自动隐私脱敏和公开分享。
- P5.3 不实现离线写入队列、冲突合并或双写同步;`queue` 只是协议预留。
- P5.4 当前只路由聊天回复生成;记忆抽取、STT、TTS 和主动心跳仍在当前节点执行。
- P5.5 不做屏幕截图、OCR、应用内容识别或高频行为监控;活动信号只用于主动心跳抑制。
