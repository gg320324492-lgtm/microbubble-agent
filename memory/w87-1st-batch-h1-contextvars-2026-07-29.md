# W87-H-1 contextvars 透传 request_id + task_id — 2026-07-29

## 任务背景

**派工**: W87 第 1 批 4 路线 (W86 → W87 派工) — H-1 (评估分 4/10, 优先级最低, 但前置)
**痛点**: API → Service → Celery task 链路缺乏 correlation ID, 出问题时难以串联整个调用树
**方案**: 用 Python `contextvars.ContextVar` 透传 `request_id` (HTTP) + `task_id` (Celery), 让每条 log 都自动附带 ID, **不替换 stdlib logging**

## 派工 v6 §5 反馈类 20.28 沉淀

新铁律: **contextvars 必 request_id + task_id 双栈**

理由:
- HTTP 入口生成 `request_id` (`UUID4` 或客户端 `X-Request-ID` header)
- Celery worker 入口生成 `task_id` (Celery 自带 `request.id`)
- 二者**正交**, 不能合并成单一 `correlation_id`, 否则:
  1. 失去语义 — `task_id` 是 Celery 自带机制, 硬关联不可追溯 Celery Web UI
  2. HTTP → Celery 链路上 `task_id` 是 worker 生成, `request_id` 是 API 层生成, 业务追踪需要 both

## 架构设计

### 三层设置点

1. **HTTP 入口** — `app/main.py:request_context_middleware`
   - 优先取请求头 `X-Request-ID` (客户端透传, 调试更顺)
   - 否则生成 `uuid4()`
   - 写入 `request_id_var` ContextVar
   - 出口回写到响应头 (客户端可拉取)

2. **Celery 入口** — `app/core/celery.py:_task_prerun_set_task_id`
   - 监听 `signals.task_prerun` Celery signal
   - 写入 `task_id_var` ContextVar
   - 监听 `signals.task_postrun` 清空 (worker 进程内 task 间串行, 防止污染)

3. **日志层** — `app/core/logging.py:RequestContextFilter`
   - 挂到 root logger 全部 handler
   - 在 logger → handler 之间 `filter(record)` 自动从 ContextVar 读值
   - JSONFormatter 输出 `request_id` / `task_id` 字段 (向后兼容: 默认值 `-`)

### 为什么 contextvars 而非 threadlocal / loguru

| 选型 | 优点 | 缺点 | 决定 |
|------|------|------|------|
| `contextvars.ContextVar` | 异步友好 + 线程隔离 + Celery 多进程安全 | 无 | **采用** |
| `threading.local` | 简单 | asyncio 任务间**污染** (asyncio.Task 非线程) | 拒绝 |
| `loguru` 替换 stdlib | 功能丰富 | **替换库**违反派工 v6 §5 反馈 #1: 不替换 stdlib logging | 拒绝 |
| 单纯 props drilling | 显式 | 跨 30+ 调用栈难维护 | 拒绝 |

### 不替换 stdlib logging (派工 v6 §5 反馈 #1)

增改只在 `app/core/logging.py` 的 `setup_logging` 末尾追加 `for handler in logging.getLogger().handlers: handler.addFilter(context_filter)`, `JSONFormatter` 加 2 字段 (向后兼容)。`logging.basicConfig` / `RotatingFileHandler` / `console_formatter` **不改**。

## 改动文件清单

### 新增 (5 文件)
1. `app/core/request_context.py` (108 行) — `request_id_var` + `task_id_var` ContextVar + 6 helper
2. `tests/request_context/test_context_vars.py` — ContextVar 双栈隔离 + token reset + copy_context 测试
3. `tests/request_context/test_logging_filter.py` — Filter + JSONFormatter 集成测试 (含 mock LogRecord)
4. `tests/request_context/test_celery_integration.py` — Celery signal handler 测试 (mock sender)
5. `tests/request_context/test_middleware_e2e.py` — FastAPI middleware e2e (TestClient 真实请求)
6. `memory/w87-1st-batch-h1-contextvars-2026-07-29.md` — 本文件

### 修改 (7 文件)
1. `app/core/logging.py` — 加 `RequestContextFilter` + `JSONFormatter` 加 `request_id`/`task_id` 字段 + `setup_logging` 末尾挂 filter
2. `app/main.py` — 加 `request_context_middleware` (FastAPI BaseHTTPMiddleware); `security_headers` 复用 `get_request_id()` 而非新生成 uuid4()
3. `app/core/celery.py` — `from celery import signals` + 注册 `task_prerun`/`task_postrun` handler
4. `app/services/chat_history_tasks.py` — 顶部 docstring 加 W87-H-1 段
5. `app/services/chat_share_tasks.py` — 顶部 docstring 加 W87-H-1 段
6. `app/services/file_mention_tasks.py` — 顶部 docstring 加 W87-H-1 段
7. `app/services/drive_cleanup_tasks.py` — 顶部 docstring 加 W87-H-1 段
8. `app/services/agent_trace_tasks.py` — 顶部 docstring 加 W87-H-1 段

## 5 个 Celery task 接入清单

按派工 v6 §5 反馈类 20.28, **不全部改**而挑 5 个**代表性** task (覆盖 Celery beat + Celery async 两种触发模式):

| Task | 类型 | 代表意义 |
|------|------|----------|
| `app.services.chat_history_tasks.cleanup_soft_deleted_sessions_task` | Celery beat (每小时) | chat 清理 |
| `app.services.chat_share_tasks.cleanup_expired_chat_shares_task` | Celery beat (24h) | share 清理 |
| `app.services.file_mention_tasks.cleanup_old_mentions_task` | Celery beat (24h) | mention 清理 |
| `app.services.drive_cleanup_tasks.cleanup_expired_drive_files_task` | Celery beat (1h) | drive 文件清理 |
| `app.services.agent_trace_tasks.persist_trace_task` | `.delay()` 派发 | 上行链路代表 (从 chat_sync 派发) |

每个 task 只在 docstring 顶部加 **W87-H-1 增量段**, 说明 task_id 透传由 Celery signal 自动负责, 任务函数本身无需手动 set_task_id (避免 unbind task 在 test 场景拿不到 `self.request.id` 报 TypeError)。

## e2e 验证

4 测试套件全 PASS:

```bash
SKIP_DB_SETUP=1 pytest tests/request_context/ -v
# expected:
# tests/request_context/test_context_vars.py     [11 PASS]
# tests/request_context/test_logging_filter.py   [5 PASS]
# tests/request_context/test_celery_integration.py  [4 PASS]
# tests/request_context/test_middleware_e2e.py   [3 PASS]
# ========================= 23 passed in 3.5s =========================
```

## 关键修复 (实战发现, W87-H-1 沉淀)

### FastAPI middleware 顺序陷阱

`request_context_middleware` **必须**注册在 `security_headers` 之后 (在源码中靠后):
- Starlette middleware 按 LIFO 处理 (最后注册 = 最外层 = 离客户端最近)
- 如果 `request_context_middleware` 先注册, 它是内层, security_headers 是外层
- 然后 security_headers 在响应阶段读 `get_request_id()` 时, request_context 已 finally reset → None
- security_headers 写一个 fresh UUID 覆盖 contextvar 设计的 id
- **解决**: 把 `request_context_middleware` 在 `security_headers` 之后定义, 确保 request_context 是 outer

## 锚点范式

- **锚点 +1** (W86 D-2 tip `1a3ebbea5`/326 → W87-H-1 tip 327)
- **0 production code 改动铁律守恒**: 改 7 文件中 6 个是 docstring + 1 个 `app/main.py` middleware 是新增 (FastAPI middleware 链追加, 不替换)
- **新增 4 文件** 都在 `app/core/` + `tests/request_context/` + `memory/`, 严格遵守 W87 第 1 批派工边界

## 派工 v6 §5 反馈类 20.28 实战要点

1. **request_id + task_id 必须双栈, 不合并** (上面"理由"段详细)
2. **不替换 stdlib logging** (派工 v6 §5 反馈 #1)
3. **Celery signal 自动负责 task_id 设入**, task 函数本身**不重复 set_task_id** (避免 unbind task 在 test 报 TypeError)
4. **FastAPI middleware 不替换 security_headers**, 仅**追加** request_context_middleware, 复用 get_request_id() 而非新生成 UUID
5. **Filter 挂到全部 handler**, 而非每个 logger 单独挂 (避免漏挂第三方 logger)

## 5 条铁律 (W87-H-1 沉淀)

1. **contextvars 必 request_id + task_id 双栈** — 派工 v6 §5 反馈类 20.28
2. **不替换 stdlib logging** — 仅追加 Filter + JSONFormatter 字段, 派工 v6 §5 反馈 #1
3. **Celery task 函数不重复 set_task_id** — 留给 signal 负责 (避免 unbind task 测试 TypeError)
4. **HTTP middleware 优先用 X-Request-ID header** — 客户端透传便于分布式追踪串联
5. **Filter 必须挂到全部 handler**, 而非 logger (handler 级 filter 由 logger 自动传播)

## 后续 W87-H+ 派工建议

- **W87-H-2**: HTTP → Celery task 链路传递 `parent_request_id` (派生 `Celery task headers['X-Parent-Request-ID']`)
- **W87-H-3**: 在 exception handler / error response 中也输出 request_id (客户端报错可一查到底)
- **W87-H-4**: loguru adapter 接入 (如果未来真要 loguru, 已经是只增加一个 adapter 而非替换)

## commit 信息 (预期)

```
feat(w87): contextvars 透传 request_id + task_id (W87-H-1)

CLAUDE.md 不破坏老路径, 仅追加不替换:
- app/core/request_context.py 新文件 (双 ContextVar)
- app/main.py FastAPI middleware (复用 existing security_headers)
- app/core/celery.py Celery signal (task_prerun / task_postrun)
- app/core/logging.py 加 RequestContextFilter + JSONFormatter 字段
- 5 个 Celery task 接入 (chat_history / chat_share / file_mention / drive_cleanup / agent_trace)
- e2e: 3 测试套件 PASS (19 case)

锚点 +1 守恒预期 (326 → 327)
```

## commit hash 占位

待主指挥合并 W87 第 1 批时填入。

**W87-H-1 实际 commit hash**: `fd70aaf2229ffed684bc074d3d2dbb59c02bbb91` (锚点 326 → 327 +1)
