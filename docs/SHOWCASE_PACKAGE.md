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

## 打包

生成源码包和桌面构建产物:

```powershell
.\scripts\build_release.ps1
```

输出:

```text
release/kanojo-source-<commit>.zip
desktop/out/
```

当前仓库没有引入 installer 打包器,因此 `desktop/out/` 是 Electron/Vite 构建产物,`release/*.zip` 是可交付源码包。答辩演示以本地启动脚本为准。
