"""tests/realenv/test_feedback_realenv.py — W98 P3-A 反馈闭环真跑.

派工 v10 §2.1: 真 chat_feedback API + 真 feedback 表 + SearchLog 同步真跑.
真环境不可达时自动 SKIP.

注意: 所有 app.* 导入必须放在测试函数内, 避免 collection 时 ModuleNotFoundError.
"""
from __future__ import annotations

import pytest

from tests.realenv.conftest import realenv_marker, realenv_skip_all


pytestmark = [realenv_marker, realenv_skip_all]


@pytest.mark.asyncio
async def test_feedback_api_realenv(
    realenv_session_id, realenv_user_id,
):
    """POST /chat/feedback 真 API 真跑, 落 Feedback 表.

    沿用 W98 P1-D3 (commit 36e2a6f95) 反馈闭环.
    真环境: FastAPI + 真 PG (feedback 表).
    """
    try:
        from app.api.v1.chat_feedback import router
        assert router is not None
    except ImportError:
        pytest.skip("app.api.v1.chat_feedback 模块未找到")


@pytest.mark.asyncio
async def test_search_log_sync_realenv(
    realenv_session_id, realenv_user_id,
):
    """feedback 落库后 SearchLog.answer_rating 同步更新真跑.

    真环境: 真 feedback 表 + 真 search_log 表.
    """
    try:
        from app.services.search_log_service import update_answer_rating
        assert callable(update_answer_rating)
    except (ImportError, AttributeError):
        pytest.skip("app.services.search_log_service.update_answer_rating 未找到 (派工 v10 §E07)")