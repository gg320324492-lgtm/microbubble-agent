# W100 服务器关机恢复 runbook (2026-08-04)

## 触发

服务器+本地电脑**同时关机**后, 用户访问 https://agent.mnb-lab.cn → 前端 SPA 200, **7 个 API 全 502 Bad Gateway**:

```
GET /api/v1/notifications?unread_only=false&limit=50 502
GET /api/v1/members?page_size=100 502
GET /api/v1/meetings?status=recording&page_size=1 502
GET /api/v1/auth/me 502
GET /api/v1/dashboard/stats 502
GET /api/v1/tasks?page_size=100 502
```

## 关键认知: 服务器 vs 本地

| 部署目标 | 跑什么 |
|---|---|
| **云服务器** agent.mnb-lab.cn | 仅 Nginx (静态 dist) + FRP 服务端 + webhook.py + deploy-auto.sh |
| **本地电脑** (FRP 客户端) | 完整 8 services compose: app + db + redis + minio + celery-worker + celery-beat + celery-meeting-worker + neo4j + ollama + sensevoice + vision-mcp + pg-exporter + glitchtip-dev + langfuse + nginx |
| **隧道** | FRP (本地 app:8000 ↔ 服务器 127.0.0.1:8000) |

服务器 nginx `proxy_pass http://127.0.0.1:8000` = 服务器本地 8000 端口 = **FRP 隧道映射本地 app 8000**. 服务器**不跑**应用容器.

**结论**: 服务器 502 = 本地 app 没起 (FRP 隧道另一头断).

## 恢复步骤

### 步骤 1: 本地 docker daemon 就绪

```bash
# 检查 Docker Desktop 是否在跑 (com.docker.backend 进程)
powershell -Command "Get-Process -Name 'com.docker.backend' -ErrorAction SilentlyContinue"

# 若无, 启动 Docker Desktop GUI (开始菜单搜 Docker Desktop, 等 30-60s 图标变绿)
```

### 步骤 2: worktree 下补 .env

```bash
# 当前在 worktree 路径 (例如 festive-mcclintock-c1869d), .env 缺失
cp E:/microbubble-agent/.env E:/microbubble-agent/.claude/worktrees/<worktree-name>/.env
```

### 步骤 3: 启动 compose 全栈

```bash
# -p 强制项目名 (避免 worktree 目录名自动生成 project 名)
# --remove-orphans 清残留僵尸容器
docker compose -f docker-compose.yml -f docker-compose.dev.yml -p microbubble-agent up -d --remove-orphans
```

预期: 14 services 全部 Started. 若报 pg-exporter-dev-1 / glitchtip-dev-1 "container name already in use":

```bash
docker rm -f microbubble-agent-pg-exporter-dev-1 microbubble-agent-glitchtip-dev-1
# 再重跑 up
```

### 步骤 4: 验证容器网络 attach (易遗漏)

```bash
# app-1 可能漏 attach 到 default network, 这是 Docker Desktop 重启后的常见 bug
docker network inspect microbubble-agent_default --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{"\n"}}{{end}}'
# 必须看到 microbubble-agent-app-1

# 验证 DNS:
docker exec microbubble-agent-app-1 bash -c "getent hosts microbubble-agent-db-1"
# 必须返回 IP (e.g. 172.18.0.4)
```

若 app-1 漏 attach:

```bash
docker network connect --alias app microbubble-agent_default microbubble-agent-app-1
```

### 步骤 5: 若报 `address already in use` 端口绑定错误

```bash
# 1) 验证宿主端口实际空闲
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen"
# 应返回空 (没人监听)

# 2) 这是 Docker Desktop 端口转发 endpoint metadata 缓存, 终端无法修复
#    **必须用户操作**: 任务栏 Docker 图标 → 右键 → Quit Docker Desktop → 等待 5-10s → 重新启动 Docker Desktop
```

不修复的尝试:
- `Restart-Service com.docker.service` → Stop-Service 报"无法打开服务控制管理器数据库" (WSL2 backend 不依赖该 service)
- `Start-Process Docker Desktop.exe` → 启动进程但端口转发 iptables 没注册 (com.docker.service 仍 Stopped)
- 重启 Windows → 用户报告已试, 无效

### 步骤 6: 验证恢复

```bash
# 本地
curl -sk -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health
# 期望: 200

# 服务器
for ep in health api/v1/auth/me api/v1/members "api/v1/meetings?status=recording&page_size=1" "api/v1/tasks?page_size=100" "api/v1/notifications?unread_only=false&limit=50" api/v1/dashboard/stats; do
  curl -sk -o /dev/null -w "$ep → %{http_code}\n" "https://agent.mnb-lab.cn/$ep"
done
# 期望: /health=200, 其余=401 (不再 502)
```

### 步骤 7: 5 件套守恒验证

```bash
docker exec microbubble-agent-app-1 python -m alembic heads | head -3
# 期望: 097_meeting_processing_persistence (head)

docker exec microbubble-agent-app-1 celery -A app.core.celery inspect ping --timeout 5
# 期望: pong + OK
```

## 关键铁律

### 类 20.138 — Docker Desktop 端口转发缓存

**触发**: 服务器 502, 本地 `docker ps | grep app` 显示 Up, 但 `curl :8000/health` 000 或 `app` 启动报 `socket.gaierror Temporary failure in name resolution`, 伴随 `failed to bind host port 127.0.0.1:8000/tcp: address already in use`.

**诊断**:
```bash
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen"
docker exec microbubble-agent-app-1 bash -c "getent hosts microbubble-agent-db-1"
docker network inspect microbubble-agent_default --format '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}'
```

**修复**: **用户操作**, 终端无法修复 — 任务栏 Docker 图标右键 → Quit → 重新启动.

### 类 20.139 — 服务器 502 = 本地 app 没起

服务器 nginx `proxy_pass http://127.0.0.1:8000` 经 FRP 隧道指向**本地电脑** app 8000. 服务器**不跑**应用容器. 服务器 502 永远不是服务器问题, 是**本地电脑** app 问题. 排查入口是**本地**, 不是服务器.

### 类 20.140 — 容器可能漏 attach default network

Docker Desktop 重启后, `docker compose up -d` 起的容器**有时**不 attach 到 default network. 表现: `getent hosts <other-container>` 返回空, `/dev/tcp/<ip>/<port>` 报 "Network is unreachable". 修复: `docker network connect --alias <name> <network> <container>`. 预防: up 后**必须**跑 `docker network inspect` 验证 app 在列表.

### 类 20.141 — pgvector 扩展不持久化

db 容器 bind-mount `./data/postgres` 但 pgvector extension 安装在 `/usr/local/share/postgresql/extension/` (镜像层), 容器重建时丢失. 恢复需手工重装:

```bash
docker exec microbubble-agent-db-1 sh -c '
  apk add --no-cache postgresql16-dev gcc git make musl-dev
  cd /tmp && git clone --depth 1 --branch v0.7.0 https://github.com/pgvector/pgvector.git
  cd pgvector && make && make install
  su postgres -c "pg_ctl -D /var/lib/postgresql/data restart -m fast"
  psql -U postgres -d microbubble -c "CREATE EXTENSION IF NOT EXISTS vector;"
'
```

**预防**: `app/Dockerfile` 应继承 `pgvector/pgvector:pg16-alpine` 镜像 (已有 pgvector); 或本地 db image build 后 `docker commit` 持久化.

### 类 20.142 — app image 与 code drift (本事故最隐蔽根因)

`docker compose up -d` 起的容器用 `microbubble-agent-app:latest` 镜像, 该镜像 build 时间**早于**当前 worktree commit. 容器内 `alembic/versions/` 看不到新加的 migration (092-097 都在, 但镜像里没). 表现: `alembic heads` 只显示 091 但代码 HEAD 是 097, DB 表数 50 (期望 64+).

**修复**:
```bash
docker cp alembic/versions/09{2,3,4,5,6,7}_*.py microbubble-agent-app-1:/app/alembic/versions/
docker exec microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic stamp 091  # 当前 DB 实际状态
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -c "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);"
docker exec microbubble-agent-app-1 alembic upgrade head
docker commit --change 'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]' microbubble-agent-app-1 microbubble-agent-app:latest
```

**预防**:
- 主拍合并新 migration 后必须 `docker build` 重新 build image
- 或运行 `bash scripts/auto-deploy.sh` (含 `docker cp + __pycache__ clear + docker restart` 流程)
- bind mount `./alembic` 到容器 (类似 `./app` 的现有做法) 让 migration 文件实时同步

## 不要做的

- ❌ 不要 SSH 进服务器重启 compose — 服务器没 app 容器, 重启无效
- ❌ 不要 `apt install nginx` 重装服务器 nginx — 配置没问题, 只是上游断
- ❌ 不要 `git pull` 在服务器上 — 服务器部署靠 webhook, 不靠 git pull
- ❌ 不要重启 Docker service — WSL2 backend 不依赖 com.docker.service, 操作无效
- ❌ 不要 `netsh winsock reset` / `netsh int ip reset` — WSL2 backend 不走 Windows 网络栈

## §8 完全自愈 (W2 +N, 类 20.143)

**目的**: 电脑开机 → 用户登录 → 自动恢复服务, 全程**无需人工干预**.

### 触发链路

```
电脑开机 → Windows 启动 → Docker Desktop 自动启动 (WSL2 backend)
↓
用户登录桌面 (Winlogon EventID=7002)
↓
schtasks DELAY 2 分钟 (给 Docker daemon + WSL2 init 充分时间)
↓
schtasks 触发 scripts/auto-recovery-eventlog.ps1
↓
智能等 docker info (5 分钟 timeout)
↓
跑 scripts/restart-recovery-after-gui-restart.sh (7 步)
↓
如果端口冲突 → 自动 Quit + Start Docker Desktop GUI (类 20.138 自愈)
↓
TTS 反馈 "MicroBubble fully restored" 或 "recovery failed"
↓
写 logs/auto-recovery/auto-recovery-YYYYMMDD.log JSON 日志
```

### 安装步骤 (一次)

```powershell
# 管理员 PowerShell
E:\microbubble-agent\scripts\install-auto-recovery.bat
```

或手动:

```bat
schtasks /Create /TN "MicroBubble-Auto-Recovery" ^
  /TR "\"E:\microbubble-agent\scripts\auto-recovery-eventlog.ps1\"" ^
  /SC ONEVENT ^
  /EC Application ^
  /MO "*[System[Provider[@Name='Microsoft-Windows-Winlogon']] and EventID=7002]" ^
  /DELAY 0002:00 ^
  /RL HIGHEST ^
  /F
```

### 验证任务注册

```bat
schtasks /Query /TN "MicroBubble-Auto-Recovery" /V /FO LIST
```

### 手动触发 (测试用)

```bat
schtasks /Run /TN "MicroBubble-Auto-Recovery"
```

### 查看日志

```powershell
Get-Content E:\microbubble-agent\logs\auto-recovery\auto-recovery-20260804.log
```

### 卸载

```bat
schtasks /Delete /TN "MicroBubble-Auto-Recovery" /F
```

### 触发器选择理由 (类 20.143)

**实测探索 (2026-08-04)**:
- ❌ Application log **没有** "Docker Desktop" provider (Docker Desktop 通过 WSL2 backend 运行, 不写 EventLog)
- ❌ System log 只有 Service Control Manager 7045 (一次性 service 安装, 不触发)
- ✅ 唯一可靠: **Winlogon EventID=7002** (用户登录 session 创建) + DELAY 2 分钟

锁屏唤醒**不**触发 (语义正确, 不需要恢复)

## 关联文档

- `memory/w100-meeting-pipeline-restart-2026-08-04.md` (本事故 memory)
- `docs/deploy.md` (主部署文档)
- `scripts/auto-deploy.sh` (本地 merge 后增量同步, 含 `docker cp + __pycache__ clear + docker restart`)
- `scripts/webhook.py` (服务器 GitHub webhook 监听 → deploy-auto.sh)
- `scripts/deploy-auto.sh` (服务器 git pull + docker restart)
- `scripts/deploy-cloud.sh` (服务器初始化, 仅 Nginx + FRP 服务端)