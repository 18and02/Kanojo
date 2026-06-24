# 项目推进日志

## 2026-06-24

### P4.3 名片版本 / 快照

- 新增 `memory_card_snapshots` 持久表,支持保存当前记忆名片完整 JSON 与 Markdown。
- 新增名片快照创建、列表、详情和对比接口。
- 桌面端“记忆”页拆为 `名片 / 命中 / 审计 / 版本` 四个内部视图。
- UI 修正:记忆页内部导航由四列改为 2x2 网格,避免侧栏宽度不足时出现“名.. / 命.. / 审..”截断。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 17 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - `pnpm build`: passed
  - 接口冒烟:快照创建、列表、对比可用。

### P4.4 反思摘要

- 修复记忆页窄侧栏 UI:内部导航改为可读的紧凑 2 列布局,新增页签后不再把“名片/命中/审计/版本”截断成省略号。
- 版本卡片继续收紧窄宽布局,时间、标签、摘要和“对比”按钮保持分层展示。
- 新增 `GET /memory-card/reflection`,从当前记忆名片确定性生成反思摘要。
- 反思摘要包含样本就绪度、分组主题、证据、后续关注点、待验证问题和 Markdown。
- 桌面端“记忆”页新增 `反思` 视图,与名片、命中、审计、版本并列。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 19 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - `pnpm build`: passed

下一步:进入 P5 规划,先补 Mac 常驻记忆源 + PC 重推理节点的实施计划,再决定第一条可交付链路。

### P5.1 节点身份与拓扑健康

- 新增 `docs/P5_IMPLEMENTATION_PLAN.md`,明确 P5 先做双机常驻的节点可观测性,再做只读远端访问和写入迁移。
- 后端新增节点配置:`KANOJO_NODE_NAME`, `KANOJO_NODE_ROLE`, `KANOJO_PEER_BASE_URL`, `KANOJO_PEER_TIMEOUT`。
- 后端新增 `GET /node/status`,返回当前节点身份、数据库路径、LLM/TTS/STT 配置摘要和对端健康状态。
- 节点角色支持 `standalone / mac_home / pc_inference`,非法值自动降级为 `standalone`。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 21 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed

### P5.2 只读远端记忆源

- 后端新增 `GET /node/peer/memory-card`,代理读取 peer 的记忆名片。
- 后端新增 `GET /node/peer/memory-card/reflection`,代理读取 peer 的反思摘要。
- 代理响应固定包含 `configured / available / base_url / url / payload`,peer 不可用时返回可解释错误。
- 当前阶段严格只读,不写 peer,不做数据库同步和冲突合并。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 23 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed

### P5.3a 写入迁移策略

- 新增 `KANOJO_MEMORY_PRIMARY` 与 `KANOJO_OFFLINE_WRITE_BEHAVIOR` 配置。
- 新增 `GET /node/memory-write-policy`,暴露当前记忆写入目标、离线策略、peer 配置完整性和迁移就绪度。
- `/node/status` 现在包含 `memory_write_policy`,方便节点巡检一次拿到拓扑和写入策略。
- 默认仍为 `local + local_only`,不改变当前聊天、记忆抽取或手动写入路径。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 25 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed

### P5.3b 记忆写入路由

- 新增 `/node/memory-writes`,作为 peer 写入的强制本地落库入口,接收节点不会再次转发,避免递归和双写。
- `/memories` 和聊天抽取出的长期记忆现在共用写入策略:`local` 写本地,`peer + reject + KANOJO_PEER_BASE_URL` 写 peer。
- peer 未配置、策略未就绪或 peer 写入失败时拒绝本轮记忆写入;聊天抽取会把拒绝原因写入记忆审计,不会静默回退本地。
- 桌面端开屏阶段文案更新到 P5.3,顶部状态条显示节点角色和当前写入目标。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 30 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed

### P5.4a 推理路由

- 新增 `KANOJO_INFERENCE_PRIMARY=auto|local|peer` 配置。
- 新增 `GET /node/inference-route-policy`,暴露当前推理路由策略、节点角色和 peer 推理配置。
- 新增 `POST /node/inference/chat`,作为 peer 推理落点,接收节点只使用本地 LLM/mock 生成回复,不会再次转发。
- `/chat` 与 `/chat/stream` 会按路由选择本地 LLM 或 peer 推理;peer 失败时回退本地。
- 评测事件 `chat.payload.inference_route` 记录路由选择、原因、模型、peer 延迟和失败回退原因。
- 桌面端调试面板显示推理路由策略,开屏阶段文案更新到 P5.4。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 35 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed

### P5.5 活动感知

- 新增 `activity_events` 表,保存低频活动类型、来源、强度、备注和时间。
- 新增 `POST /activity/events`,以及 `GET /activity/status` / `GET /activity/events` 调试接口。
- 新增 `KANOJO_ACTIVITY_GRACE_MINUTES`,默认 10 分钟。
- `/heartbeat/tick` 会把最近 active 类活动作为主动心跳抑制条件;命中时返回 `recent desktop activity`,不直接触发通知。
- 桌面端低频上报窗口显隐、focus/blur 和输入活动;输入活动默认最多 1 分钟上报一次。
- 桌面端主动心跳和调试日志面板展示最近活动信号,开屏阶段文案更新到 P5.5。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 37 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed

### P5 技术方案收口

- 新增 `docs/P5_CLOSEOUT.md`,汇总 P5.1-P5.5 完成范围、默认行为、非目标和最终自检。
- README 当前状态更新为 `P5 双机常驻闭环已完成`。
- 当前项目技术方案内的后续阶段已推进完毕;剩余项均为明确非目标或论文/答辩材料整理。

### Mac mini 环境交付准备

- 新增 `docs/MAC_MINI_CODEX_SETUP.md`,给 Mac mini 侧 Codex 使用,覆盖常驻记忆源节点的依赖、`.env`、启动命令和双机联调检查。
- 本地初始化 git 仓库并创建初始提交,用于后续推送到 GitHub 后让 Mac mini 直接 `git clone`。
- 仓库忽略规则确认不会提交 `backend/.env`、SQLite 数据库、虚拟环境、前端依赖和构建产物。
- GitHub 私有仓库已创建为 `https://github.com/18and02/Kanojo`,并把 Mac mini 指导文档更新为含实际仓库地址、Mac IP、主机名和 PC 验证 URL 的最新版。

### PC 推理节点联调

- PC 本地 `backend/.env` 已配置为 `KANOJO_NODE_ROLE=pc_inference`。
- PC 本地推理使用 `KANOJO_LLM_BASE_URL=http://127.0.0.1:11434/v1` 与 `KANOJO_LLM_MODEL=qwen2.5:14b`。
- PC 记忆写入策略已改为 `KANOJO_MEMORY_PRIMARY=peer` 与 `KANOJO_OFFLINE_WRITE_BEHAVIOR=reject`,peer 指向 `http://kanojo-mac.local:8787`。
- 自检:
  - `git pull --ff-only`: already up to date
  - `pip install -e ".[dev]"`: passed
  - PC `/node/status`: role=`pc_inference`, memory primary=`peer`, peer available=`true`
  - PC `/node/peer/memory-card`: configured=`true`, available=`true`, Mac memory_count 可返回
  - PC `/memories` 测试写入: target=`peer`, remote target=`local`,Mac memory_count 从 0 增至 1
  - PC 本地 LLM `/v1/models`: `qwen2.5:14b` 可用

### 真实双机联调

- `scripts/start_backend.ps1` 新增 `-BindAddress`,用于把 PC 后端从仅本机监听切换为局域网监听。
- PC 后端已用 `.\scripts\start_backend.ps1 -BindAddress 0.0.0.0 -Restart` 启动,当前监听 `0.0.0.0:8787`。
- PC 优先局域网地址为 `kanojo-pc.local`,备用可达地址为 `kanojo-pc-alt.local`。
- PC -> Mac 链路已实测:
  - Mac `/node/status`: role=`mac_home`, memory primary=`local`
  - PC `/node/status`: role=`pc_inference`, memory primary=`peer`, peer available=`true`
  - PC `/node/peer/memory-card`: configured=`true`, available=`true`, memory_count 可返回
  - PC `/chat`: inference_route.selected=`local`, llm_model=`qwen2.5:14b`
  - PC `/chat` 的联调文本不再写入长期记忆,Mac memory_count 保持不变
- 修复 LLM 记忆抽取误写风险:
  - 联调/冒烟/自检/链路验证类文本直接过滤,不进入长期记忆
  - LLM 抽取候选必须被原文直接支持,否则丢弃并在 hybrid 下回退启发式抽取
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 39 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
- 待 Mac -> PC 反向委托推理:
  - Mac `.env` 需要设置 `KANOJO_PEER_BASE_URL=http://kanojo-pc.local:8787` 并重启
  - Windows 防火墙当前为 `BlockInbound`;普通权限创建 `Kanojo Backend 8787` 入站规则失败,需要管理员权限放行 TCP 8787
- PC 防火墙规则已由管理员 PowerShell 成功添加:
  - `Kanojo Backend 8787`
  - Direction=`Inbound`, Action=`Allow`, Protocol=`TCP`, LocalPort=`8787`, Profile=`Private`
- PC 局域网推理落点已复核:
  - `http://kanojo-pc.local:8787/health`: ok
  - `http://kanojo-pc.local:8787/node/status`: role=`pc_inference`, peer available=`true`
  - `http://kanojo-pc.local:8787/node/inference/chat`: route.selected=`local`, llm_model=`qwen2.5:14b`
- Mac -> PC 反向委托推理已由 Mac mini 侧复核成功:
  - Mac 能访问 `http://kanojo-pc.local:8787/health`
  - Mac `.env`: `KANOJO_INFERENCE_PRIMARY=auto`, `KANOJO_PEER_BASE_URL=http://kanojo-pc.local:8787`
  - Mac `/node/status`: peer.available=`true`
  - Mac `/chat`: inference_route.selected=`peer`, llm_model=`qwen2.5:14b`, llm_configured=`true`
  - 首次 `/chat` 曾因 PC 模型冷启动 5 秒超时回退;预热 PC `/node/inference/chat` 后稳定走 peer
- 当前双机闭环基线:
  - Mac mini 常驻 SQLite 记忆真相源
  - PC 作为本地重推理节点
  - PC 长期记忆写回 Mac
  - Mac chat 自动委托 PC 推理
