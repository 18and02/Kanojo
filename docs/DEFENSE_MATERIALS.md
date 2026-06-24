# 论文与答辩材料整理

## 项目题目

面向长期陪伴的记忆驱动主动交互式桌面智能体设计、实现与评测

## 核心创新点

1. 记忆名片机制  
   把长期记忆组织为关系、偏好、事件、反思四类,支持检索、导出、版本快照和反思摘要。

2. 主动交互机制  
   通过冷却时间、免打扰时段和桌面活动信号抑制不合适打扰,避免“主动”变成频繁弹窗。

3. 双机常驻架构  
   Mac mini 作为 24/7 常驻 SQLite 记忆真相源,PC 作为本地重推理节点,实现记忆与推理职责分离。

4. 可评测桌面体验  
   后端记录聊天、心跳、记忆命中、TTS/Live2D 侧体验事件,可导出 JSON / CSV 支持论文分析。

## 系统架构答辩说法

```text
Electron Desktop
  -> PC FastAPI Backend (pc_inference)
    -> Local LLM / STT / TTS
    -> Peer memory write
      -> Mac mini FastAPI Backend (mac_home)
        -> SQLite memory truth source

Mac mini Backend
  -> Auto inference route
    -> PC /node/inference/chat
```

## 演示顺序

1. 运行 `scripts\start_demo_stack.ps1 -Restart -SkipDesktop`,展示命令行双机冒烟 `passed=true`。
2. 打开桌面端,展示 Live2D 形象、控制面板和节点拓扑。
3. 在桌面端发起普通对话,展示 PC 本地模型回复。
4. 在 Mac 或 PC 调试页展示 `inference_route.selected=peer`。
5. 展示记忆页:
   - 名片
   - 反思
   - 命中
   - 审计
   - 版本快照
6. 导出评测数据:
   - `scripts\export_evaluation_snapshot.ps1`
   - `evaluation-summary.json`
   - `evaluation-events.csv`
   - `memory-card.md`

## 论文实验数据来源

- 聊天延迟: `evaluation-summary.json -> chat.avg_latency_ms / p95_latency_ms`
- 记忆命中率: `evaluation-summary.json -> chat.memory_hit_rate`
- 主动心跳触发率: `evaluation-summary.json -> heartbeat.fired_rate`
- Live2D/TTS 首播延迟: `evaluation-summary.json -> avatar.avg_first_play_ms`
- 口型同步活跃比例: `evaluation-summary.json -> avatar.avg_mouth_active_ratio`
- 记忆样例: `memory-card.md`
- 原始事件: `evaluation-events.csv`

## 答辩风险与应答

### 为什么要双机

Mac mini 常驻、低功耗、适合作为长期记忆源;PC 算力更强,适合本地模型推理。两者分离后,记忆不会跟着 PC 关机丢失,推理也不压在常驻节点上。

### 为什么不做数据库双写

毕业设计阶段优先保证单一真相源和可解释行为。当前使用 Mac SQLite 作为唯一长期记忆源,PC 写入失败时拒绝,不静默回退本地,避免冲突合并和双写不一致。

### 如何避免假记忆

记忆抽取有审计链路;联调/冒烟/自检类文本直接过滤;LLM 抽取候选必须被原文支持,否则丢弃或回退启发式抽取。

### 如何证明不是单纯聊天壳

演示时展示记忆名片、反思、版本快照、评测导出、主动心跳和双机拓扑,这些是普通聊天壳不具备的长期陪伴机制。
