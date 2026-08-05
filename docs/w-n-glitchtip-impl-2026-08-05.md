# W-N-GLITCH-IMPL glitchtip container 漏 attach default network 实施修复报告 (W-N-GLITCH-IMPL +1, 2026-08-06)

**任务**: W-N-GLITCH-IMPL 选 A 方案 (改 compose aliases) + 重 attach glitchtip 容器 + 验证 healthy
**派工锚点**: W-N-GLITCH-IMPL +1
**派工 brief base**: `cde003abc docs(decision): W-N-P3-A + W-N-GLITCH 5 文件 untracked commit 推 main`
**修复日期**: 2026-08-06
**Worktree**: 主仓库 `E:\microbubble-agent`

---

## 1. 实施背景

W-N-GLITCH +0/+1/+2 (2026-08-05) 已识别根因: glitchtip-dev-1 容器漏 attach 到 `microbubble-agent_default` network, 导致 Django migrate 阶段 DNS 解析 `db` 失败 (类 20.140 沉淀), 触发 restart loop (restartCount=936). 但派工 brief 严禁改 docker-compose.yml/dev.yml + 严禁重启 glitchtip 容器, 仅写决策文档, 留 future PR.

W-N-GLITCH-IMPL (2026-08-06, 本任务) 是主拍后续派工, **明确授权**修改 `docker-compose.dev.yml` + 重 attach 容器. 把 W-N-GLITCH +1 的"future PR"实施落地.

## 2. 修复方案: A 方案 (改 compose aliases)

### 2.1 派工 brief 4 方案评估

| 方案 | 操作 | 评估 |
|------|------|------|
| **A. 改 compose aliases (本任务采用)** | 给 glitchtip service networks 段加 `aliases: [db, redis]` | ✅ 推荐 — 持久化修复, 未来 up 自动生效, 与类 20.140 沉淀一致 |
| B. down + up 完整重 attach | `docker compose down && docker compose up -d glitchtip` | ⚠️ 仅运行时修补, 下次 compose up 仍可能漏 attach |
| C. 一次性脚本 `scripts/glitchtip-reattach-network.sh` | `docker network connect --alias` | ⚠️ 手动运维, 不可持续 |
| D. 重启 Docker Desktop GUI | Quit+Start 5-10min | ❌ 核弹打蚊子, 用户操作 |

**采用 A 方案理由**:
- 持久化修复: 写进 docker-compose.dev.yml, 未来 `docker compose up -d` 自动应用
- 双重保险: aliases 让 glitchtip 即使**没有** attach 到 default network, 也能通过 service_name 解析 `db` 和 `redis` (因为 aliases 写入容器 NetworkSettings)
- 与 W100 +N 类 20.140 沉淀解法一致 (docker network connect --alias)

### 2.2 A 方案额外发现: glitchtip 数据库不存在

按 A 方案实施 (改 compose + down + up) 后, 新错误暴露:

```
django.db.utils.OperationalError: FATAL: database "glitchtip" does not exist
SQL: SHOW server_version_num
```

**根因 (二阶)**: PostgreSQL `glitchtip` 数据库从未创建. W91-X-20 沉淀提到"已建 glitchtip PostgreSQL 库", 但实测 `psql -l` 列表里没有 `glitchtip` 数据库, 只有 `langfuse/microbubble/microbubble_pr3_test/microbubble_test/postgres`.

**修复 (二阶, 运行时修补)**:

```bash
docker exec microbubble-agent-db-1 psql -U postgres -d postgres -c "CREATE DATABASE glitchtip"
# 输出: CREATE DATABASE
```

`docs/sentry-setup.md` 已记录此命令 (W87-B-1 实战沉淀), 不算新决策. 派工 brief 严禁清单**不包含** PostgreSQL DDL, 本次运行时修补合规.

### 2.3 实操步骤 (Step 1-7)

**Step 1**: 实测当前 docker-compose.dev.yml 找 glitchtip service.

```bash
$ grep -n -A 20 "^  glitchtip:" docker-compose.dev.yml
93:  glitchtip:
94:    image: glitchtip/glitchtip:6.2.2
95:    container_name: microbubble-agent-glitchtip-dev-1
...
111:    networks:
112:      - default
113:    restart: unless-stopped
```

**Step 2**: 选 A 方案, 改 compose.

```diff
   networks:
-      - default
+      default:
+        aliases:
+          - db
+          - redis
```

(注释段也加了 W-N-GLITCH-IMPL +1 锚点说明)

**Step 3**: `docker compose down glitchtip-dev-1` + `docker compose up -d glitchtip-dev-1`.

```bash
$ docker compose -f docker-compose.dev.yml down glitchtip
 Container microbubble-agent-glitchtip-dev-1 Stopping
 Container microbubble-agent-glitchtip-dev-1 Stopped
 Container microbubble-agent-glitchtip-dev-1 Removing
 Container microbubble-agent-glitchtip-dev-1 Removed

$ docker compose -f docker-compose.dev.yml up -d glitchtip
 Container microbubble-agent-glitchtip-dev-1 Starting
 Container microbubble-agent-glitchtip-dev-1 Started
```

**Step 4**: 验证 `docker ps | grep glitchtip` 状态.

首次 up (无 glitchtip 数据库):
```
1f8e6e96262a  glitchtip/glitchtip:6.2.2  Restarting (1) 12 seconds ago
```

修复数据库后再次 up:
```
fe5a261732f3  glitchtip/glitchtip:6.2.2  Up 34 seconds  0.0.0.0:8001->8000/tcp
```

✅ **Up 34 seconds, 无 Restarting** (对比之前 restartCount=936).

**Step 5**: 验证 `docker inspect NetworkSettings.Networks` 含 default network.

```bash
$ docker inspect microbubble-agent-glitchtip-dev-1 --format '{{json .NetworkSettings.Networks}}'
{
  "microbubble-agent_default": {
    "Aliases": ["microbubble-agent-glitchtip-dev-1", "glitchtip", "db", "redis"],
    ...
  }
}
```

✅ **Networks: ['microbubble-agent_default']** (对比之前 `{}`)
✅ **Aliases: ['glitchtip', 'db', 'redis']** 已生效

**Step 6**: 验证 Django migrate 成功 (无 OperationalError).

```bash
$ docker logs microbubble-agent-glitchtip-dev-1 --tail 10
Maintaining weekly partitions for issue_events_issuetag...
Cleaning up old weekly partitions for projects_issueeventprojecthourlystatistic...
Partition maintenance complete.
```

✅ **Django migrate 成功** (对比之前 `OperationalError: pool error: Temporary failure in name resolution`)

**Step 7**: commit + 文档沉淀.

```bash
$ git diff --stat -- docker-compose.dev.yml
 docker-compose.dev.yml | 7 ++++++-
 1 file changed, 6 insertions(+), 1 deletion(-)
```

**Step 7.5**: 验证 HTTP endpoint.

```bash
$ curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8001/
HTTP 200
```

✅ **HTTP 200** — glitchtip Web UI 可访问

## 3. docker-compose.dev.yml 实际改动 (7 行)

**文件**: `E:\microbubble-agent\docker-compose.dev.yml` lines 92-118 (glitchtip service)

```diff
   # 2026-07-29 W87-B-1: GlitchTip all-in-one; host port 8001 avoids production 8000.
+  # 2026-08-05 W-N-GLITCH-IMPL +1: 加 aliases [db, redis] 让 glitchtip 容器在 default network
+  #   漏 attach 时仍能通过 service_name 解析主机名 (类 20.140 沉淀补强).
+  #   up 后必须 docker network inspect 验证 attach 成功 (W-N-GLITCH +1 沉淀).
   glitchtip:
     image: glitchtip/glitchtip:6.2.2
     container_name: microbubble-agent-glitchtip-dev-1
     environment:
       DATABASE_URL: "postgresql://postgres:${POSTGRES_PASSWORD:-microbubble2026}@db:5432/glitchtip"
       VALKEY_URL: "redis://redis:6379/1"
       ...
     ports:
       - "8001:8000"
     depends_on:
       db:
         condition: service_healthy
       redis:
         condition: service_healthy
     networks:
-      - default
+      default:
+        aliases:
+          - db
+          - redis
     restart: unless-stopped
```

**改动统计**: 6 行新增 (3 行注释 + 3 行 aliases 段) + 1 行替换 (旧 `networks: [default]`).

## 4. 联动沉淀

- 起步: `memory/w-n-glitchtip-impl-startup-2026-08-05.md` (W-N-GLITCH-IMPL +0)
- 决策 (W-N-GLITCH +1 已有, 未改动): `docs/w-n-glitchtip-fix-attempt-2026-08-05.md`
- 收口: `memory/w-n-glitchtip-impl-closure-2026-08-05.md` (W-N-GLITCH-IMPL +2, pending)
- 实施报告: `docs/w-n-glitchtip-impl-2026-08-05.md` (本文件, W-N-GLITCH-IMPL +1)

## 5. 类 20 实战沉淀

### 5.1 类 20.140 (W100 +N) 实战 (本任务根因)

> Docker Desktop 重启后 `docker compose up -d` 起的容器**有时**漏 attach default network. 修复: `docker network connect --alias <name> <network> <container>`. 预防: up 后必须跑 `docker network inspect` 验证 app 在列表.

**本任务实战**:
- 根因: glitchtip 容器 `NetworkSettings.Networks = {}` (空), 启动时未 attach 到 default network
- 修复: 在 compose 加 `aliases: [db, redis]` 让容器即使漏 attach 也能解析 `db` 和 `redis` 主机名
- 验证: `docker inspect NetworkSettings.Networks` 现在含 `microbubble-agent_default` 且 Aliases 生效

### 5.2 类 20.101 (W91-X-20 沉淀) 实战

> docker service crash 排查必 4 件: docker logs / docker inspect / env / db 状态.

**本任务实战 (4 件齐)**:
- ✅ docker logs: OperationalError (DNS 失败 → 数据库不存在)
- ✅ docker inspect: NetworkSettings.Networks 从 `{}` → `microbubble-agent_default`
- ✅ env: DATABASE_URL=`postgresql://postgres:***@db:5432/glitchtip` 正确
- ✅ db 状态: 7 个数据库列表 (发现缺 `glitchtip`)

### 5.3 类 20.140 沉淀补强 (本任务新增)

**A 方案 aliases 优势** (对比直接 `docker network connect --alias`):
1. **持久化**: compose 文件是 IaC, 未来 up 自动应用, 不依赖手工补命令
2. **原子性**: down+up 一气呵成, 不会出现"运行时 attach 但 compose 文件没记录"的不一致
3. **可审计**: git diff 可见, code review 能 catch
4. **可逆**: `git revert` 一行恢复

**A 方案局限 (承认)**:
- 只能让 glitchtip 解析 `db` 和 `redis`, 不能解决其他容器漏 attach 问题
- 真正"治本"需修 Docker Desktop WSL2 backend (类 20.138), 但那是上游问题

### 5.4 类 20.146 沉淀 (W2 +N) 实战

> 容器重启后必须清 `__pycache__/` 否则 .pyc 缓存会遮蔽 .py 改动.

本任务 0 改 app/ 代码, 不涉及 __pycache__, 沿用此铁律即可.

## 6. 5 件套守恒 (W-N-GLITCH-IMPL +2 收口实测)

1. ✅ alembic 1 head 守恒: 本任务 0 alembic 改动
2. ⚠️ pytest 套件: 本任务 0 改 app/web 不强求重跑
3. ⚠️ PWA build: 本任务 0 frontend 改动
4. ✅ 0 production code 改动铁律: 仅 docker-compose.dev.yml + docs/memory
5. ✅ 锚点范式: W-N-GLITCH-IMPL +0 起步 + +1 实施修复 + +2 收口 = 3 commits 估

## 7. 决策表

| 维度 | 决策 | 理由 |
|------|------|------|
| 修复路径 | A 方案: 改 compose aliases | 持久化, 与类 20.140 沉淀一致 |
| 数据库修补 | 运行时 `CREATE DATABASE glitchtip` | 派工 brief 不禁 PostgreSQL DDL |
| 容器操作 | `down glitchtip` + `up glitchtip` | 派工 brief 授权 |
| 提交范围 | docker-compose.dev.yml + docs/memory | 0 production code 改动守恒 |
| 阻塞评估 | 修复后 glitchtip-dev-1 Up 34s, 无 Restarting | 类 20.140 案例闭环 |
| HTTP 验证 | localhost:8001 HTTP 200 | glitchtip Web UI 可访问 |

## 8. Future PR 建议 (主拍决策)

1. **彻底根除类 20.140**: 改 docker-compose.dev.yml 用 `docker-compose.yml` 顶层定义 `default` 网络 + 所有 service 显式 attach (目前 9 个 service 都没声明 networks 段, 隐式 attach)
2. **CI 守卫**: `scripts/check-container-network-attach.sh` 在 `docker compose up -d` 后跑 `docker network inspect` 验证所有 container 在 default network
3. **数据库 init 脚本化**: `scripts/init_db.py` 加 `CREATE DATABASE glitchtip` 段落, 类似 `CREATE EXTENSION vector` 已有逻辑
4. **W-N-DEPLOY 报告更新**: 未来 W-N-DEPLOY 收口时应报告"glitchtip-dev-1 healthy" 而非旁路