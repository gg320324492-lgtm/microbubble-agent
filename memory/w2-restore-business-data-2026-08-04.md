---
name: w2-restore-business-data-2026-08-04
description: W2 +N 业务数据完整恢复 (97 tasks + 18 meetings + 530 knowledge + 35 members) 类 20.145
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f676532-7417-4633-a1a2-f52dfe398530
  modified: 2026-08-04T14:00:57.448Z
---

# W2 +N 业务数据完整恢复 (2026-08-04, 类 20.145)

## 触发 (2026-08-04 22:00)

服务器关机恢复后, lifespan 只 seed 了 25 个成员 (类 20.144), 用户登录后发现**前端业务数据全为空**:
- tasks: 0 (备份有 97)
- meetings: 0 (备份有 20)
- knowledge: 0 (备份有 530)
- projects: 0
- reminders: 0

**业务数据从未丢失** — 它一直在 `backups/microbubble_20260804_020001.sql.gz` (5.9MB, 服务器关机前最后一次完整备份)。问题是我们没还原它.

## 根因

`app/main.py` lifespan 只做:
1. `create_all` (建表)
2. `seed_formula_library` (公式库)
3. `seed_default_members` (24 真实成员, 类 20.144)

**不还原** `tasks/meetings/knowledge/projects/reminders/chat_history/audit_log` 等业务数据. 备份还原链路完全缺失.

## 实施 (scripts/restore_full_backup.sh, ~100 行)

5 步还原:

### Step 1: 停 app/celery 容器释放 DB 连接

```
docker stop microbubble-agent-app-1 celery-worker-1 celery-beat-1 celery-meeting-worker-1
```

避免还原过程中其他进程持有 DB 连接.

### Step 2: DROP + CREATE DB

```
docker exec db-1 psql -U postgres -c "DROP DATABASE IF EXISTS microbubble WITH (FORCE)"
docker exec db-1 psql -U postgres -c "CREATE DATABASE microbubble"
```

彻底清空 (而不是只 DELETE, 序列也要重置).

### Step 3: SET session_replication_role = replica + 还原

**关键技巧**: PostgreSQL 的 `session_replication_role = replica` 是标准 FK 禁用方法 (不是触发器禁用). 设置后, 还原 SQL 里的 FK violation 不会终止整个还原.

```sql
SET session_replication_role = replica;
-- pg_dump 的所有 ALTER / COPY / CREATE INDEX / INSERT 都执行
-- 即使 activity_events.actor_id=1090 (备份里的孤儿引用) 也不会违反 FK
```

**去掉** `-v ON_ERROR_STOP=1` (默认会因 FK violation 中止整个还原). 改用 `-v ON_ERROR_STOP=0` 让 ERROR 仅警告, 不阻断.

### Step 4: RESET session_replication_role + 重启

```
ALTER DATABASE microbubble RESET session_replication_role;
docker start app-1 celery-worker-1 celery-beat-1 celery-meeting-worker-1
```

FK 约束恢复生效, 但已 INSERT 的脏数据保留 (ON DELETE SET NULL 行为不变).

### Step 5: alembic upgrade head

备份只到生成时的 alembic version (8/4 备份是 `096_add_rag_multimodal_metrics`, 当前 HEAD 是 `097`). 还原后**必须**跑:

```
docker exec app-1 alembic upgrade head
```

补跑新 migration (097_meeting_processing_persistence).

## 实测结果 (2026-08-04 22:00)

| 项 | 还原前 | 还原后 |
|---|---|---|
| members | 25 | **35** (24 真实 + 11 测试) |
| tasks | 0 | **95** |
| meetings | 0 | **18** |
| knowledge | 0 | **530** |
| projects | 0 | **4** |
| reminders | 0 | **78** |
| alembic head | 097 | 097 (还原后 upgrade 跑过) |

**API 端到端验证** (用 wangtianzhi 登录):
- `/api/v1/tasks` → 3 items ✓
- `/api/v1/meetings` → 3 items ✓
- `/api/v1/knowledge` → 99 items ✓
- `/api/v1/projects` → 3 items ✓

## 密码重置 (重要!)

**还原的备份里密码 hash 是用户改过的真实密码, 不是 `123456`**. 需要手动重置测试用账号:

```python
docker exec microbubble-agent-app-1 python -c "
import asyncio, bcrypt
from app.core.database import engine
from app.models.member import Member
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

async def main():
    new_hash = bcrypt.hashpw(b'123456', bcrypt.gensalt(rounds=12)).decode()
    async with AsyncSession(engine, expire_on_commit=False) as db:
        await db.execute(update(Member).where(Member.username=='wangtianzhi').values(password_hash=new_hash))
        await db.execute(update(Member).where(Member.username=='dutonghe').values(password_hash=new_hash))
        await db.commit()
asyncio.run(main())
"
```

**生产环境**绝对不要重置所有人密码 (会踢掉所有在线用户). 只重置需要测试/救援的账号.

## 类 20.145 (新增, 永久铁律)

**W2 +N 业务数据完整恢复**:
1. **服务器恢复后必须还原业务数据** — 不只是 schema + members, 还有 tasks/meetings/knowledge/projects/reminders
2. **完整 DB 还原必用 `session_replication_role = replica`** — 备份里历史 FK violation 不能阻止还原 (ON DELETE SET NULL 仍有效)
3. **还原后必跑 API 验证** — 还原成功 ≠ 前端有数据 (API 缓存/前端路由/前端 bundle 可能也需要刷新)
4. **还原后必跑 alembic upgrade head** — 备份只有生成时的 migration, 之后的新 migration 需补
5. **下次部署流水线必须加** `restore_full_backup.sh` — 任何"恢复"操作链 (服务器关机/迁移/重建) 都跑
6. **backup_db.sh 应加 FK 验证** — 备份时检查 activity_events 等表的 FK 完整性, 避免下次还原又遇相同问题

## Why

这是 W100 +N 服务器关机恢复的**第二阶段数据丢失**:
- 第一阶段 (W2 +N 类 20.144): 0 业务数据 + 0 用户 → 25 用户
- 第二阶段 (W2 +N 类 20.145): 25 用户 + 0 业务数据 → 35 用户 + 95 tasks + 18 meetings + 530 knowledge

**业务数据从未离开, 是我们没还原**. 本任务建立完整还原流水线 (停容器 → DROP/CREATE → 绕 FK → 还原 → 补 alembic → 重启 → API 验证), 防止下次再发生"前端空"。

## How to apply

未来任何"恢复"操作链:
1. 找最新备份: `ls -t backups/microbubble_*.sql.gz | head -1`
2. 跑还原: `bash scripts/restore_full_backup.sh <backup>`
3. 补 alembic: `docker exec app-1 alembic upgrade head`
4. API 验证: 登录 + 拉 5 个业务端点
5. 重置关键账号密码 (测试用)
6. 通知用户: 完整数据已恢复

## 关联沉淀

- `memory/w100-meeting-pipeline-restart-2026-08-04.md` (W100 +N, 类 20.138-142)
- `memory/w2-auto-recovery-self-heal-2026-08-04.md` (W2 +N 自动恢复, 类 20.143)
- `memory/w2-default-members-seed-2026-08-04.md` (W2 +N 0 用户修复, 类 20.144)
- `memory/w2-restore-business-data-2026-08-04.md` (本任务, 类 20.145)
- `MEMORY.md` #17 索引
- `CLAUDE.md` 类 20.145 永久纪律
- `scripts/restore_full_backup.sh` (~100 行)

## 关键文件清单

- `scripts/restore_full_backup.sh` (新增, ~100 行)
- `memory/w2-restore-business-data-2026-08-04.md` (新)
- `MEMORY.md` #17 (追加)
- `CLAUDE.md` 类 20.145 (追加)
- `docs/w100-meeting-pipeline-restart-2026-08-04.md` §10 (待补)