# Drive v2 PR9 — 文件版本历史 (2026-07-24)

## 概述

PR9 在 Drive v2 网盘系统上引入**文件版本历史**功能，类似 Google Drive 版本历史 / 坚果云版本管理。 用户每次上传新版本，老版本完整保留，可随时查看 / 下载 / 回滚。

PR9 与 PR4 (`KnowledgeVersion`) 是**并行**的两套系统：
- **PR4 `KnowledgeVersion`** = 变更审计日志（immutable, append-only，每次 create_version/restore 调用一行）
- **PR9 `DriveFileVersion`** = 历史版本仓库（每版本一行，含 `minio_object_key` 用于回滚时 copy_object）

主表 (`knowledge`) 只保留**当前版本** (1 行)，历史版本在独立 `drive_file_versions` 表。

## 数据库变更

### 新增表: `drive_file_versions`

```sql
CREATE TABLE drive_file_versions (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL,  -- FK knowledge.id ON DELETE CASCADE
    version_number INTEGER NOT NULL,  -- 单调递增
    minio_object_key VARCHAR(500) NOT NULL,
    size BIGINT NOT NULL,
    uploader_id INTEGER NOT NULL,  -- FK members.id ON DELETE RESTRICT
    comment TEXT,  -- 可选备注
    is_current INTEGER NOT NULL DEFAULT 0,  -- 1=当前版本, 0=否
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_drive_file_versions_file_version ON drive_file_versions(file_id, version_number);
CREATE INDEX ix_drive_file_versions_file_current ON drive_file_versions(file_id, is_current);
CREATE INDEX ix_drive_file_versions_uploader ON drive_file_versions(uploader_id);
```

迁移: `alembic/versions/063_drive_file_versions.py` (down_revision=061)

## API 文档

### 1. 列出文件所有版本

```
GET /api/v1/drive/versions/files/{file_id}/versions
```

权限: 走 `_can_see_file`（private 仅 owner）

响应:
```json
{
  "file_id": 42,
  "file_name": "thesis.docx",
  "count": 3,
  "items": [
    {
      "id": 105,
      "file_id": 42,
      "version_number": 3,
      "minio_object_key": "uploads/drive/1/v3_a3f4b5c6..._1234567890.docx",
      "size": 524288,
      "uploader_id": 1,
      "uploader_name": "Alice",
      "comment": "Final revision",
      "is_current": true,
      "created_at": "2026-07-24T10:30:00"
    },
    ...
  ]
}
```

排序: 按 `version_number desc`（最新版本在前）

### 2. 上传新版本

```
POST /api/v1/drive/versions/files/{file_id}/versions
Content-Type: multipart/form-data
```

请求体:
- `file`: 新文件 bytes（UploadFile）
- `comment`: 版本备注（可选, max 500 chars）

权限: 创建人 OR folder admin OR 平台管理员 (Member.role='admin')

流程:
1. 校验文件存在 + 权限
2. 算下一版本号 = `max(version_number) + 1`
3. 写 MinIO: `uploads/drive/{owner_id}/v{N}_{hash12}_{ts}{ext}`
4. 创建 `DriveFileVersion` 行 (`is_current=1`)
5. 旧 `is_current=1` 行翻 `is_current=0`
6. 更新主表 `Knowledge` 行 (`file_path` / `file_size` / `version_number`)

响应: 201 Created
```json
{
  "version": { /* DriveFileVersionItem */ },
  "file_id": 42,
  "new_version_number": 3,
  "file_name": "thesis_v3.docx",
  "file_size": 524288
}
```

### 3. 下载指定版本

```
GET /api/v1/drive/versions/versions/{version_id}/download
```

权限: 走 `_can_see_file`（private 仅 owner）

响应:
```json
{
  "version_id": 103,
  "file_id": 42,
  "version_number": 1,
  "download_url": "http://localhost:9000/microbubble/uploads/drive/1/v1_abc...def.docx?X-Amz-Signature=...",
  "expires_in": 3600,
  "file_name": "thesis.docx",
  "size": 491520
}
```

`download_url` 是 MinIO presigned URL（1 小时有效），浏览器可直接 GET。

### 4. 回滚到历史版本

```
POST /api/v1/drive/versions/files/{file_id}/versions/{version_id}/rollback
Content-Type: application/json
```

请求体（可选）:
```json
{ "new_comment": "Rolled back to v2 because v3 has bugs" }
```

权限: 创建人 OR folder admin OR 平台管理员

流程:
1. 校验目标版本存在 + `file_id` 匹配
2. 从目标版本 `minio_object_key` **copy_object** 到新路径（`uploads/drive/{owner_id}/v{max+1}_{hash}_{ts}{ext}`）
3. 创建新 `DriveFileVersion` 行（`version_number=max+1`, `is_current=1`）
4. 旧 current 行翻 0
5. 更新主表 `Knowledge` 行

回滚 = **创建新版本**（不删除中间版本），历史链完整保留。

响应: 200 OK
```json
{
  "version": { /* 新版本 DriveFileVersionItem */ },
  "rolled_back_from": 2,
  "new_version_number": 4,
  "file_id": 42
}
```

### 5. 删除指定版本

```
DELETE /api/v1/drive/versions/versions/{version_id}
```

权限: 创建人 OR folder admin OR 平台管理员

**限制**:
- 不能删 `is_current=1` 的当前版本（先上传新版本才能删旧版）
- 只能删**最新非当前版本**（防误删中间版导致 rollback 悬空）

响应: 200 OK
```json
{
  "deleted_version_id": 103,
  "deleted_object_key": "uploads/drive/1/v1_abc...def.docx",
  "remaining_versions": 2
}
```

删除流程:
1. 删 MinIO object（best-effort, 失败不阻塞 DB 删除）
2. 删 DB 行
3. 返回剩余版本数

## 版本号自增规则

- 版本号 1, 2, 3, ... 单调递增
- 同一 `file_id` 下**唯一**（业务层用 `SELECT MAX(version_number)+1` 原子写入）
- 回滚 = 创建新版本号（不重用历史号）
- 删除版本**不重排**（删除 v2 后, v1 仍是 v1, v3 仍是 v3, 不会变成 v2）

## MinIO 存储路径约定

新版本路径: `uploads/drive/{owner_id}/v{n}_{hash12}_{ts}{ext}`

例:
- v1: `uploads/drive/1/v1_a3f4b5c6d7e8_1721808000.docx`
- v2: `uploads/drive/1/v2_9f8e7d6c5b4a_1721808200.docx`
- v3 (rollback 副本): `uploads/drive/1/v3_a3f4b5c6d7e8_1721808500.docx`（hash 来自 v1）

要点:
- `{owner_id}` 固定为 `Knowledge.created_by`（不跟随 uploader，权限稳定）
- `{hash12}` 是文件 SHA256 前 12 字符（用于 dedup 排查）
- `{ts}` 是 UTC unix timestamp（防覆盖）
- `{ext}` 是文件扩展名（小写，带 `.`）

## 回滚权限

| 角色 | list | download | upload_new_version | rollback | delete |
|------|------|----------|--------------------|----------|--------|
| 文件 owner (created_by) | ✅ 任何 visibility | ✅ 任何 visibility | ✅ | ✅ | ✅ |
| Folder admin (PR7 admin permission) | ✅ folder 范围内 | ✅ | ✅ | ✅ | ✅ |
| 平台管理员 (Member.role='admin') | ✅ 全部 | ✅ 全部 | ✅ 全部 | ✅ 全部 | ✅ 全部 |
| 其他成员 | ✅ visibility != private | ✅ visibility != private | ❌ | ❌ | ❌ |
| 匿名 | ❌ | ❌ | ❌ | ❌ | ❌ |

## 业务规则

1. **创建初始版本**: `app/services/drive_upload_service.py:create_initial_version()` 在新文件上传成功后调用（普通上传 / 秒传 / 分片上传 三路径统一）。
2. **版本号单调**: 业务层 `SELECT MAX + 1`，不依赖 PostgreSQL 序列（避免并发漏洞）。
3. **is_current 唯一**: 同一 `file_id` 下 `is_current=1` 只能有 1 行，业务层强制。
4. **删除中间版本禁止**: 防 rollback 悬空，仅允许删最新非当前版本。
5. **失败 best-effort**: `create_initial_version` 失败仅 logger.warning，不阻塞上传主流程（CLAUDE.md 2026-06-28 教训复用）。

## 调用方 (前端)

PR9 UI 由 Web 端 Drive v2 子组件实现:
- `web/src/views/drive/FileVersionHistory.vue` — 版本列表 + 上传新版本按钮
- `web/src/views/drive/VersionDiffViewer.vue` — 文本 diff（PR10 范围, 二进制 hash 对比已可用）
- `web/src/views/drive/FileUploadDialog.vue` — 新增 "上传为新版本" 选项

## 部署必做

```bash
# 1. 跑迁移
docker cp alembic/versions/063_drive_file_versions.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 重启 Python 进程 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 3. 验证表
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_file_versions"
```

不跑这两步,新代码读 `drive_file_versions` 表会报 `relation does not exist` 500。

## 后续 PR (PR10+)

- 共享盘版本（folder 维度版本, 不同 file_id 间共享版本池）
- 版本对比 (diff 算法, 文本/二进制 hash diff)
- 版本标签 (v1.0 release tag, 自定义命名)
- 自动清理老版本 (保留最近 N 个, Celery beat)

## 相关

- `app/models/drive_file_version.py` — DriveFileVersion 模型
- `app/services/drive_version_service.py` — 业务逻辑
- `app/services/drive_upload_service.py` — create_initial_version 辅助
- `app/api/v1/drive_versions.py` — 5 个 API endpoints
- `alembic/versions/063_drive_file_versions.py` — 数据库迁移
- `tests/e2e/test_drive_v2_pr9_versions.py` — 5 场景 e2e 测试
- PR4 (`app/models/knowledge.py:KnowledgeVersion`) — 并行审计日志
- PR7 (`app/models/drive_share.py`) — folder 权限模型（admin permission）

---

文档版本: 2026-07-24
作者: Agent "W68 路线 F-2: Drive v2 PR9 文件版本历史"
锚点范式: 第 37 守恒