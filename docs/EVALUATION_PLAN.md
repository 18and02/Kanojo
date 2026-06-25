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
- `evaluation-report.md`

`evaluation-report.md` 是自动生成的 Markdown 摘要,可直接作为论文/答辩取数材料的索引页。

报告中包含 `Coverage Scorecard`,自动检查:

- 双机 peer 健康状态。
- 聊天是否出现 peer 推理路由。
- 记忆名片是否已有长期记忆。
- 聊天记忆命中率是否非零。
- 主动心跳、形象首播、口型同步和打断事件是否有记录。

Scorecard 的 `TODO` 不是脚本失败,而是提示当前导出样本还缺少对应演示证据。答辩前应把缺项补齐后重新导出。

如果只需要原始 JSON / CSV,可以跳过报告:

```powershell
.\scripts\export_evaluation_snapshot.ps1 -SkipReport
```

## 多次导出对比

如果需要比较两次演示或两种配置的指标变化,先分别导出到不同目录,再生成对比报告:

```powershell
.\scripts\export_evaluation_snapshot.ps1 -OutDir exports-before
.\scripts\export_evaluation_snapshot.ps1 -OutDir exports-after
.\scripts\compare_evaluation_exports.ps1 -BeforeDir exports-before -AfterDir exports-after
```

默认会在 `AfterDir` 写入:

```text
evaluation-comparison.md
```

`-OutFile` 可显式指定仓库内输出路径;脚本会拒绝仓库外绝对路径、`..\` 逃逸路径和不存在的父目录。未传 `-OutFile` 时默认写入 `AfterDir\evaluation-comparison.md`,因此 `AfterDir` 也需要位于仓库内。

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
