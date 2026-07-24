# W68 第 12 批 C-2: Drive v2 PR9 评论删除权限 (锚点范式第 153 守恒)

> **主基调**: W68 第 8 批 PR9 (commit 0bfe36751) 实施评论 CREATE / READ / UPDATE / 反应 4 能力, 缺 DELETE 端点. C-2 加 DELETE + 软删 + 3 角色权限 + audit_log 联动.
> **2026-07-24 收官**: 6 e2e PASS + 锚点范式第 153 守恒 + 5 新铁律沉淀. 0 production code 改动铁律维持 (PR9 续 = Drive v2 新功能扩展, 不破坏老路径).
> **分支**: `feat/w68-12th-batch-c2-pr9-comment-delete-2026-07-24` (主指挥合并)
> **plan 收官**: `C:/Users/pc/.claude/plans/drive-pr9-comment-delete-permission-2026-07-24.md` (NOT_IMPLEMENTED → COMPLETED)

---

## 1. 背景与决策

### 1.1 调研发现 (W68 第 12 批 A-1 plans-status)

W68 第 8 批 PR9 (commit 0bfe36751) 在 W68 第 9 批 D-2 调研中确认:
- drive_comments 表 4 个端点 (POST/GET/PATCH/reactions), 缺 DELETE
- 评论误发/违规内容无法删除, 只能 admin 改 DB (无审计 + 无权限)
- 商业网盘 (Dropbox/坚果云) 评论删除标配

### 1.2 决策 (主指挥拍板 W68 第 12 批 C-2)

1 个 DELETE 端点 + 软删 (`deleted_at` + `deleted_by`) + 权限控制 (author / file owner / 平台 admin) + 软删后保留 audit_log.

### 1.3 0 production code 改动铁律

PR9 是 W68 第 8 批启动的新功能 (Drive v2 网盘), 算例外 (W68 第 6+7+8 批 "Drive v2 系列" 例外清单明确允许).
- 仅在 `app/services/drive_*` + `app/api/drive_*` + `app/models/drive_*` + `app/schemas/drive_*` 新增/改
- 不动 `app/services/task_service.py` / `meeting_service.py` / `knowledge_service.py` 等老模块

---

## 2. 实施 (7 文件)

### 2.1 alembic 070_drive_comments_soft_delete.py (新建)

**Schema 增量**:
- `deleted_at TIMESTAMPTZ NULL` — 软删时间戳
- `deleted_by INT NULL FK members(id) ON DELETE SET NULL` — 删除人
- `ix_drive_comments_deleted_at` 索引

**down_revision**:
- `070 → 069_drive_comments_recursive_func` (B-2 075_drive_version_tags 还没合并, 临时接 069)
- 主指挥合并顺序: 069 → 075 (B-2 先) → 070 (C-2 改 down_revision='075_drive_version_tags' 并改名 076)

### 2.2 app/models/drive_comment.py (改)

加 deleted_at/deleted_by 列 + `is_deleted` property.

### 2.3 app/services/drive_comment_service.py (改)

**delete_comment 改造** (W68 第 8 批 PR9 老 hard delete → W68 第 12 批 C-2 软删):
- 3 角色权限校验 (author / file owner / 平台 admin, 满足任一)
- 软删: set deleted_at + deleted_by (不 DELETE FROM)
- 保留 audit_log (调用方 API 层写)
- 幂等: 已软删评论再次删 → 返回 False (API 层返 404)
- list_comments / list_by_path_prefix 默认过滤 deleted_at IS NULL

### 2.4 app/api/v1/drive_comments.py (改)

**DELETE 端点改造**:
- 同步写 audit_log (action='delete', resource_type='comment', status_code=204)
- audit_log 写失败 best-effort (try/except + logger.warning), 不阻塞 204
- 幂等: 已删评论返 404 (RESOURCE_NOT_FOUND)

### 2.5 tests/test_drive_pr9_comment_delete.py (新建 ~340 行)

**6 e2e 场景 PASS**:
1. author 删自己评论 → 204
2. file owner 删别人评论 → 204
3. 平台 admin 删评论 → 204
4. 普通成员删别人评论 → 403
5. 删不存在评论 → 404
6. 已软删评论再删 → 404 (幂等)

**自包含 fixtures** (不依赖 conftest.py 中已坏的 test_member):
- `author_member` / `second_member` / `admin_member` 各带 wechat_id (alembic 057 NOT NULL)
- `drive_folder` (public) + `drive_file` (storage_mode='drive', created_by=author_member)
- teardown: `SET session_replication_role = 'replica'` + DELETE

### 2.6 docs/drive-v2-pr9-comments.md (改)

§1.5 删除段重写:
- 权限: 3 角色 (author / file owner / 平台 admin)
- 行为: 软删 + audit_log + 子回复保留
- Schema 增量: deleted_at + deleted_by + ix_drive_comments_deleted_at
- 错误: 403 / 404 (含幂等)
- 前端行为变化: list API 默认过滤软删评论

### 2.7 plan Status (改)

`C:/Users/pc/.claude/plans/drive-pr9-comment-delete-permission-2026-07-24.md`:
- 旧: NOT_IMPLEMENTED (W68 第 12 批 C-2 派工)
- 新: COMPLETED (W68 第 12 批 C-2 收官) + 7 文件实施记录 + 6 e2e 场景 PASS

---

## 3. 5 新铁律 (永久纪律固化)

### 铁律 1: 软删必含 (deleted_at + deleted_by)

评论删除永远软删, 不硬删:
- `deleted_at TIMESTAMPTZ NULL` — 时间戳
- `deleted_by INT NULL FK members(id) ON DELETE SET NULL` — 删除人 (SET NULL 而非 CASCADE, 与 resolved_by 一致)
- list API 默认过滤 `deleted_at IS NULL`, 历史数据保留在 DB
- DB 物理清除靠 Celery beat 每天扫 (W68 后续留待)

反例: hard delete + CASCADE 子回复 (PR9 老逻辑) → 删 1 条带 5 子回复的评论, 5 子回复全没, 父子关系链断, 追溯审计失败.

### 铁律 2: 3 角色权限 (author / file owner / 平台 admin)

满足任一可删:
```python
is_author = comment.author_id == user_id
is_admin = (actor.role == 'admin')
is_file_owner = (file_row is not None and file_row.created_by == user_id)
if not (is_author or is_file_owner or is_admin):
    raise DriveCommentServiceError(403)
```

注意:
- 仅 `comment.file_id IS NOT NULL` 时才检查 file owner (folder 级评论无 file owner)
- folder owner / folder admin member 当前不开放删评论权限 (与 PR9 调研一致, 暂不扩展, 留 W69)
- 平台 admin 全权 (Member.role='admin', 不区分平台 admin / 课题组 admin)

### 铁律 3: audit_log 联动 (PR7 audit 复用)

API 层同步写 AuditLog (不在 service 层, 避免破坏幂等性):
```python
audit = AuditLog(
    user_id=current_user.id,
    method="DELETE",
    path=f"/api/v1/drive/comments/{comment_id}",
    action="delete",
    resource_type="comment",
    resource_id=str(comment_id),
    status_code=204,
    meta_data={
        "soft_delete": True,
        "comment_author_id": snapshot.author_id,
        "comment_file_id": snapshot.file_id,
        "comment_folder_id": snapshot.folder_id,
        "actor_role": getattr(current_user, "role", "member"),
    },
)
```

纪律:
- audit_log 写失败 → best-effort (try/except + logger.warning + db.rollback), 不阻塞 204 (用户体验优先, CLAUDE.md 2026-06-29 Phase 3 铁律 5 复用)
- service 层不写 audit (让 service 保持幂等, audit 是 API 层关注点)
- meta_data 必含 soft_delete=True 标识 (供后续审计统计区分软/硬删)

### 铁律 4: 软删不 CASCADE 子回复 (父子保留)

软删 = 单行 deleted_at, 不 DELETE FROM, 不触发 FK CASCADE.
- 子回复保留, parent_id 链不断
- list 时不显示软删评论, 但 list 子回复时如 parent 已软删 → 显示 "[父评论已删除]" 占位
- 未来恢复软删功能 (如需) → 只需 UPDATE deleted_at = NULL, 子回复立即恢复父子关系

反例: PR9 老 hard delete + parent_id CASCADE → 删 1 条父评论, 5 子回复全没, 父子链断, audit 无法追溯子回复原始 parent.

### 铁律 5: alembic 串单链 (070 临时接 069, 主指挥合并后改 075)

纪律 (W68 第 12 批 C-2 实操):
- B-2 075_drive_version_tags 还没合并, 本 PR 临时 down_revision="069_drive_comments_recursive_func"
- 主指挥合并顺序: 069 → 075 (B-2 先) → 070 (C-2 改 down_revision='075_drive_version_tags' 并改名 076)
- 验证: `python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"` 期望只 1 个 head

反例: 并行派多个 alembic migration agent 没明确 down_revision 接续关系 → merge 后双头 → `alembic upgrade head` 报 `Multiple head revisions are present` (CLAUDE.md W68 第 4 批 5 铁律)

---

## 4. 验证清单

- [x] alembic 070 syntax 正确 (`alembic upgrade head` 无错, 实际跑通, version_num 06X → 070)
- [x] 6 e2e 场景 PASS (在 docker microbubble-agent-app-1 容器内跑, 18.58s)
- [x] typing imports CI 0 错误 (`bash scripts/check_typing_imports.sh` 输出 "扫描了 163 个文件 OK 所有 typing 注解的 import 都齐全")
- [x] drive_comments 表加 deleted_at + deleted_by 列成功 (DB schema 验证)
- [x] audit_log 同步写 (audit_log 表新增 1 条记录 / 每次 DELETE 204)
- [x] list API 默认过滤 deleted_at IS NULL (软删评论不在前端展示)
- [x] plan Status 段更新 (NOT_IMPLEMENTED → COMPLETED)
- [x] docs §1.5 删除段重写 (3 角色 + 软删 + audit_log)
- [x] 0 production code 改动铁律维持 (PR9 续 = Drive v2 新功能扩展例外)

---

## 5. 锚点范式第 153 守恒

W68 累计 commits: 169 (第 8 批 155 + 第 9 批 12 + 第 10 批 5 + 第 11 批 6 + 第 12 批 C-2 1 待合并) → 单调上升预期.

W68 第 12 批 C-2 贡献 1 个 commit (7 文件):
- alembic 070 + model + service + API + e2e + docs + plan + memory

锚点范式第 153 守恒 = 本 PR 完整收口.

---

## 6. 沉淀的位置 (CLAUDE.md / memory / plan)

- `CLAUDE.md` — 本节经主指挥 grand closure 后可提取为 "## W68 第 12 批纪律沉淀" 子章节
- `memory/w68-route-12-c2-pr9-comment-delete-2026-07-24.md` — 本文件
- `C:/Users/pc/.claude/plans/drive-pr9-comment-delete-permission-2026-07-24.md` — plan Status 更新 (COMPLETED)
- `docs/drive-v2-pr9-comments.md` §1.5 — 用户文档
- `tests/test_drive_pr9_comment_delete.py` — 6 e2e 守门

---

## 7. 后续 PR (W68 留 / W69 启动)

1. **前端 UI 二次确认弹窗**: MobileFileCommentsView.vue + DesktopFileCommentsView.vue 长按/右键 → 弹 ElMessageBox → "删除后管理员仍可恢复 (90 天内), 您确定吗?" → 调 DELETE API. (W68 第 12 批 C-2 仅后端, UI 留给前端 PR)
2. **Celery beat 90 天物理清除**: 每天扫 deleted_at < now() - 90 days 的 drive_comments, 真删. (与 task_service.auto_purge_trash_task 同 pattern)
3. **评论恢复端点**: `POST /api/v1/drive/comments/{id}/restore` (admin only), 设 deleted_at = NULL. (W69 调研)
4. **folder owner / folder admin member 删权限扩展**: 与 resolve 权限统一, 留 W69.

---

## 8. commit 信息模板 (主指挥合并后填)

```
feat(drive-pr9): W68 第 12 批 C-2 评论软删 + 3 角色权限 (锚点范式第 153 守恒)

PR9 续: 加 DELETE 端点 (PR9 老 hard delete 移除).

变更 (7 文件):
- alembic 070_drive_comments_soft_delete.py (新建): deleted_at + deleted_by + 索引
- app/models/drive_comment.py: 加 2 列 + is_deleted property
- app/services/drive_comment_service.py: delete_comment 改软删 + 3 角色权限
- app/api/v1/drive_comments.py: DELETE 端点同步写 audit_log + 幂等
- tests/test_drive_pr9_comment_delete.py (新建): 6 e2e 场景 PASS
- docs/drive-v2-pr9-comments.md §1.5: 重写 (3 角色 + 软删 + audit_log)
- memory/w68-route-12-c2-pr9-comment-delete-2026-07-24.md (新建): 5 新铁律沉淀

alembic 链: down_revision='069_drive_comments_recursive_func'
主指挥合并后: 069 → 075 (B-2) → 070 (改 down_revision='075', 改名 076)

验证: 6 e2e PASS + typing imports CI 0 错误 + alembic upgrade head OK.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```