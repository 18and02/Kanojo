# P5 实施计划

P5 目标是把当前 Windows 单机系统扩展为“Mac 常驻记忆源 + PC 重推理节点”的局域网双机架构。Mac mini 作为 24/7 常驻家,保存唯一真相源和轻量编排;PC/eGPU 在用户回桌时承担重 LLM、语音和高负载推理。

## 里程碑

| 编号 | 交付 | 验收 |
| --- | --- | --- |
| P5.1 | 节点身份与拓扑健康 | 后端能声明当前节点角色,并检查可选对端节点健康状态 |
| P5.2 | 只读远端记忆源 | PC 节点可从 Mac 节点读取记忆名片/反思摘要,但不写入远端 |
| P5.3 | 写入迁移协议 | 明确单写入点、冲突处理和离线回退;先暴露策略,再迁移真实写入 |
| P5.4 | 重推理路由 | Mac 轻脑与 PC 重脑按任务类型切换,记录路由理由和延迟 |
| P5.5 | 屏幕/活动感知 | 接入低频活动信号,进入主动引擎而非直接触发打扰 |

## P5.1 方案

P5.1 只建立节点层观测能力,不迁移数据:

- 新增节点角色配置:`standalone / mac_home / pc_inference`;
- 新增节点名称配置,用于 UI 和日志显示;
- 新增可选对端节点 URL,用于局域网健康检查;
- 新增 `GET /node/status`,返回当前节点身份、数据库路径、LLM/TTS/STT 配置摘要和对端健康;
- 对端不可用只返回 `available: false`,不影响单机聊天、记忆和桌面端运行。

## P5.2 方案

P5.2 只允许 PC 节点读取 Mac 节点的记忆 artifact:

- 新增 `GET /node/peer/memory-card`,代理读取 peer 的 `/memory-card`;
- 新增 `GET /node/peer/memory-card/reflection`,代理读取 peer 的 `/memory-card/reflection`;
- 响应外层固定包含 `configured / available / base_url / url / payload`;
- peer 未配置或不可用时只返回错误状态,不影响本地记忆读写;
- 该阶段不写 peer,不做同步,不做冲突合并。

## P5.3 方案

P5.3 分两步推进写入迁移:先暴露策略,再迁移真实写入路径。

- 新增 `KANOJO_MEMORY_PRIMARY=local|peer`;
- 新增 `KANOJO_OFFLINE_WRITE_BEHAVIOR=local_only|reject|queue`;
- 新增 `GET /node/memory-write-policy`,返回当前写入目标、离线策略、peer 是否配置完整和迁移就绪度;
- 默认保持 `local + local_only`,即当前 Windows 单机行为不变;
- `peer + reject` 且配置了 `KANOJO_PEER_BASE_URL` 后才视为迁移准备完成;
- `queue` 只是协议枚举,当前不实现队列,避免假装具备离线合并能力。
- P5.3b 起,聊天抽取出的长期记忆和手动 `POST /memories` 会经过同一份写入策略:
  - `local` 写入本机 SQLite;
  - `peer + reject + peer_base_url` 写入 peer 的 `/node/memory-writes`,由接收节点只在本地落库;
  - peer 不可用、未配置或策略未就绪时拒绝本轮记忆写入,写入拒绝原因进入记忆审计,不会静默回退本地。

## 设计约束

- SQLite 仍是唯一真相源;迁移到 Mac 前不允许双写。
- P5.1/P5.2 不做数据库同步,只做拓扑可观测性和只读远端访问。
- P5.3a 只暴露写入策略;P5.3b 已迁移聊天抽取和手动记忆写入路径,但仍不实现离线队列和冲突合并。
- 所有跨节点 HTTP 都必须可超时、可失败、可降级。
- PC 节点不能假设 Mac 一定在线;Mac 节点也不能假设 PC 可用。

## P5.4 方案

P5.4 先交付可观测、可回退的聊天推理路由:

- 新增 `KANOJO_INFERENCE_PRIMARY=auto|local|peer`;
- 新增 `GET /node/inference-route-policy`,暴露当前推理路由策略、节点角色和 peer 推理配置;
- 新增 `POST /node/inference/chat`,作为 peer 推理落点,接收节点只使用本地 LLM/mock 生成回复,不会再次转发;
- `/chat` 和 `/chat/stream` 在生成回复前选择推理路由:
  - `local` 固定本地推理;
  - `peer` 在配置 peer 时委托 peer,未配置时回退本地;
  - `auto` 下 `mac_home` + peer 会把聊天回复委托给 peer,`standalone / pc_inference` 保持本地;
- 每次聊天评测事件写入 `payload.inference_route`,记录选择结果、原因、模型、peer 延迟和失败回退原因。

P5.4 当前只路由聊天回复生成;记忆抽取、STT、TTS 和主动心跳仍在当前节点执行。`/chat/stream` 走 peer 时会先等待 peer 完整回复,再向桌面端按片段吐出,用于保持现有 UI 流式协议不变。

## P5.5 方案

P5.5 接入低频活动信号,只作为主动心跳的抑制条件,不直接触发打扰:

- 新增 `activity_events` 表,记录活动类型、来源、强度、备注和时间;
- 新增 `POST /activity/events`,供桌面端写入 `user_input / app_visible / app_hidden / active / idle` 等低频事件;
- 新增 `GET /activity/status` 和 `GET /activity/events`,用于调试最近活动状态;
- 新增 `KANOJO_ACTIVITY_GRACE_MINUTES`,默认 10 分钟;
- `/heartbeat/tick` 会读取最近 active 类活动时间,若仍在 grace 窗口内则返回 `recent desktop activity`,不触发主动通知;
- `force=true` 仍绕过活动抑制,用于手动链路测试;
- 桌面端对窗口显隐、focus/blur 和输入事件做低频上报;输入事件默认最多 1 分钟上报一次。

该阶段不做屏幕截图、OCR、应用内容识别或高频监控,避免扩大隐私面和误触发风险。
