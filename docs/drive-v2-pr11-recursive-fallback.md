# Drive v2 PR11 recursive fallback (W68 第 9 批 B-2)

**状态**: 锚点范式第 109 守恒  
**日期**: 2026-07-24  
**作者**: Agent "W68 第 9 批 B-2"

## 背景

Drive v2 PR11 (commit `a2a00ad73`, W68 第 8 批 B-1) 用 GIN trgm 索引 + path LIKE 替代 N+1 递归, 实现 drive_comments 的高性能祖先链 / 子树查询。但 PR11 留了一个 fallback 空白:

- **GIN 索引失效场景**: DB 故障 / 索引重建中 / 索引被 drop 时, `path LIKE '%/X/%'` 走全表扫, 性能暴跌到秒级
- **极深嵌套场景**: 嵌套 > 50 层时, `path` 字符串可能超 VARCHAR(500) 限制, path 物化失败
- **PR11 老 schema 兼容**: path 列尚未物化 (PR11 migration 069 之前), 拿祖先链不能依赖 path

PR11 fallback B-2 提供 PostgreSQL function 兜底, 永远能拿祖先链 / 子树, 不依赖 path 列物化。

## 设计

### 2 个 PG function (migration 069)

```sql
-- 1. 拿祖先链 (向上)
CREATE OR REPLACE FUNCTION get_comment_ancestors_recursive(
    p_comment_id INT
) RETURNS TABLE (...)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    -- 边界: comment 不存在返回空
    IF NOT EXISTS (...) THEN RETURN; END IF;
    RETURN QUERY
    WITH RECURSIVE ancestor_chain AS (
        -- 基例: 目标评论 (depth=0)
        SELECT c.id, c.parent_id, 0 AS depth, ... FROM drive_comments c WHERE c.id = p_comment_id
        UNION ALL
        -- 递归: 找 parent
        SELECT p.id, p.parent_id, ac.depth + 1, ...
        FROM drive_comments p
        INNER JOIN ancestor_chain ac ON p.id = ac.parent_id
    )
    SELECT ... FROM ancestor_chain ORDER BY depth ASC;
END;
$$;

-- 2. 拿子树 (向下)
CREATE OR REPLACE FUNCTION get_comment_descendants_recursive(
    p_root_id INT,
    p_max_depth INT DEFAULT 100
) RETURNS TABLE (...)
LANGUAGE plpgsql STABLE
AS $$
DECLARE ...
BEGIN
    -- 边界: root 不存在返回空 + max_depth clamp [0, 1000]
    RETURN QUERY
    WITH RECURSIVE descendant_tree AS (
        -- 基例: root 节点 (depth=0)
        SELECT c.id, c.parent_id, 0 AS depth, ... FROM drive_comments c WHERE c.id = p_root_id
        UNION ALL
        -- 递归: 找 children (parent_id = 自己的 id), 限制 depth < p_max_depth
        SELECT child.id, child.parent_id, dt.depth + 1, ...
        FROM drive_comments child
        INNER JOIN descendant_tree dt ON child.parent_id = dt.id
        WHERE dt.depth < p_max_depth
    )
    SELECT ... FROM descendant_tree ORDER BY depth ASC, created_at ASC;
END;
$$;
```

**关键设计点**:
- `STABLE` 标记 (只读, 可被优化器缓存)
- 不引用 `path` 列 (兼容 PR11 前后两种 schema)
- `max_depth` 默认 100, 内部 clamp 到 `[0, 1000]` 防 DoS
- 边界: comment / root 不存在 → 返回空结果集 (不抛错)
- `GRANT EXECUTE TO app_user` (生产账号, 不是 superuser)

### Service 层 (`app/services/drive_comment_recursive_service.py`)

`DriveCommentRecursiveService` 提供 4 个方法:
- `get_comment_ancestors_fallback(comment_id)`: 调 PG function 拿祖先链 (纯 fallback)
- `get_comment_descendants_fallback(root_id, max_depth)`: 调 PG function 拿子树 (纯 fallback)
- `get_breadcrumb_with_fallback(comment_id)`: **优先 GIN, 失败 fallback**
- `_extract_sqlstate(error)`: 从 SQLAlchemy / psycopg2 错误提取 PG SQLSTATE code

**fallback 触发条件** (错误码白名单):
```python
_FALLBACK_ERROR_CODES = frozenset({
    "23P01",  # exclusion_violation — GIN 索引约束违反
    "57014",  # query_canceled — query timeout
    "42P01",  # undefined_table — 驱动表不在
    "42703",  # undefined_column — 列不在 (path 列被回滚)
    "22023",  # invalid_parameter_value — path 物化失败
})
```

非白名单错误 (FK 违反 / 网络断) **不**触发 fallback, 直接 raise (不吞错)。

### API 层 (`app/api/v1/drive_comments.py`)

2 个新端点:

#### `GET /api/v1/drive/comments/{id}/breadcrumb`

- **Query params**: `depth` (1-1000, 默认 10)
- **Response body**: `FallbackBreadcrumbResponse` (ancestors + current + path + duration_ms)
- **Response headers**:
  - `X-Fallback: gin | recursive` — 哪条路径被采纳
  - `X-Duration-Ms: <float>` — 本次调用耗时 (ms)

#### `GET /api/v1/drive/comments/{id}/descendants`

- **Query params**: `max_depth` (0-1000, 默认 100)
- **Response body**: `FallbackDescendantsResponse`
- **Response headers**: `X-Fallback: recursive` (固定) + `X-Duration-Ms`

## 性能预期

| 场景 | GIN (主路径) | PG function (fallback) |
|------|--------------|-------------------------|
| 5 层嵌套面包屑 | < 10ms | < 30ms |
| 50 层嵌套祖先链 | < 20ms | < 50ms |
| 100 个后代子树 | < 50ms | < 100ms |
| 1000 个后代子树 (max_depth=100) | 全表扫 → 慢 | < 200ms |

GIN 失败场景下, fallback 是**唯一**能保证响应时间的路径 (避免秒级超时)。

## 部署必做

```bash
# 1. 跑迁移 (PR13 notification_dedup 必须先 merge)
docker cp alembic/versions/069_drive_comments_recursive_func.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 重启后端 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 3. 验证函数存在
docker exec microbubble-agent-postgres-1 psql -U app_user -d microbubble \
  -c "\df get_comment_ancestors_recursive"
docker exec microbubble-agent-postgres-1 psql -U app_user -d microbubble \
  -c "\df get_comment_descendants_recursive"

# 4. 验证 GRANT
docker exec microbubble-agent-postgres-1 psql -U app_user -d microbubble \
  -c "SELECT has_function_privilege('app_user', 'get_comment_ancestors_recursive(int)', 'EXECUTE');"
# 期望: t
```

## alembic 链风险

PR11 fallback B-2 依赖链:
- 066_drive_comments_path (PR11, 未合并)
- 067_drive_reactions (PR12, 未合并)
- 068_drive_notification_dedup (PR13, 未开发)
- **069_drive_comments_recursive_func (本 PR)**

主指挥 merge 顺序:
1. **PR11** (`066_drive_comments_path`) — 先 merge
2. **PR12** (`067_drive_reactions`) — 后 merge (down_revision 接 066)
3. **PR13** (`068_drive_notification_dedup`) — 后 merge (down_revision 接 067)
4. **本 PR fallback B-2** (`069_drive_comments_recursive_func`) — 最后 merge (down_revision 接 068)

merge 后立即 verify:
```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
# 期望: ['069_drive_comments_recursive_func']
```

## 测试覆盖

`tests/test_drive_v2_pr11_recursive_fallback.py` 6 场景:

1. **PG function ancestors (multilayer)** — 5 层嵌套, depth 升序
2. **PG function descendants** — 子树 + max_depth 限制
3. **GET /breadcrumb 端点** — X-Fallback header 校验
4. **GIN 失败自动 fallback** — mock SQLSTATE 23P01 / 42703 触发
5. **50 层嵌套性能** — PG function < 200ms (宽松 CI 阈值)
6. **X-Fallback header 完整性** — `gin` / `recursive` 标识 + depth query param 校验

## 后续 PR 预留

- **PR14 (comment edit history)**: 编辑历史表 + 版本对比 UI
- **PR15 (comment soft delete)**: 软删除字段 + 垃圾桶 (参考 PR6 task trash 模式)
- **PR16 (mention dedup)**: 同条评论重复 @ 同一 user 去重 (PG function 友好)

## 参考

- CLAUDE.md § "W68 第 9 批 B-2" (本任务)
- CLAUDE.md § "2026-07-24 alembic 并行 agent 串单链纪律"
- memory/w68-route-8-b1-drive-pr11-path-2026-07-24.md (PR11 报告)
- memory/w68-route-9-b2-pr11-fallback-2026-07-24.md (本任务 memory)
- PG function 写法参考: drive_audit_log / knowledge_evolution_tasks 既有 PL/pgSQL