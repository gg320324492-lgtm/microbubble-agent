# 本地启动注意事项

> 本文档覆盖**从关机状态恢复** / **本地首次启动** / **重启电脑后** 三种场景的完整启动流程、注意事项与验证清单。
> 云端部署见 [deploy.md](deploy.md)。

---

## TL;DR — 一键启动

```bash
# 1. 启动 Docker Desktop（GUI 启动或脚本）
cmd //c start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
# 等 daemon 就绪（~15s，轮询 docker info 看 Server Version）

# 2. 启动 9 个服务
docker compose up -d

# 3. 启动 FRP 隧道（必须清代理环境变量，详见下文）
cd frp && HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" NO_PROXY="*" no_proxy="*" \
  powershell -Command "Start-Process -FilePath '.\frpc.exe' -ArgumentList '-c','frpc.toml' -WindowStyle Hidden -WorkingDirectory '$(pwd -W)'"

# 4. 验证（必须跑全 8 点 curl，否则 502/401 无法定位）
# 详见 [§4 验证清单](#4-验证清单)
```

---

## 1. 启动顺序

| 顺序 | 操作 | 失败表现 | 原因 |
|------|------|----------|------|
| 1 | Docker Desktop daemon | `docker compose` 报 `failed to connect to the docker API` | 进程起 ≠ daemon 起来 |
| 2 | `docker compose up -d` | 容器一直 `Restarting` | 多数是 stdin 关闭 / `adduser` 镜像问题 / 端口被占 |
| 3 | frpc.exe 隧道 | 外网头像 502 / API 不可达 | 进程起 ≠ 隧道通（详见 §3.2）|
| 4 | 应用层验证 | API 500 / 路由 404 | Python 模块缓存（详见 §3.3）|

**关键纪律**：必须**按顺序**，且每一步都验证再走下一步。

---

## 2. 启动前检查

### 2.1 必备条件

- [ ] Docker Desktop 已安装（`C:\Program Files\Docker\Docker\Docker Desktop.exe`）
- [ ] 项目根目录有 `docker-compose.yml` + `docker-compose.override.yml`
- [ ] `frp/frpc.exe` + `frp/frpc.toml` 存在
- [ ] `app/.env`（或 `.env.local`）存在（docker compose 会读）
- [ ] **磁盘 ≥ 30 GB**（Docker 镜像 + modelscope 缓存约 25 GB）
- [ ] **GPU + CUDA**（whisper 容器需要；CPU 也能跑但慢 10x+）

### 2.2 启动前必清

```bash
# 杀残留 frpc.exe（重启电脑后常见）
taskkill //F //IM frpc.exe 2>/dev/null

# 清旧 frpc.log（避免误导判断）
rm -f frp/frpc.log

# 看 frp/start.sh 是不是能直接一键（可选，绕过手动 start.bat）
ls frp/start.sh
```

### 2.3 必看的环境变量

| 变量 | 用途 | 缺值后果 |
|------|------|----------|
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | 容器启动会 warn 但继续，DB 实际无密码（开发模式）|
| `WEBHOOK_SECRET` | GitHub webhook HMAC 验证 | 部署失败 push 后服务挂 |
| `WHISPER_MODEL` | faster-whisper 模型大小 | 默认 `large-v3`，CPU 机器改成 `small` |
| `ANTHROPIC_API_KEY` / `CLAUDE_API_KEY` | LLM 调用 | 助手直接 500 |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | 对象存储 | 上传头像失败 |

`POSTGRES_PASSWORD not set` 的 warning **无害**，开发模式不设密码。

---

## 3. 启动铁律（基于真实事故）

### 3.1 容器内 `pip install` 不持久化

- 容器内手动 `pip install --upgrade X` 是**临时修复**
- 下次 `docker compose build` 会重装 `requirements.txt` 锁定的版本 → bug 复发
- **正确流程**：容器内验证有效 → 改 `requirements.txt` → commit → push

### 3.2 frpc.exe 启动三件套（必看，最常踩坑）

**症状**：进程跑起来后 `tasklist` 看到 PID ✓，但 `frpc.log` 最后修改时间还是几天前，浏览器访问外网头像 502。

**根因**：frpc.exe 启动失败时**进程不立即退出**（在等云服务器响应），光看进程在跑没用。

**正确启动命令**（清代理环境变量 + 后台启动 + 验证 log 写入）：

```bash
cd frp
taskkill //F //IM frpc.exe 2>/dev/null
rm -f frpc.log

HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" NO_PROXY="*" no_proxy="*" \
  powershell -Command "Start-Process -FilePath '.\frpc.exe' -ArgumentList '-c','frpc.toml' -WindowStyle Hidden -WorkingDirectory '$(pwd -W)'"

sleep 5
tail -10 frpc.log
# 必须看到: "login to server success" + "start proxy success" 三个代理
# [microbubble-app] start proxy success
# [minio] start proxy success
# [ssh] start proxy success

netstat -ano | grep ":7000.*ESTABLISHED"
# 看到的 PID 必须是刚启动的 frpc.exe（用 tasklist | grep frpc 比对 PID）
```

**3 步验证法**（缺一不可）：

1. `frpc.log` 最新时间 = 刚刚（`stat -c %y frp/frpc.log`）
2. `netstat :7000 ESTABLISHED` 的 PID 是 frpc.exe（不是 clash-win64.exe）
3. 外网头像 HTTP 200（`curl https://agent.mnb-lab.cn/minio/microbubble/avatars/<任意>.<jpg>`）

### 3.3 Docker Python 模块缓存陷阱

**症状**：改了 `app/api/v1/chat.py` 加新路由 → volume 挂载同步了文件 → `docker exec cat chat.py` 能看到新代码 → 但 `curl /openapi.json | grep 新路由` **完全没有**。

**根因**：volume 挂载只换文件不换 Python 模块缓存。FastAPI 进程启动时 import 一次路由表，运行期不再扫描新文件。

**修复**：
```bash
docker compose restart app celery-worker celery-beat
```

**何时必须重启**（3 类变更）：
1. 改了 `app/api/v1/*.py`（路由注册）
2. 加了 `app/agent/tools/*.py`（装饰器注册）
3. 改了 `app/agent/protocol.py`（SSE 事件类型）

**反例**：只改 `app/services/*.py`（内部实现，import 链不变）**不需要**重启，HMR 模式或下次自然重启即可。

### 3.4 git clean -fdx 误清 .env

**纪律**：`scripts/deploy-auto.sh` line 31 用 `git clean -fdx` 清 untracked 文件，**会顺手清掉 `.gitignore` 里的 .env*** 文件**（包括 `.env.webhook`），导致 webhook 服务下次重启找不到 secret 启动失败。

**预防**：deploy 脚本加守卫 `[ -f .env.webhook ] || { echo "ERROR: missing"; exit 1; }`；本地 .env 移到 `/etc/microbubble-agent/`（不在 git 工作区）。

### 3.5 clash / v2ray 代理劫持 frpc HTTPS

**症状**：frpc 启动后卡在 `try to connect to server...` 永远不出 `login to server success`。

**根因**：本机开了 clash 系统代理，frpc 默认走 `HTTP_PROXY` 环境变量被劫持。

**修复**：见 §3.2 启动命令里的 `HTTP_PROXY="" HTTPS_PROXY=""` 清空（必须清空 4 个变量名 + 2 种大小写）。

### 3.6 frps 服务端重启后旧 run id 失效

**症状**：外网访问突然全 502 / 连接拒绝；`tail frpc.log` 看到 `run id` 变了（旧的 `531dadd3bd53b7d1` → 新的 `2723f1d42c04b27b`）。

**修复**：手动重启 frpc.exe（不要等自动重连，frpc 0.x 长时间无活动 + frps 重启可能错过重连窗口）。

**改进**（可选）：`frpc.toml` 加 `transport.heartbeatInterval = 30` + `transport.heartbeatTimeout = 90`，缩短发现断连时间。

### 3.7 MCP stdio 容器必须 `stdin_open: true`

**症状**：vision-mcp 容器一直 `Restarting (1) X seconds ago`，日志只有 `Starting...` 一行没 traceback。

**根因**：MCP stdio 协议靠 stdin 通信，Docker 启动时 stdin 默认关闭 pipe → 立即 EOF → 退出 → restart 死循环。

**修复**（已配）：`docker-compose.yml` 的 vision-mcp 服务加：
```yaml
stdin_open: true
tty: true
```

如升级 vision-mcp 镜像后出问题，第一时间检查这两行。

---

## 4. 验证清单

启动后**必须**跑完这 8 点 curl，**任何一项失败都要排查**再宣告启动成功：

```bash
echo "=== 1. 本机 API ===" && curl "http://127.0.0.1:8000/api/v1/auth/me" -s -o /dev/null -w "HTTP %{http_code}\n"
# 期望: 401（缺 token = API 注册成功）

echo "=== 2. FRP 隧道 ===" && curl -sk "https://agent.mnb-lab.cn/api/v1/auth/me" -s -o /dev/null -w "HTTP %{http_code}\n"
# 期望: 401（FRP 通 + API 通）

echo "=== 3. MinIO 头像 (FRP) ===" && curl -sk "https://agent.mnb-lab.cn/minio/microbubble/avatars/ce71e922b5b4491da9221df678a39acf.jpeg" -s -o /dev/null -w "HTTP %{http_code}\n"
# 期望: 200（MinIO 隧道通）

echo "=== 4. App /health ===" && curl "http://127.0.0.1:8000/health" -s -o /dev/null -w "HTTP %{http_code}\n"
# 期望: 200

echo "=== 5. Neo4j ===" && curl "http://127.0.0.1:7474/" -s -o /dev/null -w "HTTP %{http_code}\n"
# 期望: 200

echo "=== 6. Redis ===" && docker exec microbubble-agent-redis-1 redis-cli ping
# 期望: PONG

echo "=== 7. PostgreSQL ===" && docker exec microbubble-agent-db-1 pg_isready -U postgres
# 期望: accepting connections

echo "=== 8. Whisper (容器网络真实路径) ===" && docker exec microbubble-agent-app-1 python -c "
import urllib.request
print(urllib.request.urlopen('http://whisper:8002/health', timeout=5).read().decode()[:100])
"
# 期望: {"status":"healthy","model":"large-v3","device":"cuda"}
```

### 4.1 关键误解：**不要在主机测 whisper /health**

Whisper 容器**没映射** 8002 到主机（设计上只对 app 暴露），主机 `curl 127.0.0.1:8002/health` 永远返回 502。

正确做法：用 `docker exec` 进 app 容器通过容器网络 `whisper:8002` 访问（如上 §4 第 8 点）。

### 4.2 容器状态二次确认

```bash
docker compose ps
# 期望每个服务:
#   app             Up + (healthy)
#   celery-beat     Up
#   celery-worker   Up
#   db              Up + (healthy)
#   minio           Up + (healthy)
#   neo4j           Up + (healthy)
#   redis           Up + (healthy)
#   vision-mcp      Up (走 stdio，没 healthcheck)
#   whisper         Up
```

### 4.3 Celery worker [tasks] 完整性

```bash
docker logs microbubble-agent-celery-worker-1 2>&1 | grep -A 12 "^\[tasks\]$" | head -15
```

**期望看到 11 个任务**（少一个 = import 漏注册，运行时该任务会卡死）：
```
. app.services.agent_trace_tasks.persist_trace_task
. app.services.knowledge_evolution_tasks.evolve_knowledge_base
. app.services.knowledge_evolution_tasks.fuse_entities_task
. app.services.knowledge_evolution_tasks.health_check_knowledge_base
. app.services.knowledge_evolution_tasks.process_pending_gaps
. app.services.memory_service.maintenance_task
. app.services.orphan_meeting_cleanup.cleanup_orphan_meetings
. app.services.post_meeting_tasks.post_meeting_process
. app.services.reminder_service.process_reminders_task
. app.services.task_service.auto_purge_trash_task
. app.wechat.scheduler.run_proactive_checks
```

如果少了某个任务，看 [deploy.md](deploy.md) 的 Celery import 列表配置。

---

## 5. 常见故障排查

### 5.1 容器一直 Restarting

| 现象 | 根因 | 修复 |
|------|------|------|
| vision-mcp `Restarting (1) X seconds ago` | stdin 关闭（见 §3.7）| docker-compose 加 `stdin_open: true` + `tty: true` |
| celery-worker `Restarting` | `app/core/celery.py` 的 `imports` 列表漏了某个任务模块 | 补 imports 列表 |
| app `Restarting` | `app/main.py` 启动时抛 `ImportError` / `NameError` | `docker logs microbubble-agent-app-1 --tail 30` 看 traceback |

### 5.2 API 路由 404

**先看 OpenAPI**（决定性证据）：
```bash
curl -s "http://127.0.0.1:8000/openapi.json" | python -c "import json, sys; paths=json.load(sys.stdin)['paths']; print([p for p in paths if 'chat' in p])"
```

- 路径在 OpenAPI 里 → 客户端路径拼错
- 路径**不在** OpenAPI → 100% 是 §3.3 模块缓存问题，重启 `app` 容器

### 5.3 外网头像 502

按 §3.2 三步验证法排查：
1. `frpc.log` 最新时间 = 现在
2. `netstat :7000` 的 PID 是 frpc.exe
3. `curl https://agent.mnb-lab.cn/minio/...` 返回 200

如果 1+2 通过但 3 仍然 502 → 云服务器 Nginx 配 `minio` location 坏了，看 `/var/log/nginx/error.log`。

### 5.4 TTS 500

`/api/v1/voice/tts` 返回 500 → 99% 是 edge-tts 版本过期：

```bash
docker exec microbubble-agent-app-1 pip show edge-tts
# 期望: Version: 7.2.8 (或 >= 6.5.0 任意 < 8.0.0)
# 如果 6.1.9 → 升 edge-tts (Microsoft 更新了 TrustedClientToken)
```

### 5.5 应用白屏（前端）

| 现象 | 根因 | 修复 |
|------|------|------|
| `https://agent.mnb-lab.cn/manifest.<hash>.webmanifest` 返回 `application/octet-stream` | Nginx `types` 块在 server context 覆盖 mime.types（2026-06-13 整站事故）| 见 deploy.md 修复（`/etc/nginx/mime.types` 加 `application/manifest+json webmanifest;`）|
| 浏览器报 `bad-precaching-response` + SW 装不上 | vite-plugin-pwa 异步生成 sw.js 路径不同步 | `git add -f web/dist/sw.js`（dist 在 .gitignore）|
| 旧 HTML 被 SW 缓存 | SW 污染 cache | BUMP `SW_VERSION` 触发升级 + `caches.keys() + Promise.all(keys.map(caches.delete))` |

---

## 6. 关闭 / 重启

### 6.1 软重启（推荐，保留数据）

```bash
docker compose restart                # 重启所有容器
# 或只重启某个
docker compose restart app celery-worker
```

### 6.2 硬重启（解决僵尸进程 / 缓存问题）

```bash
docker compose down                   # 停容器（保留 volumes）
docker compose up -d                  # 重新启动

# 如要彻底清（含 volumes，会丢数据！慎用）
# docker compose down -v
```

### 6.3 关电脑前

```bash
# 1. 停 frpc.exe（避免 frps 服务端残留僵尸连接）
taskkill //F //IM frpc.exe

# 2. 停所有容器（更快关电脑）
docker compose down

# 3. 关 Docker Desktop
# GUI 退出 或 taskkill //F //IM "Docker Desktop.exe"
```

不按这个顺序，下次开机时：
- frpc.exe 启动后可能 zombie 化（clash 代理劫持 + frps run id 失效）
- Docker 容器数据没落盘可能丢部分

---

## 7. 启动脚本（参考）

如要把启动流固化到脚本，可参考 `frp/start.sh`（项目内已有的最小启动脚本）+ 在项目根加 `start.bat` / `start.sh`：

```bash
# start.sh (Git Bash / WSL)
#!/usr/bin/env bash
set -e

# 1. Docker Desktop
if ! docker info > /dev/null 2>&1; then
  echo "Starting Docker Desktop..."
  cmd //c start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  for i in {1..20}; do
    docker info > /dev/null 2>&1 && break
    sleep 3
  done
fi

# 2. Docker compose
docker compose up -d

# 3. FRP tunnel
cd frp
taskkill //F //IM frpc.exe 2>/dev/null || true
rm -f frpc.log
HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" NO_PROXY="*" no_proxy="*" \
  powershell -Command "Start-Process -FilePath '.\frpc.exe' -ArgumentList '-c','frpc.toml' -WindowStyle Hidden -WorkingDirectory '$(pwd -W)'"
cd ..

# 4. Wait + verify
sleep 10
echo "=== Verification ==="
bash scripts/verify-startup.sh  # 见 §4 验证清单脚本化的版本
```

---

## 8. 相关文档

- [deploy.md](deploy.md) — 云端部署 + 单机部署（含 frps 服务器配置）
- [README.md](../README.md) — 项目概览 + 技术栈
- [ROADMAP.md](../ROADMAP.md) — 版本历史 + 路线图
- [migration-5090-server.md](migration-5090-server.md) — 5090 服务器迁移专项

---

## 9. 启动铁律速查表

| # | 铁律 | 违反后果 |
|---|------|----------|
| 1 | frpc.exe 启动后必须验证 frpc.log + netstat | 进程活 ≠ 隧道通 |
| 2 | 改 API 路由后必须 `docker compose restart app` | 路由 404（模块缓存）|
| 3 | 容器内 `pip install` 必须同步改 requirements.txt | 下次 build 失效 |
| 4 | frpc 启动前必须清代理环境变量（4 个变量）| clash 劫持卡死 |
| 5 | `git clean -fdx` 部署前必须备份 .env* | webhook 挂 |
| 6 | 改 vite.config.js / sw.js 后必须 `git add -f web/dist/` | 线上 404 |
| 7 | Celery worker [tasks] 必须有 11 个 | 缺任务入队后永不消费 |
| 8 | 启动后必跑 8 点 curl 验证 | 502/401/404 无法定位 |
| 9 | Whisper /health 必须用 `docker exec` 进 app 测 | 主机测永远 502（端口未映射）|
| 10 | MCP stdio 容器必须 `stdin_open: true` | Restarting 死循环 |
