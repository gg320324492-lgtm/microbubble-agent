# W-N-GLITCH glitchtip-dev-1 重启循环修复尝试 (W-N-GLITCH +1, 2026-08-05)

**任务**: W-N-GLITCH glitchtip-dev-1 重启循环修复尝试
**派工锚点**: W-N-GLITCH +1
**派工 brief base**: `74d1a965e` (W-N-DEPLOY 收口)
**修复范围**: docs/memory 范畴 (派工 brief 严禁改 docker-compose.yml)
**决策**: 选项 (b) 仅写决策文档留 future PR

---

## 1. 现状 (2026-08-05)

```
docker ps -a | grep glitch
d4b48d1be102  microbubble-agent-glitchtip-dev-1  Restarting (1) 16 seconds ago   28 hours ago
48373813dee7  microbubble-agent-glitchtip-1       Exited (1) 28 hours ago         6 days ago
```

- `glitchtip-dev-1` (dev 版): `Restarting (1)`, `restartCount=936`, 每次 restart 间隔 ~10-15s
- `glitchtip-1` (prod 版): `Exited (1) 28 hours ago`, 已被主拍明确停用
- W-N-DEPLOY 报告: 10 healthy + 1 glitchtip-dev-1 Restarting (旁路)

## 2. 根因定位 (Step 1-3 实施)

### 2.1 Step 1: `docker ps -a` 完整状态 (派工 brief Step 1)

完成. 见上节. 关键字段: `Restarting (1)`, `restartCount=936`.

### 2.2 Step 2: `docker logs` 错误原因 (派工 brief Step 2)

完成. 关键 stack trace:

```
django.db.utils.OperationalError: pool error: Error occurred while creating a new object:
  error connecting to server -> error connecting to server ->
  failed to lookup address information: Temporary failure in name resolution
SQL: SHOW server_version_num
params: []
```

**根因**: glitchtip 启动 Django migrate, 尝试连接 PostgreSQL (`DATABASE_URL=postgresql://postgres:microbubble2026@db:5432/glitchtip`), **DNS 解析 `db` 失败** (Temporary failure in name resolution).

### 2.3 Step 3: docker-compose 配置 (派工 brief Step 3)

文件 `E:\microbubble-agent\docker-compose.dev.yml` lines 91-113:

```yaml
glitchtip:
  image: glitchtip/glitchtip:6.2.2
  container_name: microbubble-agent-glitchtip-dev-1
  environment:
    DATABASE_URL: "postgresql://postgres:${POSTGRES_PASSWORD:-microbubble2026}@db:5432/glitchtip"
    VALKEY_URL: "redis://redis:6379/1"
    SECRET_KEY: "${GLITCHTIP_SECRET_KEY:-dev-glitchtip-change-me}"
    PORT: "8000"
    GLITCHTIP_DOMAIN: "${GLITCHTIP_DOMAIN:-http://localhost:8001}"
    EMAIL_ENABLED: "False"
    SERVER_ROLE: "all_in_one"
  ports:
    - "8001:8000"
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy
  networks:
    - default
  restart: unless-stopped
```

**配置审视**:
- 配置语法正确 ✅ (`networks: [default]`)
- `depends_on` 有 `service_healthy` 守卫 ✅
- `restart: unless-stopped` 触发 restart loop ✅
- **配置本身是对的**, 但运行时容器**没有**按配置 attach 到 default network

### 2.4 网络验证 (派工 Step 1-3 旁支)

```bash
docker inspect microbubble-agent-glitchtip-dev-1 --format '{{json .NetworkSettings.Networks}}'
# 输出: {}  ← 容器网络配置为空!
```

对照 default network 当前成员:

```bash
docker network inspect microbubble-agent_default --format '...containers...'
# 10 个成员: nginx, ollama, celery-worker, redis, celery-meeting-worker, app, db, minio, sensevoice, celery-beat
# 注意: glitchtip-dev-1 不在列表中! ⚠️
```

**旁证**: `docker exec microbubble-agent-app-1 getent hosts db` 返回 `172.18.0.2` (app 在 default network, 解析正常). glitchtip-dev-1 若在 default network 上, `SHOW server_version_num` 不会 DNS 失败.

## 3. 根因总结 (派工 brief 类 20.140 实战)

**类 20.140 (W100 +N) 实战复现**:
> Docker Desktop 重启后 `docker compose up -d` 起的容器**有时**漏 attach 到 default network. 表现: `getent hosts <other> ` 返回空, 触发 "Network is unreachable" / "Temporary failure in name resolution". 修复: `docker network connect --alias <name> <network> <container>`.

**本案例具体表现**:
- `docker compose up -d glitchtip` (在某次 docker desktop 重启后) 启动时, glitchtip 容器**未**成功 attach 到 `microbubble-agent_default` network
- `docker network inspect microbubble-agent_default` 列表里**没有** glitchtip
- glitchtip 容器 `NetworkSettings.Networks = {}` (空 map)
- 启动后 Django 尝试 `db:5432` / `redis:6379` DNS 解析 → fail → exit 1 → restart loop
- 跑了 `restartCount=936` 次 (实测)

**前因 (W100 +N 沉淀)**: 跟 `docker-compose v1 vs v2` 无关 (本机 Docker Compose v5.3.1), 是 Docker Desktop for Windows WSL2 backend 端口转发/up 阶段的 race condition.

## 4. 修复尝试 (派工 brief Step 4)

### 4.1 派工 brief 严禁清单核对

- ❌ 严禁改 docker-compose.yml ✅ (本任务 0 改)
- ❌ 严禁改 docker-compose.dev.yml ✅ (本任务 0 改)
- ❌ 严禁改 alembic/versions/ ✅ (本任务 0 改)
- ❌ 严禁重启 glitchtip 容器 (派工 brief 严禁, 主拍决策) ✅ (本任务 0 操作)
- ❌ 严禁改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits ✅ (本任务 0 改)

### 4.2 选项 (a) 评估: 修复配置

派工 brief 严禁改 docker-compose.yml, 即使想改也无法实施. 唯一合规运行时修补:

```bash
# 把容器重新接回 default network (类 20.140 沉淀解法)
docker network connect \
  --alias glitchtip --alias db --alias redis \
  microbubble-agent_default \
  microbubble-agent-glitchtip-dev-1
```

**但**: 派工 brief 严禁"重启 glitchtip 容器", `docker network connect` 不重启容器 (attached 状态会保留), 但运行中 glitchtip 仍会因 DNS 失败而在下一次 crash 前无法工作. 实际实施需 `docker restart`, 派工 brief 严禁.

**结论**: 选项 (a) 在派工 brief 严禁清单下**不可执行**. (即使技术可行, 也违规)

### 4.3 选项 (b) 决策: 仅写决策文档留 future PR

**本任务选择性 (b)**: 严格只在 docs/memory 范畴, 0 production code 改动.

**派工 brief 2 选 1 中的 (b) 实施**:

1. **未来 PR 修复方案 (主拍决策)**: 在后续 W-N 系列 PR 中, 由主拍决策:
   - 方案 A (推荐): 修改 `docker-compose.dev.yml` 给 glitchtip service 加 `aliases: [glitchtip, db, redis]` (关键: glitchtip 需要解析 `db` 和 `redis`, 反向可能不需要, 单向 `aliases: [glitchtip]` 即可)
   - 方案 B: 跑 `docker compose down && docker compose up -d glitchtip` (不是 `docker restart`, 完整 down+up 重新 attach network)
   - 方案 C: 一次性脚本 `scripts/glitchtip-reattach-network.sh` (类 20.140 实战沉淀, 跑 `docker network connect --alias <name> <network> <container>`)
   - 方案 D: 重启 Docker Desktop GUI (类 20.138 套路, Quit+Start, 慎用, 5-10min)

2. **Glitchtip 库存在性核查 (W91-X-20 沉淀)**: W91-X-20 已建 `glitchtip` PostgreSQL 库, 主运行时 db:5432 仍可访问 (W-N-DEPLOY 10 healthy 已验证). 不需重建库.

### 4.4 阻塞评估

- glitchtip-dev-1 restart loop **不影响** W-N-DEPLOY 10 healthy 核心服务
- glitchtip 在部署中标记为**旁路** (W-N-DEPLOY 报告明确)
- W-N-DEPLOY 收口结论: 部署**可用**, glitchtip **不阻塞**
- W-N-GLITCH 本任务选择性**不修复**, 留 future PR

## 5. 类 20 实战沉淀

### 5.1 类 20.140 实战 (本任务)

- W-N-GLITCH +1 复现 W100 +N 沉淀: "Docker Desktop 重启后 `docker compose up -d` 起的容器**有时**漏 attach default network"
- 排查路径: `docker logs` → Django OperationalError → 关键短语 "Temporary failure in name resolution" → `docker inspect NetworkSettings.Networks` → `{}` → 类 20.140 命中
- 修复 4 选 1 (主拍决策): 改 compose / down+up / 脚本 attach / GUI 重启
- 派工 brief 严禁改 compose + 严禁重启 → 选 (b) 文档化

### 5.2 类 20.101 实战 (W91-X-20 沉淀, 本任务沿用)

- docker service crash 排查必 4 件: docker logs / docker inspect / env / db 状态
- 本任务 4 件齐: ✅ logs (根因 DNS) / ✅ inspect (Networks=`{}`) / ✅ env (DATABASE_URL 正确) / ✅ db 状态 (db healthy, app 解析 `db → 172.18.0.2` 正常)

### 5.3 类 20.138 实战 (W100 +N 沉淀, 旁路)

- Docker Desktop 端口转发 endpoint metadata 缓存只能 GUI Quit+Start 清掉
- W-N-GLITCH +1 旁路: 即使重启容器, 下次 `docker compose up -d` 仍可能漏 attach, 根因在 WSL2 backend, 不是容器
- 修复"真正的"类 20.140 需改 compose (方案 A) 或 down+up (方案 B), 派工 brief 严禁不实施

## 6. 5 件套守恒 (W-N-GLITCH +2 收口实测)

1. ✅ alembic 1 head 守恒: 本任务 0 alembic 改动, 沿用 W-N-DEPLOY 097/098 状态
2. ⚠️ pytest 套件: 本任务不强求重跑, 沿用 W-N-DEPLOY baseline (主拍决策)
3. ⚠️ PWA build: 本任务 0 frontend 改动, 沿用 W-N-DEPLOY baseline
4. ✅ 0 production code 改动铁律: 仅 docs/memory, 0 改 app/ web/src/ alembic/ docker-compose
5. ✅ 锚点范式: W-N-GLITCH +0 起步 + +1 修复尝试 + +2 收口 = 3 commits 估, 实测据实

## 7. 决策表

| 维度 | 决策 | 理由 |
|------|------|------|
| 修复路径 | 选项 (b) 仅写决策文档 | 派工 brief 严禁改 docker-compose.yml + 严禁重启容器 |
| 提交范围 | 仅 docs/memory | 0 production code 改动守恒 |
| 阻塞评估 | 旁路, 不阻塞部署 | W-N-DEPLOY 报告 10 healthy 已确认 |
| Future PR 修复 | 主拍决策, 留 W-N-GLITCH +N 续 | 4 方案 A/B/C/D 列在 §4.3 |
| 类 20.140 实战沉淀 | 5 件套守恒 + 排查 4 件 | 本任务沉淀完整 |

## 8. 联动沉淀

- 起步: `memory/w-n-glitchtip-fix-startup-2026-08-05.md` (W-N-GLITCH +0)
- 决策: `docs/w-n-glitchtip-fix-attempt-2026-08-05.md` (本文件, W-N-GLITCH +1)
- 收口: `memory/w-n-glitchtip-fix-closure-2026-08-05.md` (W-N-GLITCH +2, pending)
- 派工 brief 锚点: W-N-GLITCH +0..+2 (3 commits 估, 实际据实)
- 关联: W91-X-20 实战 (W91-X-20 memory + glitchtip-ensure-db.sh)
- 关联: W100 +N 类 20.140 沉淀 (W100-meeting-pipeline-restart 段)
- 关联: W-N-DEPLOY 收口 (W-N-DEPLOY +0/+1/+2, base head 74d1a965e)
