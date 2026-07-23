# Drive v2 PR10 — API & 部署文档（2026-07-24, W68 第 5 批骨架）

> **状态**: W68 第 5 派工调研 + 骨架收官。**W69 实施前**本文件为「未来 API 契约」+ 部署规划。W69 实施时按此契约实施。

---

## 1. 0. alembic 链风险（CLAUDE.md §2026-07-24 铁律）

> ⚠️ **W68 第 3 批双头事故教训**: 062/063 派工时未明确 down_revision 接续, merge 后 alembic 报 Multiple head revisions are present。

**本 PR 064 链**:
- `down_revision = "063_drive_file_versions"`
- 完整单链: `061_drive_folder_share → 062_drive_comments → 063_drive_file_versions → 064_drive_documents`

**派工时必须**:
- W69 派工 prompt 必须写 `down_revision = "064_drive_documents"`
- W70 派工 prompt 必须写 `down_revision = "064_drive_documents"` (W70 复用 064, 不写新 migration)
- W71 派工 prompt 必须写 `down_revision = "064_drive_documents"` (同上)

**merge 顺序**:
1. W69 (含 064) merge 进 main
2. W70 merge
3. W71 merge

**merge 后 verify**:
```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
# 期望: ['064_drive_documents']
```

---

## 2. API 契约（W69 实施）

### 2.1 WebSocket 端点

**URL**: `WS /api/v1/drive/collab/{file_id}?token=<jwt>`

**鉴权**: JWT token 走 query string（WS 协议限制 Header 复杂）

**鉴权失败**: 立即 close (code 4403)

**Client → Server 事件**:
| 事件 | payload | 说明 |
|------|---------|------|
| `op` | `{ "payload": "<base64>", "client_id": <uint32> }` | Yjs update 字节 |
| `awareness` | `{ "user": "张三", "cursor": 42, "color": "#FF7A5C" }` | 协作者状态 |
| `save` | `{ "request_id": "<uuid>" }` | 显式触发 flush |

**Server → Client 事件**:
| 事件 | payload | 说明 |
|------|---------|------|
| `init` | `{ "state": "<base64>", "version": 0 }` | 初始 state 同步 |
| `op` | `{ "payload": "<base64>", "origin": <client_id> }` | 其他客户端的 op |
| `awareness` | `{ "from": <client_id>, "payload": {...} }` | 其他客户端的协作者状态 |
| `saved` | `{ "version": N, "ops_count": M }` | flush 完成 |
| `error` | `{ "code": "PERM_DENIED" \| "FILE_NOT_FOUND" \| "RATE_LIMIT" \| "INVALID_OP", "message": "..." }` | 错误 |

### 2.2 HTTP 端点（辅助）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/drive/collab/{file_id}/snapshot` | GET | 拿最新 ydoc_state (二进制下载) |
| `/api/v1/drive/collab/{file_id}/text` | GET | 导出纯文本 (供 PR9 save_version) |
| `/api/v1/drive/collab/{file_id}/users` | GET | 当前活跃用户列表 |
| `/api/v1/drive/collab/{file_id}/history` | GET | 时间机器 (按时间窗口返回 op log) |

### 2.3 权限模型

| 端点 | 权限 |
|------|------|
| WS 连入 | `DriveService._can_see_file` (PR1 已有) |
| 发 op | `_can_see_file` + `_can_edit_file` (PR6 已有) |
| GET snapshot / text | `_can_see_file` |
| GET users | `_can_see_file` |
| GET history | 文件 owner / folder 管理员 / 平台管理员 |

### 2.4 Rate Limit

| 端点 | 限制 |
|------|------|
| WS op | 单 client 600/min (10 op/s 持续输入峰值) |
| HTTP GET | read tier 100/min |
| HTTP POST | write tier 30/min |

---

## 3. 数据模型

### 3.1 `drive_documents` (alembic 064)

```sql
CREATE TABLE drive_documents (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL UNIQUE
        REFERENCES knowledge(id) ON DELETE CASCADE,
    ydoc_state BYTEA NOT NULL DEFAULT ''::bytea,
    ops_count BIGINT NOT NULL DEFAULT 0,
    version_number INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0,
    last_edited_by INTEGER REFERENCES members(id) ON DELETE SET NULL,
    last_edited_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_drive_documents_file ON drive_documents(file_id);
CREATE INDEX ix_drive_documents_last_edited_by ON drive_documents(last_edited_by);
```

### 3.2 `drive_doc_op_logs` (alembic 064 同一 migration)

```sql
CREATE TABLE drive_doc_op_logs (
    id BIGSERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
    op BYTEA NOT NULL,
    client_id BIGINT NOT NULL,
    user_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_drive_doc_op_logs_file_time ON drive_doc_op_logs(file_id, applied_at);
CREATE INDEX ix_drive_doc_op_logs_user ON drive_doc_op_logs(user_id);
```

### 3.3 与 PR9 `drive_file_versions` 关系

- **PR9**: 顺序版本历史（手动 check-in）
- **PR10**: 实时协同（多人同时编辑）
- **共存**: PR10 可调用 PR9 `save_version` 留快照
- **无 schema 依赖**: 064 与 063 仅逻辑引用，无 FK

---

## 4. 服务层

### 4.1 `DriveCollabService` 接口

```python
class DriveCollabService:
    @staticmethod
    async def get_or_create_ydoc_state(db, file_id: int) -> bytes: ...

    @staticmethod
    async def apply_remote_op(
        db, file_id: int, op_bytes: bytes, client_id: int, user_id: Optional[int] = None
    ) -> bytes: ...

    @staticmethod
    async def get_snapshot(db, file_id: int) -> bytes: ...

    @staticmethod
    async def flush_ydoc_state(
        db, file_id: int, state: bytes, version: int
    ) -> None: ...

    @staticmethod
    async def export_text(db, file_id: int) -> str: ...

    @staticmethod
    async def get_active_users(db, file_id: int) -> int: ...
```

**W68 第 5 批**: 5 个方法均为 stub, 不连 DB, 仅验证签名
**W69**: 完整实现, 加 `YDocAdapter` 抽象层

### 4.2 Celery 任务

| 任务 | 周期 | 职责 |
|------|------|------|
| `flush_ydoc_state_task` | 30s | 从 collab-gateway 内存 Y.Doc 同步刷盘到 drive_documents |
| `compress_op_logs_task` | 每天 03:00 | 合并 7 天前 op → 写 ydoc_state → 删老 op |
| `cleanup_orphan_rooms_task` | 5min | 清无活跃 room (collab-gateway 内存) |

---

## 5. 前端 (W71)

### 5.1 依赖

```json
{
  "dependencies": {
    "yjs": "^13.6.0",
    "y-websocket": "^2.0.0",
    "y-codemirror.next": "^0.3.5",
    "@codemirror/state": "^6.4.0",
    "@codemirror/view": "^6.26.0"
  }
}
```

### 5.2 关键组件

- `web/src/composables/drive/useCollabSession.ts` — WS 连接 + 生命周期
- `web/src/views/drive/DriveCollabEditor.vue` — CodeMirror + Yjs 集成
- `web/src/components/drive/CollabUserList.vue` — 协作者头像列表
- `web/src/components/drive/CollabCursor.vue` — 远端光标渲染

### 5.3 离线兜底

- IndexedDB 暂存 Y.Doc 状态（参考 PWA 策略）
- 重连时 merge → 提交 ops

---

## 6. 部署（W69 / W70 / W71 三批派工时各跑一次）

### 6.1 W69 部署必做

```bash
# 1. 跑 alembic 064
docker cp alembic/versions/064_drive_documents.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 验证表
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_documents"
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_doc_op_logs"

# 3. Dockerfile 加 pycrdt (在 W68 第 5 批已确认 win_amd64 wheel 可用)
echo "pycrdt==0.14.1" >> requirements.txt
docker compose build app
docker compose up -d app
```

### 6.2 W70 部署必做

```bash
# 1. 注册 Celery beat
# 在 app/services/celery_app.py 加:
# - flush_ydoc_state_task (30s)
# - compress_op_logs_task (每天 03:00)
# - cleanup_orphan_rooms_task (5min)

# 2. 重启 celery-worker
docker compose restart celery-worker

# 3. 验证 Celery beat
docker exec microbubble-agent-celery-worker-1 celery -A app.celery_app beat --loglevel=info
```

### 6.3 W71 部署必做

```bash
# 1. 前端 npm install
cd web && npm install yjs y-websocket y-codemirror.next

# 2. npm run build (CLAUDE.md 铁律: 唯一合法 build 命令)
npm run build

# 3. 重启 nginx
docker compose restart nginx
```

### 6.4 6 点 curl 验证（CLAUDE.md §2026-06-13 铁律）

```bash
# 验证 HTML / WS endpoint 200 (SPA fallback 正常)
curl -sk -o /dev/null -w "%{http_code}\n" https://xxx/drive/collab/123

# 验证新表存在
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_documents"
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_doc_op_logs"

# 验证 pycrdt 装上
docker exec microbubble-agent-app-1 python -c "import pycrdt; print(pycrdt.__file__)"
```

---

## 7. 监控（W70 实施）

| 指标 | 来源 | 告警阈值 |
|------|------|----------|
| drive_documents.ydoc_state 大小 | PG `pg_column_size(ydoc_state)` | > 50KB |
| drive_doc_op_logs 行数 | PG `SELECT count(*) FROM drive_doc_op_logs WHERE applied_at > NOW() - interval '1 day'` | > 100k/day |
| WS 连入数 | app metrics | > 200 同时 |
| op 频率 (op/s) | app metrics | > 100/s/file |
| flush 失败率 | Celery metrics | > 1% |

---

## 8. 回滚策略

**Schema 回滚**:
```bash
docker exec microbubble-agent-app-1 alembic downgrade -1
# 回滚到 063_drive_file_versions
```

**应用回滚**:
```bash
git revert <commit-hash-of-pr10>
docker compose restart app celery-worker
```

**数据保留**:
- 064 表数据**不自动清理**（W70 实施 `compress_op_logs_task` 7 天压缩 + 保留 ydoc_state）
- 删表前先 `pg_dump drive_documents` 备份

---

## 9. 已知限制

| 限制 | 影响 | 缓解 |
|------|------|------|
| 1 文件仅 1 个 Y.Doc (UNIQUE) | 无法「同一文件 2 个独立编辑视图」 | 业务上不需要 |
| ydoc_state 50KB 阈值 | 大文档性能下降 | W70 强制 snapshot 重建 |
| 离线 op 重发 7 天后丢失 | 长离线用户数据丢失 | 文档重要性 < 7 天 |
| 移动端只读 | 手机无法编辑 | 简化版 input 兜底 |

---

## 10. 引用

- 设计 doc: [drive-v2-pr10-collab-editing-design.md](./drive-v2-pr10-collab-editing-design.md)
- memory: [memory/w68-route-5-drive-pr10-collab-2026-07-24.md](../memory/w68-route-5-drive-pr10-collab-2026-07-24.md)
- 串单链铁律: CLAUDE.md §2026-07-24
- pycrdt 0.14.1: https://pypi.org/project/pycrdt/
- Yjs 13.6.x: https://github.com/yjs/yjs
- y-codemirror.next: https://github.com/yjs/y-codemirror.next
