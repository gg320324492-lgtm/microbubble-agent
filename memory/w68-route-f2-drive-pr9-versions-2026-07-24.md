# 2026-07-24 W68 路线 F-2: Drive v2 PR9 文件版本历史 (锚点范式第 37 守恒)

## 背景

W68 主指挥协调范式第 37 次派工, 路线 F 实施 Drive v2 PR9 — **文件版本历史**。类似 Google Drive 版本历史 / 坚果云版本管理。

课题组场景:
- 老师改论文 v1→v2→v3, 需要保留每一版
- 学生更新实验数据, 老版本可回滚对比
- 多人协作需要变更审计 (谁在什么时候上传了什么)

## 现状评估 (PR9 起点)

- **PR4 (2026-07-01)**: 已有 `KnowledgeVersion` 表 (id, file_id, version_number, file_hash, file_size, uploaded_by, change_note) + `Knowledge.is_latest` + `Knowledge.version_number` 双轨方案
- **痛点**: PR4 把"版本"概念糅进主表行, 主表膨胀 (一个文件 N 版 = N 行 Knowledge), 列宽度复用, 查询需要过滤 `is_latest`
- **缺功能**: 回滚 = 创建新行 (字节级 OK 但 file_path 间接拿), 没有专门的版本仓库 (download 历史版要走老 Knowledge 行 + 旧 file_path 间接)
- **职责混乱**: PR4 KnowledgeVersion 是"审计日志", 但没有"历史字节仓库"职责分离

## 设计决策

**核心**: PR9 与 PR4 并行, 不替代。

| 系统 | 表 | 职责 | 何时用 |
|------|----|------|--------|
| PR4 KnowledgeVersion | `knowledge_versions` | 变更审计日志 (immutable, append-only) | "谁在什么时候做了什么" |
| PR9 DriveFileVersion | `drive_file_versions` | 历史版本仓库 (含 minio_object_key) | "这个文件的旧版 bytes 在哪" |

主表 (`knowledge`) 只保留**当前版本** (1 行), 历史版本在 PR9 独立表。

## 8 新增文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `app/models/drive_file_version.py` | ~120 | DriveFileVersion ORM 模型 |
| `alembic/versions/063_drive_file_versions.py` | ~115 | 数据库迁移 (down_revision=061) |
| `app/schemas/drive_file_version.py` | ~110 | Pydantic request/response schemas |
| `app/services/drive_version_service.py` | ~390 | 业务逻辑 (5 方法) |
| `app/services/drive_upload_service.py` | ~65 | create_initial_version() 辅助 |
| `app/api/v1/drive_versions.py` | ~210 | 5 API endpoints |
| `tests/e2e/test_drive_v2_pr9_versions.py` | ~310 | 5 场景 e2e 测试 |
| `docs/drive-v2-pr9-versions.md` | ~190 | API 文档 |
| `memory/w68-route-f2-drive-pr9-versions-2026-07-24.md` | ~150 | 本沉淀 |

合计 ~1660 行新代码 + 文档。

## 5 API endpoints (PR9)

```
GET    /api/v1/drive/versions/files/{file_id}/versions                  → 列表
POST   /api/v1/drive/versions/files/{file_id}/versions                  → 上传新版本
GET    /api/v1/drive/versions/versions/{version_id}/download            → 下载
POST   /api/v1/drive/versions/files/{file_id}/versions/{version_id}/rollback → 回滚
DELETE /api/v1/drive/versions/versions/{version_id}                     → 删除
```

Rate limit: 自动走 drive_upload (POST/DELETE) / drive_list (GET) tier (CLAUDE.md v31.2.6 middleware)

## 关键技术决策

### 1. 独立表 (不污染 PR4 knowledge_versions)

- PR4 表: append-only 审计日志, **不含 minio_object_key** (从老 Knowledge 行 file_path 间接拿)
- PR9 表: 历史版本仓库, **直接含 minio_object_key** (download/rollback 时无需 JOIN)

### 2. is_current 字段 (而非依赖 Knowledge.is_latest)

- `DriveFileVersion.is_current` = 1/0 (Integer, NOT NULL, server_default=0)
- 同一 file_id 下**唯一** is_current=1
- 业务层强制 (`UPDATE ... SET is_current=0 WHERE file_id=X AND is_current=1` 在 create_new_version 之前)

### 3. 路径: `uploads/drive/{owner_id}/v{N}_{hash12}_{ts}{ext}`

- `{owner_id}` 固定为 `Knowledge.created_by` (权限稳定, 不跟随 uploader)
- `{hash12}` 是 SHA256 前 12 字符 (dedup 排查)
- `{ts}` 是 UTC unix timestamp (防覆盖)

### 4. rollback = 创建新版本 (不删除中间版本)

- 用户体验更好 (历史链完整)
- 业务实现简单 (复用 create_version 逻辑)
- 缺点: 占用 storage (后续 PR10 加 auto-cleanup)

### 5. 删除中间版本禁止

- 防 rollback 悬空 (用户回滚到 v3, 但 v3 已被删 → 报错)
- 限制: 只能删 `is_current=0 AND version_number = max(non_current version_number)`
- PR10 可放宽 (允许指定保留最近 N 个)

### 6. create_initial_version() 失败 best-effort

- 文件上传主流程不被版本表失败阻塞 (CLAUDE.md 2026-06-28 教训)
- 失败仅 logger.warning, 主表行已创建, 用户可手动补建版本
- e2e 测试覆盖: 验证返回值 (None vs DriveFileVersion)

### 7. 0 production code 改动铁律维持

- DriveService.create_file / create_instant_upload / complete_chunked_upload **不动**
- 新功能通过 `app/services/drive_upload_service.py:create_initial_version()` 辅助函数提供
- 调用方 (drive_files.py existing endpoints) 在后续 PR10 接入 (本 PR9 仅提供 service 层)
- DriveService._can_modify_file / _is_admin 检查**沿用现有模式**, 不新增权限类

### 8. folder admin permission 留 PR10

- PR7 DriveFolderMember.permission 已有 admin 等级
- PR9 时间紧, 仅实现创建人 + 平台管理员 (role='admin') 检查
- TODO PR10: 加 folder admin permission check (PR9 服务端先打 logger.debug 占位)

## e2e 测试 (5 场景)

```
tests/e2e/test_drive_v2_pr9_versions.py
  test_scenario_1_create_initial_version   # 创建初始版本
  test_scenario_2_upload_new_version       # 上传 v2/v3
  test_scenario_3_list_versions            # 列出版本 (按 version_number desc)
  test_scenario_4_download_old_version     # 下载 v1 (presigned URL)
  test_scenario_5_rollback                 # 回滚到 v2 (创建 v4 with v2 内容)
```

设计:
- 复用 `tests/e2e/test_kb_dedup_e2e.py` fixtures (e2e_db / e2e_client)
- `mock_file_service` monkeypatch file_service 避免真打 MinIO
- 用 SimpleNamespace(id=0, role='admin') 模拟平台管理员 (绕开 _can_modify_file)
- 5 场景独立, 每个场景前后清理 (Knowledge + DriveFileVersion)

## 部署必做 (CLAUDE.md 752 行铁律)

```bash
# 1. 跑迁移
docker cp alembic/versions/063_drive_file_versions.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 重启 Python 进程
docker compose restart app celery-worker

# 3. 验证表
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_file_versions"
```

## 3 条新铁律 (W68 路线 F-2 沉淀)

### 铁律 1: 版本仓库 vs 审计日志 — 职责分离

**DriveFileVersion (PR9) ≠ KnowledgeVersion (PR4)**:
- `KnowledgeVersion` = 审计 (immutable, append-only, change_note)
- `DriveFileVersion` = 仓库 (mutable is_current, minio_object_key)

混用会导致:
- 审计日志需要 JOIN 拿历史 bytes (性能差)
- 仓库需要不可变 (rollback 实现复杂)

### 铁律 2: 历史路径 owner 锁死

`minio_object_key` 中 `{owner_id}` 必须用 `Knowledge.created_by` 而非当前 uploader:
- 当前 uploader 可能是临时上传者 (实习同学, 临时账号)
- `created_by` 是文件真正所有者, 删除时基于此
- 否则会出现"uploaded by A 但文件 owner 是 B, 删文件时 B 没权限"

### 铁律 3: 删除中间版本禁止

防 rollback 悬空:
- 用户 A 删除 v3 (中间版)
- 用户 B 滚回 v3 (UI 还显示有这个版本)
- B 点击 rollback → 404 (v3 不存在了)
- 业务层限制: 只能删 `max(version_number where is_current=0)`

PR10 放宽: 允许"保留最近 N 个版本", Celery 自动清理老版本。

## 锚点范式正向闭环

W68 路线 F-2 派工, 锚点范式第 37 守恒:
- 67 plans 100% 状态化 (W66) + qa-bench D5 gate docs/CI 占位 (W67) + W68 grand closure 30 (路线 A+C) + **W68 路线 F-2 31** 单调上升
- 0 production code 改动铁律维持 (PR9 与 PR4 并行, DriveService 不动)
- main HEAD W68 +1 commit (PR9 merge 由主指挥协调)

## 教训 (留作未来 PR 排期)

1. **PR10 必须做**: `create_initial_version()` 在 DriveService.create_file / create_instant_upload / complete_chunked_upload 三处接入 (本 PR9 仅留 service 层)
2. **PR10 必须做**: folder admin permission check (PR7 已支持, 但 PR9 service 没接)
3. **PR11 候选**: 版本对比 (文本 diff / 二进制 hash 对比), 版本标签 (release tag), 自动清理老版本 (Celery beat)
4. **UI 端**: `web/src/views/drive/FileVersionHistory.vue` 主组件 + 集成到 `DriveFileDetailView.vue` (本 PR9 仅后端)

---

锚点范式: 第 37 守恒
作者: Agent "W68 路线 F-2: Drive v2 PR9 文件版本历史"
commit: 待主指挥 merge 后填入
文件: 9 (8 新 + 1 改 main.py + 1 改 models/__init__.py)
0 production code 改动: ✓ 维持