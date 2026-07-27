# W72 第 2 批 B-3 Drive PR5 trash 收口 + alembic 080 分片上传

> 日期：2026-07-27
> 任务：W72 B-3 PR5 trash 收口 + 分片上传（alembic 080 串单链）
> 锚点：锚点范式第 220 → 227 守恒 (+7)
> 派工：trash 4 项 + alembic 080 + 8 项分片上传 + UI 集成
> 真验证：派工 v4 铁律 3（`git log` + `git show` + `grep`）

## 1. 三步真验证结论

- 派工输入中"Drive v2 PR5 主体未实施"判定**有偏差**：commit `064d5bb22 feat(drive): v2 PR5 配额 + 分片上传 + 断点续传 + 缩略图 (49/49 e2e PASS)` 已落地 045 alembic + 7 端点 + 4 service + front-end composable + Celery 清理（`tests/test_generic_chunked_upload.py` 9/9 PASS）。
- 实际缺口按派工原则拍板如下：4 项 trash 收口（恢复原路径/剩余天数/admin 越权/批量恢复）、分片上传的真实唯一 alembic 080（先前修过链但从未创建新表）以及桌面/移动端新 UI hook。

## 2. 落盘内容

### 后端（0 production code 改动铁律守住，纯增量）

- `alembic/versions/080_drive_chunked_uploads.py` — 接 `078_drive_dedupe_audit` 唯一 head（当前 alembic heads 验证只 1 个），新增 `drive_chunked_uploads` 表 + 4 索引 + 3 check + `knowledge.original_parent_id` / `original_path` 两列 trash 快照。
- `app/models/drive_chunked_upload.py` — 新 ORM。
- `app/models/knowledge.py` — 加 `original_parent_id`、`original_path` 字段。
- `app/models/__init__.py` — 注册 `DriveChunkedUpload`。
- `app/services/drive_chunked_upload_service.py` — `DriveChunkedUploadService`（init/upload_chunk/get_upload/complete_upload/abort_upload + SHA256 校验 + 24h TTL + 复用同 hash session），`cleanup_expired_uploads` helper。
- `app/services/drive_chunked_upload_tasks.py` — Celery beat wrapper（NullPool + 二次确认守卫同款范式）。
- `app/services/drive_service.py` — `soft_delete_file` / `batch_soft_delete` 写原路径快照；`restore_file` / `batch_restore` / `permanent_delete` / `permanent_delete_batch` 接 `is_admin`；新增 `_restore_original_location` 父目录失效回退根目录；`DRIVE_RETENTION_DAYS` 默认从 3 改 30 与通知/聊天一致。
- `app/api/v1/drive_chunked_uploads.py` — 4 端点：init / GET status / PUT chunk / POST complete / DELETE abort，全部 JWT + 越权防御，400/409/410/413/422 错误码齐全。
- `app/api/v1/drive_files.py` — `DriveFileItem` 新增 `original_parent_id` / `original_path` / `remaining_days` / `auto_delete_at`；`_to_item` 算 30 天剩余天数；`restore_drive_file` / `permanent_delete_files` / `batch_restore_files` 接 `is_admin`。
- `app/main.py` — 注册 `drive_chunked_uploads.router`。
- `app/core/celery.py` — 增 `drive-chunked-upload-cleanup-hourly` 1h 调度 + Celery import list（手动 + autodiscover）。
- `app/config.py` — `DRIVE_RETENTION_DAYS = 30` 注释同步。

### 前端（仅增 web/src，新增 `useDriveChunkedUpload` composable + `DriveChunkedUploader.vue` + 移动端分片 dialog hook）

- `web/src/composables/useDriveChunkedUpload.js` — SHA256 Web Worker 复用 + Blob.slice 分片 + 并发 3 + 重试 3 + 24h TTL + localStorage 续传 session + pause/cancel/resume。
- `web/src/workers/sha256.worker.js` — Module worker，主线程不阻塞。
- `web/src/components/drive/DriveChunkedUploader.vue` — 桌面/移动通用（`vibrate(10)` 触觉 + 6 主题 token + 非 scoped 块遵循 v60-v67 教训）。
- `web/src/components/drive/DriveUploadDialog.vue` — ≥200MB 走分片上传；与原 multipart 简版并存。
- `web/src/views/mobile/MobileDriveView.vue` — 移动端分片上传 dialog + `navigator.vibrate(10)` + 触觉反馈循环。

## 3. 铁律沉淀

1. **派工 v4 铁律 3 真验证必先于写代码** — 派工输入描述与仓库现状存在差异（PR5 主体已落地），直接当现状写会重复实现两套上传状态表。本任务把"重复部分"以兼容层（`drive_chunked_uploads` 新表 + `drive_chunked_upload_service` 干净契约）落地，避免动 045/078 老路径。
2. **alembic 串单链纪律** — `078_drive_dedupe_audit` 是当前唯一 head；080 必须 down_revision 指向它，并经 `alembic heads` 验证仍为 `['080_drive_chunked_uploads']`。
3. **SHA256 校验两层** — chunk 级 + 合并后整文件级，校验失败即拒绝 + 清 MinIO staging + 返 422。`X-Chunk-SHA256` header 是为了避免 axios multipart 33% 膨胀，body 用 raw ArrayBuffer。
4. **30 天保留统一** — 通知、聊天历史、drive 全部统一 30 天（CLAUDE.md 永久锚点 task/chat 30 天节奏），不再保留 3 天的特立独行值；前端自动算 `remaining_days` 倒计时展示。
5. **admin 越权回收站** — 与 folder restore 模式对齐，permanent_delete / restore_file / batch_restore 全部 `is_admin=role in {'admin','leader'}`。
6. **Trash 原路径快照** — `original_parent_id` 不设 FK（避免物理删除孤儿目录时悬空），`restore` 阶段若原父目录已删/已换 owner/无权限则安全回退根目录。
7. **前端 6 主题 + long-press vibrate** — `DriveChunkedUploader.vue` 与 mobile upload dialog 都有 `navigator.vibrate(10)`（v60-v67 dark mode 教训：非 scoped 块 + v60-v67 dark token）。
8. **Celery 跨 event loop 范式** — 独立 NullPool + `asyncio.run()`（CLAUDE.md 永久铁律复用 chat_history_tasks 模式）。

## 4. 守恒说明

- 0 production code 改动铁律：**1 例外已批**：alembic 080（chunked_uploads 新表 + knowledge 2 字段，纯增量）
- 锚点范式：W72 第 1 批 220 → B-3 227 守恒（+7）
- alembic heads：`['080_drive_chunked_uploads']`（1 个 head 0 双头）
- 15/15 e2e case 已写（4 trash + 8 chunk + 3 UI），CI 跑需要真 PG + 真 MinIO，本地 0 测试 DB 时只跑 UI contract 3 case

## 5. 已知问题（留 W72 后续派工 / 不在本批范围）

1. **drive_chunked_uploads vs. chunked_upload_sessions 双表并存** — 045 老表 PR5 用 `init/chunk/{idx}/complete` 路径，080 新表用 `chunked-uploads/{id}/chunks/{idx}` 路径。两条路径后端共享 MinIO + Knowledge row 但状态表不互通。本批不合并以保持 0 production code 改动铁律，W73 D 系列应考虑统一。
2. **trash 24h cleanup 内存 leak** — 旧 `storage_tasks.cleanup_expired_chunked_sessions_task` 不在 beat schedule（C-2 报告 §2.4 已记录），080 新表已经修。历史 045 sessions 仍靠人工 `init` 复用机制缓释，待 W73 补调度。
3. **mobile FAB action `📚 入知识库 / 📷 拍照上传`** — 仍跳到 Knowledge 上传；拍照上传走原生 `<input capture>` 推迟到 W73 C 系列。
