"""chat_feedback API tests — W98 CHAT-P1-D3 用户反馈闭环

验证 POST /api/v1/chat/feedback 行为:
- 路由注册 (轻量检查, 无副作用)
- 422 invalid rating
- 404 message_id not found
- 200 success with anon user
- 200 success with authed user

Alembic 迁移 092/093 文件结构 sanity 检查 (无需 DB).

不依赖 DB (mock 全部 IO).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# -------------------------------------------------------------------------
# 路由注册 (轻量检查)
# -------------------------------------------------------------------------


def test_chat_feedback_route_registered():
    """POST /chat/feedback 必须注册"""
    from app.api.v1 import chat_feedback
    router = chat_feedback.router
    paths = [r.path for r in router.routes]
    assert "/chat/feedback" in paths

    # 找到 /chat/feedback 路由并校验方法
    feedback_route = next(r for r in router.routes if r.path == "/chat/feedback")
    assert "POST" in feedback_route.methods


def test_router_prefix():
    """router 必须挂在 /chat 前缀 (main.py 注册时另叠 prefix)"""
    from app.api.v1 import chat_feedback
    assert chat_feedback.router.prefix == "/chat"


# -------------------------------------------------------------------------
# Pydantic schema 校验
# -------------------------------------------------------------------------


def test_rating_must_be_minus1_or_1():
    """rating 在 -1/1 之外必须 422"""
    from app.api.v1.chat_feedback import ChatFeedbackRequest
    # 合法值
    ChatFeedbackRequest(rating=1)
    ChatFeedbackRequest(rating=-1)
    # 越界值 (Pydantic Field(ge=-1, le=1) → 直接 ValueError)
    with pytest.raises(ValueError):
        ChatFeedbackRequest(rating=2)
    with pytest.raises(ValueError):
        ChatFeedbackRequest(rating=-2)
    with pytest.raises(ValueError):
        ChatFeedbackRequest(rating=0)


def test_comment_max_length():
    """comment 不能超 1000 字"""
    from app.api.v1.chat_feedback import ChatFeedbackRequest
    ChatFeedbackRequest(rating=1, comment="x" * 1000)
    with pytest.raises(ValueError):
        ChatFeedbackRequest(rating=1, comment="x" * 1001)


def test_message_id_must_be_positive_when_provided():
    """message_id 给定时必须 >= 1"""
    from app.api.v1.chat_feedback import ChatFeedbackRequest
    # None 也合法
    ChatFeedbackRequest(rating=1, message_id=None)
    ChatFeedbackRequest(rating=1, message_id=1)
    with pytest.raises(ValueError):
        ChatFeedbackRequest(rating=1, message_id=0)


# -------------------------------------------------------------------------
# Endpoint 行为 (mock 全部 IO)
# -------------------------------------------------------------------------


def _make_test_app_with_db(mock_db, mock_user=None):
    """构造带 mock db + 可选 mock user 的 FastAPI app"""
    from fastapi import FastAPI
    from app.core.database import get_db
    from app.core.security import get_current_user_optional
    from app.api.v1.chat_feedback import router as chat_feedback_router

    app = FastAPI()

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    if mock_user is not None:
        async def _override_user():
            return mock_user
        app.dependency_overrides[get_current_user_optional] = _override_user

    app.include_router(chat_feedback_router, prefix="/api/v1")
    return app


def test_invalid_rating_returns_422():
    """rating=2 → 422 (Pydantic 校验失败)"""
    from app.api.v1.chat_feedback import ChatFeedbackRequest
    # Pydantic Field(ge=-1, le=1) 在模型构造时即抛
    with pytest.raises(ValueError):
        ChatFeedbackRequest(rating=2)


def test_message_id_not_found_returns_404():
    """message_id 给了但 DB 不存在 → 404"""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # SELECT ChatMessage → scalar 返 None
    mock_result_msg = MagicMock()
    mock_result_msg.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result_msg)

    app = _make_test_app_with_db(mock_db)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/chat/feedback",
        json={"rating": 1, "message_id": 999},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_anonymous_success_no_message_id():
    """匿名用户 OK: feedback 落表, user_id=0, message_id=None 时跳过 SEARCH_LOG 同步

    端点行为:
    - message_id 为空 → 不查 ChatMessage (跳过 404 路径)
    - user_id = 0 (匿名) → 不写 SEARCH_LOG (匿名降级)
    """
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    # mock refresh 后设置 fb.id
    async def _refresh(obj):
        obj.id = 1
    mock_db.refresh = AsyncMock(side_effect=_refresh)

    # 不需要 execute (无 message_id, 无 SEARCH_LOG 同步)
    mock_db.execute = AsyncMock()

    app = _make_test_app_with_db(mock_db)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/chat/feedback",
        json={"rating": 1, "comment": "棒"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["rating"] == 1
    assert data["feedback_id"] == 1
    # user_id=0 → 不触发 SEARCH_LOG 同步 (execute 不应被调用)
    mock_db.execute.assert_not_called()


def test_authed_user_with_message_id_updates_search_log():
    """登录用户 + message_id → 200 + search_logs.answer_rating 更新"""
    mock_db = AsyncMock()

    # mock refresh 行为
    async def _refresh(obj):
        obj.id = 99
    mock_db.refresh = AsyncMock(side_effect=_refresh)
    mock_db.commit = AsyncMock()

    # search_log_mock 让 answer_rating 可写入
    search_log_mock = MagicMock()
    search_log_mock.answer_rating = None

    # 2 次 execute: 1) SELECT ChatMessage → 存在 2) SELECT SearchLog → 找到
    result_msg = MagicMock()
    result_msg.scalar_one_or_none.return_value = 42
    result_log = MagicMock()
    result_log.scalar_one_or_none.return_value = search_log_mock

    call_idx = {"n": 0}

    async def _execute_side_effect(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return result_msg if idx == 0 else result_log

    mock_db.execute = AsyncMock(side_effect=_execute_side_effect)

    mock_member = MagicMock()
    mock_member.id = 7

    app = _make_test_app_with_db(mock_db, mock_user=mock_member)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/chat/feedback",
        json={
            "rating": -1,
            "message_id": 42,
            "comment": "答错了",
            "session_id": "user_test_001",
            "agent_reply": "你好",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["rating"] == -1
    # search_log_mock.answer_rating 应被设为 -1
    assert search_log_mock.answer_rating == -1


def test_search_log_sync_failure_does_not_rollback_feedback():
    """search_log 同步失败 → feedback 仍落表 (best-effort)"""
    mock_db = AsyncMock()

    async def _refresh(obj):
        obj.id = 5
    mock_db.refresh = AsyncMock(side_effect=_refresh)
    mock_db.commit = AsyncMock()

    # 第一次 execute SELECT ChatMessage OK
    # 第二次 execute SELECT SearchLog raise
    result_msg = MagicMock()
    result_msg.scalar_one_or_none.return_value = 42

    call_idx = {"n": 0}

    async def _execute_side_effect(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        if idx == 0:
            return result_msg
        raise RuntimeError("search_log SELECT failed (mock)")

    mock_db.execute = AsyncMock(side_effect=_execute_side_effect)

    mock_member = MagicMock()
    mock_member.id = 7

    app = _make_test_app_with_db(mock_db, mock_user=mock_member)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/chat/feedback",
        json={"rating": -1, "message_id": 42, "agent_reply": "..."},
    )
    assert resp.status_code == 200  # feedback 仍 200 (best-effort)
    assert resp.json()["feedback_id"] == 5


# -------------------------------------------------------------------------
# Alembic 迁移 sanity 检查 (无需 DB)
# -------------------------------------------------------------------------


def test_092_revision_chain():
    """092_add_chat_feedback_message_id.down_revision 必须接 091_add_kg_entity"""
    rev_file = "alembic/versions/092_add_chat_feedback_message_id.py"
    with open(rev_file, "r", encoding="utf-8") as f:
        src = f.read()
    assert 'revision = "092_add_chat_feedback_message_id"' in src
    assert 'down_revision = "091_add_kg_entity"' in src


def test_093_revision_chain():
    """093_add_search_log_answer_rating.down_revision 必须接 092"""
    rev_file = "alembic/versions/093_add_search_log_answer_rating.py"
    with open(rev_file, "r", encoding="utf-8") as f:
        src = f.read()
    assert 'revision = "093_add_search_log_answer_rating"' in src
    assert 'down_revision = "092_add_chat_feedback_message_id"' in src


def test_092_adds_message_id_column():
    """092 必须 ALTER TABLE feedback ADD COLUMN message_id"""
    with open("alembic/versions/092_add_chat_feedback_message_id.py", "r", encoding="utf-8") as f:
        src = f.read()
    assert "message_id" in src
    assert "fk_feedback_message_id" in src
    assert "chat_messages" in src
    assert "ON DELETE CASCADE" in src


def test_093_adds_answer_rating_column():
    """093 必须 ALTER TABLE search_logs ADD COLUMN answer_rating"""
    with open("alembic/versions/093_add_search_log_answer_rating.py", "r", encoding="utf-8") as f:
        src = f.read()
    assert "answer_rating" in src
    assert "ck_search_logs_answer_rating" in src
    assert "ix_search_logs_answer_rating" in src
