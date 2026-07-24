# W68 第 7 批 B-1 — Drive v2 PR10 协同编辑 WS endpoint 实施 (2026-07-24)

**锚点范式第 80 守恒** (W68 第 5 批 58-72 → 第 7 批 B-1 第 80 守恒).

## 任务

W68 第 5 批 #2 已建调研 doc (456 行) + service 骨架 (305 stub) + alembic 064 (drive_documents + drive_doc_op_logs). W68 第 7 批 B-1 = 真实实施 CRDT 协同编辑:

- service 骨架 → 完整实施 (9 方法, 含 Redis pub/sub + 崩溃恢复)
- 新建 WS + REST API endpoint
- 新建 Celery flush + compress task
- 修正 model relationship
- 新增 e2e 6 场景
- docs §8bis 实施段 + 本 memory

## 交付 (6 文件, 全部 origin push)

| 文件 | 改动 |
|------|------|
| `app/services/drive_collab_service.py` | 305 stub → 630+ 行实施 |
| `app/api/v1/drive_collab.py` | 新建 WS + 2 REST (~320 行) + main.py 注册 |
| `app/services/drive_collab_tasks.py` | 新建 flush (30s) + compress (7 天) Celery task |
| `app/models/drive_document.py` | relationship 显式 primaryjoin + viewonly 修正 |
| `tests/test_drive_v2_pr10_collab_e2e.py` | 新建 6 场景 e2e (7 test) |
| `docs/drive-v2-pr10-collab-editing.md` | §8bis 实施段 |
| `app/core/celery.py` | 2 beat + imports + autodiscover 注册 |

## 验证

- e2e: `SKIP_DB_SETUP=1 pytest tests/test_drive_v2_pr10_collab_e2e.py -v` → **7 passed** (get_or_create / apply_op / get_snapshot / subscribe_room / room_channel / flush / crash_recovery)
- smoke (W68 第 5 批留): 6 passed (无回归)
- typing imports: 156 文件 0 错误
- celery: 2 collab task 注册成功 (flush_ydoc_state_task + compress_op_logs_task)
- API router: 3 route 全挂载 (WS collab + GET snapshot + POST op)

## 5 新铁律

### 铁律 1: WS 鉴权必须在 accept 前, token 走 query string
WS 协议 Header 复杂, JWT 走 `?token=<jwt>`。鉴权链: `decode_token` → `type=='access'` → `int(sub)` → `DrivePermissionService.check_file_owner_or_folder_admin`。任一失败 **在 accept 前** `close(code=44xx)` (4401 鉴权 / 4403 无权限)。accept 后再 close 客户端拿不到 close code 语义。复用 `ws_notifications.py` 模式。

### 铁律 2: op log 压缩删除前必须先重放确保 snapshot 完整
`compress_op_logs_task` 删 7 天前 op log 前, 对每个受影响 file_id 调 `recover_from_crash` (幂等重放 snapshot + 全部 op → 写回 ydoc_state)。**否则**删 op 后若 snapshot 恰好没含这些 op → 内容永久丢失。虽然 `apply_remote_op` 每次已同步落 snapshot, 但 compress 前显式重建是防御性双保险 (CRDT 幂等, 重复 apply 无副作用)。

### 铁律 3: snapshot 存全量 update 字节, 不是 state vector
`drive_documents.ydoc_state` 存 `Doc.get_update()` (无参, 全量), **不是** `Doc.get_state()` (state vector)。state vector 只是"我知道哪些 update"的摘要 (1-2 字节), 无法重建内容。客户端 init 需全量 update 才能 `apply_update` 重建。踩坑点: pycrdt `get_state()` 名字误导, 实为 state vector。

### 铁律 4: 跨 event loop 安全 — redis/session 由 handler 内按当前 loop 创建
方案 C 铁律 1 复用。service 层不在模块顶部创建 redis/session 全局单例。WS handler 内 `redis = await get_redis()` (loop-aware lazy pool) + `async with async_session() as db` (每次操作独立 session, WS 生命周期长不能用 Depends(get_db) 请求级 session)。Celery task 用 `create_celery_engine_and_session()` + NullPool + `engine.dispose()`。

### 铁律 5: pycrdt 双 FK-to-knowledge 表 relationship 必须显式 primaryjoin + viewonly
`drive_documents` 和 `drive_doc_op_logs` 的 `file_id` 都 FK 到 `knowledge`, **互相之间无 FK**。SQLAlchemy 无法推断 `DriveDocument.op_logs` join 条件 → mapper 初始化报 "Could not determine join condition ... no foreign keys linking these tables"。修法: 显式 `primaryjoin="DriveDocument.file_id == foreign(DriveDocOpLog.file_id)"` + `viewonly=True` (DB 级 CASCADE 走 knowledge FK, ORM 不承担删除传播, 避免 `delete-orphan` 对非 FK 关系报错)。W68 第 5 批骨架 model 的 `cascade="all, delete-orphan" + foreign_keys=` 写法在 mapper configure 时才炸 (骨架 smoke 未触发 mapper 全量配置, 故漏检)。

## endpoint 命名差异 (契约 vs 实施)

契约 §2.1 `/api/v1/drive/collab/{file_id}` → 实施 `/api/v1/drive/files/{file_id}/collab` (与 PR9 `/drive/files/{id}/versions` file 子资源命名对齐)。

## MVP 边界 (留 W70/W71)

- 无 in-memory collab-gateway (每 op 即时 DB 重建, 高频待 W70 内存缓存)
- 权限统一门槛 check_file_owner_or_folder_admin (W71 细分 read-only 观察者)
- awareness 协作者光标留 W71 前端
- cleanup_orphan_rooms_task 留 W70 (内存房间引入后才有意义)

## 部署必做

见 `docs/drive-v2-pr10-collab-editing.md` §8bis.6 (alembic 064 cp + clear cache + pycrdt requirements + 重启 app/celery-worker)。

## 引用

- 上游调研: [w68-route-5-drive-pr10-collab-2026-07-24.md](w68-route-5-drive-pr10-collab-2026-07-24.md)
- docs: docs/drive-v2-pr10-collab-editing.md §8bis
- 跨 loop 铁律: CLAUDE.md 方案 C 铁律 1
- alembic 单链铁律: CLAUDE.md §2026-07-24
