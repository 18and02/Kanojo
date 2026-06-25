# 最终展示包装说明

## 展示定位

Kanojo 当前展示重点是“长期记忆驱动 + 主动交互 + 双机常驻闭环”,不是单纯聊天壳。

答辩展示建议按下面顺序呈现:

1. 桌面端启动后展示 Live2D 形象和控制面板。
2. 打开调试页,展示节点拓扑:
   - PC: `pc_inference`
   - Mac: `mac_home`
   - peer available
   - memory primary / inference route
3. 用 `scripts\dual_node_demo.ps1` 展示双机冒烟 `passed=true`。
4. 在桌面端发起一次对话,展示回复、命中记忆、记忆审计和评测事件。
5. 打开记忆页,展示名片、反思、审计、版本快照。
6. 导出评测数据和记忆名片,作为论文材料。

## 当前形象资产

当前使用仓库内 Live2D Haru sample 作为答辩占位形象:

```text
desktop/src/renderer/public/live2d/haru
```

这满足毕业设计技术展示需求:

- 有可见人格化形象。
- 支持基础姿态、动作和口型联动。
- 已接入 TTS / 打断 / 评测埋点。

后续如果需要更强“最终形象”,优先替换模型资产,而不是重写桌面逻辑:

```text
desktop/src/renderer/public/live2d/<custom-model>
```

替换后只需更新 `Live2DAvatar.tsx` 的模型路径或配置选择逻辑。

## 演示启动

PC:

```powershell
cd "G:\Codex env\Kanojo"
.\scripts\start_demo_stack.ps1 -Restart
```

该脚本会:

- 启动 PC 后端并监听 `0.0.0.0:8787`
- 自动预热本地推理模型
- 检查防火墙规则
- 执行双机冒烟
- 启动桌面端

如果只想做命令行检查:

```powershell
.\scripts\start_demo_stack.ps1 -Restart -SkipDesktop
```

如果只启动桌面端,但希望桌面端启动前自动确认 PC 后端已拉起:

```powershell
.\scripts\start_desktop.ps1 -EnsureBackend -Restart
```

## 演示截图采集

生成答辩展示截图:

```powershell
.\scripts\capture_showcase_screenshots.ps1 -OutDir exports-showcase
```

该脚本会临时启动 Vite 预览服务,调用本机 Edge/Chrome 的 DevTools Protocol,自动切换关键页签并输出 PNG 截图和 manifest。默认输出:

```text
exports-showcase/01-control.png
exports-showcase/02-memory-card.png
exports-showcase/03-memory-audit.png
exports-showcase/04-debug-node.png
exports-showcase/showcase-screenshots.json
```

如需在截图前确认本机后端已启动:

```powershell
.\scripts\capture_showcase_screenshots.ps1 -EnsureBackend -OutDir exports-showcase
```

## 演示素材包

把截图、评测报告、关键说明文档和当前 release 校验信息汇总到一个目录:

```powershell
.\scripts\build_showcase_package.ps1 -OutDir exports-showcase-package
```

默认输出:

```text
exports-showcase-package/SHOWCASE_INDEX.md
exports-showcase-package/showcase-package.json
exports-showcase-package/screenshots/
exports-showcase-package/evaluation/
exports-showcase-package/docs/
```

`SHOWCASE_INDEX.md` 是答辩前的材料入口,包含截图清单、评测报告路径、关键文档副本和当前 commit 的 release SHA256。默认不复制 release zip,只引用 `release/` 下的已有交付包;如确实需要把 zip 一并放进素材包:

```powershell
.\scripts\build_showcase_package.ps1 -OutDir exports-showcase-package -IncludeReleaseArtifacts
```

## PC 后端登录自启

PC 可以把后端注册到当前用户的 Startup 文件夹。该方式不需要管理员权限,登录后会启动 `start_backend.ps1`,默认监听 `0.0.0.0:8787`,并沿用启动预热逻辑:

```powershell
.\scripts\install_windows_backend_startup.ps1 -RunNow
```

查看启动项:

```powershell
Get-ChildItem ([Environment]::GetFolderPath("Startup")) -Filter "Kanojo Backend.cmd"
```

卸载:

```powershell
.\scripts\uninstall_windows_backend_startup.ps1
```

## 打包

生成源码包和桌面构建产物:

```powershell
.\scripts\build_release.ps1
```

输出:

```text
release/kanojo-source-<commit>.zip
release/kanojo-desktop-portable-<commit>.zip
release/SHA256SUMS-<commit>.txt
desktop/out/
```

`kanojo-desktop-portable-<commit>.zip` 内包含 Electron runtime 和已构建桌面端,解压后运行 `Kanojo.exe`。它仍需要本机后端已经启动,推荐先执行:

```powershell
.\scripts\start_backend.ps1 -BindAddress 0.0.0.0
```

也可以只生成桌面 portable 包:

```powershell
.\scripts\build_desktop_portable.ps1
```

当前仓库仍未引入 NSIS/MSI installer。已尝试接入 `electron-builder`,但当前 pnpm 供应链校验输出会污染 builder 读取依赖树的 JSON 输出,因此先采用可验证的 portable 交付包作为答辩分发形态。

`SHA256SUMS-<commit>.txt` 可用于拷贝或提交前后校验交付包完整性:

```powershell
Get-FileHash .\release\kanojo-desktop-portable-<commit>.zip -Algorithm SHA256
```

生成 release 包后,可以创建或更新 GitHub draft release:

```powershell
.\scripts\publish_github_release.ps1 -SkipBuild
```

默认会创建 draft release,标签为 `kanojo-<commit>`,并上传源码包、portable 包和 SHA256 清单。先预览不上传:

```powershell
.\scripts\publish_github_release.ps1 -SkipBuild -DryRun
```

查看 GitHub draft release 清理建议:

```powershell
.\scripts\prune_github_draft_releases.ps1 -Keep 2
```

该命令默认 dry-run,只输出将保留和建议清理的草稿。只有显式加 `-Apply` 才会删除旧 draft release;如还要同步删除对应 tag,再加 `-CleanupTag`。

## 评测报告

导出评测数据时会同步生成 Markdown 摘要:

```powershell
.\scripts\export_evaluation_snapshot.ps1 -OutDir exports-demo
```

核心文件:

```text
exports-demo/evaluation-report.md
```

报告包含节点基线、聊天/心跳/形象指标、推理路由统计、记忆名片摘要和最近事件,可直接作为论文/答辩材料索引。
