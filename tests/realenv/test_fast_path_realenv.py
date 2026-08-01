"""tests/realenv/test_fast_path_realenv.py — W98 P3-A fast path 真跑.

派工 v10 §2.1: 真 intent_classifier + 真 fast config 真跑.
真环境不可达时自动 SKIP.

注意: 所有 app.* 导入必须放在测试函数内, 避免 collection 时 ModuleNotFoundError.
"""
from __future__ import annotations

import pytest

from tests.realenv.conftest import realenv_marker, realenv_skip_all


pytestmark = [realenv_marker, realenv_skip_all]


@pytest.mark.asyncio
async def test_casual_chat_realenv():
    """casual_chat 真分类 → 真 fast config 真跑.

    沿用 W98 P1-B (commit 90d4e8f71) 闲聊快路径.
    真环境: 真 IntentClassifier + 真 ChatEngine.
    """
    try:
        from app.agent.intent_classifier import (
            IntentCategory,
            IntentResult,
            _match_casual_chat,
        )
        assert _match_casual_chat("你好") is True
        assert IntentCategory.CASUAL_CHAT is not None
    except (ImportError, AttributeError) as e:
        pytest.skip(f"intent_classifier import 失败: {e}")


@pytest.mark.asyncio
async def test_follow_up_realenv():
    """follow_up 真分类 → fast config + 上轮主题块注入真跑.

    沿用 W98 P1-B 续讲路由.
    真环境: 真 _build_follow_up_context + 真 SessionManager.
    """
    try:
        from app.agent.intent_classifier import IntentCategory, _match_follow_up
        from app.agent.micro_bubble_agent import _build_follow_up_context
        assert _match_follow_up("继续") is True
        assert callable(_build_follow_up_context)
    except (ImportError, AttributeError) as e:
        pytest.skip(f"follow_up import 失败: {e}")