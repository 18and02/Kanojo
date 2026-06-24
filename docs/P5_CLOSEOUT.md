# P5 收口说明

## 完成范围

P5 已把 Windows 单机原型扩展为可配置的“Mac 常驻记忆源 + PC 重推理节点”双机底座:

- P5.1 节点身份与拓扑健康: `GET /node/status` 返回节点角色、peer 健康和配置摘要。
- P5.2 只读远端记忆源: PC 可通过 peer proxy 读取记忆名片和反思摘要。
- P5.3 写入迁移: 记忆写入支持 `local` 与 `peer + reject`,peer 写入落到 `/node/memory-writes`,不双写、不递归。
- P5.4 推理路由: 聊天回复可按 `auto / local / peer` 路由到本地或 peer 推理,并记录路由原因与延迟。
- P5.5 活动感知: 桌面端低频上报活动信号,主动心跳在最近活动窗口内抑制打扰。

## 当前默认行为

- 默认仍是单机本地模式,未配置 peer 时聊天、记忆、心跳、TTS/STT 均可独立运行。
- `KANOJO_MEMORY_PRIMARY=peer` 只有配合 `KANOJO_OFFLINE_WRITE_BEHAVIOR=reject` 和 `KANOJO_PEER_BASE_URL` 才会写 peer。
- `KANOJO_INFERENCE_PRIMARY=auto` 下,只有 `mac_home` 且配置 peer 时才把聊天回复委托给 peer。
- 活动感知只抑制主动心跳,不直接触发通知。

## 非目标

- 不做数据库双写同步、离线队列或冲突合并。
- 不做屏幕截图、OCR、应用内容识别或高频行为监控。
- 不把记忆抽取、STT、TTS 路由到 peer;当前只路由聊天回复生成。
- 不引入最终自定义 Live2D 角色资产和透明悬浮窗。

## 自检

- `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 37 passed
- `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
- bundled `pnpm build`: passed
