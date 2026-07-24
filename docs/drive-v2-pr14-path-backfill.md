# Drive v2 PR14 — 历史评论 path 自动重建 (W68 第 12 批 B-1)

> **状态**: 收官, 2026-07-24
> **作者**: W68 第 12 批 B-1 agent
> **锚点范式**: 第 148 守恒
> **依赖**: Drive v2 PR9 (062_drive_comments) + PR11 (066_drive_comments_path) + PR11 fallback (069_drive_comments_recursive_func)
> **commit 链**: `alembic 070 + service + Celery task + CLI + e2e + docs + memory`

## 背景

Drive v2 PR11 (W68 第 8 批 B-1, commit `a2a00ad73`) 引入 `drive_comments.path` 物化列
+ GIN trgm 索引 + breadcrumb 端点。当时 migration 体内自动 `WITH RECURSIVE` 重算
现有评论的 path (PR9 时期填的), 解决"新评论自动算 path"的问题。

但生产部署后 (W68 第 9+10 批) 发现:

- **历史评论 path 是空** — PR11 的 066 migration 只对 `parent_id IS NULL` 起点有效,
  如果某评论 `parent_id` 指向一个**还没创建**的 ID (孤儿), 它会被跳过
- **循环引用 A.parent=B, B.parent=A** — `WITH RECURSIVE` 会爆错 (虽然 PR11 有
  `cp.depth < 100` 防无限递归, 但 cycle detection 不完整)
- **后续 schema 变更 (rebuild_paths 之类) 可能让 path 失同步** — 任何 path IS NULL
  或 path = '/' 但 depth > 0 的评论, 都是数据漂移

PR14 是一次性自动重建 + 持续后台慢速回填 (Celery 每日 02:00)。

## 算法

### 1. 孤儿引用修复 (前置步骤)

```sql
UPDATE drive_comments dc
SET parent_id = NULL, path = '/', depth = 0
WHERE dc.parent_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM drive_comments parent
      WHERE parent.id = dc.parent_id
  )
```

**逻辑**: 任何 `parent_id NOT NULL` 但不在 `drive_comments.id` 集合里的评论
→ 视为孤儿, `parent_id` 置 NULL, `path` 置 `'/'`, `depth` 置 0。

**安全**: 不删评论, 不破坏嵌套关系, 只"剪枝"。

### 2. WITH RECURSIVE 重算 (file_id 维度)

```sql
WITH RECURSIVE comment_path_calc AS (
    SELECT
        id, parent_id, file_id, folder_id,
        '/'::text AS path, 0 AS depth
    FROM drive_comments
    WHERE parent_id IS NULL
      AND file_id IS NOT NULL

    UNION ALL

    SELECT
        c.id, c.parent_id, c.file_id, c.folder_id,
        (cp.path || cp.id::text || '/')::text AS path,
        cp.depth + 1
    FROM drive_comments c
    INNER JOIN comment_path_calc cp ON c.parent_id = cp.id
    WHERE c.file_id IS NOT NULL
      AND cp.depth < 100  -- 防无限递归硬上限
)
UPDATE drive_comments dc
SET path = cpc.path, depth = cpc.depth
FROM comment_path_calc cpc
WHERE dc.id = cpc.id
  AND dc.file_id IS NOT NULL
```

### 3. WITH RECURSIVE 重算 (folder_id 维度)

与 file_id 维度对称, 走 `folder_id IS NOT NULL` 过滤 (folder 级评论)。

## 性能预期

| 评论数 | 嵌套深度 | 耗时 (1 次 backfill_all_paths) |
| --- | --- | --- |
| 100 | 5 层 | < 100ms (本地 PG) |
| 1,000 | 10 层 | < 500ms |
| 10,000 | 20 层 | < 3s |
| 100,000 | 50 层 | < 30s |

`WITH RECURSIVE` 单 query 完成, 不需要 N+1。GIN trgm 索引 (PR11 066 加) 不影响
path 重建, 但加快后续 `list_by_path_prefix` / `get_breadcrumb` 端点。

## 部署必做

### 步骤 1: 跑 alembic 070

```bash
# 1. cp 到容器
docker cp alembic/versions/070_drive_comments_path_backfill.py microbubble-agent-app-1:/app/alembic/versions/

# 2. 清 cache (CLAUDE.md 752 行铁律: __pycache__ 残留会让老 down_revision 继续生效)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# 3. 升级
docker exec microbubble-agent-app-1 alembic upgrade head

# 期望输出:
#   Running upgrade 069_drive_comments_recursive_func -> 070_drive_comments_path_backfill
```

**重要**: alembic 070 的 `upgrade()` 体内自动跑 `WITH RECURSIVE` 重算 path
+ 修孤儿引用。生产评论数 < 100k 时, 这一步 < 30s 即可完成。

### 步骤 2: 验证 path 全部非空

```sql
-- 应该 0 行 (所有 path 非空)
SELECT COUNT(*) FROM drive_comments WHERE path IS NULL OR path = '';

-- 应该 0 行 (所有 parent_id 引用合法)
SELECT COUNT(*) FROM drive_comments c
WHERE c.parent_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM drive_comments p WHERE p.id = c.parent_id);
```

### 步骤 3: 重启 Python 进程 (CLAUDE.md 752 行铁律)

```bash
docker compose restart app celery-worker
```

### 步骤 4: 跑手动 CLI 验证 (可选)

```bash
# dry-run, 只看不写
docker exec microbubble-agent-app-1 python /app/scripts/backfill_drive_comments_path.py --all

# 期望输出:
#   ============================================================
#     target           = all
#     dry_run          = True
#     updated          = 0
#     orphans_fixed    = 0
#     total_examined   = 1234
#   ============================================================
#     (DRY-RUN: 未写库. 跑 --apply 真更新)
```

### 步骤 5: (可选) 触发 Celery 异步回填

```bash
# 异步触发全表回填 (适合生产评论数 > 100k 不想停服务)
docker exec microbubble-agent-app-1 python -c "
from app.services.drive_comments_path_backfill_tasks import backfill_paths_task
result = backfill_paths_task.delay()
print('Task ID:', result.id)
"
```

或通过 Flower UI 调度。

## alembic 链

```
065_push_subscriptions
  → 066_drive_comments_path (PR11 path 物化)
  → 067_drive_reactions (PR12 reactions)
  → 068_drive_notification_dedup (PR13 dedup)
  → 069_drive_comments_recursive_func (PR11 PG function 兜底)
  → 070_drive_comments_path_backfill (PR14 本批) ← 在此
```

**纪律 (CLAUDE.md 2026-07-24 alembic chain discipline)**: 并行派 alembic migration
agent 必须明确 down_revision 接续关系, merge 后必须 verify 只 1 个 head。本批
PR14 070 串单链接 069, 0 双头。

## 测试

5 核心场景 (`tests/test_drive_v2_pr14_path_backfill.py`):

1. **根评论 path 重建** — 模拟 path=NULL, 调 backfill_for_file 恢复
2. **嵌套 5 层 path 重建** — 5 层嵌套全部 path='/stale/' 后重建, 验证 depth + path 正确
3. **跨文件 dry-run** — backfill_all_paths(dry_run=True) 不写库, updated=0, total_examined 正确
4. **Celery task 调度** — 验证 task 注册到 celery_app.tasks + beat_schedule + 返回结构
5. **baseline audit 守恒** — 9 baseline files 仍全存在, 71 PASS + 7 SKIP 不变

## 5 新铁律 (W68 第 12 批 B-1 沉淀)

1. **嵌套 path 重建必须先修孤儿** — `parent_id` 指向不存在 ID 的评论必须在
   `WITH RECURSIVE` 之前先剪枝 (置 NULL), 否则起点选不到这棵子树, 留
   path=NULL 漂移。
2. **WITH RECURSIVE 必须有 depth 上限** — `cp.depth < 100` 硬上限防
   循环引用导致无限递归。`UNION ALL` 不像 `UNION` 自动去重, 循环会爆
   PostgreSQL 内存。
3. **跨文件 dry-run 默认 True** — service + Celery task + CLI 三层入口
   都默认 `dry_run=True`, 显式 `--apply` / `dry_run=False` 才写库。
   防误操作是 PR14 的核心 UX 设计。
4. **Celery 慢速回填用 NullPool** — 复用 chat_history_tasks 模式
   (`create_celery_engine_and_session + NullPool + asyncio.run + engine.dispose`),
   避免连接池跨事件循环 (`Future attached to different loop`)。
5. **baseline 守恒 9 files + 71 PASS + 7 SKIP** — 任何 PR 实施后必须跑
   `pytest tests/test_baseline_audit.py -v` 验证, 不能让老 baseline
   路径被破坏。

## 相关文件

- **alembic**: `alembic/versions/070_drive_comments_path_backfill.py` (主迁移)
- **service**: `app/services/drive_comments_path_backfill_service.py` (业务逻辑)
- **Celery**: `app/services/drive_comments_path_backfill_tasks.py` (后台任务)
- **CLI**: `scripts/backfill_drive_comments_path.py` (手动触发)
- **e2e**: `tests/test_drive_v2_pr14_path_backfill.py` (5 场景)
- **memory**: `memory/w68-route-12-b1-pr14-path-2026-07-24.md` (5 新铁律沉淀)

## 回滚路径

```bash
# 1. alembic 降级 (注意: PR14 是 data migration, 降级不恢复旧 path)
docker exec microbubble-agent-app-1 alembic downgrade -1

# 2. 真要回滚旧 path, 需 git revert + 重新部署
# (因为 downgrade() 是 pass — 不可逆 data migration)
```

如果用户误触发了 `backfill_all_paths --apply` 走错了 path, 真要回滚需从
PG backup 恢复, **不可逆**。这是 PR14 的核心权衡: 简化逻辑 (无 history path
保留) 换 0 复杂回滚代码。
