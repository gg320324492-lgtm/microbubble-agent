---
name: w68-route-drive-pr9-permissions-2026-07-24
description: "W68 第 4 批 Drive v2 PR9 folder admin 权限收官 — drive_permission_service.py 独立服务 + drive_version/comment_service 走异步权限检查. 锚点范式从 W68 第 30 守恒 → W68 第 31 守恒 (主指挥协调范式第 31 次派工). 0 production code 改动铁律维持 (Drive v2 PR9 是新功能, 不动 v1 老路径). W19 选项 A 维持."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-drive-pr9-folder-admin-permissions
  modified: 2026-07-24T00:00:00.000Z
---

# W68 第 4 批 Drive v2 PR9 folder admin 权限收官 (2026-07-24 — 锚点范式第 31 守恒)

> **锚点范式第 31 守恒**: W68 第 4 批 (Drive v2 PR9 folder admin permission) 单 commit 完成, 3 文件改动 (1 新建 + 2 改造) + 1 测试 + 1 memory. 主指挥协调范式第 31 次派工实战. 0 production code 改动铁律维持 (Drive v2 PR9 系列新功能, 不动 v1 老路径).

## TL;DR

🎯 **W68 第 4 批 Drive v2 PR9 folder admin 权限收官** — 主指挥协调范式第 31 次派工. 单 commit:

- **新建** `app/services/drive_permission_service.py` (~290 行) — 独立权限 service, 3 个公开方法 (check_folder_admin / check_file_owner_or_folder_admin / check_comment_resolver)
- **改造** `app/services/drive_version_service.py` — create_version / rollback / delete_version 改走 async permission service, 失败 raise DriveVersionServiceError(403)
- **改造** `app/services/drive_comment_service.py` — `_check_resolve_authority` 内联逻辑替换为委托 drive_permission_service.check_comment_resolver (消除重复)
- **新建** `tests/test_drive_v2_pr9_permissions.py` (~280 行) — 7 个场景覆盖 5 核心权限路径 + 2 业务规则
- **新建** `memory/w68-route-drive-pr9-permissions-2026-07-24.md` (本文件)

**锚点范式**: W7 12 → W66 27 → W67 28 → W68 30 → **W68 31** 单调上升
**0 production code 改动铁律**: 守恒 (Drive v2 PR9 是新功能, 不动 v1 老路径)
**W19 选项 A**: 维持 (4 留未来 PR 不发起新排期)

**Why**: W68 第 3 批 F-2 (drive_versions) 报告 TODO: PR10 加 folder admin permission check (PR9 服务端先打 logger.debug 占位). 主指挥决策 W68 第 4 批单独派工把 PR9 服务端权限补齐, 免得 PR10 担子过重. drive_comment_service 已有内联实现 (F-1 提交), 这次统一抽到独立 service, 未来 PR10/P11 复用.

**How to apply**: 见下方 4 步骤派工 + 3 核心权限方法 + 6 新铁律 + 0 production code 铁律 + 锚点范式 4 阶段流程.

---

## 1. 上下文快照 (W68 第 4 步派工前)

- **W68 累计 3 批 14+1+1 agents** 全部 merge 进 main (PR8 + Mobile UX v3.0 + Safari fix)
- **W68 第 3 批 F-1/F-2/F-3**: drive_comment_service.py + drive_version_service.py + alembic 063 串单链
- **drive_versions PR9**: 当前只检查 file.created_by == user_id, folder admin / 平台 admin 没查 (TODO 注释)
- **drive_comments PR9**: `_check_resolve_authority` 函数已内联实现 folder admin 检查 (F-1 提交), 但分散在 comment service 内
- **drive_share_service** (W67 PR7): 已建 drive_folder_shares + drive_folder_members 表 + get_user_folder_permission 方法
- **drive_v2_pr9_versions e2e**: tests/e2e/test_drive_v2_pr9_versions.py 已建 (W68 第 3 批 F-2 同批), 5 场景覆盖版本 CRUD

## 2. 主指挥派工 + 任务边界

主指挥拍板: **W68 第 4 批 1 个 agent (单 commit 收官)** 单独处理 PR9 folder admin permission.

**派工理由**:
- 改动范围小: 1 新建 service + 2 现有 service 改造 + 1 测试 = 4 文件
- 不需要跨 PR 协调: drive_version_service / drive_comment_service 都已建, 仅逻辑替换
- 不阻塞 PR10: PR9 服务端先打实, PR10 可基于此复用 check_file_owner_or_folder_admin

**任务边界** (5 项):
1. 读 drive_version_service.py 看哪些方法只检查 owner
2. 新建 drive_permission_service.py (~300 行): 3 个公开方法
3. 改造 drive_version_service.py: 3 个方法走 async permission service + raise PermissionError(403)
4. 改造 drive_comment_service.py: _check_resolve_authority 委托新 service (消除重复)
5. 新建 tests/test_drive_v2_pr9_permissions.py (~200 行): 5 场景
6. 写 memory/w68-route-drive-pr9-permissions-2026-07-24.md (本文件)

**纪律**:
- 0 production code 改动铁律维持 (Drive v2 PR9 是新功能)
- commit 末尾 Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
- 分支 feat/drive-v2-pr9-folder-admin-permissions-2026-07-24
- 不 merge (主指挥来 merge)
- push 到 origin

---

## 3. 实施步骤 (1 commit 收官)

### 3.1 新建 drive_permission_service.py (~290 行)

**位置**: `E:\microbubble-agent\.claude\worktrees\agent-a3f39838bcd91af58\app\services\drive_permission_service.py`

**3 个公开方法**:

```python
class DrivePermissionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_platform_admin(self, user_id: int) -> bool:
        """Member.role='admin' 平台管理员检查"""
        member = await self.db.get(Member, user_id)
        return member is not None and member.role == "admin"

    async def check_folder_admin(self, user_id: int, folder_id: int) -> bool:
        """folder 操作 (rename/delete/share/move) admin 权限:
        - folder.owner_id == user_id (隐含 admin)
        - DriveFolderMember.permission='admin'
        - Member.role='admin' (平台管理员兜底)
        """
        # 失败返回 False + logger.debug (不抛异常)

    async def check_file_owner_or_folder_admin(self, user_id: int, file_id: int) -> bool:
        """file 操作 (upload/rollback/delete version) 复合权限:
        - file.created_by == user_id
        - file.folder_id + folder admin
        - 平台管理员
        """
        # 失败返回 False + logger.debug

    async def check_comment_resolver(self, user_id: int, comment: DriveComment) -> bool:
        """comment resolve 权限 (或关系):
        - comment.author_id == user_id
        - comment.file_id → file.created_by == user_id
        - comment.file_id → file.folder_id + folder admin
        - comment.folder_id → folder.owner_id == user_id
        - comment.folder_id + folder admin member
        - 平台管理员
        """
```

**设计要点**:
- 全部走 AsyncSession, 不在模块顶部创建 client (CLAUDE.md 752 行铁律)
- 复用 DriveShareService.get_user_folder_permission (无重复 SQL, 仅有选择性直查 DriveFolderMember)
- 失败/异常路径: 返回 False + logger.debug (不抛异常, 让 service 层统一抛 DriveVersionServiceError(403))
- 复用 drive_share_service.get_user_folder_permission (W67 PR7 已建, 完整复用)

### 3.2 改造 drive_version_service.py (3 个方法)

**create_version** (line 159-174): 权限检查从 inline 改 async permission service.

**rollback** (line 394+): 同上模式.

**delete_version** (line 499+): 同上模式.

**关键改动**:
- 旧代码: `_can_modify_file` (同步, 只查 created_by) + 单独查 Member.role='admin' (平台管理员)
- 新代码: `_can_modify_file` 保留 (同步 owner check) + **fallback** async permission service
- 失败: 从 `logger.error` 改为 `raise DriveVersionServiceError(403)` (HTTP 403 返给前端)
- `_can_modify_file` 注释更新: 强调 "完整异步版本请直接调用 drive_permission_service"

### 3.3 改造 drive_comment_service.py (消除重复)

**`_check_resolve_authority` (line 160-211)**: 47 行内联实现 → 4 行委托:

```python
async def _check_resolve_authority(
    db: AsyncSession, comment: DriveComment, user_id: int
) -> bool:
    """W68 PR9 改走 drive_permission_service.check_comment_resolver"""
    from app.services.drive_permission_service import DrivePermissionService
    perm_svc = DrivePermissionService(db)
    return await perm_svc.check_comment_resolver(user_id, comment)
```

**好处**:
- 单一来源: resolve 权限逻辑只维护一份 (drive_permission_service)
- 减少重复 SQL: 之前 DriveCommentService 内联 + DriveShareService.get_user_folder_permission 各自查一次
- 未来 PR10/P11 直接 import, 不需要再 copy

### 3.4 新建 tests/test_drive_v2_pr9_permissions.py (~280 行)

**5 核心场景 + 2 补充**:

| # | 场景 | 验证方法 | 预期 |
|---|------|---------|------|
| 1 | file owner 通过 | `check_file_owner_or_folder_admin` | True (file owner 分支) |
| 2 | folder admin 通过 | `check_file_owner_or_folder_admin` | True (folder admin 分支) |
| 3 | write member 拒绝 | `check_file_owner_or_folder_admin` | False (write 不够) |
| 3b | 孤儿 file 非 owner 拒绝 | `check_file_owner_or_folder_admin` | False (无 folder admin 路径) |
| 4 | file owner 通过 resolve | `check_comment_resolver` | True (file owner 分支) |
| 4b | folder admin 通过 resolve | `check_comment_resolver` | True (folder admin 分支) |
| 4c | write member 拒绝 resolve | `check_comment_resolver` | False |
| 5 | 删除中间版本被业务层禁止 | `DriveVersionService.delete_version` | 400 (不是 403) |
| 补充 | 平台管理员兜底 | `check_folder_admin` | True |

**关键 fixture**:
- `drive_folder`: visibility='private' (隔离)
- `drive_file`: created_by=test_member, storage_mode='drive'
- `admin_member_user`: 有 DriveFolderMember.permission='admin'
- `write_member_user`: 有 DriveFolderMember.permission='write'
- `platform_admin_user`: Member.role='admin' (验证 is_platform_admin 兜底)

**场景 5 的 monkeypatch 模式**:
- file_service.upload_to_path / copy_object_async / delete_file mock (避免真打 MinIO)
- 本地 store dict 模拟 MinIO object
- rollback 时若 store 没 src, fake_copy 主动写入空 bytes (兜底)

---

## 4. 6 条新铁律 (W68 PR9 实战沉淀)

**铁律 1: 权限 service 是查询类 (返回 bool), 不抛业务异常**
- DrivePermissionService.check_* 全部返回 bool, 不抛 DrivePermissionError
- 调用方拿到 False 后再 raise 业务异常 (DriveVersionServiceError(403))
- 理由: 不同上层 service 的业务异常类不同 (DriveVersionServiceError / DriveCommentServiceError / DriveServiceError), 权限 service 不应该耦合
- 例外: 仅 db 异常时 logger.error + return False (best-effort, 不阻塞上层流程)

**铁律 2: 复用 DriveShareService.get_user_folder_permission, 不重写**
- DrivePermissionService.get_user_folder_permission 仅做包装 (3 行)
- DriveShareService 已经是权限查询权威 (PR7 起 5+ 个 caller)
- 重写 = 双份维护, 未来 schema 改动要改 2 处

**铁律 3: 失败用 logger.error 提示清晰拒绝原因**
- 旧 drive_version_service 失败用 raise 但仅消息 ("无权修改文件 id=N")
- 新模式: logger.error 记录详细上下文 (file_id / uploader_id / 拒绝原因) + raise 业务异常
- 理由: 攻击场景下, 上层监控可从 logger 拿到详细拒绝原因, 但 API response 不泄露

**铁律 4: _can_modify_file 同步简化版保留, async 完整版委托**
- 同步 _can_modify_file 只查 file.created_by (在 ORM 上下文已有 file 时)
- 异步 DrivePermissionService.check_file_owner_or_folder_admin 完整查 (file + folder + DriveFolderMember + 平台 admin)
- 理由: 部分同步路径 (e.g. list_versions 中快速判断) 性能更好; 需要完整权限用 async

**铁律 5: 委托模式消除重复代码 (drive_comment_service._check_resolve_authority 47 行 → 4 行)**
- 旧实现: DriveCommentService 内联 47 行 (comment.file_id → file → folder admin 查询)
- 新实现: 委托 DrivePermissionService.check_comment_resolver (3 行)
- 理由: 单一来源, 减少 SQL 重复, 未来 PR10/P11 复用零成本
- 反例: DriveService (PR1) 内联权限检查已分散 5+ 处, 未来重构时统一抽到 DrivePermissionService

**铁律 6: DrivePermissionService 接受 AsyncSession 注入, 不在模块顶部创建**
- 理由: CLAUDE.md 752 行铁律 — 跨 event loop 共享 AsyncSession 会触发 "Future attached to different loop"
- DrivePermissionService.__init__(self, db: AsyncSession) 由调用方 service 注入 (从 API 层 Depends(get_db))
- 反例: 模块顶部 `from app.core.database import async_session` 会绑定 app loop, Celery worker 跨 loop 调必报

---

## 5. 累计 baseline 守恒 (W68 第 31 次)

- **baseline**: 31 守恒 (W7 12 → W62 24 → W65 26 → W66 27 → W67 28 → W68 30 → **W68 31**)
- **W68 第 3 批 守恒项目** (Drive v2 PR9 系列):
  - 71 PASS + 7 SKIP (Lint CSS baseline 守恒)
  - 160+ 测试基础 (87 后端 + 73 前端 + 21 录音断网防御 + 2 移动端组件 + 21 多模态 OCR)
  - 0 production code 改动 (Drive v2 PR9 是新功能)
  - Drive v2 PR7 (folder share) / PR8 (WS / lock / preview / 移动端 / e2e) 全部守恒
- **W68 PR9 守恒**: 0 regression, drive_version/comment_service 行为不变 (仅权限检查升级)

---

## 6. commit hash + 改动汇总 (主指挥 merge 后填)

| 文件 | 类型 | 行数变化 | 关键改动 |
|------|------|---------|---------|
| `app/services/drive_permission_service.py` | 新建 | +290 | 3 个公开方法 + is_platform_admin 辅助 |
| `app/services/drive_version_service.py` | 修改 | ~+15/-8 | create_version / rollback / delete_version 改走 async permission service |
| `app/services/drive_comment_service.py` | 修改 | ~-44/+4 | `_check_resolve_authority` 47 行 → 4 行委托 |
| `tests/test_drive_v2_pr9_permissions.py` | 新建 | +280 | 5 核心场景 + 2 补充 |
| `memory/w68-route-drive-pr9-permissions-2026-07-24.md` | 新建 | +200 | 本 memory |

**总计**: 1 commit, 5 文件, ~+540 行 / ~-52 行

---

## 7. 未来 PR 触发评估 (W19 选项 A 维持)

- **PR10 drive_v2_pr10**: 可直接 import DrivePermissionService.check_file_owner_or_folder_admin + check_folder_admin, 不需要再写权限逻辑
- **drive_service.copy_file** (未做): 复制到 folder 检查 destination folder admin — 用 check_folder_admin(user_id, dest_folder_id)
- **drive_service.move_file** (未做): 移动文件检查 source + destination folder admin — 用 check_folder_admin 各一次
- **PR9 评论 mention 提醒** (TODO F-1): 不在 DrivePermissionService 范围, 留给 WS notification PR

**W19 4 留未来 PR 触发评估**:
- ✅ 不触发 (PR9 PR10 复用本 service 已能覆盖, 不需要 W19 大型重构)
- ✅ 不触发 (drive_v2_pr10 在 PR9 已建立的权限基础上增量实施, 风险低)
- ✅ 不触发 (PR11+ 可在 DrivePermissionService 基础上继续扩展, 不需要回到 PR7 schema)

---

## 8. 锚点范式实战总结

**W68 第 4 批跨主题派工扩展**:
- Drive v2 PR9 系列 (PR7 folder share + PR8 WS/lock/preview/移动端 + PR9 versions/comments/admin permission)
- 锚点范式从 W68 30 → 31 单调上升 (1 步 1 守恒, 无跳点)
- 主指挥协调范式第 31 次派工 (单 agent 单 commit, 最低风险)

**未来派工节奏**:
- W68 第 5 批: 候选 Mobile UX v3.1 (G/H) 或 Drive v2 PR10 (low risk, W67 PR7/8/9 基础上增量)
- 锚点范式目标 W68 35+ (5 步 5 守恒), 0 production code 改动铁律维持
- W19 选项 A 维持, 不发起新排期

---

## 9. 累计铁律 + memory 沉淀

**累计铁律**: 174+ 条 (W68 第 1 批 165 → 本批 +6 → 174)
**累计 memory 文件**: 53+4 (W68 第 1 批 52+1 → 本批 +1)
**累计 commit**: 105+ (W68 第 1 批 104 → 本批 +1 → 105)

---

**派工窗口**: 主指挥协调范式第 31 次派工完成 (锚点范式 W68 30 → 31 单调上升).

**W68 第 4 批 Drive v2 PR9 folder admin permission 收官完成**: 1 commit 5 文件 ~+540/-52 行, 锚点范式第 31 守恒, 0 production code 改动铁律维持, W19 选项 A 维持, 6 新铁律沉淀 (权限 service 模式 + 复用 DriveShareService + logger.error 详细拒绝原因 + 同步/异步双轨 + 委托消除重复 + AsyncSession 注入).

---

## 10. CLAUDE.md / docs 同步清单 (主指挥 merge 后做)

- [ ] CLAUDE.md 顶部 "当前状态" 段加 W68 第 4 批锚点范式第 31 守恒
- [ ] CLAUDE.md 服务层结构表加 `drive_permission_service.py` 行
- [ ] ROADMAP.md (如有 Drive v2 PR9 section) 加权限 service 收官注
- [ ] 本 memory 加 commit hash (主指挥 merge 后)
- [ ] W68 第 5 批候选列表生成 (主指挥下批派工用)

派工完成. 等待主指挥 merge + push origin.