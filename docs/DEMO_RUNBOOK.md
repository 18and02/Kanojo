# Kanojo 双机演示手册

这份手册用于答辩或现场演示前快速确认双机闭环。当前稳定基线:

- Mac mini: 常驻记忆源,`mac_home`,SQLite 真相源。
- PC: 推理节点,`pc_inference`,本地 `qwen2.5:14b`。
- PC -> Mac: 长期记忆写回 Mac。
- Mac -> PC: Mac `/chat` 自动委托 PC 推理。

## 1. 启动顺序

### PC

```powershell
cd "G:\Codex env\Kanojo"
.\scripts\start_backend.ps1 -BindAddress 0.0.0.0 -Restart
```

PC 在 `KANOJO_NODE_ROLE=pc_inference` 时会自动调用 `/node/inference/prewarm`,避免第一次 Mac 委托推理触发模型冷启动。

如需手动预热:

```powershell
.\scripts\prewarm_inference.ps1 -BaseUrl http://127.0.0.1:8787
```

### Mac mini

```bash
cd ~/Projects/Kanojo/backend
source .venv/bin/activate

set -a
source .env
set +a

export PYTHONPATH=src
uvicorn kanojo_agent.main:app --host 0.0.0.0 --port 8787
```

Mac `.env` 关键项:

```env
KANOJO_NODE_ROLE=mac_home
KANOJO_INFERENCE_PRIMARY=auto
KANOJO_PEER_BASE_URL=http://kanojo-pc.local:8787
KANOJO_MEMORY_PRIMARY=local
```

PC `.env` 关键项:

```env
KANOJO_NODE_ROLE=pc_inference
KANOJO_PEER_BASE_URL=http://kanojo-mac.local:8787
KANOJO_MEMORY_PRIMARY=peer
KANOJO_OFFLINE_WRITE_BEHAVIOR=reject
KANOJO_INFERENCE_PRIMARY=local
```

## 2. 一键冒烟

在 PC 执行:

```powershell
.\scripts\dual_node_demo.ps1
```

预期结果:

```json
{
  "passed": true,
  "checks": {
    "pc_status": {
      "role": "pc_inference",
      "memory_primary": "peer"
    },
    "mac_status": {
      "role": "mac_home",
      "peer_available": true
    },
    "mac_chat_delegates_to_pc": {
      "route_selected": "peer",
      "llm_model": "qwen2.5:14b",
      "llm_configured": true
    }
  }
}
```

当前实测结果:

- PC `/health`: ok
- Mac `/health`: ok
- PC `/node/status`: `role=pc_inference`, peer available
- Mac `/node/status`: `role=mac_home`, peer available
- PC `/node/inference/prewarm`: ok
- PC `/node/peer/memory-card`: available
- Mac `/chat`: `inference_route.selected=peer`

## 3. 写回演示

默认冒烟不写测试记忆。需要演示 PC 写回 Mac 时:

```powershell
.\scripts\dual_node_demo.ps1 -WritebackTest -CleanupAfterWrite
```

该命令会:

- 通过 PC `/memories` 写入一条带 `联调测试` 标记的测试记忆。
- 验证 PC 将记忆写到 Mac peer。
- 调 Mac `/maintenance/cleanup-test-memories` 清理测试记忆。

如果只想检查会清理哪些测试记忆:

```powershell
.\scripts\cleanup_test_memories.ps1 -BaseUrl http://kanojo-mac.local:8787
```

正式清理:

```powershell
.\scripts\cleanup_test_memories.ps1 -BaseUrl http://kanojo-mac.local:8787 -Apply
```

## 4. 故障判断

### Mac 不能访问 PC

检查 PC:

```powershell
Get-NetTCPConnection -LocalPort 8787
Get-NetFirewallRule -DisplayName "Kanojo Backend 8787"
```

预期:

- PC 后端监听 `0.0.0.0:8787`
- 防火墙规则 `Kanojo Backend 8787` 已启用
- Mac 可访问 `http://kanojo-pc.local:8787/health`

### Mac chat 没走 peer

检查 Mac:

```bash
curl http://127.0.0.1:8787/node/status
```

预期:

- `node.role=mac_home`
- `inference_route_policy.primary=auto`
- `peer.available=true`

### 第一次请求超时回退

通常是 PC 本地模型冷启动。先预热:

```bash
curl -X POST http://kanojo-pc.local:8787/node/inference/prewarm \
  -H "Content-Type: application/json" \
  -d '{"text":"预热 PC 推理节点"}'
```

然后重新调用 Mac `/chat`。
