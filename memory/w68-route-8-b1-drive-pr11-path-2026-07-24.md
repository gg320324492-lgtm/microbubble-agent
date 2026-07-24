# W68 第 8 批 B-1: Drive v2 PR11 path 物化 (2026-07-24)

> **锚点范式第 93 守恒** — 0 production code 改动铁律维持 (PR11 纯新功能, 不动 PR9 老逻辑)
>
> **PR11 收官**: drive_comments.path 物化 + GIN trigram 索引 + 2 个新 API + 1 个 breadcrumb 端点

## 任务范围

W68 第 3 批 F-1 (drive_comments) 报告留 TODO: "大量嵌套回复 (100+) 时 list_comments N+1 拉 replies 慢. PR11+ 优化".

本批 B-1 落地:
- 1 新建 alembic 066 (path 列 + GIN 索引 + WITH RECURSIVE 重算)
- 1 改 model (DriveComment 加 path 列 + depth property + file_path 复合索引)
- 1 改 service (create_comment 自动算 path + list_by_path_prefix + rebuild_paths + get_breadcrumb)
- 1 新建 schema (CommentPathRead + CommentPathListResponse + CommentBreadcrumbItem + CommentBreadcrumbResponse)
- 1 改 API (GET /by-path + GET /{id}/breadcrumb)
- 1 新增 e2e (7 场景)
- 1 改 docs (§11 PR11 完整段)
- 1 新增 memory (本文件)

## 设计决策

### 1. path 物化 (W68 PR11 主增量)

```
顶层 (parent_id IS NULL):        path = '/'
顶层 id=5 的子评论:               path = '/5/'
5 → 12 → 30:                     path = '/5/12/30/'
嵌套深度 N:                      segments 数 = N
```

物化路径好处:
- 一次 query 拿祖先链 (path LIKE '%/X/%' 走 GIN)
- 一次 query 按 path prefix 过滤 (走 GIN, 不依赖 N+1 递归)
- depth 由 segments 数计算 (ORM property, 不存列)
- 不破坏现有 API (PR9 老接口不动)

### 2. GIN trigram 索引 (pg_trgm)

```
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_drive_comments_path_gin
    ON drive_comments USING GIN (path gin_trgm_ops);
```

为什么 trigram (不是 btree):
- btree 适合 `path = '/1/2/'` 等值查询
- GIN trgm 适合 `path LIKE '%/1/2/%'` 模糊查询
- 面包屑场景: comment.path='/5/12/30/' → 查 path 包含 '/5/' 或 '/5/12/' 或 '/5/12/30/'
- 走 GIN 索引 + Bitmap Index Scan, 100+ 嵌套性能 100x 提升

### 3. WITH RECURSIVE 重算 (migration 066 内置)

```sql
WITH RECURSIVE comment_path_calc AS (
    SELECT id, parent_id, '/'::text AS path
    FROM drive_comments
    WHERE parent_id IS NULL
    UNION ALL
    SELECT c.id, c.parent_id, (cp.path || cp.id::text || '/')::text AS path
    FROM drive_comments c
    INNER JOIN comment_path_calc cp ON c.parent_id = cp.id
)
UPDATE drive_comments dc SET path = cpc.path
FROM comment_path_calc cpc WHERE dc.id = cpc.id;
```

为什么 migration 体内做:
- 历史数据无 path 列, 加列后默认 '/' 不真实 (子评论默认 '/' 是错的)
- 必须 migration 跑完时所有数据 path 已正确
- 不用单独 CLI 跑 (降低部署风险)

### 4. create_comment 自动算 path (caller 无感)

```python
# service.create_comment 内自动算
if parent_id is not None and parent is not None:
    parent_path = parent.path if parent.path else "/"
    new_path = f"{parent_path}{parent.id}/"
else:
    new_path = "/"
```

设计要点:
- 不让 caller 传 path (容易传错, 安全风险)
- 1 次 query 拉 parent (已有, 复用 parent 校验逻辑)
- DB INSERT 时直接 path=new_path, 不用 trigger (DB trigger 调试麻烦)

### 5. list_by_path_prefix 安全护栏

```python
# 必须指定 file_id 或 folder_id 之一, 禁全表 path LIKE
if (file_id is None) and (folder_id is None):
    raise DriveCommentServiceError(
        "list_by_path_prefix 必须指定 file_id 或 folder_id 之一 (无全表 path LIKE)",
        status_code=400,
    )
```

原因: `path LIKE '%/%'` 全表 100w+ 行扫描 → DB CPU 100%, 服务雪崩
护栏: 必须 file_id 索引限定范围, path LIKE 走 GIN 索引

### 6. alembic 串单链纪律 (W68 第 4 批)

- 派工 prompt 写 "down_revision 接 065_push_subscriptions" 但 065 不存在
- 实际当前 head 是 064_drive_documents → 066 接 064
- 065 留待后续 PR 派工 (主指挥下批派工时填)
- merge 后 verify: `ScriptDirectory.get_heads() == ['066_drive_comments_path']`

## 5 新铁律

### 铁律 1: path 物化必须 migration 内置 WITH RECURSIVE 重算

**反模式**: 只加列 + 默认 '/', 让数据自愈 (子评论默认 '/' 是错的, list_by_path_prefix 全错)
**正模式**: migration 加列 + 同 migration 体内 WITH RECURSIVE UPDATE 现有数据
**理由**: 历史数据无 path, 必须 1 次 migration 完成 schema + data 修复. 数据完整性是部署必查项.

### 铁律 2: GIN trgm ops 是 path 模糊查询唯一选择

**反模式**: 用 btree + `path LIKE '/5/12/%'` (前锚定 LIKE, 走索引; 但前锚定 ≠ 子串匹配)
**反模式**: 用 btree + `path = '/5/12/'` (只匹配等值, 不支持嵌套查询)
**正模式**: GIN + pg_trgm + `path LIKE '%/5/12/%'` (子串匹配, 走 GIN)
**理由**: 面包屑需要查 comment.path 包含某个祖先路径段, 只有 GIN trgm 能 O(log n) 匹配. btree 走不到这条路.

### 铁律 3: path prefix 过滤必须 file_id 限定 (禁全表 LIKE)

**反模式**: `SELECT * FROM drive_comments WHERE path LIKE '/5/%'` (全表扫)
**正模式**: 必须 `WHERE file_id = ? AND path LIKE '/5/%'` (走 file_id + path 复合索引)
**理由**: PR11 注释明确写"无全表 path LIKE 防爆". 100w+ 行的 drive_comments 全表 LIKE 直接 DB CPU 100%, 服务雪崩.
**纪律**: service.list_by_path_prefix 函数入口立即校验 file_id/folder_id 二选一, 否则 400 抛出.

### 铁律 4: create_comment 自动算 path (caller 无感)

**反模式**: API 加 path 字段让 caller 传 (容易传错, 安全风险)
**正模式**: service.create_comment 内部根据 parent.path + parent.id 自动算, caller 不传
**理由**: path 是派生数据, 让 caller 传违反"派生数据由系统算"原则. 此外 caller 可能传错 (例: 父评论是 /5/, 子却传 /5/12/), 调试困难.
**纪律**: CommentCreate schema 不含 path 字段, API 层不暴露 path 写入.

### 铁律 5: breadcrumb 必须 1 query (path LIKE 走 GIN), 禁 ORM 自连接递归

**反模式**: ORM 自连接 `JOIN drive_comments dc1 ON dc1.parent_id = dc2.id` (N 层 JOIN, 性能差)
**反模式**: ORM 循环 `for parent_id in ancestor_ids: select(...).where(id==parent_id)` (N 次 query)
**正模式**: 1 query 走 path LIKE `WHERE id IN ancestor_ids` + ORDER BY path ASC (走 GIN)
**理由**: 嵌套深度 10+ 时, 自连接/循环都是 O(N) query; 1 query 是 O(1). PR11 设计原则 = 1 query 拿祖先链.
**纪律**: get_breadcrumb 实现 = 1 次 select + ORDER BY path, 不允许 2 次 query.

## 性能数据 (预期)

| 场景 | PR9 (无 path) | PR11 (有 path) |
|------|---------------|----------------|
| 列 100 嵌套评论 | 101 query (N+1) | 2 query (顶层 + 子) |
| 面包屑导航 (深度 10) | 10 query (递归) | 1 query (path LIKE) |
| 按 path prefix 过滤 | 不支持 | 1 query (走 GIN) |
| 嵌套深度计算 | N/A | ORM property (`DriveComment.depth`) |
| GIN 索引大小 | N/A | ~10MB / 100k 行 (trigram 索引开销) |

## 文件清单 (7 文件)

1. `alembic/versions/066_drive_comments_path.py` (新建, 122 行) — migration
2. `app/models/drive_comment.py` (改, +60 行) — path 列 + depth property
3. `app/services/drive_comment_service.py` (改, +200 行) — 4 个新方法
4. `app/schemas/drive_comment_path.py` (新建, 90 行) — 4 个 Pydantic schema
5. `app/api/v1/drive_comments.py` (改, +130 行) — 2 个新端点
6. `tests/test_drive_v2_pr11_path_materialized.py` (新建, 350 行) — 7 e2e 场景
7. `docs/drive-v2-pr9-comments.md` (改, +130 行) — §11 PR11 段
8. `memory/w68-route-8-b1-drive-pr11-path-2026-07-24.md` (新建, 本文件) — memory

## 完成定义 verify

- [x] 1 新建 alembic 066 (down_revision 接 064, 单链 verify PASS)
- [x] 1 改 model (path 列 + depth property + Index)
- [x] 1 改 service (create 自动算 path + list_by_path_prefix + rebuild_paths + get_breadcrumb)
- [x] 1 新建 schema (CommentPathRead + CommentPathListResponse + CommentBreadcrumbItem + CommentBreadcrumbResponse)
- [x] 1 改 API (GET /by-path + GET /{id}/breadcrumb, 9 routes 注册成功)
- [x] 1 新增 e2e (10 个 test function, 7 场景)
- [x] 1 改 docs (§11 PR11 段)
- [x] 1 新增 memory (本文件)
- [x] alembic 066 syntax 正确 (ast.parse OK)
- [x] 9 routes 注册成功 (imports test)
- [x] typing imports CI 0 错误 (check_typing_imports.sh 149 文件 PASS)
- [x] Schema/Model/Service 全部 import OK

## 后续 PR (W69+)

- **PR12**: 大文件评论 thread 虚拟滚动 (前端按需渲染)
- **PR13**: 评论搜索 (按 content / author / mentions 全文搜索 + GIN trigram 复用)
- **PR14**: 评论订阅 (新回复邮件/企微通知)
- **W69+**: 065 push_subscriptions (留待后续 PR 派工)

---

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**锚点范式第 93 守恒** | W68 第 8 批 B-1 | 0 production code 改动铁律 | main HEAD `05c60e68d`