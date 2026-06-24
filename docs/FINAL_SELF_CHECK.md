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

1. 给 Mac mini 配置 launchd 常驻服务的完整安装/卸载脚本,避免手动维护。
2. 给 PC 后端配置开机启动或桌面端启动前自动拉起。
3. 引入 installer 打包器。
4. 替换最终 Live2D / 视觉资产。
5. 增加更严格的记忆编辑 UI,支持人工确认、删除和降权。
6. 增加评测报告自动生成 Markdown。
7. 增加 peer 断线告警和桌面端提示。
8. 适当增大 Mac `KANOJO_PEER_TIMEOUT` 或保证 PC 开机后预热,进一步降低冷启动回退概率。
