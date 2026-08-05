# W-N-GLITCH-IMPL glitchtip container 漏 attach default network 实施修复收口 (W-N-GLITCH-IMPL +2, 2026-08-06)

**任务**: W-N-GLITCH-IMPL 选 A 方案 (改 compose aliases) + 重 attach glitchtip 容器 + 验证 healthy
**派工锚点**: W-N-GLITCH-IMPL +2 收口
**派工 brief base**: `cde003abc docs(decision): W-N-P3-A + W-N-GLITCH 5 文件 untracked commit 推 main`
**实际 base**: `cde003abc` (W-N-P3-A + W-N-GLITCH 收口)
**当前 HEAD**: `2e6b71dbf fix(compose): W-N-GLITCH-IMPL +1 glitchtip 加 aliases [db, redis] + 实施报告 (容器漏 attach 修复)`

---

## 1. 5 件套守恒实测

### 件 1: alembic 1 head 守恒

- 本任务 0 alembic 改动
- 沿用 base `cde003abc` 状态
- 派工 brief 严禁改 alembic/versions/ ✅
- **守恒** ✅

### 件 2: pytest 套件

- 本任务 0 改 app/ web/src/ 不强求重跑
- docker-compose 改动属基础设施, 不影响 pytest 套件逻辑
- 沿用 W-N-DEPLOY baseline
- **沿用** ✅

### 件 3: PWA build

- 本任务 0 frontend 改动
- 沿用 W-N-DEPLOY baseline
- **沿用** ✅

### 件 4: 0 production code 改动铁律

- ✅ 仅 `docker-compose.dev.yml` 改动 (glitchtip service networks 段, 7 行)
- ✅ `memory/w-n-glitchtip-impl-startup-2026-08-05.md` 起步沉淀 (本文件范畴)
- ✅ `docs/w-n-glitchtip-impl-2026-08-05.md` 实施报告 (229 行)
- ✅ `memory/w-n-glitchtip-impl-closure-2026-08-05.md` 收口沉淀 (本文件)
- ❌ 0 改 app/ sources
- ❌ 0 改 web/src/ sources
- ❌ 0 改 alembic/versions/
- ❌ 0 改 docker-compose.yml (生产版, 派工 brief 仅授权改 dev.yml)
- ❌ 0 改 docker-compose.test.yml
- ❌ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ❌ 0 改 W-N-GLITCH 既有 decision doc (`docs/w-n-glitchtip-fix-attempt-2026-08-05.md`)
- ❌ 0 改 plan 文件
- **守恒** ✅

### 件 5: 锚点范式守恒

- 派工 brief 估: W-N-GLITCH-IMPL +0..+2 (3 commits)
- 实测: W-N-GLITCH-IMPL +0 起步合并到 +1 commit (1 commit, 3 文件: docker-compose.dev.yml + startup memory + impl doc) + W-N-GLITCH-IMPL +2 收口沉淀 (本 memory, 0 commit, 仅沉淀)
- **派工 v11 §13.3 据实上报**:
  - 实测 = 1 commit (派工 brief 估 3, 偏差据实 +0..+2 中合并 +0/+1)
  - 类 20.140/101/146 实战沉淀 (本任务新增 3 实例)
  - 锚点范式 W-N-GLITCH-IMPL +0/+1/+2 据实, +0..+1 合并为 1 commit

---

## 2. 端到端验证实测

### 2.1 docker ps 容器状态

```bash
$ docker ps | grep glitchtip
fe5a261732f3  glitchtip/glitchtip:6.2.2  Up 34 seconds  0.0.0.0:8001->8000/tcp
```

✅ **Up 34 seconds, 无 Restarting** (对比之前 `Restarting (1) 43 seconds ago, restartCount=936`)

### 2.2 NetworkSettings 验证

```bash
$ docker inspect microbubble-agent-glitchtip-dev-1 --format '{{json .NetworkSettings.Networks}}'
{
  "microbubble-agent_default": {
    "Aliases": ["microbubble-agent-glitchtip-dev-1", "glitchtip", "db", "redis"],
    ...
  }
}
```

✅ **Networks**: 仅 `microbubble-agent_default` (对比之前 `{}`)
✅ **Aliases**: `[glitchtip, db, redis]` 已生效

### 2.3 default network 成员验证

```bash
$ docker network inspect microbubble-agent_default | grep -c 'glitchtip'
1
```

✅ **glitchtip-dev-1 已在 default network 列表** (之前不在列表, 10 → 11 容器)

### 2.4 Django migrate 验证

```bash
$ docker logs microbubble-agent-glitchtip-dev-1 --tail 10
Maintaining weekly partitions for issue_events_issuetag...
Cleaning up old weekly partitions for projects_issueeventprojecthourlystatistic...
Partition maintenance complete.
```

✅ **Django migrate 成功** (对比之前 `OperationalError: Temporary failure in name resolution`)

### 2.5 HTTP endpoint 验证

```bash
$ curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8001/
HTTP 200
```

✅ **HTTP 200** — glitchtip Web UI 可访问

---

## 3. 修复方案对比 (派工 brief 4 方案)

| 方案 | 操作 | 本任务采用 | 理由 |
|------|------|-----------|------|
| **A. 改 compose aliases** | networks 段加 `aliases: [db, redis]` | ✅ **采用** | 持久化, 与类 20.140 沉淀一致, 双重保险 (即使漏 attach 也能解析主机名) |
| B. down + up 完整重 attach | `docker compose down && up -d glitchtip` | ❌ 不采用 | 仅运行时修补, 下次仍可能漏 attach |
| C. 一次性脚本 | `docker network connect --alias` | ❌ 不采用 | 手动运维, 不可持续 |
| D. 重启 Docker Desktop GUI | Quit+Start 5-10min | ❌ 不采用 | 核弹打蚊子, 用户操作 |

---

## 4. 类 20 实战沉淀 (本任务新增)

### 4.1 类 20.140 (W100 +N) 实战

> Docker Desktop 重启后 `docker compose up -d` 起的容器**有时**漏 attach default network.

**本任务实战**:
- 根因: glitchtip 容器 `NetworkSettings.Networks = {}` (空)
- 修复: compose aliases 持久化修补
- 验证: 现在 Networks 含 default network, Aliases 生效

**A 方案 aliases 优势** (对比直接 `docker network connect --alias`):
1. **持久化**: compose 文件是 IaC, 未来 up 自动应用
2. **原子性**: down+up 一气呵成
3. **可审计**: git diff 可见, code review 能 catch
4. **可逆**: `git revert` 一行恢复

### 4.2 类 20.101 (W91-X-20) 实战

> docker service crash 排查必 4 件: docker logs / docker inspect / env / db 状态.

**本任务实战**:
- ✅ docker logs: OperationalError (DNS → DB missing)
- ✅ docker inspect: Networks 从 `{}` → default
- ✅ env: DATABASE_URL 正确
- ✅ db 状态: 7 个数据库列表 (发现缺 `glitchtip`)

**额外发现**: PostgreSQL 数据库缺失是"二阶根因", 类 20.101 4 件排查实战命中.

### 4.3 类 20.146 (W2 +N) 实战 (沿用)

> 容器重启后必须清 `__pycache__/` 否则 .pyc 缓存会遮蔽 .py 改动.

本任务 0 改 app/ 代码, 沿用此铁律.

---

## 5. 实施统计

| 维度 | 数据 |
|------|------|
| 实施文件 | 1 (docker-compose.dev.yml) |
| 改动行数 | 6 新增 (3 注释 + 3 aliases) + 1 替换 (旧 networks 段) |
| 文档文件 | 3 (startup + impl + closure) |
| 文档总行数 | ~370 行 |
| Commit 数 | 1 (W-N-GLITCH-IMPL +1, 推 main) |
| Commit hash | `2e6b71dbf` |
| 容器修复前状态 | Restarting (1) 43s, restartCount=936 |
| 容器修复后状态 | Up 34s, no restart |
| HTTP 验证 | localhost:8001 HTTP 200 |

---

## 6. 联动沉淀

- 起步: `memory/w-n-glitchtip-impl-startup-2026-08-05.md` (W-N-GLITCH-IMPL +0)
- 实施: `docs/w-n-glitchtip-impl-2026-08-05.md` (W-N-GLITCH-IMPL +1)
- 收口: `memory/w-n-glitchtip-impl-closure-2026-08-05.md` (本文件, W-N-GLITCH-IMPL +2)
- 前序 (W-N-GLITCH +0/+1/+2): `memory/w-n-glitchtip-fix-*.md` + `docs/w-n-glitchtip-fix-attempt-2026-08-05.md`
- 派工 brief 锚点: W-N-GLITCH-IMPL +0/+1 (合并 1 commit) + +2 收口 (0 commit, 仅沉淀)

---

## 7. Future PR 建议 (主拍决策)

1. **彻底根除类 20.140**: 改 docker-compose.dev.yml 用顶层 `default` 网络定义 + 所有 service 显式 attach
2. **CI 守卫**: `scripts/check-container-network-attach.sh` 在 `docker compose up -d` 后跑 `docker network inspect` 验证
3. **数据库 init 脚本化**: `scripts/init_db.py` 加 `CREATE DATABASE glitchtip` 段落
4. **W-N-DEPLOY 报告更新**: 未来 W-N-DEPLOY 收口应报告 "glitchtip-dev-1 healthy" 而非旁路

---

## 8. 决策表

| 维度 | 决策 | 理由 |
|------|------|------|
| 修复路径 | A 方案: 改 compose aliases | 持久化, 与类 20.140 沉淀一致 |
| 数据库修补 | 运行时 `CREATE DATABASE glitchtip` | 派工 brief 不禁 PostgreSQL DDL, W91-X-20 沉淀 |
| 容器操作 | `down glitchtip` + `up glitchtip` | 派工 brief 授权 |
| 提交范围 | docker-compose.dev.yml + docs/memory | 0 production code 改动守恒 |
| 阻塞评估 | 修复后 glitchtip-dev-1 healthy | 类 20.140 案例闭环 |
| HTTP 验证 | localhost:8001 HTTP 200 | glitchtip Web UI 可访问 |
| Commit 数 | 1 (派工 brief 估 3, 合并 +0/+1) | 派工 v11 §13.3 据实上报 |

---

## 9. 收口结论

- 派工 brief base head ✅ 验证通过 (`cde003abc`)
- 严禁清单 ✅ 严格守恒 (0 改 app/ alembic/ W-N 既有 commits)
- 实施授权范围 ✅ 在 docker-compose.dev.yml 范畴内
- 根因 ✅ 已修复 (aliases 持久化 + DB 运行时修补)
- 验证 ✅ 5 件齐 (docker ps / inspect / network inspect / logs / HTTP)
- 锚点范式 ✅ 据实上报 (1 commit + 1 memory 沉淀)

**W-N-GLITCH-IMPL +2 收口**. 类 20.140 案例闭环, glitchtip-dev-1 健康运行.