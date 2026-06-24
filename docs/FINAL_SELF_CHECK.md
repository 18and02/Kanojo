# 最终自检与后续优化清单

## 当前稳定基线

- GitHub 私有仓库: `https://github.com/18and02/Kanojo`
- PC 后端: `http://kanojo-pc.local:8787`
- Mac 后端: `http://kanojo-mac.local:8787`
- Mac role: `mac_home`
- PC role: `pc_inference`
- PC LLM: `qwen2.5:14b`
- PC -> Mac 记忆写回: 已通
- Mac -> PC 推理委托: 已通
- Mac 测试记忆清理: 已完成,`memory_count=0`
- 桌面端: 可展示聊天、TTS、Live2D、记忆名片、反思、审计、版本、评测、节点拓扑

## 已完成的 5 轮循环

1. 清理测试记忆能力 + PC 推理预热
2. 双机演示冒烟脚本 + 演示手册
3. 评测数据导出 + 桌面端预热入口
4. 展示包装 + 演示启动 + release 打包脚本
5. 论文/答辩材料 + 最终自检

## 最终自检命令

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests
backend\.venv\Scripts\python.exe -m ruff check backend
cd desktop
pnpm build
```

双机检查:

```powershell
.\scripts\dual_node_demo.ps1
```

演示启动:

```powershell
.\scripts\start_demo_stack.ps1 -Restart
```

评测导出:

```powershell
.\scripts\export_evaluation_snapshot.ps1
```

release 打包:

```powershell
.\scripts\build_release.ps1
```

## 2026-06-24 最终验证结果

- `backend\.venv\Scripts\python.exe -m pytest backend\tests`: 42 passed
- `backend\.venv\Scripts\python.exe -m ruff check backend`: passed
- bundled `pnpm build`: passed
- `.\scripts\dual_node_demo.ps1`: passed=`true`
- 双机路由实测:PC `/node/inference/prewarm` 成功,随后 Mac `/chat` 返回 `inference_route.selected=peer`,模型为 `qwen2.5:14b`
- `.\scripts\build_release.ps1`: passed,生成源码交付包与 `desktop/out/`

## 2026-06-24 阻塞解除复核

- Mac mini 已拉取 `main@5ecad2d`,重新安装后端并重启 `com.kanojo.backend`。
- Mac `/maintenance/cleanup-test-memories` 已可用,测试记忆已软删除。
- PC 侧复跑 `.\scripts\cleanup_test_memories.ps1`: `matched_count=0`, `remaining_matches=0`。
- PC 侧复跑 `.\scripts\cleanup_test_memories.ps1 -Apply`: `deactivated_count=0`,说明没有剩余测试记忆。
- Mac `/memory-card`: `memory_count=0`。
- `.\scripts\dual_node_demo.ps1`: passed=`true`,Mac `/chat` 继续委托 PC peer 推理,模型为 `qwen2.5:14b`,client_elapsed_ms 约 974ms。

## 当前未完成事项

### 1. 最终自定义形象资产

当前使用 Live2D Haru sample 作为答辩占位。技术链路已通,但如果追求最终作品观感,应替换为自定义模型或至少替换封面/展示视觉。

### 2. Installer 级打包

当前 `build_release.ps1` 生成源码包和 `desktop/out/` 构建产物,尚未引入 electron-builder / forge 生成安装包。答辩演示可接受本地脚本启动。

## 后续优化优先级

1. 引入 NSIS/MSI installer 打包器。
2. 替换最终 Live2D / 视觉资产。
3. 增加更完整的记忆审核工作流,例如批量批准、批量拒绝和修改后批准。
4. 增加从桌面端应用推荐 peer URL 到 `.env` 的受控配置流程。

## 2026-06-24 继续优化循环

- Mac mini 常驻:新增 `scripts/install_macos_launchd.sh` 与 `scripts/uninstall_macos_launchd.sh`,把 `com.kanojo.backend` 的安装、重启、日志和卸载流程固化。
- PC 自启:新增 `scripts/install_windows_backend_startup.ps1` 与 `scripts/uninstall_windows_backend_startup.ps1`,使用当前用户 Startup 文件夹,不依赖管理员权限。
- 桌面启动: `scripts/start_desktop.ps1` 新增 `-EnsureBackend`,启动桌面前可自动拉起 PC 后端。
- 评测报告: `scripts/export_evaluation_snapshot.ps1` 默认生成 `evaluation-report.md`,也可单独运行 `scripts/write_evaluation_report.ps1`。
- 桌面体验:侧栏增加节点告警条,自动刷新拓扑状态,直接显示 peer 不可用、写回未就绪、PC 推理节点和 Mac 委托 PC 等状态。
- 桌面诊断:节点拓扑面板新增“一键诊断”,并发扫描候选 Mac/PC 地址,按当前节点角色推荐最佳 peer。
- 冷启动处理:新增 `scripts/prewarm_peer_inference.sh`,Mac 侧可一条命令预热 PC peer。
- 记忆治理:桌面端记忆名片每条记忆新增软停用按钮,复用后端 `DELETE /memories/{id}`,停用后刷新名片和反思摘要。
