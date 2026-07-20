---
name: w5-plus-one-followup-ultimate-closure
description: "W5+1 follow-up 6 层闭环完整时间线 + 终极验证证据 + 1 个未闭环 blocker (W8 follow-up)"
metadata:
  type: project
  originSessionId: W7
  modified: 2026-07-20T23:30:00Z
---

# W5+1 Follow-up 闭环 — 终极记录 (2026-07-20)

> **背景**: 2026-07-20 一天之内, W5+1 follow-up 跨 6 层闭环 async engine 单例 bug class + W7 沉淀 + W8 修补. 本文记录完整时间线 + 验证证据 + **选项 A 决策落地**.

---

## TL;DR

🎯 **9 文件合跑 SKIP 模式终极闭环已 commit 入 main HEAD `5c77c417`** — **71 passed + 7 skipped 与 W2 T2 基线 100% 一致, 0 regression**.

**Why**: W5+1 follow-up 链从 redis pool 单例 bug 一路闭环到 conftest.py 跨 scope 修复. W8 (主指挥亲自 commit `5c77c417`) 补 conftest model import (37 张表) + _get_test_session_maker 优化. **主指挥决策 (选项 A)**: E2E 7 真 DB 闭环留未来 PR, test_maxlen_200 真闭环已 W2 T3 验证 (5 文件合跑 37/37 PASS), 整体 W5+1 跨模块 follow-up 收官.

**How to apply**: 见下方完整时间线 + 终极证据 + 9 commit 索引 + 沉淀铁律.

---

## 9 commit 完整链 (含 W6 + W8 增量)

### 第 1 层: W5 修复 `app/core/redis.py` lazy init (commit `ca0fb0a3`)

**根因**: `app/core/redis.py` 模块顶部创建全局 `redis_pool = aioredis.from_url(...)` 绑首次访问 loop. Celery worker 跨 event loop 调用时 → "Future attached to different loop".

**修法**: `redis_pool` 改成 lazy init (function 返回时按 `asyncio.get_running_loop()` 检查, loop 不匹配时重建).

**沉淀**: redis_pool 单例 bug 是同类问题的范式, 任何 module-level 客户端都需 lazy init.

### 第 2 层: W3 修复 `app/core/database.py` 同样模式 (commit `fe09010a`)

**根因**: 跟 redis.py 一样, `app/core/database.py:7` 创建全局 `engine = create_async_engine(...)` 绑首次 loop.

**修法**: 引入 `_EngineProxy` / `_SessionFactoryProxy` 动态代理 + `_get_engine()` / `_get_session_factory()` 函数式调用, 内部用 `_engine_loop` 缓存当前 loop.

**沉淀**: W3 的 12 个测试 (`test_database_lazy_init.py`) 验证代理语义, 但硬编码 `loop=None` 期望 (W5.1 fallback 后漂移).

### 第 3 层: W5.1 加 `get_event_loop` fallback (commit `105d4ecc`)

**根因**: W3 修的 `_get_engine()` 用 `asyncio.get_running_loop()`, 在 sync context 抛 `RuntimeError`. 主指挥验证 `engine1 is engine2 = True` 表明跨 loop rebuild 没触发.

**修法**: `_get_engine()` + `_get_session_factory()` 加 try/except fallback:
```python
try:
    current_loop = asyncio.get_running_loop()
except RuntimeError:
    try:
        current_loop = asyncio.get_event_loop()  # sync context fallback
    except RuntimeError:
        current_loop = None
```

**副作用**: 测试期望漂移 — 硬编码 `loop=None` 失败, 因为 sync context 下 `_engine_loop` 现在是真 EventLoop 对象.

### 第 4 层: W2 T2 修 2 测试期望漂移 (commit `0ae3319a`)

**根因**: `test_database_lazy_init.py::TestProxyBehavior::test_engine_proxy_repr_no_real_engine` 等 2 case 硬编码 `assert repr(engine_proxy) == "<_EngineProxy loop=None>"`, 跟 W5.1 fallback 后语义不符.

**修法**: 用 regex `^<_EngineProxy loop=(None|<.+>)$` 兼容两种合法状态 (None 或真 EventLoop). 同时删 `assert _engine is None` (跨测试隔离问题不该靠断言解决).

**沉淀铁律**:
1. module-level 单例的 repr 必须如实反映状态 (None 或 EventLoop 都合法)
2. 测试期望用 regex 兼容 fallback 语义, 不用 hard code 字面量
3. 跨测试隔离: 不要在后续 test 断言前序 test 没 populate global state

### 第 5 层: W1 T1 修 conftest 跨 scope lazy init (commit `9b7913b1`)

**根因**: `tests/conftest.py` 也有 module-level `engine = create_async_engine(...)` 单例, 跟生产代码同样的 bug class. `setup_db (session-scope) + db (function-scope)` 跨 loop 用同一 engine → "Event loop is closed".

**修法**:
- conftest.py 引入 lazy pattern (跟 W5.1 一致): `_get_conftest_engine()` + `_get_test_session_maker()` + `get_event_loop()` fallback
- 老 `from tests.conftest import engine, TestSession` 路径返回 `None` (强制改用 lazy helper)
- `setup_db` 改 `scope='function'` + autouse (W6 修复 ScopeMismatch: session-scope setup_db + function-scope event_loop)

**沉淀铁律**: 测试 conftest 也要 lazy init (跟生产代码同样模式), 别只看 production 不看 test infra.

### 第 6 层: 主指挥 9b7913b1 commit message 终极闭环

**当前 main HEAD**: `9b7913b1 test(tests): conftest 跨 scope lazy init (W5+1 follow-up 第 6 层闭环)`

完整 commit 链:
- `ca0fb0a3` fix(redis): pool lazy init + loop-aware (第 1 层)
- `fe09010a` fix(db): async_engine lazy init (第 2 层)
- `105d4ecc` fix(db): lazy init _get_engine 加 get_event_loop fallback (第 3 层)
- `0ae3319a` test(database): 修 2 repr 期望漂移 (第 4 层)
- `9b7913b1` test(tests): conftest 跨 scope lazy init (第 6 层)

---

## 终极验证证据

### 5 文件合跑正反序 (W2 T3 baseline, 2026-07-20 早期)

| 顺序 | 测试范围 | 结果 | 耗时 |
|---|---|---|---|
| 正序 | buffer → orphan → ua → audio_chunk → cancel | **37/37 PASS** | 1.25s |
| 反序 | ua → audio_chunk → cancel → orphan → buffer | **37/37 PASS** | 1.14s |

✅ test_maxlen_200 真闭环已验证 (redis lazy init 修彻底).

### 3 类 production 测试 (W2 T2 round 1, 2026-07-20)

| Class | 测试范围 | 结果 |
|---|---|---|
| 1 | 5 文件合跑 | **37/37 PASS** |
| 2 | chat_history_tasks + chat_share_cleanup | **15/15 PASS** |
| 3 | buffer + KB dedup admin CLI (纯函数) | **21 PASS + 7 SKIP** |

⚠️ 7 SKIP 是 E2E 真 DB 测试, 在 SKIP 模式下跳过 (依赖真 DB + 真 engine).

### 9 文件合跑终极验证 (W7 T2, 2026-07-20 末)

**期望**: 78 passed + 0 skipped (W6 修 conftest 后 E2E 7 skipped 应变 passed)

**实际**: 71 passed + 7 skipped (无变化, E2E 7 still skipped)

**根因 (本次 W7 T2 发现)**:
- W6 改 `setup_db(scope='function')` 后, 每次 test 重 create_all + drop_all
- 但 conftest 27-30 行只 import `from app.models.member import Member` (1 个 model)
- `Base.metadata.tables` 只注册 Member (1 张表), E2E 测试需要 `knowledge_extractions` (39 张表)
- 第一次 create_all 后 DB 有 1 张 members 表, E2E `_create_dup_record` 立即报 `knowledge_extractions table does not exist`

---

## 未闭环 Blocker (W8 follow-up)

**W6 conftest 修复的副作用**: `setup_db(scope='function')` 解决了 ScopeMismatch, 但没解决 model import 不全.

**修复方案** (W8 应做, 不在 W7 T2 scope):
```python
# tests/conftest.py line 27-30 (current)
from app.models.member import Member  # ← 只 import Member

# W8 fix
from app.models.member import Member  # noqa: F401
import app.models  # ← 触发 app/models/__init__.py 全部 import
```

或者更彻底: `from app.core.database import Base; from app.models import *  # noqa` 强制注册所有 model.

**验证**: W8 修复后重跑 W7 T2 9 文件合跑, 期望 78 passed + 0 skipped.

---

## 8 新铁律 (W5+1 follow-up 完整沉淀)

### 协调铁律 (3 条)
1. **module-level 单例 bug 是同类问题范式** — 任何模块顶部创建的客户端 (redis_pool / async_engine / pg_pool) 都需 lazy init, 找到一个就要 grep 其他
2. **修一个文件必须 grep 整个代码库同类模式** — W1 修 redis.py 后, W3/W5.1 才发现 database.py 同样的 bug, 应当一开始就 grep 全部
3. **测试 conftest 也是生产代码** — lazy init 同样适用, 别只看生产不看 test infra

### 技术铁律 (5 条)
4. **`asyncio.get_running_loop()` 在 sync context 抛 RuntimeError** — 必须 try/except fallback 到 `get_event_loop()`, 再 fallback 到 `None`
5. **session-scope async fixture + function-scope event_loop = ScopeMismatch** — pytest-asyncio 0.26+ 必须一致, 或改 fixture scope
6. **proxy repr 必须如实反映状态** — `_engine_loop` 是 None 或真 EventLoop 都合法, 用 regex 兼容
7. **跨测试隔离靠 fixture scope, 不靠断言** — 不要在后续 test 断言 `dbmod._engine is None`
8. **module-level 单例 + get_running_loop 是 anti-pattern** — 任何全局客户端都该 lazy init, async 框架的 hard lesson

---

## 相关 memory + commit 索引

- 锚点 memory: `multi-agent-task-orchestration-baseline.md` (W5+1 follow-up 是锚点范式的实战验证)
- 协调铁律: `orchestrator-mode-coordination-2026-07-20.md`
- 配置契约: `config-value-contract-regression-2026-07-20.md` (8 技术铁律基础)
- 沉淀来源: `a068c50b docs(memory): 沉淀 W2 T2 真闭环排查 + database.py engine 单例 bug 发现`
- 相关 commit: 见上方 6 层 commit 链

---

## 下一步建议 (主指挥拍板)

- **选项 A**: W7 沉淀当前 memory 收官, W8 follow-up 留未来 PR (推荐)
- **选项 B**: 主指挥直接派 W8 单 commit 修 conftest model import (30 行改动), 立即闭环
- **选项 C**: 接受 71/78 PASS 状态, 7 skipped 永久 skip (不推荐, E2E 是 PR6-P18 admin CLI 黄金范式)

---

## W7 T2 完成汇报 (worker → 主指挥)

1. **9 文件合跑结果**: 71 passed + 7 skipped (vs 期望 78 passed + 0 skipped)
2. **未闭环 blocker**: W6 conftest `setup_db(scope='function')` 只 import Member, `Base.metadata` 缺 38 张表
3. **不擅自修**: 严格遵守 W7 T2 任务范围 (写 memory + 验证), 不动 conftest.py (W3/W5.1/W6 已改)
4. **沉淀 memory**: 本文件 (`w5-plus-one-followup-ultimate-closure-2026-07-20.md`) 完整记录 6 层闭环 + 8 新铁律 + blocker

---

## W8 终极闭环 + 选项 A 落地 (主指挥 commit `5c77c417`)

### W8 主指挥亲自 commit

主指挥在 W7 沉淀后亲自 commit W8 (`5c77c417`):

**修复 1: conftest model import 全集**
```python
# tests/conftest.py:42-46 (L48 在我看到的最终版本里)
from app.models.member import Member
import app.models  # ← 触发 app/models/__init__.py 全部 model import
# 旧: 1 张表 (Member) → E2E 报 knowledge_extractions table does not exist
# 新: 37 张表 (E2E 需要的 knowledge_extractions 等齐全)
```

**修复 2: _get_test_session_maker 优化** — 取消 cache 模式, 每次 new (cache 跟 _engine 同步失效路径被排除).

**修复 3: _reset_conftest_engine_cache() 保留** — 供未来 cache 模式需要时复用.

### 选项 A 决策落地 (主指挥)

> E2E 7 skipped 仍 fail 的根因 (W7 报告已明确) — pytest_asyncio loop_scope 跨 fixture
> 跟 test 函数的 event loop 不一致 (function-scope setup_db + function-scope test
> 但 session-scope engine cache) 是**框架层问题**, 不是 lazy init 能修.
>
> 主指挥决策 (选项 A 接受 W7 报告): **71 passed + 7 skipped 留未来 PR**
> - test_maxlen_200 真闭环已 W2 T3 验证 (5 文件合跑 37/37 PASS) ✅
> - E2E 7 skipped 是 pytest_asyncio 框架层 + asyncpg connection pool 跨 loop 复合问题
> - 修法需重写 conftest 全部 fixture (跨 loop + cache 一致性), 超出单 commit 范围

### W5+1 follow-up 闭环完整 9 commit 链

```
W2 T2 (a068c50b) docs(memory): 沉淀 W2 T2 真闭环排查 + database.py engine 单例 bug 发现
   │
   ├─→ W1 round 2 (ca0fb0a3) fix(redis): pool lazy init + loop-aware
   │     └─→ 5 文件合跑 37/37 PASS (test_maxlen_200 真闭环)
   │
   ├─→ W3 (fe09010a) fix(db): async_engine lazy init (主指挥亲自 commit)
   │     └─→ 12 case test_database_lazy_init.py 配套测试
   │
   ├─→ W5.1 (105d4ecc) fix(db): lazy init _get_engine 加 get_event_loop fallback
   │     └─→ 修了 W3 sync context 抛 RuntimeError bug
   │
   ├─→ W2 T2 (0ae3319a) test(database): 修 2 repr 期望漂移
   │     └─→ 9 文件合跑 71/78 PASS, 7 SKIP (E2E 真闭环未达)
   │
   ├─→ W1 T1 (9b7913b1) test(tests): conftest 跨 scope lazy init (主指挥亲自 commit)
   │     ├─→ _get_conftest_engine() + _get_test_session_maker() lazy
   │     ├─→ 老 compat path engine/TestSession = None
   │     └─→ setup_db(scope='function') 修 ScopeMismatch (W6)
   │
   └─→ W8 (5c77c417) test(tests): conftest model import 全集 + W8.1 sessionmaker 优化 (主指挥)
         ├─→ import app.models → Base 37 张表
         ├─→ _get_test_session_maker 取消 cache (避免 cache 跟 _engine 同步失效)
         └─→ 选项 A 决策落地: 71/78 留未来 PR
```

**当前 main HEAD `5c77c417`** 已包含全部修复 + W7 T2 本次终极验证 (71/78 PASS, 与 W2 T2 基线 100% 对齐).

---

## W7 沉淀 → W8 决策的完整路径 (锚点范式)

| 阶段 | commit | 内容 |
|---|---|---|
| **沉淀 base** | `a068c50b` docs | W2 T2 真闭环排查 + database.py engine 单例 bug 发现 (12 行 memory) |
| **bug class 闭环** | `ca0fb0a3` → `fe09010a` → `105d4ecc` | redis.py → database.py → fallback (3 个 production fix) |
| **测试漂移修复** | `0ae3319a` | 2 个 test 期望 regex 兼容 (W5.1 fallback 副作用) |
| **test infra 闭环** | `9b7913b1` → `5c77c417` | conftest 跨 scope + model import (2 个主指挥亲自 commit) |
| **终极决策** | W7 选项 A | E2E 真 DB 闭环留未来 PR, 71/78 PASS 是合理收官状态 |

**主指挥范式** (锚点 memory: `multi-agent-task-orchestration-baseline.md`):
- W7 worker 沉淀 blocker, 主指挥决策拍板, 不擅自跨 scope 改动
- W6 (我的) 发现 ScopeMismatch, 在原 W1 T1 commit message 内已 cite
- W8 (主指挥) 亲自修 conftest model import, 选项 A 落地
- W9 (本次) 终极验证 + 沉淀本 memory 收口

---

## W7 T2 vs W9 T1 (本次) 对比

| 验证项 | W7 T2 (decision point) | W9 T1 (本次终极验证) |
|---|---|---|
| 9 文件合跑 SKIP 模式 | 71 PASS + 7 SKIP | **71 PASS + 7 SKIP (基线对齐, 0 regression)** |
| commit count | 6 commits (W7 报告时) | **9 commits (含 W6/W7/W8 后增量)** |
| main HEAD | `9b7913b1` (W1 T1 commit) | `5c77c417` (W8 终极 commit) |
| 选项 A 状态 | 待主指挥决策 | **已落地 (主指挥 `5c77c417` commit message)** |
| E2E 闭环真 DB | 仍是 7 SKIP (test infra 阻塞) | **7 SKIP (test_maxlen_200 已闭环, 7-skipped 是框架层, 选项 A 接受)** |