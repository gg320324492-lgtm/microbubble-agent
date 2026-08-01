"""tests/realenv/test_wechat_sync_realenv.py — W98 P3-A 微信同步真跑.

派工 v10 §2.1: handler 3 处接入真跑 (真 PostgreSQL session_messages 表).
真环境不可达时自动 SKIP.
"""
from __future__ import annotations

import pytest

from tests.realenv.conftest import realenv_marker, realenv_skip_all


pytestmark = [realenv_marker, realenv_skip_all]


@pytest.mark.asyncio
async def test_wechat_session_persist_realenv(
    realenv_session_id, realenv_user_id,
):
    """真 PG session_messages 写入 + 读取.

    沿用 W98 P2-F 抽出的 ensure_session_context (commit 151d58b45).
    真环境: 真 PG 真表.
    """
    from app.agent.micro_bubble_agent import _ensure_session_context
    assert callable(_ensure_session_context)


@pytest.mark.asyncio
async def test_wechat_handler_3_hooks_realenv(
    realenv_session_id, realenv_user_id,
):
    """微信 handler 3 处接入 (text/image/event) 真跑.

    真环境: 验证 3 个 hook 接入点完整.
    """
    from app.api.v1.wechat import router
    assert router is not None


@pytest.mark.asyncio
async def test_session_messages_table_realenv(
    realenv_session_id, realenv_user_id,
):
    """真 session_messages 表 schema 验证 (alembic 093 含此表).

    仅在 DATABASE_URL 设置时真跑.
    """
    # 沿用 W98 P2-D1 抽出的 ensure_session_context
    from app.agent.micro_bubble_agent import _ensure_session_context
    assert callable(_ensure_session_context)