# Mac mini Codex 最新配置指导

这份文档给 Mac mini 侧 Codex 使用。目标是把 Mac mini 配成 Kanojo 的常驻记忆源节点,用于 24/7 保存 SQLite 记忆真相源,并接收 PC 推理节点写回的长期记忆。

## 当前已知信息

- GitHub 仓库: `https://github.com/18and02/Kanojo.git`
- Mac mini 主机名: `kanojo-mac.local`(示例;换成你自己的 mDNS 名或局域网 IP)
- Mac mini 局域网 IP:
  - `en0`: `<MAC_LAN_IP>`
  - `en1`: `<MAC_LAN_IP_ALT>`
- 建议优先用 `en0` 的地址(或 `kanojo-mac.local`)做 PC 访问地址。
- 后端端口: `8787`
- Mac 侧目标项目路径: `~/Projects/Kanojo`
- Mac 侧目标后端路径: `~/Projects/Kanojo/backend`

Mac mini 侧已经确认:

- Python 可用: `Python 3.14.6`
- git 可用: `git 2.50.1`
- Homebrew 可用: `6.0.3`
- `8787` 端口当前未占用
- macOS 防火墙当前关闭
- 接电常驻配置已设置: `sleep 0`, `disksleep 0`

Python 3.14.6 可以先直接使用。本项目声明要求是 Python `>=3.11`。如果后续 `pip install` 遇到第三方依赖暂不支持 Python 3.14 的问题,再切换到 Homebrew 的 `python@3.12`。

## Mac mini 的角色

Mac mini 负责:

- 常驻后端服务: `FastAPI + SQLite`
- 唯一长期记忆真相源
- 记忆名片、反思摘要、版本快照
- 接收 PC 节点写回的长期记忆
- 可选:把聊天推理委托给 PC

Mac mini 暂时不需要:

- Electron 桌面端
- Live2D
- STT / TTS
- 本地大模型

## 1. 登录 GitHub

仓库是私有仓库,Mac mini 必须先登录能访问 `18and02/Kanojo` 的 GitHub 账号。

如果 Mac mini 还没有 GitHub CLI:

```bash
brew install gh
```

登录:

```bash
gh auth login
```

推荐选项:

- GitHub.com
- HTTPS
- Login with a web browser

登录后验证:

```bash
gh auth status
```

预期能看到已登录 `github.com`。

## 2. 拉取项目源码

如果旧目录里只有文档或错误项目,先不要在里面继续装依赖。直接重新拉取完整仓库。

```bash
mkdir -p ~/Projects
cd ~/Projects

rm -rf Kanojo
git clone https://github.com/18and02/Kanojo.git Kanojo
cd Kanojo
```

检查源码结构:

```bash
ls
ls backend
ls backend/src/kanojo_agent
```

必须能看到:

```text
backend/pyproject.toml
backend/src/kanojo_agent/main.py
backend/src/kanojo_agent/settings.py
docs/MAC_MINI_CODEX_SETUP.md
```

如果 clone 失败:

- 先确认 `gh auth status` 已登录。
- 确认登录账号有私有仓库 `18and02/Kanojo` 的访问权限。
- 也可以打开仓库页面确认权限: `https://github.com/18and02/Kanojo`

## 3. 安装后端依赖

```bash
cd ~/Projects/Kanojo/backend

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e ".[dev]"
```

如果 `pip install -e ".[dev]"` 因 Python 3.14 兼容性失败,再执行下面的降级方案:

```bash
brew install python@3.12
rm -rf .venv

/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e ".[dev]"
```

安装完成后验证:

```bash
python -m pytest tests
python -m ruff check .
```

## 4. 配置 Mac mini 的 `.env`

在 `~/Projects/Kanojo/backend/.env` 写入:

```bash
cat > .env <<'EOF'
KANOJO_NODE_NAME=mac-mini
KANOJO_NODE_ROLE=mac_home

KANOJO_DB_PATH=data/kanojo.db

KANOJO_MEMORY_PRIMARY=local
KANOJO_OFFLINE_WRITE_BEHAVIOR=local_only

KANOJO_INFERENCE_PRIMARY=auto
KANOJO_PEER_BASE_URL=
KANOJO_PEER_TIMEOUT=12

KANOJO_MEMORY_EXTRACTION=heuristic

KANOJO_QUIET_START=23
KANOJO_QUIET_END=8
KANOJO_PROACTIVE_COOLDOWN=120
KANOJO_ACTIVITY_GRACE_MINUTES=10
EOF
```

说明:

- `KANOJO_NODE_ROLE=mac_home`:当前节点是常驻 Mac 记忆源。
- `KANOJO_DB_PATH=data/kanojo.db`:SQLite 数据库放在 `backend/data/`。
- `KANOJO_MEMORY_PRIMARY=local`:Mac 本地保存长期记忆。
- `KANOJO_OFFLINE_WRITE_BEHAVIOR=local_only`:Mac 本地写入,不依赖 peer。
- `KANOJO_INFERENCE_PRIMARY=auto`:后续 PC peer 配好后,Mac 可以优先委托 PC 推理。
- `KANOJO_PEER_BASE_URL=`:PC 节点还没配好前先留空。
- `KANOJO_PEER_TIMEOUT=12`:演示时给 PC 本地模型冷启动留出缓冲。仍建议优先预热 PC peer。
- `KANOJO_MEMORY_EXTRACTION=heuristic`:Mac 暂时用启发式抽取,降低常驻环境复杂度。

确认 `.env` 存在:

```bash
cat .env
```

## 5. 启动 Mac mini 后端

在 Mac mini 上启动:

```bash
cd ~/Projects/Kanojo/backend
source .venv/bin/activate

set -a
source .env
set +a

export PYTHONPATH=src
uvicorn kanojo_agent.main:app --host 0.0.0.0 --port 8787
```

必须使用:

```bash
--host 0.0.0.0
```

不要只监听 `127.0.0.1`,否则 PC 访问不到 Mac。

### 5.1 安装为 launchd 常驻服务

仓库提供了 launchd 安装脚本,用于把 Mac 后端注册为当前用户的 LaunchAgent。脚本会生成:

- `~/Library/LaunchAgents/com.kanojo.backend.plist`
- `~/Projects/Kanojo/backend/.launchd/run_backend.sh`
- `~/Projects/Kanojo/backend/logs/launchd.out.log`
- `~/Projects/Kanojo/backend/logs/launchd.err.log`

安装:

```bash
cd ~/Projects/Kanojo
bash scripts/install_macos_launchd.sh
```

安装脚本默认参数:

```bash
LABEL=com.kanojo.backend
PROJECT_ROOT=~/Projects/Kanojo
BIND_ADDRESS=0.0.0.0
PORT=8787
PYTHON_BIN=~/Projects/Kanojo/backend/.venv/bin/python
```

如需覆盖参数:

```bash
PROJECT_ROOT="$HOME/Projects/Kanojo" PORT=8787 bash scripts/install_macos_launchd.sh
```

查看状态:

```bash
launchctl print gui/$UID/com.kanojo.backend
curl http://127.0.0.1:8787/health
tail -n 80 ~/Projects/Kanojo/backend/logs/launchd.err.log
```

卸载:

```bash
cd ~/Projects/Kanojo
bash scripts/uninstall_macos_launchd.sh
```

更新代码或 `.env` 后重启服务:

```bash
launchctl kickstart -k gui/$UID/com.kanojo.backend
```

## 6. Mac 本机验证

另开一个终端:

```bash
curl http://127.0.0.1:8787/health
curl http://127.0.0.1:8787/node/status
curl http://127.0.0.1:8787/memory-card
```

预期:

- `/health` 返回 `{"status":"ok","version":"0.1.0"}`
- `/node/status` 中:
  - `node.role` 是 `mac_home`
  - `memory_write_policy.primary` 是 `local`
  - `peer.configured` 在 PC 未配置时是 `false`
- `/memory-card` 能正常返回 JSON。

## 7. PC 访问 Mac 验证

在 PC 浏览器或 PowerShell 访问:

```text
http://kanojo-mac.local:8787/health
http://kanojo-mac.local:8787/node/status
```

如果 `kanojo-mac.local` 不通,再尝试:

```text
http://kanojo-mac.local:8787/health
http://kanojo-mac-alt.local:8787/health
```

也可以在 PC 侧直接扫描候选地址:

```powershell
.\scripts\find_peer.ps1 -PreferredRole mac_home
```

判断标准:

- PC 能访问 `/health`,说明 Mac 后端已对局域网开放。
- PC 能访问 `/node/status`,说明双机拓扑可进入联调。

## 8. PC 侧后续配置

等 Mac 后端确认可访问后,PC 的 `backend/.env` 应改成指向 Mac:

```env
KANOJO_NODE_NAME=pc
KANOJO_NODE_ROLE=pc_inference

KANOJO_PEER_BASE_URL=http://kanojo-mac.local:8787

KANOJO_MEMORY_PRIMARY=peer
KANOJO_OFFLINE_WRITE_BEHAVIOR=reject

KANOJO_INFERENCE_PRIMARY=local
```

这样 PC 的长期记忆会写回 Mac:

```text
PC /chat
  -> PC 本地推理
  -> 抽取长期记忆
  -> POST http://kanojo-mac.local:8787/node/memory-writes
  -> Mac SQLite 落库
```

## 9. 双机联调检查

### 9.1 PC 能读 Mac 记忆名片

在 PC 后端本机调用:

```text
http://127.0.0.1:8787/node/peer/memory-card
```

预期:

- `configured: true`
- `available: true`
- `payload.memory_count` 能返回

### 9.2 PC 写入 Mac 记忆

在 PC 桌面端输入:

```text
我周五有英语口语考试
```

然后在 Mac 上检查:

```bash
curl http://127.0.0.1:8787/memory-card
```

预期:Mac 的记忆名片里出现新记忆。

### 9.3 Mac 委托 PC 推理

Mac `.env` 后续可以设置。当前 PC 已发现的优先局域网地址是 `kanojo-pc.local`,PC 后端需要用 `0.0.0.0` 监听:

```powershell
.\scripts\start_backend.ps1 -BindAddress 0.0.0.0 -Restart
```

如果 Windows 防火墙开启,需要用管理员 PowerShell 放行 PC 的 `8787` 入站:

```powershell
New-NetFirewallRule -DisplayName "Kanojo Backend 8787" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8787 -Profile Private
```

然后在 Mac 的 `backend/.env` 设置:

```env
KANOJO_INFERENCE_PRIMARY=auto
KANOJO_PEER_BASE_URL=http://kanojo-pc.local:8787
```

在 Mac 调:

```bash
curl -X POST http://127.0.0.1:8787/chat \
  -H "Content-Type: application/json" \
  -d '{"text":"你好","session_id":"default"}'
```

如果 PC peer 在线,响应里的 `inference_route.selected` 应该是 `peer`。如果 PC 不在线,应该回退本地,并在 `inference_route.reason` 里说明 peer 失败。

真实联调确认:

- Mac 能访问 `http://kanojo-pc.local:8787/health`。
- Mac `.env` 已设置 `KANOJO_INFERENCE_PRIMARY=auto` 与 `KANOJO_PEER_BASE_URL=http://kanojo-pc.local:8787`。
- Mac `/node/status` 显示 `peer.available=true`。
- Mac `/chat` 最终返回 `inference_route.selected=peer`, `llm_model=qwen2.5:14b`, `llm_configured=true`。

如果第一次 `/chat` 约 5 秒超时并回退本地,通常是 PC 本地模型冷启动。先在 Mac 上预热 PC 推理节点:

```bash
curl -X POST http://kanojo-pc.local:8787/node/inference/chat \
  -H "Content-Type: application/json" \
  -d '{"text":"预热 PC 推理节点","memories":[]}'
```

预热后重新调用 Mac `/chat`,应稳定走 `selected=peer`。

新版本也提供专用预热接口:

```bash
curl -X POST http://kanojo-pc.local:8787/node/inference/prewarm \
  -H "Content-Type: application/json" \
  -d '{"text":"预热 PC 推理节点"}'
```

也可以用仓库脚本:

```bash
cd ~/Projects/Kanojo
bash scripts/prewarm_peer_inference.sh http://kanojo-pc.local:8787
```

PC 侧 `scripts/start_backend.ps1` 在 `KANOJO_NODE_ROLE=pc_inference` 时会自动调用该预热接口。也可以手动执行:

```powershell
.\scripts\prewarm_inference.ps1 -BaseUrl http://127.0.0.1:8787
```

### 9.4 清理联调测试记忆

Mac mini 更新到包含维护接口的新版本后,先 dry-run 查看会清理哪些长期记忆:

```bash
curl -X POST http://127.0.0.1:8787/maintenance/cleanup-test-memories \
  -H "Content-Type: application/json" \
  -d '{"dry_run":true}'
```

确认只匹配联调/冒烟/链路验证产生的测试记忆后,再正式软删除:

```bash
curl -X POST http://127.0.0.1:8787/maintenance/cleanup-test-memories \
  -H "Content-Type: application/json" \
  -d '{"dry_run":false}'
```

该操作不会物理删除 SQLite 行,只把匹配记忆标记为 `inactive`,后续名片、检索和反思摘要不会再使用这些测试记忆。

## 10. 常见问题

### clone 私有仓库失败

检查:

```bash
gh auth status
```

确认登录账号有 `18and02/Kanojo` 访问权限。

### `.env` 没生效

macOS 直接跑 uvicorn 不会自动加载 `.env`,必须先执行:

```bash
set -a
source .env
set +a
```

然后再启动 uvicorn。

### PC 访问不到 Mac

检查启动命令是否包含:

```bash
--host 0.0.0.0
```

检查监听:

```bash
lsof -i :8787
```

检查 Mac IP:

```bash
ipconfig getifaddr en0
ipconfig getifaddr en1
```

检查 PC 和 Mac 是否在同一局域网。当前优先尝试 `kanojo-mac.local`。

### 端口被占用

```bash
lsof -i :8787
kill <PID>
```

### SQLite 路径不对

确认后端启动目录是:

```bash
~/Projects/Kanojo/backend
```

如果从别的目录启动,`KANOJO_DB_PATH=data/kanojo.db` 会相对当前工作目录解析。

## 最小成功标准

Mac mini 配好后,至少要满足:

- Mac 本机 `curl http://127.0.0.1:8787/health` 成功。
- PC 访问 `http://kanojo-mac.local:8787/health` 成功。
- Mac `/node/status` 显示 `role=mac_home`。
- Mac `/memory-card` 可返回。
- PC 配 peer 后,`/node/peer/memory-card` 可读取 Mac 名片。

做到这里,Mac 常驻记忆源环境就算配置完成。
