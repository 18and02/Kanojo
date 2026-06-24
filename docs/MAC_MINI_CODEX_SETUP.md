# Mac mini 常驻节点环境配置指导

这份文档给 Mac mini 那边的 Codex 使用。目标是先把 Mac mini 配成 Kanojo 的常驻记忆源节点,用于 24/7 保存 SQLite 记忆真相源,并接收 PC 写回的长期记忆。

## 目标角色

Mac mini 负责:

- 常驻后端服务: `FastAPI + SQLite`
- 唯一长期记忆真相源
- 记忆名片、反思摘要、版本快照
- 接收 PC 节点写回的记忆
- 可选:把聊天推理委托给 PC

Mac mini 暂时不需要:

- Electron 桌面端
- Live2D
- STT / TTS
- 本地大模型

## 需要的环境

在 Mac mini 上准备:

```bash
python3 --version
git --version
```

要求:

- Python 3.11 或以上
- git
- Mac 和 PC 在同一局域网
- Mac mini 有固定局域网 IP 或稳定主机名

查看 Mac 局域网 IP:

```bash
ipconfig getifaddr en0
```

如果用有线网,可能是:

```bash
ipconfig getifaddr en1
```

## 放置项目

推荐通过 GitHub 拉取完整源码。拿到仓库地址后,在 Mac mini 上执行:

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone <GitHub仓库地址> Kanojo
cd Kanojo
```

如果仓库是私有仓库,先在 Mac mini 登录 GitHub CLI 或配置 SSH key:

```bash
gh auth login
```

也可以用 SSH 地址:

```bash
git clone git@github.com:<owner>/<repo>.git Kanojo
```

如果不是 git 仓库,也可以直接把整个项目目录拷贝到:

```bash
~/Projects/Kanojo
```

如果 Mac mini 只拿到了这份文档,还不能继续安装。目标目录必须至少包含下面这些后端源码:

```text
~/Projects/Kanojo/
  backend/
    pyproject.toml
    src/kanojo_agent/main.py
    src/kanojo_agent/settings.py
    tests/
  docs/
    MAC_MINI_CODEX_SETUP.md
```

如果当前没有 git 仓库地址,可以从 PC 侧打包一份轻量源码包传过去。源码包不要包含:

- `backend/.env`
- `backend/.venv`
- `backend/data`
- `desktop/node_modules`
- `desktop/out`
- `.ruff_cache` / `.pytest_cache`

Mac mini 收到压缩包后放到 `~/Projects`,解压并改名为 `Kanojo`:

```bash
cd ~/Projects
unzip Kanojo-macmini-backend-source-*.zip
mv Kanojo-macmini-backend-source-* Kanojo
```

## 安装后端依赖

```bash
cd ~/Projects/Kanojo/backend

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e ".[dev]"
```

如果只想最小运行,也可以:

```bash
pip install -e .
```

建议装 `dev`,方便运行测试和 ruff。

## 配置 `.env`

在 Mac mini 的 `backend/.env` 写入:

```env
KANOJO_NODE_NAME=mac-mini
KANOJO_NODE_ROLE=mac_home

KANOJO_DB_PATH=data/kanojo.db

KANOJO_MEMORY_PRIMARY=local
KANOJO_OFFLINE_WRITE_BEHAVIOR=local_only

KANOJO_INFERENCE_PRIMARY=auto
KANOJO_PEER_BASE_URL=
KANOJO_PEER_TIMEOUT=5

KANOJO_MEMORY_EXTRACTION=heuristic

KANOJO_QUIET_START=23
KANOJO_QUIET_END=8
KANOJO_PROACTIVE_COOLDOWN=120
KANOJO_ACTIVITY_GRACE_MINUTES=10
```

说明:

- `KANOJO_MEMORY_PRIMARY=local`:Mac 自己保存记忆,作为真相源。
- `KANOJO_OFFLINE_WRITE_BEHAVIOR=local_only`:Mac 本地写入。
- `KANOJO_INFERENCE_PRIMARY=auto`:后续配置 PC peer 后,Mac 可把聊天推理委托给 PC。
- `KANOJO_PEER_BASE_URL=`:如果 PC 节点还没准备好,先留空。
- `KANOJO_MEMORY_EXTRACTION=heuristic`:Mac 先不用大模型抽取,降低环境复杂度。

等 PC 节点准备好后,把 `KANOJO_PEER_BASE_URL` 改成 PC 的局域网地址:

```env
KANOJO_PEER_BASE_URL=http://PC的局域网IP:8787
```

例如:

```env
KANOJO_PEER_BASE_URL=http://192.168.1.23:8787
```

## 启动后端

注意:当前项目没有 macOS 版启动脚本,直接用 shell 加载 `.env` 后运行 uvicorn。

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

## 本机验证

在 Mac mini 上新开一个终端:

```bash
curl http://127.0.0.1:8787/health
curl http://127.0.0.1:8787/node/status
curl http://127.0.0.1:8787/memory-card
```

预期:

- `/health` 返回 `{"status":"ok","version":"0.1.0"}`
- `/node/status` 里:
  - `node.role` 是 `mac_home`
  - `memory_write_policy.primary` 是 `local`
  - `peer.configured` 在 PC 未配置时是 `false`

## 从 PC 验证 Mac

在 PC 浏览器或 PowerShell 访问:

```text
http://Mac的局域网IP:8787/health
http://Mac的局域网IP:8787/node/status
```

如果 PC 能看到返回,说明 Mac 常驻后端已对局域网开放。

## PC 侧应该怎么配

PC 的 `backend/.env` 后续应指向 Mac:

```env
KANOJO_NODE_NAME=pc
KANOJO_NODE_ROLE=pc_inference

KANOJO_PEER_BASE_URL=http://Mac的局域网IP:8787

KANOJO_MEMORY_PRIMARY=peer
KANOJO_OFFLINE_WRITE_BEHAVIOR=reject

KANOJO_INFERENCE_PRIMARY=local
```

这样 PC 的长期记忆会写回 Mac:

```text
PC /chat
  -> PC 本地推理
  -> 抽取长期记忆
  -> POST http://MacIP:8787/node/memory-writes
  -> Mac SQLite 落库
```

## 联调检查项

### 1. PC 能读 Mac 记忆名片

在 PC 后端调用:

```text
http://127.0.0.1:8787/node/peer/memory-card
```

预期:

- `configured: true`
- `available: true`
- `payload.memory_count` 能返回

### 2. PC 写入 Mac 记忆

在 PC 桌面端输入:

```text
我周五有英语口语考试
```

然后在 Mac 上检查:

```bash
curl http://127.0.0.1:8787/memory-card
```

预期:Mac 的记忆名片里出现新记忆。

### 3. Mac 委托 PC 推理

Mac `.env` 设置:

```env
KANOJO_INFERENCE_PRIMARY=auto
KANOJO_PEER_BASE_URL=http://PC的局域网IP:8787
```

在 Mac 调:

```bash
curl -X POST http://127.0.0.1:8787/chat \
  -H "Content-Type: application/json" \
  -d '{"text":"你好","session_id":"default"}'
```

预期响应里:

```json
"inference_route": {
  "selected": "peer"
}
```

如果 PC 不在线,应该回退本地,并在 `inference_route.reason` 里说明 peer 失败。

## 常见问题

### PC 访问不到 Mac

检查:

```bash
uvicorn kanojo_agent.main:app --host 0.0.0.0 --port 8787
```

确认不是 `--host 127.0.0.1`。

检查 Mac 防火墙:

- System Settings
- Network 或 Privacy & Security
- Firewall
- 允许 Python / Terminal / uvicorn 接收入站连接

检查 PC 和 Mac 是否在同一局域网。

### `.env` 没生效

macOS 直接跑 uvicorn 不会自动加载 `.env`,必须先执行:

```bash
set -a
source .env
set +a
```

然后再启动 uvicorn。

### 端口被占用

```bash
lsof -i :8787
```

结束旧进程:

```bash
kill <PID>
```

### SQLite 路径不对

确认 Mac 后端的工作目录是:

```bash
~/Projects/Kanojo/backend
```

如果从别的目录启动,`KANOJO_DB_PATH=data/kanojo.db` 会相对当前工作目录解析。

## 最小成功标准

Mac mini 配好后,至少要满足:

- Mac 本机 `curl http://127.0.0.1:8787/health` 成功。
- PC 访问 `http://MacIP:8787/health` 成功。
- Mac `/node/status` 显示 `role=mac_home`。
- Mac `/memory-card` 可返回。
- PC 配 peer 后,`/node/peer/memory-card` 可读取 Mac 名片。

做到这里,Mac 常驻记忆源环境就算配置完成。
