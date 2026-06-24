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

### Goal 循环 1/5: 清理测试记忆与推理预热

- 新增长期记忆软删除能力:
  - `DELETE /memories/{memory_id}` 将本地记忆标记为 `inactive`,不物理删除 SQLite 行。
  - `POST /maintenance/cleanup-test-memories` 默认 dry-run 匹配联调/冒烟/链路验证测试记忆,确认后可软删除。
- 新增 PC 推理预热能力:
  - `POST /node/inference/prewarm` 触发一次极短本地 LLM 调用。
  - `scripts/prewarm_inference.ps1` 支持手动预热。
  - `scripts/start_backend.ps1` 在 `KANOJO_NODE_ROLE=pc_inference` 时自动预热,避免 Mac 首次委托推理因模型冷启动回退。
- 新增 `scripts/cleanup_test_memories.ps1`,可从 PC 调用 Mac 的维护接口先 dry-run 再 apply。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 42 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed

### Goal 循环 2/5: 演示闭环与真实双机联调固化

- 新增 `scripts/dual_node_demo.py` 与 `scripts/dual_node_demo.ps1`,把双机演示冒烟固化为一键脚本。
- 冒烟覆盖:
  - PC / Mac `/health`
  - PC / Mac `/node/status`
  - PC `/node/inference/prewarm`
  - PC `/node/peer/memory-card`
  - Mac `/chat` 是否委托 PC peer 推理
- 新增 `docs/DEMO_RUNBOOK.md`,整理启动顺序、冒烟命令、写回演示、测试记忆清理和故障判断。
- README 增加双机演示基线和一键冒烟入口。
- 真实冒烟结果:
  - `.\scripts\dual_node_demo.ps1`: passed=`true`
  - Mac `/chat`: route_selected=`peer`, llm_model=`qwen2.5:14b`, llm_configured=`true`
  - PC 预热后 Mac chat 客户端观测耗时约 961ms

### Goal 循环 3/5: 评测数据与桌面端体验打磨

- 桌面端调试面板新增“预热推理”操作,可直接调用本机 `/node/inference/prewarm`,并显示模型与耗时。
- preload 与 browser fallback API 均接入 `prewarmInference`。
- 新增 `scripts/export_evaluation_snapshot.ps1`,一键导出:
  - `node-status.json`
  - `evaluation-summary.json`
  - `evaluation-events.json`
  - `evaluation-events.csv`
  - `memory-card.json`
  - `memory-card.md`
- 新增 `docs/EVALUATION_PLAN.md`,说明评测指标、导出命令和答辩取数建议。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 42 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed
  - `.\scripts\export_evaluation_snapshot.ps1 -OutDir exports-cycle3`: passed

### Goal 循环 4/5: 展示包装与打包启动

- 新增 `scripts/start_demo_stack.ps1`,面向答辩演示启动:
  - 可选启动 STT / TTS
  - PC 后端监听 `0.0.0.0:8787`
  - 自动预热 PC 推理
  - 检查防火墙规则
  - 执行双机冒烟
  - 启动桌面端
- 新增 `scripts/build_release.ps1`,执行后端测试、ruff、桌面构建,并通过 `git archive` 生成源码交付包。
- 新增 `docs/SHOWCASE_PACKAGE.md`,说明展示定位、Live2D 当前形象资产、演示顺序、启动命令和打包方式。
- README 增加演示启动和 release 打包入口。
- 自检:
  - `.\scripts\start_demo_stack.ps1 -Restart -SkipDesktop`: passed,双机冒烟 passed=`true`
  - `.\scripts\build_release.ps1`: passed,生成 `release/kanojo-source-<commit>.zip` 与 `desktop/out/`

### Goal 循环 5/5: 论文答辩材料与最终自检

- 新增 `docs/DEFENSE_MATERIALS.md`,把项目题目、核心创新点、系统架构、演示顺序、论文取数来源和答辩风险应答整理成可直接给答辩准备使用的材料。
- 新增 `docs/FINAL_SELF_CHECK.md`,汇总当前双机稳定基线、五轮循环完成项、最终自检命令、未完成事项和后续优化优先级。
- 更新 `docs/P5_CLOSEOUT.md`,补充双机实测、预热能力和收口文档入口。
- 当前仍需 Mac mini 拉取最新代码后执行测试记忆清理接口;PC 侧接口、脚本和说明已经就绪。PC 侧复测 Mac 维护接口仍返回 404。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 42 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed
  - `.\scripts\dual_node_demo.ps1`: passed=`true`,Mac `/chat` 委托 PC peer 推理,client_elapsed_ms 约 1035ms
  - `.\scripts\build_release.ps1`: passed,生成 `release/kanojo-source-<commit>.zip` 与 `desktop/out/`

### Goal 阻塞解除: Mac 测试记忆清理完成

- Mac mini 已拉取 `main@5ecad2d`,重新安装 editable 包并重启 `com.kanojo.backend`。
- Mac 侧 `/maintenance/cleanup-test-memories` 已可见并实际执行,测试记忆已软删除,`/memory-card` 当前 `memory_count=0`。
- PC 侧复跑:
  - `.\scripts\cleanup_test_memories.ps1`: `matched_count=0`, `remaining_matches=0`
  - `.\scripts\cleanup_test_memories.ps1 -Apply`: `deactivated_count=0`
  - `.\scripts\dual_node_demo.ps1`: passed=`true`,PC peer memory_count=`0`,Mac `/chat` 继续委托 PC peer 推理,client_elapsed_ms 约 974ms
- 当前五轮 goal 的阻塞点已解除。

### Goal 继续优化循环: 常驻、自启、评测报告和桌面拓扑提示

- 新增 Mac 常驻服务脚本:
  - `scripts/install_macos_launchd.sh`
  - `scripts/uninstall_macos_launchd.sh`
  - `docs/MAC_MINI_CODEX_SETUP.md` 增补 launchd 安装、状态查看、日志和卸载说明
- 新增 PC 登录自启脚本:
  - `scripts/install_windows_backend_startup.ps1`
  - `scripts/uninstall_windows_backend_startup.ps1`
  - 使用当前用户 Startup 文件夹,避免 Scheduled Task 在受限用户环境下被拒绝
- `scripts/start_desktop.ps1` 新增 `-EnsureBackend`,只启动桌面端时也可先确认后端已拉起。
- 新增 `scripts/write_evaluation_report.ps1`,并让 `scripts/export_evaluation_snapshot.ps1` 默认生成 `evaluation-report.md`。
- 桌面侧栏新增节点告警条,并每 30 秒刷新节点拓扑状态,便于演示时直接看出 peer 不可用、写回未就绪或 Mac 委托 PC 状态。
- 新增 `scripts/prewarm_peer_inference.sh`,Mac 侧可直接预热 PC peer,降低首次聊天因模型冷启动回退的概率。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 42 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed
  - PowerShell / shell 脚本语法检查: passed
  - `.\scripts\export_evaluation_snapshot.ps1 -OutDir exports-loop2`: passed,生成 `evaluation-report.md`
  - `.\scripts\dual_node_demo.ps1`: passed=`true`,Mac `/chat` 委托 PC peer 推理,client_elapsed_ms 约 1124ms

### Goal 继续优化循环: 记忆软停用 UI

- 桌面端记忆名片每条记忆新增软停用按钮,调用 `DELETE /memories/{id}`。
- 停用前进行用户确认,停用后刷新记忆名片和反思摘要,并在名片状态行显示结果。
- preload 与 browser fallback API 均接入 `deactivateMemory`。
- 自检:
  - bundled `pnpm build`: passed
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 42 passed

### Goal 继续优化循环: 评测导出对比

- 新增 `scripts/compare_evaluation_exports.ps1`,可对比两次导出的 `evaluation-summary.json` 和 `node-status.json`。
- 默认在后一次导出目录生成 `evaluation-comparison.md`,展示节点上下文和关键指标 delta。
- `docs/EVALUATION_PLAN.md` 增加多次导出对比流程。
- 自检:
  - PowerShell 语法检查: passed
  - `.\scripts\compare_evaluation_exports.ps1 -BeforeDir exports-report-test -AfterDir exports-loop2`: passed

### Goal 继续优化循环: 桌面 portable 打包

- 尝试接入 `electron-builder`,但当前 pnpm 供应链校验输出会污染 builder 读取依赖树的 JSON 输出,因此未提交该依赖链。
- 新增 `scripts/build_desktop_portable.ps1`,直接用 Electron runtime、`desktop/out/` 和最小 `package.json` 生成可运行 portable 目录与 zip。
- `scripts/build_release.ps1` 现在除源码包外,也会生成 `kanojo-desktop-portable-<commit>.zip`。
- `docs/SHOWCASE_PACKAGE.md` 增加 portable 包说明和运行前后端要求。
- 自检:
  - `.\scripts\build_desktop_portable.ps1 -SkipBuild`: passed,生成 portable zip
  - `.\scripts\build_release.ps1`: passed,生成 source zip、portable zip 与 `desktop/out/`

### Goal 继续优化循环: peer 断线操作建议

- 桌面端节点拓扑面板在 peer 不可用、写回未就绪、Mac 委托 PC、PC 推理节点等状态下显示下一步检查建议。
- 该提示用于演示现场快速定位 PC 防火墙、Mac launchd、peer URL、写回策略和冷启动预热问题。
- 自检:
  - bundled `pnpm build`: passed
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 42 passed

### Goal 继续优化循环: 记忆编辑与降权

- 后端新增 `PATCH /memories/{memory_id}`,支持更新长期记忆内容、重要性和置信度。
- 存储层新增 `update_memory`,保留软删除语义,只更新时间戳和指定字段。
- 桌面端记忆名片每条记忆新增编辑、降权和停用三类操作。
- preload 与 browser fallback API 均接入 `updateMemory`。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 43 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed

### Goal 继续优化循环: peer 超时可观测与 Mac 默认值

- `/node/status` 的 `node` 摘要新增 `peer_timeout_seconds`,方便桌面端和联调脚本直接确认当前 peer 超时配置。
- 桌面端节点拓扑面板新增 Peer 超时展示。
- `docs/MAC_MINI_CODEX_SETUP.md` 将 Mac 示例 `.env` 的 `KANOJO_PEER_TIMEOUT` 从 5 秒调整到 12 秒,并明确仍建议优先预热 PC peer。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 43 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed

### Goal 继续优化循环: 记忆人工确认队列

- 存储层新增 `memory_audit_by_id` 与 `update_memory_audit_decision`。
- 后端新增 `POST /memory-audits/{audit_id}/approve`,可把审计候选记忆人工批准写入长期记忆。
- 桌面端记忆审计页新增最近审计列表,待确认候选可直接点击“批准写入”。
- preload 与 browser fallback API 均接入 `memoryAudits` 与 `approveMemoryAudit`。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 44 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed

### Goal 继续优化循环: peer 候选地址扫描

- 新增 `scripts/find_peer.ps1` 与 `scripts/find_peer.sh`,用于在现场 IP 变化时扫描 Mac/PC 候选节点。
- 扫描结果包含 `preferred_role`、`best` 和完整 `results`,并按候选顺序稳定选择最佳地址。
- 支持按目标角色选择:
  - PC 侧找 Mac 记忆节点: `.\scripts\find_peer.ps1 -PreferredRole mac_home`
  - Mac 侧找 PC 推理节点: `bash scripts/find_peer.sh --role pc_inference`
- `docs/DEMO_RUNBOOK.md` 与 `docs/MAC_MINI_CODEX_SETUP.md` 增加对应排障命令。
- 自检:
  - PowerShell 语法检查: passed
  - bash 语法检查: passed
  - `.\scripts\find_peer.ps1 -PreferredRole mac_home`: best=`http://kanojo-mac.local:8787`,role=`mac_home`
  - `.\scripts\find_peer.ps1 -PreferredRole pc_inference`: best=`http://kanojo-pc.local:8787`,role=`pc_inference`
  - `bash scripts/find_peer.sh --role mac_home`: best=`http://kanojo-mac.local:8787`,role=`mac_home`
  - `bash scripts/find_peer.sh --role pc_inference`: best=`http://kanojo-pc.local:8787`,role=`pc_inference`

### Goal 继续优化循环: 桌面 peer 一键诊断

- 节点拓扑面板新增“一键诊断”按钮,根据当前节点角色自动优先查找 `mac_home` 或 `pc_inference`。
- 桌面端会把当前配置的 peer URL 与默认候选地址去重后并发探测 `/health` 和 `/node/status`。
- 诊断结果展示最佳 peer、目标角色和每个候选地址的角色/节点名/错误信息。
- preload 与 browser fallback API 均接入 `peerScan`,确保 Electron 与浏览器预览行为一致。
- 自检:
  - bundled `pnpm build`: passed

### Goal 继续优化循环: 记忆审计批量治理

- 后端新增 `POST /memory-audits/{audit_id}/reject`,支持人工拒绝待确认候选记忆。
- `POST /memory-audits/{audit_id}/approve` 支持传入编辑后的 `candidate`,批准前可修正内容、重要性和置信度。
- 新增 `POST /memory-audits/batch`,支持批量批准或批量拒绝。
- 桌面端记忆审计页新增候选内容编辑框、单条拒绝、勾选、多选批量批准和批量拒绝;批量批准会逐条保留已编辑内容。
- `docs/API_CONTRACT.md` 增加记忆审计人工治理接口说明。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 47 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed

### Goal 继续优化循环: 推荐 peer 受控写入

- Electron 主进程新增 `kanojo:apply-peer-config`,仅在用户确认后写入本机 `backend/.env` 的 `KANOJO_PEER_BASE_URL`。
- 写入前自动创建 `.env.bak-<timestamp>` 备份;找不到 `backend/.env` 时返回明确原因,不会静默创建。
- 节点拓扑面板新增“写入配置”按钮,使用一键诊断得到的最佳 peer 地址。
- `docs/DEMO_RUNBOOK.md` 与 `docs/FINAL_SELF_CHECK.md` 更新桌面诊断和受控写入说明。
- 自检:
  - bundled `pnpm build`: passed

### Goal 继续优化循环: 记忆审计历史筛选与分页

- `GET /memory-audits` 新增 `limit`、`offset`、`decision` 和 `q` 查询参数。
- 审计记录返回 `decision=accepted|pending|rejected`,避免手动拒绝后仍被桌面端当作待确认项。
- 桌面端记忆审计页新增状态筛选、关键词搜索和“加载更多”。
- `docs/API_CONTRACT.md` 与 `docs/FINAL_SELF_CHECK.md` 更新审计历史查询说明。
- 自检:
  - `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 48 passed
  - `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
  - bundled `pnpm build`: passed

### Goal 继续优化循环: peer 配置写入后复查脚本

- 新增 `scripts/apply_peer_config.ps1`,一条命令写入 `KANOJO_PEER_BASE_URL`、备份 `.env`、重启后端并复查 `/node/status`。
- 该脚本与桌面端“写入配置”互补,用于命令行排障和双机现场复查。
- `docs/DEMO_RUNBOOK.md` 与 `docs/FINAL_SELF_CHECK.md` 增加脚本说明。
- 自检:
  - PowerShell 语法检查: passed
