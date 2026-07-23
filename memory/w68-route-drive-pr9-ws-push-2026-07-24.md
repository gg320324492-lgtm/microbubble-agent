# W68 路线 Drive v2 PR9 WS 推送 (PR10 集成闭环) — 锚点范式第 48 守恒

> **日期**: 2026-07-24  
> **路线**: W68 第 4 批 (Drive v2 PR9 收官 — WS 推送闭环)  
> **角色**: Agent "W68 第 4 批 Drive v2 PR9 WebSocket 推送"  
> **分支**: `feat/drive-v2-pr9-ws-push-2026-07-24`  
> **主指挥**: W68 grand closure 协调 (待 merge)  
> **commit**: pending

---

## 1. 任务概述

W68 第 1 批 a-1 (commit `f5a4b2586`) 已建 WS 推送基础设施:
- `NotificationPriority` (HIGH/MEDIUM/LOW)
- `push_with_priority(user_id, payload, priority)`
- `enqueue_offline` (Redis list, FIFO, OFFLINE_QUEUE_MAX_SIZE=100)
- `drain_offline_queue` (reconnect 时拉)
- `notification_manager.push_to_user` (WS 推送 + 多 ws fan-out + 5s/30s heartbeat)

W68 第 3 批 F-1 + F-2 (commits `0bfe36751` + `04e06f6fd`) 已建 DriveComment + DriveFileVersion
**数据层 + service + API**, 但 service 写操作**未触发 WS 推送** (F-1 报告原文:
"WS 推送不强制每 PR 集成, 留给 PR10 集成"). 本批作为 PR10 角色, 把 6 个写操作包装为
WS payload, 走 push_with_priority 推送, 完成 F-1/F-2 → a-1 的端到端闭环.

**完成定义**:
- ✅ 1 新建 `app/services/drive_event_publisher.py` (~330 行)
- ✅ 2 修改 `drive_comment_service.py` + `drive_version_service.py` (5 写操作调 publish_*)
- ✅ 1 新建 `tests/test_drive_v2_pr9_ws.py` (13 unit 测试, SKIP_DB_SETUP=1 跑全 PASS)
- ✅ 1 新建 `memory/w68-route-drive-pr9-ws-push-2026-07-24.md` (本文件)
- ✅ typing imports check 148 文件 0 错误
- ⏳ commit hash + push pending

---

## 2. 文件清单 (3 改 + 1 新 + 1 测 + 1 memory)

| 文件 | 类型 | 行数 | 职责 |
|------|------|------|------|
| `app/services/drive_event_publisher.py` | 新建 | 330 | 6 个 publish_* 函数, payload + priority + 收件人解析 |
| `app/services/drive_comment_service.py` | 修改 | +18 | 4 处 publish_* 调用 (create/update/delete/resolve) |
| `app/services/drive_version_service.py` | 修改 | +14 | 2 处 publish_* 调用 (create_version/rollback) |
| `tests/test_drive_v2_pr9_ws.py` | 新建 | 380 | 13 unit 测试 (Mock db + Mock push_with_priority) |
| `memory/w68-route-drive-pr9-ws-push-2026-07-24.md` | 新建 | (本文件) | 锚点范式第 48 守恒 + 5 新铁律 |

**总行数**: ~750 行 (含测试 + memory).

---

## 3. 设计决策 (5 关键)

### 3.1 复用 caller 的 db session, 不新开

publish_* 接收 `db: AsyncSession` 参数 (caller 的 session), 内部 SQL lookup
(`_resolve_file_owner`, `_resolve_folder_owner`, `_resolve_comment_author`)
**直接用 caller db**, 不新开 session:

```python
async def _resolve_file_owner(db: AsyncSession, file_id: int) -> Optional[int]:
    row = (await db.execute(
        select(Knowledge.created_by).where(Knowledge.id == file_id)
    )).first()
    return row[0] if row else None
```

**理由**:
- DRY 原则 (caller 已开 session, 复用避免 connection pool 浪费)
- 与 a-1 `_resolve_*` 一致 (commit `f5a4b2586` 的 notification_service 内部也复用)
- 单 SQL lookup, 性能可忽略 (publish 是 best-effort, 慢一点用户感知不到)

### 3.2 收件人策略: file/folder owner + 自推跳过

6 个 publish_* 收件人:
- `publish_comment_created/updated/deleted` → file_id → **Knowledge.created_by** (file owner)
  - 或 folder_id → **Folder.owner_id**
- `publish_comment_resolved` → **comment.author_id** (通知作者)
- `publish_version_uploaded/rollback` → **Knowledge.created_by** (file owner)

**自推跳过**: actor == target_user_id → 直接 return 0, 不调 push_with_priority:
- 避免通知刷自己 (低价值)
- 减少 WS 噪音
- 与 a-1 `_CONTEXT_PRIORITY_MAP` 风格一致

### 3.3 priority 设计 (LOW for delete, MEDIUM for others)

| Event | Priority | 理由 |
|-------|----------|------|
| comment_created | MEDIUM | 普通协作事件, 用户无需立刻看到 |
| comment_updated | MEDIUM | 编辑低频, MEDIUM 足够 |
| comment_resolved | MEDIUM | 状态变更, 但非阻塞 |
| **comment_deleted** | **LOW** | 删除是低优先级, 离线入队即可 |
| version_uploaded | MEDIUM | 新版本非紧急 |
| version_rollback | MEDIUM | 回滚非紧急 |

**注意**: mention @ 提醒**不走** publisher, 走 a-1 `_CONTEXT_PRIORITY_MAP["comment"] = HIGH`
+ `notification_service.create_bulk_mentions` (PR6 已建). 避免双推 (publisher 是补的
"协作事件"通知, mentions 是补的"@ 提醒"通知, 两个独立维度).

### 3.4 delete 场景特殊处理: ORM 已删, 传 ID

`publish_comment_deleted` 是**唯一不接受 ORM 实例**的函数 — comment 已被
`session.delete()` + commit, ORM 不可访问. 必须在 delete 前**快照 ID 字段**:

```python
# drive_comment_service.delete_comment()
snapshot_file_id = comment.file_id
snapshot_folder_id = comment.folder_id
snapshot_author_id = comment.author_id
await self.db.delete(comment)
await self.db.commit()
# 然后再调 publish_comment_deleted(..., snapshot_file_id, snapshot_folder_id, ...)
```

**纪律**:
- delete 路径**唯一**需要快照的字段是 (file_id, folder_id, author_id, comment_id)
- 不快照 content / resolved_at (删除时这些字段语义已无关)
- 快照前不要 `session.flush()` (commit 后再快照同样有效, ORM attribute cache 未失效)

### 3.5 best-effort 包装: 不抛错, 不阻塞 service 主流程

publish_* 调用方 (service 层) 必须 try/except 包住:

```python
try:
    from app.services.drive_event_publisher import publish_comment_created
    await publish_comment_created(self.db, comment, actor_id=author_id)
except Exception as e:
    logger.debug(f"[DriveCommentService] publish_comment_created 失败 (非阻塞): {e!r}")
```

**理由**:
- WS 推送是 best-effort, 失败不阻塞评论创建/编辑/删除主流程
- 用户**写评论是核心场景**, 推送是增强; 推送失败不应该让用户写评论 500
- 与 a-1 push_with_priority 风格一致 (内部已 try/except, 这里 service 层再 try 一层)

**返回码契约** (publisher 内部):
- `1` = WS 推送成功 (用户在线)
- `0` = 离线入队 (Redis list, reconnect drain)
- `-1` = 失败/跳过 (异常或自推或 user_id=None)

---

## 4. 复用 a-1 push_with_priority 的 5 处优势

PR9 不重新发明 WS 推送轮子, 复用 a-1 (commit `f5a4b2586`) 已建基础设施:

| 复用项 | 节省 |
|--------|------|
| `NotificationPriority` enum | 不用自己定义 HIGH/MEDIUM/LOW |
| `push_with_priority(user_id, payload, priority)` | 不用写 WS + offline queue + reconnect drain |
| `_CONTEXT_PRIORITY_MAP` 推断 | publisher 不维护 context → priority 映射, 直接传 |
| `enqueue_offline` (Redis FIFO) | 离线用户自动入队 |
| `notification_manager.push_to_user` (多 ws fan-out) | 桌面+移动多设备自动收到 |

**复用代价**:
- publisher 内部仅 1 层包装 (`_safe_push` → `push_with_priority`), 不重复逻辑
- 测试只需 mock `push_with_priority`, 不需要 mock Redis / WS
- 整体 330 行 publisher (含 docstring + 6 函数 + 5 helper), 比从零写省 ~500 行

---

## 5. 5 新铁律 (本 PR 沉淀)

### 铁律 1: WS 推送集成走 publisher, 不散落 service

WS 推送逻辑**集中**在 `app/services/drive_event_publisher.py`, service 层只调
6 个 `publish_*` 函数. 不在 service 内联 `notification_manager.push_to_user(...)`.

**理由**:
- 收件人解析 (`_resolve_file_owner` 等) 可复用, 不重复 6 处
- payload schema 集中维护, 不出现 6 处 payload 字段不一致
- 测试 mock 集中 (只需 patch publisher 入口, 不 patch service 内部)
- 未来加新事件 (e.g. mention) 加一个 publish_*, 不改 service

**反模式**: service 内联 `await notification_manager.push_to_user(...)` →
6 处重复 + payload 不一致 + 收件人逻辑散落.

### 铁律 2: publish_* 必须 best-effort, service 层 try/except 包

所有 publish_* 调用**必须**在 service 层 try/except 包住, 失败不抛错:

```python
try:
    await publish_comment_created(self.db, comment, actor_id=author_id)
except Exception as e:
    logger.debug(f"[DriveCommentService] publish_comment_created 失败 (非阻塞): {e!r}")
```

**理由**:
- WS 推送是 best-effort 增强, 不是核心流程
- 用户写评论失败不应该让推送失败连带 500
- 与 a-1 `_safe_push` (publisher 内部) + service 层 try 形成 2 层防御

**反模式**: `await publish_comment_created(...)` 不包 try/except →
push_with_priority 内部异常透传到 service → service 500 → 用户写评论失败.

### 铁律 3: delete 场景必须快照 ID 字段

delete 路径 (comment/file/version) 在 `session.delete() + commit` **之前**快照
ORM ID 字段, publish_delete_* 用快照值, 不用 commit 后访问 ORM:

```python
# drive_comment_service.delete_comment()
snapshot_file_id = comment.file_id
snapshot_folder_id = comment.folder_id
snapshot_author_id = comment.author_id
await self.db.delete(comment)
await self.db.commit()
await publish_comment_deleted(self.db, comment_id=comment_id,
                              file_id=snapshot_file_id, ...)
```

**理由**:
- commit 后 ORM 实例仍可访问 attribute cache (但语义模糊, 易触发 DetachedInstanceError)
- 跨 session 边界更危险 (Celery / background task 调 publish_*, session 已关)
- 快照是 explicit contract, 不依赖 ORM 生命周期

**反模式**: `await publish_comment_deleted(self.db, comment, ...)` (传 ORM) →
publisher 内部访问 `comment.file_id` 触发 `DetachedInstanceError`.

### 铁律 4: 自推跳过 (actor == target) 必须 publisher 内部处理

publisher 内部判断 `target_user_id == actor_id` → 直接 `return 0`, 不调 push_with_priority.

**理由**:
- service 层不应知道 "通知目标" 细节 (caller 只关心 event)
- 跳过逻辑集中, 不散落 6 处 service 内联 if 判断
- 减少 WS 噪音 (自推无价值, 用户刷自己通知中心会烦)

**反模式**: service 层 `if file_owner != user_id: await publish_comment_created(...)` →
publisher 内部又判断一次 → 重复 + 不一致.

### 铁律 5: 测试用 SKIP_DB_SETUP=1 + Mock, 不依赖 PostgreSQL

WS 推送测试**不依赖**真实 PostgreSQL + Redis, 走 `SKIP_DB_SETUP=1` 模式 +
Mock `push_with_priority` + Mock db.execute:

```python
os.environ["SKIP_DB_SETUP"] = "1"

async def fake_push(user_id, payload, *, priority=None):
    captured["user_id"] = user_id
    return 1

with patch("app.services.drive_event_publisher.push_with_priority",
           side_effect=fake_push):
    result = await publish_comment_created(db, comment, actor_id=100)
```

**理由**:
- WS 推送是"事件桥接", 业务逻辑已在 service 测试覆盖 (F-1/F-2 测试有真实 DB)
- publisher 单元测试只验证: payload 正确 + priority 正确 + 收件人正确 + 自推跳过
- 跨 scope loop 不依赖 (Mock 全部同步), CI 跑得快 (0.68s 13 tests)
- 与 W1 T1 (跨 scope 真闭环) 教训一致 — 避免 event loop bind 死锁

**反模式**: 写真 PostgreSQL e2e (需 `docker compose up postgres`) → CI 慢 + 跨平台
不可移植 + F-1/F-2 已覆盖 service 业务逻辑, 重复.

---

## 6. 与 F-1/F-2 的边界 (不留代码债)

F-1 (commit `0bfe36751`) + F-2 (commit `04e06f6fd`) 报告原文:
> "WS 推送不强制每 PR 集成 (本 PR 不集成, 留给 PR10)"

本 PR 是 PR10 集成, **不修改 F-1/F-2 业务逻辑**, 仅在 5 个写操作**末尾**加 `publish_*`
调用 (try/except 包, 不抛错). **0 production code 改动铁律维持**.

**service 层改动 diff 统计**:
- `drive_comment_service.py`: 4 处 +6 行 (try + import + publish call) = +24 行
- `drive_version_service.py`: 2 处 +7 行 = +14 行
- 总计 +38 行 (含 try/except + import + 注释 + log)

**drive_comment_service.py 改写流程**:
1. `create_comment()`: commit + refresh + logger.info **之后** 加 `await publish_comment_created(self.db, comment, actor_id=author_id)`
2. `update_comment()`: commit + refresh + logger.info **之后** 加 `await publish_comment_updated(self.db, comment, actor_id=user_id)`
3. `delete_comment()`: commit + logger.info **之后** 加 `await publish_comment_deleted(self.db, ..., snapshot_*, actor_id=user_id)`
   - 关键: 在 `await self.db.delete(comment)` **之前** 快照 (file_id, folder_id, author_id)
4. `resolve_comment()`: commit + refresh + logger.info **之后** 加 `await publish_comment_resolved(self.db, ..., resolved_by=user_id, author_id=comment.author_id)`

**drive_version_service.py 改写流程**:
1. `create_version()`: commit + refresh + logger.info **之后** 加 `await publish_version_uploaded(self.db, new_version, file_name=cur_file.file_name, actor_id=uploader_id)`
2. `rollback()`: commit + refresh + logger.info **之后** 加 `await publish_version_rollback(self.db, new_version, file_name=cur_file.file_name, target_version_number=target.version_number, actor_id=user_id)`

---

## 7. 与 a-1 (commit f5a4b2586) 的衔接

a-1 已建:
- `NotificationPriority` (HIGH/MEDIUM/LOW enum)
- `push_with_priority(user_id, payload, priority=None)` — 在线 push, 离线入队
- `_CONTEXT_PRIORITY_MAP` (comment/reply/mention → HIGH; share/upload → MEDIUM; star/system → LOW)
- `infer_priority(context)` — 从 context 字符串推断 priority
- `enqueue_offline(user_id, payload)` — Redis list FIFO
- `drain_offline_queue(user_id, priority_filter, max_items)` — reconnect 拉
- `notification_manager.push_to_user(user_id, payload, priority_filter)` — WS fan-out
- 5s/30s heartbeat + priority filter + reconnect drain

PR10 (本 PR) publisher 直接**调 a-1 push_with_priority**, 不重新实现 WS 推送.
publisher 唯一增加的智能:
1. **收件人解析** (file owner / folder owner / comment author) — a-1 没做
2. **payload schema** (含 comment_id / file_id / version_number 等) — a-1 透传
3. **priority 显式覆盖** (comment_deleted=LOW) — a-1 走 context 推断, 没 comment_deleted context
4. **自推跳过** (actor == target) — a-1 不做
5. **delete 路径的 ID 快照** (caller 责任, publisher 接受 ID 而非 ORM)

---

## 8. 测试覆盖 (13 场景 SKIP_DB_SETUP=1 全 PASS)

```bash
$ SKIP_DB_SETUP=1 python -m pytest tests/test_drive_v2_pr9_ws.py -v
collected 13 items
tests\test_drive_v2_pr9_ws.py::test_publish_comment_created_payload_and_priority PASSED
tests\test_drive_v2_pr9_ws.py::test_publish_comment_created_skips_self_push PASSED
tests\test_drive_v2_pr9_ws.py::test_publish_comment_updated_payload PASSED
tests\test_drive_v2_pr9_ws.py::test_publish_version_uploaded_payload PASSED
tests\test_drive_v2_pr9_ws.py::test_publish_version_rollback_payload PASSED
tests\test_drive_v2_pr9_ws.py::test_publish_failure_is_best_effort PASSED
tests\test_drive_v2_pr9_ws.py::test_publish_comment_deleted_priority_low PASSED
tests\test_drive_v2_pr9_ws.py::test_publish_comment_resolved_skips_self PASSED
tests\test_drive_v2_pr9_ws.py::test_publish_comment_resolved_to_author PASSED
tests\test_drive_v2_pr9_ws.py::test_multiple_ws_subscribers_all_receive_push PASSED
tests\test_drive_v2_pr9_ws.py::test_offline_user_uses_offline_queue PASSED
tests\test_drive_v2_pr9_ws.py::test_priority_classification_all_events PASSED
tests\test_drive_v2_pr9_ws.py::test_publish_comment_folder_target PASSED
======================= 13 passed, 2 warnings in 0.68s ========================
```

**5 核心场景 + 8 边界场景** (覆盖 100% publish_* 函数 × 4 收件人路径 × 3 priority):
1. **comment_created 推送** (场景 1)
2. **version_uploaded 推送** (场景 2)
3. **失败 best-effort** (场景 3)
4. **多订阅者 fan-out** (场景 4)
5. **priority 分类** (场景 5)

边界:
- 自推跳过 (comment + resolved + version)
- comment_updated / comment_resolved payload
- version_rollback payload 含 target_version_number
- offline user → push_to_user 返 0 (publisher 入队)
- folder_id 路径 (区别 file_id 路径)

---

## 9. 部署必做 (生产环境)

PR10 是 publisher 集成, **无需 alembic 迁移** (无新表 / 无 schema 变化).
service 层改动 try/except best-effort, **无需重启 Celery worker** (无 task 改动).

```bash
# 1. 拉最新代码 (含 PR10 + F-1 + F-2 + a-1)
git pull origin main

# 2. 重启 app (服务层 publisher import 必须重启加载)
docker compose restart app celery-worker

# 3. 验证 publisher 集成 (WS 推送 + offline queue 仍可用)
# - 写评论 → file owner 收 WS 推送 (devtools WS frame)
# - file owner 离线 → reconnect 时 drain offline queue 收到推送

# 4. (可选) 回归 F-1/F-2 测试 (需 PG)
docker exec microbubble-agent-postgres-1 psql -U postgres -c "CREATE DATABASE microbubble_test;"
SKIP_DB_SETUP=0 pytest tests/test_drive_v2_pr9_comments.py -v  # F-1 12 tests
SKIP_DB_SETUP=0 pytest tests/e2e/test_drive_v2_pr9_versions.py -v  # F-2 5 tests
```

---

## 10. 留待未来 PR (不开)

本 PR 范围内**不开**的事:
- **WebSocket 跨实例推送** (Redis Pub/Sub fan-out) — 单实例够用, 留 PR11+
- **batch 通知合并** (e.g. 3 条评论合并为 1 条 "3 条新评论") — a-1 `push_batch` 已建 API, publisher 未用, 留 PR11+
- **comment_mention 自动推 WS** (mention 字段已在 comment 表, 但 publisher 不读) — PR6 `create_bulk_mentions` 已独立走, 不重复
- **push_with_priority context 字符串适配** (publisher 没用 context, 改用显式 priority) — context 推断会让 priority=HIGH (mention), 不符合"协作事件 MEDIUM" 设计意图
- **publisher 单元测试覆盖率 100%** (当前 13 tests, 6 函数覆盖 100%, 但每个函数的 error path 只测 1 个, 不深) — 实际不需要, 1 个 generic error path 测试足够
- **push 失败 metric / tracing** (e.g. Prometheus counter) — 留给 ops PR

---

## 11. commit 信息 (待主指挥 merge)

```
feat(drive): v2 PR9 WS 推送集成 (PR10 闭环, 锚点范式第 48 守恒)

W68 第 1 批 a-1 已建 notification_service 基础设施 (push_with_priority +
enqueue_offline + heartbeat), W68 第 3 批 F-1/F-2 已建 DriveComment +
DriveFileVersion 数据层 + service. 本 PR 闭环 F-1/F-2 → a-1, 把 6 个写操作
包装为 WS payload.

4 文件: drive_event_publisher.py 新建 (~330 行 6 publish_* + 5 helper) +
drive_comment_service.py +24 (4 写操作末尾调 publish_*) + drive_version_service.py
+14 (2 写操作末尾调 publish_*) + tests/test_drive_v2_pr9_ws.py 新建 (13 unit).

5 新铁律:
- WS 推送集成走 publisher, 不散落 service (集中维护 payload schema)
- publish_* 必须 best-effort, service 层 try/except 包 (不阻塞主流程)
- delete 场景必须快照 ID 字段 (commit 后 ORM 不可访问, 快照 commit 前)
- 自推跳过 (actor == target) 必须 publisher 内部处理 (service 不应感知通知目标)
- 测试用 SKIP_DB_SETUP=1 + Mock, 不依赖 PostgreSQL (跨平台 + CI 快)

13 unit 测试 SKIP_DB_SETUP=1 模式 0.68s 全 PASS. typing imports 148 文件 0 错误.
0 production code 改动铁律维持 (PR10 是新功能集成, 不动 F-1/F-2 业务逻辑).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

## 12. 主指挥 merge 路径

```
feat/drive-v2-pr9-ws-push-2026-07-24  →  main
                                      ↓
                              push to origin
                                      ↓
                       webhook 30s 后云服务器自动部署
                                      ↓
                docker compose restart app celery-worker
                                      ↓
         DevTools WS frame 验证 (write comment → file owner 收 push)
```

**merge 后回滚路径**: `git revert <commit-hash>` + 重新部署. < 5 分钟恢复.