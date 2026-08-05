# W-N-GLITCH-IMPL glitchtip container 漏 attach default network 实施修复起步 (W-N-GLITCH-IMPL +0, 2026-08-05)

**任务**: W-N-GLITCH-IMPL 选 A 方案 (改 compose aliases) + 重 attach glitchtip 容器 + 验证 healthy
**派工锚点**: W-N-GLITCH-IMPL +0 起步 / +1 实施修复 / +2 收口
**派工 brief base**: `cde003abc docs(decision): W-N-P3-A + W-N-GLITCH 5 文件 untracked commit 推 main (W-N-P3-A + W-N-GLITCH 收口)`
**Worktree**: 主仓库 (本任务仅 docker-compose.dev.yml + docs/memory 范畴, 未开 worktree)

---

## 1. 起步 6 项 (W73 铁律)

### 1.1 派工锚点核对

- ✅ 派工 brief: W-N-GLITCH-IMPL +0..+2 (3 commits)
- ✅ base head 实测: `git log --oneline -3` → `cde003abc docs(decision): W-N-P3-A + W-N-GLITCH 5 文件 untracked commit 推 main (W-N-P3-A + W-N-GLITCH 收口)` ✅
- ⚠️ 派工 brief 工作目录核对: 本任务在主仓库 `E:\microbubble-agent` ✅
- ✅ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ✅ 0 改 alembic/versions/
- ✅ 0 改 W-N-GLITCH 既有 decision doc (`docs/w-n-glitchtip-fix-attempt-2026-08-05.md`)

### 1.2 派工 brief 严禁清单 vs 本任务授权

**严禁清单 (严格守恒)**:
- ❌ 改 plan 文件
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ❌ 改 app/
- ❌ 改 alembic/versions/
- ❌ 改 W-N-GLITCH 既有 decision doc

**本任务 W-N-GLITCH-IMPL 明确授权范围** (区别于 W-N-GLITCH +1 严禁改 compose):
- ✅ 改 `docker-compose.dev.yml` (glitchtip service 加 `aliases`)
- ✅ `docker compose down glitchtip-dev-1` + `docker compose up -d glitchtip-dev-1` 重 attach
- ✅ 写 `docs/w-n-glitchtip-impl-2026-08-05.md` 实施报告
- ✅ 写 `memory/w-n-glitchtip-impl-startup-2026-08-05.md` 起步沉淀 (本文件)
- ✅ 写 `memory/w-n-glitchtip-impl-closure-2026-08-05.md` 收口沉淀

### 1.3 上下文关联: W-N-GLITCH +0/+1/+2 (前序派工)

- **W-N-GLITCH +0** 起步 (`memory/w-n-glitchtip-fix-startup-2026-08-05.md`)
- **W-N-GLITCH +1** 决策文档 (`docs/w-n-glitchtip-fix-attempt-2026-08-05.md`, 201 行, commit `821874cca`)
- **W-N-GLITCH +2** 收口 (`memory/w-n-glitchtip-fix-closure-2026-08-05.md`, 仅 memory, 0 commit)

**前序派工结论**: 派工 brief 严禁改 docker-compose.yml/dev.yml + 严禁重启 glitchtip 容器 → 仅写决策文档, 留 future PR.

**本任务 W-N-GLITCH-IMPL 派工授权**: 明确**允许**改 docker-compose.dev.yml + 重 attach 容器 + 实施修复. 这是主拍后续派工, 把 W-N-GLITCH +1 的"future PR"实施落地.

### 1.4 当前状态实测 (Step 0: 派工起点必实测)

```bash
$ docker ps -a | grep glitch
d4b48d1be102  microbubble-agent-glitchtip-dev-1  glitchtip/glitchtip:6.2.2  Restarting (1) 43 seconds ago  28 hours ago

$ docker network inspect microbubble-agent_default | grep -E 'Name|Containers'
# 10 个成员: nginx, ollama, celery-worker, redis, celery-meeting-worker, app, db, minio, sensevoice, celery-beat
# 注意: glitchtip-dev-1 不在列表中! ⚠️ (根因确认)

$ docker logs microbubble-agent-glitchtip-dev-1 --tail 5
django.db.utils.OperationalError: pool error: ... failed to lookup address information: Temporary failure in name resolution
SQL: SHOW server_version_num
```

**根因确认 (类 20.140 实战)**:
- glitchtip 容器启动时**未**成功 attach 到 `microbubble-agent_default` network
- 容器 `NetworkSettings.Networks = {}` (空 map)
- Django 尝试 `db:5432` DNS 解析 → fail → exit 1 → restart loop
- 已跑 `restartCount=936` 次 (W-N-GLITCH +1 实测)

### 1.5 W73 铁律起点 6 项

- ✅ git log --oneline -3 验证 base head = `cde003abc`
- ✅ git status clean (无未提交改动)
- ⚠️ docker ps 验证容器状态 (Restarting 符合预期)
- ✅ docker network inspect 验证网络成员 (glitchtip 不在列表)
- ✅ docker logs 验证根因 (DNS 解析失败)
- ⚠️ 派工 brief base head 实测 (cde003abc ✅)

### 1.6 起步结论

- 派工 brief base head ✅ 验证通过 (`cde003abc`)
- 严禁清单 ✅ 已核对
- 实施授权范围 ✅ 已确认 (docker-compose.dev.yml + docs/memory)
- 根因 ✅ 已确认 (类 20.140, 容器漏 attach default network)
- 修复方案 ✅ 选定 (A 方案: 改 compose aliases + 重 attach)

**W-N-GLITCH-IMPL +1 实施修复起跑**.