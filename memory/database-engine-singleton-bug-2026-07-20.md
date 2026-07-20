---
name: database-engine-singleton-bug-2026-07-20
description: app/core/database.py 仍有 module-level engine 单例 bug — W5+1 follow-up 下一层
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f277dd1-0a27-4a11-b320-da966057abae
  modified: 2026-07-20T13:24:47.282Z
---

# App/Core/Database.py Engine Singleton Bug (2026-07-20)

## TL;DR

🎯 **W5+1 follow-up 下一层** — `app/core/database.py:7` 仍有 module-level `engine` 单例绑首次 event loop bug, 跟 W1 round 2 修的 `app/core/redis.py` 是**完全相同的 bug class**。

**Why**: W2 T2 真闭环验证时, E2E 7 skipped 跑不起来, 根因是 `kb_dedup_admin_cli.py` 内部 `from app.core.database import async_session` 拿 module-level `engine`, 跨 event loop 复用立即 `Future attached to different loop`。

**How to apply**: 见下方 3 步修复路径 + 2 个相关 bug + 4 铁律。

## 核心 Bug

### `app/core/database.py:7` (当前未修)
```python
# 模块顶部 import 时立即创建 engine
engine = create_async_engine(DATABASE_URL, ...)
async_session = async_sessionmaker(engine, ...)
```

### 触发场景
1. pytest_asyncio 默认 `function` scope, 每个 test_fn 起新 event loop
2. 第一次调用 `async_session()` 创建 connection 绑 loop 1
3. 第二个 test_fn 起 loop 2, 复用同一 connection → `Future attached to a different loop`
4. W1 round 2 修的 `redis.py` 同 pattern, 但 `database.py` 未覆盖

### 影响范围
所有 `from app.core.database import async_session` 的脚本/Celery task:
- `scripts/kb_dedup_admin_cli.py` (E2E 7 skipped 阻塞)
- `app/services/chat_share_tasks.py` (W1 P2-A Celery 清理)
- `app/services/chat_history_tasks.py` (PR6-P10 备份)
- `app/services/orphan_meeting_cleanup.py` (W1 录音 fix)
- `app/core/celery.py` Celery autodiscover 30+ modules

## 3 步修复路径 (留 W3 单 commit 闭环)

### 步骤 1: 改 `app/core/database.py` 跟 `redis.py:31` 同模式
```python
_engine: Optional[AsyncEngine] = None
_engine_loop: Optional[asyncio.AbstractEventLoop] = None
_engine_lock = asyncio.Lock()

def _get_engine() -> AsyncEngine:
    global _engine, _engine_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    if _engine is None or _engine_loop is not current_loop:
        _engine = create_async_engine(DATABASE_URL, ...)
        _engine_loop = current_loop
    return _engine
```

### 步骤 2: 改 `get_db()` 走 lazy engine
```python
def get_db() -> AsyncGenerator[AsyncSession, None]:
    engine = _get_engine()
    Session = async_sessionmaker(engine, ...)
    async with Session() as session:
        yield session
```

### 步骤 3: Celery task 内自己建 engine (跟 chat_share_tasks 同模式)
已有 `chat_share_tasks.py` 用 `create_celery_engine_and_session()`, 复用范式即可

## 验证步骤

```bash
# 1. 重跑 7 skipped E2E
docker exec -e SKIP_DB_SETUP=0 -e TEST_DATABASE_URL=postgresql://postgres:microbubble2026@db:5432/microbubble_test \
  microbubble-agent-app-1 bash -c 'cd /app && python -m pytest tests/scripts/test_kb_dedup_admin_cli_e2e.py --tb=line -q'
# 期望: 7/7 PASS (无 skip)

# 2. 9 文件合跑 71 PASS + 7 skip 变 78 PASS
# 3. Celery task 启动不报错
docker compose restart celery-worker celery-beat
```

## 2 个相关 Bug (W5+1 follow-up 4 层闭环链)

| Commit | 修复 | 状态 |
|---|---|---|
| `081c55e8` (W5) | TRANSCRIPT_BUFFER_MAX_ENTRIES 默认值 (LTRIM 200 契约回归) | ✅ |
| `f9130c34` (W8) | monkeypatch sys.modules 污染 | ✅ |
| `641e402f` (W9) | pytest.ini loop_scope=function | ✅ |
| `ca0fb0a3` (W1 round 2) | app/core/redis.py lazy init | ✅ |
| **`app/core/database.py` lazy init** | **(W3 留尾, 本次未修)** | ⏳ |

## W2 T2 排查路径 (诚实记录)

| Step | 操作 | 结果 |
|---|---|---|
| 1 | 连 DB (`db:5432/microbubble_test`) | ✅ DB 已存在, 含 39 张表 (历史遗留) |
| 2 | 跑 E2E (`SKIP_DB_SETUP=0`) | ❌ 7 ERROR (ScopeMismatch event_loop) |
| 3 | 加 `-o asyncio_default_fixture_loop_scope=session` | ❌ 6 fail + 1 pass (新错: Future attached to different loop) |
| 4 | 定位根因 | ✅ database.py module-level engine 绑首次 loop |

## test_maxlen_200 真闭环状态 (W2 T2 决策点)

- ✅ **W2 T3 验证**: 5 文件合跑正反序 37/37 PASS, 1.25s/1.14s
- ✅ E2E 7 skipped 是**另一个独立 bug** 阻塞 (database.py), 跟 test_maxlen_200 闭环无关
- ✅ 主指挥决策: **选项 A** (接受当前状态, 留未来 PR)

## 4 新铁律 (W2 T2 沉淀)

1. **W5+1 follow-up 是分层闭环** — 修 redis 不够, 还要修 database; 同样 W5 修 maxlen 不够, 还要修 test fixture scope
2. **E2E 7 skipped 实际是独立 bug 阻塞** — 跟当前任务范围不同, 必须诚实上报而不是 "SKIP 视为 PASS"
3. **asyncpg Connection 跟 redis ConnectionPool 同样的"首次 loop 绑定"陷阱** — 任何模块顶部 import 时创建的 async 资源都需要 lazy init
4. **test_maxlen_200 真闭环 ≠ E2E 真闭环** — 前者已 W1 round 2 修 (`ca0fb0a3`), 后者需 database.py 修才能解

## 留给 W3 (主指挥下批派活)

| 任务 | 优先级 | 工作量 |
|---|---|---|
| 改 `app/core/database.py` lazy init | P1 | 1.5h |
| 重跑 7 skipped E2E 真 DB | P1 | 1h |
| 跨 30+ 文件回归测试 | P1 | 1h |
| 沉淀 W3 memory | P2 | 30min |

**总计 4h**, 1 worker 足够。

## 相关 memory

- `config-value-contract-regression-2026-07-20.md` — W5+1 follow-up 4 层闭环
- `multi-agent-task-orchestration-baseline.md` — 协调范式
- `orchestrator-mode-coordination-2026-07-20.md` — 5 协调铁律