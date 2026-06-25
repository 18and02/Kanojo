# Kanojo 演示讲稿

- 生成时间: {{GENERATED_AT}}
- Commit: `{{COMMIT}}`
- 素材目录: `{{PACKAGE_DIR}}`

## 演示前检查

1. PC 后端已启动并预热: `.\scripts\start_backend.ps1 -BindAddress 0.0.0.0 -Restart`
2. 双机冒烟通过: `.\scripts\dual_node_demo.ps1`
3. 展示素材已生成: `.\scripts\build_showcase_package.ps1 -OutDir {{PACKAGE_DIR}}`
4. GitHub draft release 资产存在: 源码包、portable 包和 SHA256 清单。

## 当前证据摘要

| 项目 | 当前值 |
| --- | --- |
| 节点角色 | {{NODE_ROLE}} |
| 节点名称 | {{NODE_NAME}} |
| Peer configured | {{PEER_CONFIGURED}} |
| Peer available | {{PEER_AVAILABLE}} |
| Peer URL | {{PEER_URL}} |
| 记忆写入目标 | {{MEMORY_PRIMARY}} |
| 推理路由策略 | {{INFERENCE_PRIMARY}} |
| 聊天事件数 | {{CHAT_COUNT}} |
| Peer 推理事件数 | {{PEER_ROUTE_COUNT}} |
| 记忆条数 | {{MEMORY_COUNT}} |
| 主动心跳事件数 | {{HEARTBEAT_COUNT}} |
| 形象首播事件数 | {{AVATAR_VOICE_START_COUNT}} |

## 三分钟演示节奏

| 时间 | 动作 | 重点 |
| --- | --- | --- |
| 0:00-0:20 | 打开控制面板 | 说明 Kanojo 不是单轮聊天壳，而是长期记忆驱动的桌面陪伴智能体。 |
| 0:20-0:55 | 打开节点拓扑 | 说明 Mac 常驻记忆源和 PC 推理节点的职责分离。 |
| 0:55-1:30 | 发起一次对话 | 展示本地模型回复、推理路由和延迟证据。 |
| 1:30-2:05 | 打开记忆名片 | 展示长期记忆、反思、审计和版本快照。 |
| 2:05-2:35 | 打开评测报告 | 展示延迟、命中、心跳和形象埋点都可以导出。 |
| 2:35-3:00 | 展示交付包 | 展示 portable 包、SHA256 清单和 GitHub draft release。 |

## 旁白稿

### 1. 开场定位

- 画面: 控制面板和 Live2D 形象
- 讲法: Kanojo 的核心不是单轮聊天，而是把长期记忆、主动心跳、语音/形象反馈和可评测事件串成一个桌面陪伴闭环。

### 2. 双机闭环

- 画面: 调试页的节点拓扑
- 讲法: Mac mini 负责常驻和 SQLite 记忆真相源，PC 负责本地大模型推理。PC 写入长期记忆时会写回 Mac，Mac 需要生成回复时会委托 PC。

### 3. 对话与推理路由

- 画面: 聊天输入框和调试日志
- 讲法: 每次聊天都会记录推理路由、模型、延迟和记忆命中。这里重点看 `inference_route` 是否能证明当前请求走到了预期节点。

### 4. 记忆治理

- 画面: 记忆名片和记忆审计页
- 讲法: 长期记忆不是黑盒累积，而是可以查看、编辑、降权、停用和人工审计。这样能降低假记忆和联调测试文本污染。

### 5. 评测与交付

- 画面: `evaluation-report.md` 与 `SHOWCASE_INDEX.md`
- 讲法: 项目的聊天、主动心跳、TTS 和 Live2D 体验都有事件数据，可以导出为论文评测材料；交付包也有 SHA256 清单用于复核。

## 截图索引

| 画面 | 文件 |
| --- | --- |
{{SCREENSHOT_ROWS}}

## 常见追问短答

- 为什么要双机: Mac mini 常驻、低功耗，适合作为长期记忆源；PC 算力更强，适合本地模型推理。
- 为什么不做数据库双写: 当前阶段优先保证单一真相源，写入 peer 失败时拒绝，不静默回退本地，避免冲突合并和双写不一致。
- 如何避免假记忆: 联调/冒烟/自检类文本会过滤，抽取候选进入审计，桌面端支持人工批准、拒绝、编辑、降权和停用。
- 如何证明不是聊天壳: 演示时展示记忆名片、反思、版本快照、评测导出、主动心跳和双机拓扑。
