# 评测数据导出说明

本项目的评测数据来自后端 `evaluation_events` 表,覆盖聊天、主动心跳和 Live2D / TTS 侧体验埋点。

## 核心指标

- 对话次数: `evaluation.summary.chat.count`
- 平均延迟: `evaluation.summary.chat.avg_latency_ms`
- P95 延迟: `evaluation.summary.chat.p95_latency_ms`
- 记忆命中率: `evaluation.summary.chat.memory_hit_rate`
- 主动心跳触发率: `evaluation.summary.heartbeat.fired_rate`
- 首播延迟: `evaluation.summary.avatar.avg_first_play_ms`
- 口型活跃时长: `evaluation.summary.avatar.avg_mouth_active_ms`
- 打断到静默延迟: `evaluation.summary.avatar.avg_interrupt_to_silent_ms`

## 导出命令

在 PC 执行:

```powershell
cd "G:\Codex env\Kanojo"
.\scripts\export_evaluation_snapshot.ps1
```

默认输出到 `exports/`:

- `node-status.json`
- `evaluation-summary.json`
- `evaluation-events.json`
- `evaluation-events.csv`
- `memory-card.json`
- `memory-card.md`

如果要导出 Mac mini 的记忆源:

```powershell
.\scripts\export_evaluation_snapshot.ps1 -BaseUrl http://kanojo-mac.local:8787 -OutDir exports-mac
```

## 答辩取数建议

1. 演示前先运行 `scripts\dual_node_demo.ps1`,确认双机链路可用。
2. 用桌面端完成 3-5 轮典型交互,覆盖记忆命中、记忆写回、TTS 播放、打断和主动心跳。
3. 运行 `scripts\export_evaluation_snapshot.ps1` 导出 PC 侧评测数据。
4. 运行 `scripts\export_evaluation_snapshot.ps1 -BaseUrl http://kanojo-mac.local:8787 -OutDir exports-mac` 导出 Mac 侧记忆名片。
5. 在论文/答辩材料中引用 `evaluation-summary.json` 的聚合指标和 `memory-card.md` 的记忆名片示例。
