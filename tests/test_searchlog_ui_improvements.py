"""W99 N-6 件 7 SearchLog UI 改进 — analytics / chat_feedback / store 端到端测试

派工 v10 §3 单测目标: tests/test_searchlog_ui_improvements.py 新增 8/8 PASS
- 必 `pytest.importorskip` 守护
- 现有 mock 测试保持 PASS (PR6 + P2-E2E 不破)

测试 8 项 (覆盖 6 类 UI 改进清单的可测单元):
  1. analytics answer_rating by_rating 聚合 (👍 / 👎 / 无反馈 bucket)
  2. analytics answer_trend 14 天趋势 (date -> {up, down, unrated})
  3. analytics 兼容 (无 answer_rating 数据时不抛)
  4. chat_feedback 匿名 user 同步 search_log (W99 N-6 改进 5)
  5. chat_feedback 登录 user 也走 session_id 优先
  6. useSearchAnalytics store 行为: startSearch 失败不抛 + reset 清状态
  7. useSearchAnalytics store: recordClick 在没 currentSearchId 时不调
  8. analytics endpoint 路由存在 + path
"""
import asyncio
import pytest


def _run(coro):
    """兼容无 pytest-asyncio 的环境, 用 asyncio.run 跑 async 测试逻辑"""
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────
# 1. analytics answer_rating by_rating 聚合
# ─────────────────────────────────────────────────────────────

def _build_analytics_db(rows, by_user_rows=None, by_model_rows=None, by_source_rows=None, trend_rows=None, main_row=None):
    """构造 mock_db 让 analytics.get_stats 跑得通

    rows: list of (rating, count) 给 by_rating SQL
    by_user_rows: list of (user_key, name, username, avatar, searches, clicks, avg_pos)
    by_model_rows / by_source_rows / trend_rows / main_row 同结构
    main_row: (total_searches, total_clicks, avg_click_pos, zero_click_count)
    trend_rows 元素要是 (date_obj, searches, clicks), date_obj 必须有 .isoformat()
    """
    from unittest.mock import AsyncMock, MagicMock
    from datetime import date

    if main_row is None:
        main_row = (100, 30, 2.5, 70)
    if by_user_rows is None:
        by_user_rows = []
    if by_model_rows is None:
        by_model_rows = [("Qwen3-Embedding-0.6B", 100, 30)]
    if by_source_rows is None:
        by_source_rows = [("knowledge_search", 100, 30)]
    if trend_rows is None:
        trend_rows = [(date(2026, 8, 1), 100, 30)]

    db = MagicMock()
    call_idx = {"n": 0}

    # 按执行顺序: main → by_model → by_source → by_user → trend → by_rating → answer_trend
    all_results = [main_row, by_model_rows, by_source_rows, by_user_rows, trend_rows, rows, []]

    async def _execute(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        payload = all_results[idx] if idx < len(all_results) else []

        result = MagicMock()
        if idx == 0:
            # main 单行
            result.fetchone.return_value = payload
        else:
            result.__iter__.return_value = iter(payload)
        return result

    db.execute = AsyncMock(side_effect=_execute)
    return db


def test_analytics_by_rating_buckets():
    """W99 N-6 改进 (6): answer_rating 聚合 👍/👎/无反馈 3 桶

    by_rating 应有 up / down / unrated / answer_rate / upvote_rate / total 字段
    """
    from app.api.v1.analytics import get_stats

    # (rating_bucket, count) — rating=0 表示无反馈 (COALESCE)
    rows = [(1, 25), (-1, 5), (0, 70)]
    db = _build_analytics_db(rows)

    out = _run(get_stats(days=7, db=db))

    assert "by_rating" in out, "必须返回 by_rating 字段"
    br = out["by_rating"]
    assert br["up"] == 25
    assert br["down"] == 5
    assert br["unrated"] == 70
    assert br["total"] == 100
    # answer_rate = (up + down) / total * 100 = 30
    assert br["answer_rate"] == 30.0
    # upvote_rate = up / total * 100 = 25
    assert br["upvote_rate"] == 25.0


def test_analytics_by_rating_empty():
    """无任何 answer_rating 数据时, by_rating 仍合法 (up=0, down=0, unrated=0)

    防止空库 / 新部署 0 搜索时前端看板报 500
    """
    from app.api.v1.analytics import get_stats

    db = _build_analytics_db([])  # 无任何 by_rating 行
    out = _run(get_stats(days=7, db=db))

    br = out["by_rating"]
    assert br["up"] == 0
    assert br["down"] == 0
    assert br["unrated"] == 0
    assert br["total"] == 0
    assert br["answer_rate"] == 0.0
    assert br["upvote_rate"] == 0.0


def test_analytics_answer_trend_in_response():
    """answer_trend 字段必须存在 (即使 0 行)"""
    from app.api.v1.analytics import get_stats

    db = _build_analytics_db([])
    out = _run(get_stats(days=7, db=db))

    assert "answer_trend" in out
    assert isinstance(out["answer_trend"], list)
    # 空库 0 长度
    assert len(out["answer_trend"]) == 0


# ─────────────────────────────────────────────────────────────
# 4-5. chat_feedback 改进 (5) 匿名/登录用户
# ─────────────────────────────────────────────────────────────

def test_chat_feedback_anon_writes_search_log_via_session_id():
    """W99 N-6 改进 (5): 匿名 + message_id + session_id → search_log.answer_rating 写入

    旧: user_id=0 守卫跳过 → 匿名数据盲区
    新: 优先按 session_id 定位最近 search_log
    """
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.core.database import get_db
    from app.core.security import get_current_user_optional
    from app.api.v1.chat_feedback import router as chat_feedback_router

    db = AsyncMock()

    async def _refresh(obj):
        obj.id = 7
    db.refresh = AsyncMock(side_effect=_refresh)
    db.commit = AsyncMock()

    search_log_mock = MagicMock()
    search_log_mock.answer_rating = None

    result_msg = MagicMock()
    result_msg.scalar_one_or_none.return_value = 99
    result_log = MagicMock()
    result_log.scalar_one_or_none.return_value = search_log_mock

    call_idx = {"n": 0}

    async def _execute(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return result_msg if idx == 0 else result_log

    db.execute = AsyncMock(side_effect=_execute)

    app = FastAPI()

    async def _override_db():
        yield db
    app.dependency_overrides[get_db] = _override_db
    # 显式 None: 匿名 (get_current_user_optional 返 None)
    async def _override_user():
        return None
    app.dependency_overrides[get_current_user_optional] = _override_user
    app.include_router(chat_feedback_router, prefix="/api/v1")

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat/feedback",
        json={"rating": 1, "message_id": 99, "session_id": "anon_session_xyz"},
    )
    assert resp.status_code == 200
    # 匿名 + session_id 也能写 answer_rating (消除盲区)
    assert search_log_mock.answer_rating == 1


def test_chat_feedback_fallback_to_user_id_when_session_miss():
    """session_id 找不到 search_log → 登录用户按 user_id 兜底 (W99 N-6 改进 5 兜底逻辑)

    场景: 旧 session_id (用户清缓存) 但有 user_id 归属
    """
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.core.database import get_db
    from app.core.security import get_current_user_optional
    from app.api.v1.chat_feedback import router as chat_feedback_router

    db = AsyncMock()

    async def _refresh(obj):
        obj.id = 11
    db.refresh = AsyncMock(side_effect=_refresh)
    db.commit = AsyncMock()

    # 第 1 次 (ChatMessage) 命中, 第 2 次 (session_id SELECT) 返 None,
    # 第 3 次 (user_id 兜底) 命中
    search_log_mock = MagicMock()
    search_log_mock.answer_rating = None

    result_msg = MagicMock()
    result_msg.scalar_one_or_none.return_value = 33
    result_session_miss = MagicMock()
    result_session_miss.scalar_one_or_none.return_value = None
    result_user_hit = MagicMock()
    result_user_hit.scalar_one_or_none.return_value = search_log_mock

    call_idx = {"n": 0}
    queue = [result_msg, result_session_miss, result_user_hit]

    async def _execute(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return queue[idx] if idx < len(queue) else result_msg

    db.execute = AsyncMock(side_effect=_execute)

    mock_member = MagicMock()
    mock_member.id = 42

    app = FastAPI()

    async def _override_db():
        yield db
    app.dependency_overrides[get_db] = _override_db
    async def _override_user():
        return mock_member
    app.dependency_overrides[get_current_user_optional] = _override_user
    app.include_router(chat_feedback_router, prefix="/api/v1")

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat/feedback",
        json={"rating": -1, "message_id": 33, "session_id": "stale_session"},
    )
    assert resp.status_code == 200
    # 兜底 user_id 命中, 写入
    assert search_log_mock.answer_rating == -1


# ─────────────────────────────────────────────────────────────
# 6-7. useSearchAnalytics store 行为
# ─────────────────────────────────────────────────────────────

def test_store_start_silent_on_api_failure():
    """埋点 API 失败时, startSearch 静默 (不抛), 业务主流程不受影响

    W99 N-6 改进 (1) 配套: 埋点是 best-effort, 失败也不应阻断搜索
    注: 这里是 JS store, 通过解析 .js 文件验证 startSearch 的 try/except 模式
    """
    import pathlib
    p = pathlib.Path("web/src/stores/useSearchAnalytics.js")
    src = p.read_text(encoding="utf-8")
    # startSearch 必须包 try/catch (best-effort 铁律)
    assert "try {" in src or "try{" in src
    # 失败时不应 throw, 应 set state
    assert "currentSearchId = null" in src
    assert "this.currentSearchId = null" in src


def test_store_reset_clears_state():
    """reset() 必须在 store 中实现 (避免跨 query 串味)

    W99 N-6 改进 (1) + (2): KnowledgeView.handleSearch 加 reset, 移动端同
    """
    import pathlib
    p = pathlib.Path("web/src/stores/useSearchAnalytics.js")
    src = p.read_text(encoding="utf-8")
    # reset action 必须存在
    assert "reset()" in src
    # reset 必须清 currentSearchId + lastTopIds
    assert "this.currentSearchId = null" in src
    assert "this.lastTopIds = []" in src


def test_store_record_click_skips_without_event():
    """无 currentSearchId 时 recordClick 不发请求 (静默守卫)

    W99 N-6 改进 (1) 配套: 防止 stale eventId 串味
    """
    import pathlib
    p = pathlib.Path("web/src/stores/useSearchAnalytics.js")
    src = p.read_text(encoding="utf-8")
    # recordClick 入口必须有守卫: !this.currentSearchId → return
    assert "!this.currentSearchId" in src or "currentSearchId === null" in src or "currentSearchId === undefined" in src


# ─────────────────────────────────────────────────────────────
# 8. analytics 路由 sanity
# ─────────────────────────────────────────────────────────────

def test_analytics_routes_registered():
    """POST + PATCH + GET 3 个 analytics 路由都注册了"""
    from app.api.v1 import analytics
    paths = {r.path for r in analytics.router.routes}
    assert "/analytics/search-event" in paths
    assert "/analytics/stats" in paths
    assert "/analytics/logs" in paths

    # PATCH 路由单独校验
    patch_route = next(
        r for r in analytics.router.routes
        if "search-event" in r.path and "click" in r.path
    )
    assert "PATCH" in patch_route.methods
