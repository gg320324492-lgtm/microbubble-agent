# Drive v2 PR9 — 文件/文件夹 评论 Thread (2026-07-24)

> **背景**: Drive v2 PR6 已有 `FileComment` (file_comments 表, 仅绑 file_id, 2 层嵌套 + 无 resolved).  
> 课题组场景需要**文件夹级别讨论** + **多层嵌套回复** + **已解决标记** (GitHub PR review comments 风格).  
> 本 PR 引入新表 `drive_comments` + 5 个 REST 端点 (含 resolve/unresolve), 与 PR6 FileComment 共存.

---

## 1. API 文档

### 1.1 创建评论

```http
POST /api/v1/drive/comments
Authorization: Bearer <token>
Content-Type: application/json

{
  "file_id": 42,           // 与 folder_id 二选一
  "content": "这个实验数据有疑问 @张三",
  "parent_id": null,       // 顶层评论
  "mentions": [2, 3]       // @ user_id 列表
}
```

**Response 201**:
```json
{
  "id": 1,
  "file_id": 42,
  "folder_id": null,
  "author": {"id": 1, "name": "测试用户", "avatar_url": null},
  "parent_id": null,
  "content": "这个实验数据有疑问 @张三",
  "mentions": [2, 3],
  "is_top_level": true,
  "is_resolved": false,
  "resolved_at": null,
  "resolved_by": null,
  "created_at": "2026-07-24T10:00:00",
  "updated_at": "2026-07-24T10:00:00",
  "replies": []
}
```

**嵌套回复** (parent_id 非空):
```json
{
  "file_id": 42,
  "parent_id": 1,
  "content": "我看了下, 这部分是仪器误差"
}
```

**folder 级别评论** (file_id 改 folder_id):
```json
{
  "folder_id": 7,
  "content": "本月论文归类讨论"
}
```

**错误**:
- `400 VALIDATION_ERROR` — file_id + folder_id 同时传或都不传 (XOR 违反)
- `400 VALIDATION_ERROR` — 嵌套回复与父评论 target 不一致 (file ↔ folder)
- `400 VALIDATION_ERROR` — file 不是 `storage_mode=drive`
- `403 FORBIDDEN` — 用户无权限访问 file/folder
- `404 RESOURCE_NOT_FOUND` — parent_id/file_id/folder_id 不存在

### 1.2 列评论 (顶层 + 嵌套树)

```http
GET /api/v1/drive/comments?file_id=42&is_resolved=false&page=1&page_size=50
Authorization: Bearer <token>
```

**Query 参数**:
- `file_id` — 按 file 过滤
- `folder_id` — 按 folder 过滤
- `author_id` — 按作者过滤
- `is_resolved` — `true` / `false` (不传 = 全部)
- `parent_id` — 查特定 parent 的子回复 (默认 None = 仅顶层)
- `page`, `page_size` — 分页 (默认 1, 50; page_size 上限 100)

**Response 200**:
```json
{
  "items": [
    {
      "id": 1,
      "file_id": 42,
      "author": {...},
      "parent_id": null,
      "content": "顶层评论",
      "is_resolved": false,
      "replies": [
        {"id": 2, "parent_id": 1, "content": "嵌套回复", "replies": []},
        {"id": 3, "parent_id": 1, "content": "另一回复", "replies": []}
      ]
    }
  ],
  "total": 1
}
```

注意: `total` = 顶层评论数, 不含 replies. 分页作用于顶层.

### 1.3 单条详情

```http
GET /api/v1/drive/comments/{comment_id}
```

返回单条 + 所有直接子回复 (1 层嵌套). 深层嵌套请按 parent_id 逐层查.

### 1.4 编辑

```http
PATCH /api/v1/drive/comments/{comment_id}
Content-Type: application/json

{"content": "修改后的内容"}
```

**权限**: 仅 author 本人. **不能**修改 mentions / parent_id / target (防滥用).

**错误**: `403 FORBIDDEN` — 非 author.

### 1.5 删除

```http
DELETE /api/v1/drive/comments/{comment_id}
```

**权限**: 仅 author 本人. CASCADE 自动删所有子回复 (无残留).

**错误**: `403 FORBIDDEN` — 非 author. `404 RESOURCE_NOT_FOUND` — 不存在.

### 1.6 标记已解决 (幂等)

```http
POST /api/v1/drive/comments/{comment_id}/resolve
```

**权限** (满足任一):
- author 本人 (`comment.author_id == user_id`)
- file owner (`file.uploader_id == user_id`)
- folder owner (`folder.owner_id == user_id`)
- folder admin member (`DriveFolderMember.permission == "admin"`)

**幂等**: 已 resolved 再次调用不报错, 直接返回当前状态.

### 1.7 取消已解决 (幂等)

```http
POST /api/v1/drive/comments/{comment_id}/unresolve
```

权限同 resolve. 已 unresolved 再次调用不报错.

---

## 2. 权限模型

### 2.1 写评论 (POST)

用户必须能 **read** 目标 file/folder:
- `folder.owner_id == user_id` → admin (含 read)
- `folder.visibility == 'public'` → 所有人 read
- `DriveFolderMember.permission >= 'read'` → 邀请成员
- `file.uploader_id == user_id` → uploader 默认可访问 (即使 folder private)

### 2.2 编辑/删除评论 (PATCH / DELETE)

**仅 author 本人** (admin / 文件 owner 不 override).

设计原因: GitHub PR review 风格, 保证作者主权. 误发评论由作者自己撤回.

### 2.3 resolved 权限 (POST /resolve /unresolve)

满足任一即可:
1. author 本人
2. file owner (file.uploader_id)
3. folder owner (folder.owner_id)
4. folder admin member (DriveFolderMember permission='admin')

设计原因: 类似 GitHub issue close — author 自己关闭, 或 owner/admin 关闭 (话题终结).

### 2.4 与 PR6 FileComment 区别

| 维度 | FileComment (PR6) | DriveComment (PR9) |
|------|------------------|-------------------|
| target | 仅 file | file / folder (二选一) |
| 嵌套深度 | 2 层 (thread_depth ≤ 3) | 不限 (GitHub PR style) |
| resolved | 无 | `resolved_at` + `resolved_by` |
| author 删除 | SET NULL (保留评论) | CASCADE (评论删) |
| 编辑权限 | author 本人 | author 本人 |
| resolved 权限 | N/A | author / file owner / folder admin |
| 表名 | `file_comments` | `drive_comments` |

两表共存, 互不影响. 老 PR6 endpoint `/comments` 继续走 FileComment.

---

## 3. WebSocket 推送

**当前 PR 不集成 WS notification**, 留给 PR10 (计划中):

- 新评论创建 → 推送给 file/folder 订阅者
- 嵌套回复 → 推送给 parent.author + 提及 mentions
- resolved 状态变更 → 推送给 author + file owner

WS 推送架构与 Drive v2 PR8 (`ws_notifications`) 一致:
- channel: `drive.comments.{file_id}` / `drive.comments.{folder_id}`
- payload: `{type: "new_comment" | "new_reply" | "resolved", comment_id, ...}`

**前端监听方式** (PR10 落地后):
```js
ws.on('drive.comments.42', (msg) => {
  if (msg.type === 'new_comment') {
    // 增量添加评论到 UI
  }
})
```

---

## 4. 排错

### 4.1 创建评论报 400 "XOR 违反"

**症状**: `{"error": {"code": "VALIDATION_ERROR", "message": "file_id / folder_id 必须二选一"}}`

**原因**: 同时传 `file_id` + `folder_id` 或都不传. Pydantic `model_validator` 拦截.

**修法**: 二选一.

### 4.2 创建评论报 400 "不是 drive 文件"

**症状**: `{"error": {"code": "VALIDATION_ERROR", "message": "File id=X 不是 drive 文件 (storage_mode=kb), 不支持评论"}}`

**原因**: 评论流仅适用于 `storage_mode=drive` 的文件. 普通知识库文件不入评论流.

**修法**: 检查 `Knowledge.storage_mode` 字段, 仅对 drive 文件调用本接口. 老 KB 文件评论走 PR6 `/comments` (FileComment 表).

### 4.3 嵌套回复报 400 "target 不一致"

**症状**: `{"error": {"code": "VALIDATION_ERROR", "message": "嵌套回复必须与父评论同 file (父 file_id=N, 当前 file_id=M)"}}`

**原因**: 试图用 `folder_id` 嵌套回复 `file_id` 的评论 (或反向).

**修法**: 嵌套回复 target 必须与父评论完全一致.

### 4.4 编辑/删除评论报 403

**症状**: `{"error": {"code": "FORBIDDEN", "message": "仅 author 本人可编辑评论"}}`

**原因**: 当前用户不是 author. **Admin / 文件 owner 也不 override** (GitHub PR style).

**修法**: 由 author 自己操作, 或创建新评论修正.

### 4.5 resolved 报 403

**症状**: `{"error": {"code": "FORBIDDEN", "message": "无权标记该评论为已解决 (需要 author / file owner / folder admin)"}}`

**原因**: 当前用户既不是 author, 也不是 file owner, 也不是 folder owner/admin.

**修法**: 请 author / file owner / folder owner / folder admin 操作. 普通邀请成员 (`DriveFolderMember.permission == "read"|"write"`) 无 resolved 权限.

### 4.6 列表 total 与实际不符

**症状**: 创建 5 条评论后, `GET /drive/comments?file_id=X` 返回 total=1 但实际有 5 条.

**原因**: 默认仅返回**顶层评论** (parent_id IS NULL), 嵌套回复 (replies 数组) 不计入 total. 这是 GitHub PR 评论列表的标准模式 (顶层 = 主题数).

**修法**: 查所有评论数:
```sql
SELECT COUNT(*) FROM drive_comments WHERE file_id = X;  -- 含所有层
```

### 4.7 部署后 alembic upgrade 失败

**症状**: `alembic upgrade head` 报 "relation 'drive_comments' already exists" 或类似.

**原因**: 历史 environment 可能残留半迁移状态.

**修法**:
```bash
# 1. 确认 061 之前所有 migration 已应用
docker exec microbubble-agent-app-1 alembic current

# 2. 单步升级到 062
docker exec microbubble-agent-app-1 alembic upgrade 062_drive_comments

# 3. 再升级到 head
docker exec microbubble-agent-app-1 alembic upgrade head
```

### 4.8 性能: 大量嵌套回复的 list 查询慢

**症状**: 文件有 1000+ 评论时, `GET /drive/comments?file_id=X` 慢 (> 1s).

**原因**: 当前实现一次性拉所有 replies 并 group by parent (1 个 SQL), 嵌套深时 N+1.

**未来优化** (PR11 计划):
- 物化 path 字段 (`/1/4/7/` 形式), BFS 单次查询
- 加 `(file_id, parent_id, created_at)` 复合索引
- 前端 lazy load 深层嵌套

---

## 5. 测试覆盖

**E2E 测试**: `tests/test_drive_v2_pr9_comments.py` — 12 scenarios:
1. 创建顶层评论
2. 嵌套回复 (2 层深度)
3. 编辑 (author only)
4. 删除 (CASCADE 子回复)
5. resolved (author + file owner)
6. 跨用户 thread 全流程
7. 无权限用户 403
8. target 错配 400
9. XOR 校验 422
10. 非 drive 文件 400
11. folder 级别评论
12. 列表分页

**本地运行** (需要 PostgreSQL):
```bash
pytest tests/test_drive_v2_pr9_comments.py -v
```

**手动验证清单** (UI 验收):
- [ ] 顶层评论创建后立即可见
- [ ] 嵌套回复显示缩进 + @ 高亮
- [ ] resolved 评论有视觉标识 (灰底 + ✓ 图标)
- [ ] 非 author 看不到编辑/删除按钮
- [ ] 跨用户刷新看到对方回复
- [ ] folder 评论与 file 评论在同一 UI 流

---

## 6. 部署

### 6.1 跑迁移

```bash
docker cp alembic/versions/062_drive_comments.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
```

### 6.2 重启

```bash
docker compose restart app celery-worker
```

### 6.3 验证

```bash
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "\d drive_comments"

# 期望: 看到 file_id, folder_id, author_id, parent_id, content, mentions,
#       resolved_at, resolved_by, created_at, updated_at 列 + 7 索引
```

### 6.4 不需要配置项

新功能**无需新增 settings** — drive_comments 表是 schema-only 增量, 不引入新的 env 变量.

---

## 7. 后续 PR 计划

- **PR10**: WS notification 推送 (new_comment / new_reply / resolved 事件)
- **PR11**: 大量嵌套回复性能优化 (path 物化 + 复合索引) — **W68 第 8 批收官 (本节)**
- **PR12**: 邮件/企微通知 (mentions 真正发送)
- **PR13**: 评论搜索 (按 content / author / mentions 全文搜索)

---

## 11. PR11 — 嵌套路径物化 + GIN 索引 (2026-07-24, W68 第 8 批)

> **背景**: W68 第 3 批 F-1 (drive_comments) 留 TODO: 大量嵌套回复 (100+) 时 `list_comments` N+1 拉 replies 慢. 设计文档提到 "PR11 path 物化". 本节落地.
>
> **核心思想**: 在 drive_comments 表加 `path VARCHAR(500)` 物化嵌套路径, 加 GIN trigram 索引加速 path LIKE 查询, 一次 query 拿祖先链 (breadcrumb).

### 11.1 Schema 增量

```sql
-- 066_drive_comments_path.py
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE drive_comments ADD COLUMN path VARCHAR(500) DEFAULT '/';

-- WITH RECURSIVE 重算现有数据
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

CREATE INDEX ix_drive_comments_path_gin
    ON drive_comments USING GIN (path gin_trgm_ops);
CREATE INDEX ix_drive_comments_file_path
    ON drive_comments (file_id, path);
```

### 11.2 path 语义

| 场景 | path |
|------|------|
| 顶层 (parent_id IS NULL) | `/` |
| 顶层 id=5 的子评论 | `/5/` |
| 顶层 id=5 → 子 id=12 → 子 id=30 | `/5/12/30/` |
| 嵌套深度 N | segments 数 = N |

### 11.3 新增 API

#### 11.3.1 按 path prefix 过滤列评论

```http
GET /api/v1/drive/comments/by-path?file_id=42&path_prefix=/5/
Authorization: Bearer <token>
```

**Response 200**:
```json
{
  "items": [
    {
      "id": 12,
      "file_id": 42,
      "author_id": 5,
      "parent_id": 5,
      "content": "...",
      "path": "/5/12/",
      "depth": 2,
      ...
    }
  ],
  "total": 2,
  "matched_path_prefix": "/5/"
}
```

#### 11.3.2 祖先链 (breadcrumb)

```http
GET /api/v1/drive/comments/{id}/breadcrumb
Authorization: Bearer <token>
```

**Response 200**:
```json
{
  "ancestors": [
    {"id": 5, "path": "/", "depth": 0, "content_preview": "...", "author_name": "..."},
    {"id": 12, "path": "/5/", "depth": 1, "content_preview": "...", "author_name": "..."}
  ],
  "current": {"id": 30, "path": "/5/12/30/", "depth": 3, "content_preview": "...", "author_name": "..."},
  "total": 3
}
```

### 11.4 新增 service 方法

- `DriveCommentService.list_by_path_prefix(*, file_id?, folder_id?, path_prefix='/', limit, offset)` — 走 GIN 索引, 1 query
- `DriveCommentService.rebuild_paths(*, file_id?, folder_id?)` — 数据修复用, WITH RECURSIVE 重算
- `DriveCommentService.get_breadcrumb(comment_id)` — 1 query 走 path LIKE 拿祖先链

### 11.5 部署

```bash
# 1. 跑迁移
docker cp alembic/versions/066_drive_comments_path.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 重启
docker compose restart app celery-worker

# 3. 验证 (GIN 索引 + path 列)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "\d drive_comments" | grep -E "path|gin"

# 期望看到:
#   path                          | character varying(500)
#   ix_drive_comments_path_gin    | index
#   ix_drive_comments_file_path   | index
```

### 11.6 alembic 链风险

**down_revision 接 064_drive_documents** (064 是当前 head, 065 留待后续 PR 派工). W68 第 4 批 串单链纪律: 不破坏 alembic 链 (1 head only).

merge 后必须 verify:
```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
  c=Config(); c.set_main_option('script_location','alembic'); \
  s=ScriptDirectory.from_config(c); print(s.get_heads())"
```
期望只 1 个 head: `['066_drive_comments_path']`

### 11.7 性能预期

| 场景 | PR9 (无 path) | PR11 (有 path) |
|------|---------------|----------------|
| 列 100 嵌套评论 | 101 query (N+1) | 2 query (顶层 + 子) |
| 面包屑导航 (深度 10) | 10 query (递归) | 1 query (path LIKE) |
| 按 path prefix 过滤 | 不支持 | 1 query (走 GIN) |
| 嵌套深度计算 | N/A | ORM property (`DriveComment.depth`) |

### 11.8 测试

7 场景 e2e 测试在 `tests/test_drive_v2_pr11_path_materialized.py`:
1. 创建根评论 → path='/'
2. 创建子评论 → path 自动计算
3. 嵌套 5 层 path 正确性
4. list by path_prefix 过滤
5. breadcrumb 祖先链
6. rebuild_paths 数据修复
7. GIN 索引存在 + EXPLAIN 验证

### 11.9 后续 PR (W69+)

- **PR12**: 大文件评论 thread 虚拟滚动 (前端按需渲染)
- **PR13**: 评论搜索 (按 content / author / mentions 全文搜索 + GIN trigram 复用)
- **PR14**: 评论订阅 (新回复邮件/企微通知)