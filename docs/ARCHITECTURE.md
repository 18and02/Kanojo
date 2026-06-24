# 架构说明

## P1 单机架构

```text
Desktop Renderer
  -> Electron Main / Preload
    -> FastAPI Backend
      -> Chat Orchestrator
        -> Memory Retriever
        -> LLM Adapter
        -> TTS Adapter
      -> SQLite Store
      -> Heartbeat Engine
```

## 设计原则

- SQLite 做唯一真相源,保存原始消息、记忆、主动事件和审计信息。
- 向量库只做可重建索引,不直接承担业务真相。
- LLM 和 TTS 均通过适配器接入,支持本地服务、OpenAI-compatible API 和 mock fallback。
- 主动引擎必须可解释:每次触发或不触发都记录理由。
- 公开答辩版通过配置限制亲密尺度和主动频率。

## 后续扩展

- P2:接入 STT、流式 LLM、分句 TTS、barge-in。
- P3:已接入形象舞台、口型同步信号、默认 Live2D 模型和形象评测埋点。
- P4:已接入记忆名片视图、Markdown / JSON 导出、版本快照和确定性反思摘要,把长期记忆整理为可回看、可留档、可对比、可复核的 artifact。
- P5:Mac 常驻记忆源 + PC 重推理节点,已接入节点身份、拓扑健康、只读远端访问、策略化记忆写入路由、聊天推理路由和低频活动感知。
