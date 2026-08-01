# tests/realenv/ — 真环境 e2e 集成层 (W98 P3-A)

> **派工**: W98 P3-A 派工 v10 §2.2 (B 实施, 真环境 e2e 集成).
> **日期**: 2026-08-01.
> **worktree**: `E:/agent-w98-p3-a-realenv-e2e` (branch `chore/w98-p3-a-realenv-e2e`).

## 目标

为现有 mock e2e (`tests/test_chat_experience_e2e.py` 等 5 个文件) 增加真环境集成层, 验证 mock 与真环境行为一致.

**严禁改动现有 mock 测试** (派工 brief 边界约束). 真环境版为独立新文件, 与 mock 版并存.

## 文件清单

| 文件 | 覆盖范围 | 状态 |
|------|----------|------|
| `conftest.py` | SKIP 守护 + fixtures (database_url / redis_url / session_id / user_id) | 必读 |
| `test_chat_experience_realenv.py` | 5 铁证真跑 (PG 真表 + Redis 真键) | 真环境 5/5 PASS 或 5 SKIP |
| `test_consistency_realenv.py` | 真 rag_evaluator + 5 题抽样 | 真环境 1/1 PASS 或 1 SKIP |
| `test_wechat_sync_realenv.py` | handler 3 处接入 + session_messages 表 | 真环境 3/3 PASS 或 3 SKIP |
| `test_feedback_realenv.py` | 真 chat_feedback API + feedback 表 | 真环境 2/2 PASS 或 2 SKIP |
| `test_fast_path_realenv.py` | 真 intent_classifier + 真 fast config | 真环境 2/2 PASS 或 2 SKIP |

## 启用真环境 e2e

### 1. 启动 PostgreSQL + Redis (任选其一)

**方式 A: docker-compose (推荐)**

```bash
# 启 PG + Redis
docker compose up -d db redis
# 等 5s 启动完成
sleep 5
```

**方式 B: 本机原生 PG/Redis**

```bash
# macOS / Linux
brew services start postgresql redis
# Windows
net start postgresql-x64-15
net start redis
```

### 2. 跑 alembic 到 head 093

```bash
export DATABASE_URL=postgresql://postgres:microbubble2026@localhost:5432/microbubble
export SKIP_DB_SETUP=0
python -m alembic upgrade head
# 期望: 1 head = 093_add_search_log_answer_rating
```

### 3. 设环境变量 + 跑真环境 e2e

```bash
export DATABASE_URL=postgresql://postgres:microbubble2026@localhost:5432/microbubble
export REDIS_URL=redis://localhost:6379/0
unset SKIP_DB_SETUP
python -m pytest tests/realenv -v
# 期望: 13/13 PASS 或部分 SKIP (缺表/缺 API key)
```

### 4. 本机不可达时 SKIP (默认行为)

```bash
# 不设 DATABASE_URL / REDIS_URL
unset DATABASE_URL REDIS_URL
python -m pytest tests/realenv -v
# 期望: 全部 SKIP, 0 失败
```

## SKIP 守护逻辑 (conftest.py)

```python
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

REALENV_DB_AVAILABLE = bool(DATABASE_URL)
REALENV_REDIS_AVAILABLE = bool(REDIS_URL)

def pytest_collection_modifyitems(config, items):
    for item in items:
        if "tests/realenv/" in str(item.fspath):
            if os.getenv("SKIP_DB_SETUP"):
                item.add_marker(pytest.mark.skip(reason="真环境不可达"))
            else:
                item.add_marker(pytest.mark.skipif(
                    not REALENV_DB_AVAILABLE,
                    reason="DATABASE_URL 未设置"
                ))
                item.add_marker(pytest.mark.skipif(
                    not REALENV_REDIS_AVAILABLE,
                    reason="REDIS_URL 未设置"
                ))
```

## 与 mock 测试的关系

| mock 测试 | 真环境版 | 关系 |
|----------|----------|------|
| `tests/test_chat_experience_e2e.py` | `tests/realenv/test_chat_experience_realenv.py` | 并存, 互不影响 |
| `tests/test_wechat_session_sync.py` | `tests/realenv/test_wechat_sync_realenv.py` | 并存 |
| `tests/test_consistency_double_round.py` | `tests/realenv/test_consistency_realenv.py` | 并存 |
| `tests/test_chat_feedback_api.py` | `tests/realenv/test_feedback_realenv.py` | 并存 |
| `tests/test_fast_path_casual.py` | `tests/realenv/test_fast_path_realenv.py` | 并存 |

mock 测试**保持 46/46 PASS 基线**. 真环境测试**默认 SKIP, 启用后真跑**.

## 5 件套守恒

1. **alembic 1 head = 093** (沿用 W98 base, 本任务不动)
2. **真环境 e2e SKIP guard** (本任务核心交付)
3. **PWA build 沿用基线** (不动 frontend)
4. **0 production code** (`git diff main -- app/ web/src/ alembic/ | wc -l` = 0)
5. **锚点范式** (W98 +11, 1 commit)

## 后续 (P3-A.2 派工预留)

- 启用真环境后, 真跑 13/13 case 验证 mock 与真环境行为一致
- 真环境 PASS 后, 考虑在 CI/CD 加入 `pytest tests/realenv` 默认跑
- 不在本任务范围内

## 派工 v10 §5 反馈 (实施后)

实际跑法 / pytest 结果 / push 验证见 `docs/w98-p3-a-realenv-e2e-2026-08-01.md` (本任务 runbook).