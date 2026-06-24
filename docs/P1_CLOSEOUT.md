# P1 收口包

本文档用于 P1 MVP 的最终验收、演示兜底和评测数据导出。

## P1 状态

P1 目标已经覆盖:

- 文字对话闭环:桌面端输入,后端调用本地 LLM 或 mock 生成回复。
- 持久记忆闭环:消息落库、候选抽取、审核、记忆落库、检索命中展示。
- 主动心跳:后台定时、手动检查、强制测试通知、冷却、免打扰、触发理由。
- TTS 兜底:桌面端系统语音朗读、声音选择、语速、停止、重播。
- 评测埋点:记录聊天延迟、记忆命中、主动触发理由,调试页展示摘要。

## 验收命令

后端测试:

```powershell
cd "G:\Codex env\Kanojo"
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
.\backend\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
```

桌面端构建:

```powershell
cd "G:\Codex env\Kanojo\desktop"
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd" build
```

启动:

```powershell
cd "G:\Codex env\Kanojo"
.\scripts\start_backend.ps1 -Restart
.\scripts\start_desktop.ps1 -Restart
```

## Demo 兜底数据

重置并写入一组可复现演示数据:

```powershell
cd "G:\Codex env\Kanojo"
.\scripts\p1_demo.ps1 reset-seed
```

查看当前 demo 数据状态:

```powershell
.\scripts\p1_demo.ps1 status
```

注意: `reset-seed` 会清空当前 SQLite 中的消息、记忆、审计、心跳和评测事件,仅用于演示前准备。需要保留真实测试数据时不要执行。

## 演示流程

1. 启动后端和桌面端。
2. 可选:执行 `.\scripts\p1_demo.ps1 reset-seed`,让数据库进入稳定演示状态。
3. 在桌面端输入:

```text
我明天上午有数据库系统考试，今晚想早点睡。
```

预期:

- 对话区返回回复;
- “记忆”页出现命中记忆或本轮抽取审计;
- “调试”页的评测埋点中 `对话` 数增加,并记录延迟。

4. 在“控制”页点击“通知”。

预期:

- 触发桌面通知;
- 主动心跳状态为“已触发”;
- “调试”页最近事件出现 `heartbeat`,理由包含 `forced heartbeat`。

5. 打开 TTS 开关,点击“重播”。

预期:

- 使用系统语音朗读最近一条回复;
- 可停止、调语速、换声音;
- 首音延迟显示在控制页。

## 评测数据导出

接口导出:

```powershell
Invoke-RestMethod "http://127.0.0.1:8787/evaluation/export?format=json" |
  ConvertTo-Json -Depth 10
```

CSV:

```powershell
Invoke-WebRequest "http://127.0.0.1:8787/evaluation/export?format=csv" `
  -OutFile "G:\Codex env\Kanojo\exports\p1_evaluation_events.csv"
```

脚本导出:

```powershell
.\scripts\p1_demo.ps1 export-json
.\scripts\p1_demo.ps1 export-csv
```

默认输出到 `exports/` 目录。

## P1 验收口径

| 项目 | 验收口径 |
| --- | --- |
| 文字聊天 | `/chat` 返回回复、消息 ID、延迟和评测事件 ID |
| 记忆写入 | 有候选、审核记录、可接受记忆落库 |
| 记忆检索 | `/memories?query=` 返回带分数的命中记忆 |
| 记忆审计 | `/memory-audits` 可解释接受 / 拒绝原因 |
| 主动心跳 | `/heartbeat/tick` 返回触发状态、理由、评测事件 ID |
| 桌面通知 | 强制测试通知可送达;未授权时有调试理由 |
| TTS | 系统语音可朗读、停止、重播、调速 |
| 评测埋点 | `/evaluation/summary` 与 `/evaluation/export` 可用 |

## P1 后的下一步

完成本收口包后,可以进入 P2:

1. 先做 LLM 文本流式输出;
2. 再接 STT 语音输入;
3. 最后做 TTS 打断和连续对话。

不要在 P2 前跳到 Live2D、双机常驻或屏幕活动感知。
