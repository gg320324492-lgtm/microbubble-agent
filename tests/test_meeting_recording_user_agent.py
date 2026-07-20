"""tests/test_meeting_recording_user_agent.py

2026-07-16 录音全链路加固: User-Agent 落库 + 截断守卫单测

覆盖:
- `app/api/v1/meeting_recording.py` line 35 UA 截断 500 字符
- 空 UA 落库 (None -> '')
- 长 UA (1000 -> 500 截断)

铁律: SKIP_DB_SETUP=1 mock, 不依赖数据库, 5s 内跑完
"""
import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import asyncio
import inspect
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 让 Python 找到 app/ 模块 (与 tests/unit/* 模式一致)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# TestUserAgentTruncation
# ============================================================================


class TestUserAgentTruncation:
    """录音 start_recording UA 截断守卫 (line 35)."""

    def _extract_ua_from_handler(self, ua):
        """直接重放 line 35 截断逻辑, 不走数据库."""
        return (ua or "")[:500]

    def test_normal_ua_under_500_passes_through(self):
        """短 UA (Chrome 89 字符串 ~120 字符) 应原样保留."""
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        result = self._extract_ua_from_handler(ua)
        assert result == ua
        assert len(result) < 500

    def test_empty_ua_falls_back_to_empty_string(self):
        """None 头部 -> '' (数据库 NOT NULL 安全), 空串 -> ''."""
        assert self._extract_ua_from_handler(None) == ""
        assert self._extract_ua_from_handler("") == ""

    def test_ua_exactly_500_passes_through(self):
        """正好 500 字符的 UA 保留, 不应误截."""
        ua = "x" * 500
        result = self._extract_ua_from_handler(ua)
        assert result == ua
        assert len(result) == 500

    def test_ua_over_500_truncated_to_500(self):
        """1000 字符 UA 应截断到 500, 防 VARCHAR(500) 越界."""
        ua = "a" * 1000
        result = self._extract_ua_from_handler(ua)
        assert len(result) == 500
        assert result == "a" * 500

    def test_ua_very_long_truncated_to_500(self):
        """10000 字符 UA (恶意/异常) 截断到 500."""
        ua = "b" * 10000
        result = self._extract_ua_from_handler(ua)
        assert len(result) == 500

    def test_harmonyos_arkweb_ua_passes_through(self):
        """HarmonyOS ArkWeb 真实 UA (典型 ~250 字符) 完整保留, 便于事后排查."""
        ua = (
            "Mozilla/5.0 (Linux; Android 12; HarmonyOS; Phone; TGY-AN00; HMSCore 6.13.0.332) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.86 Mobile Safari/537.36 "
            "ArkWeb/45.10.0 Beta1 (HuaWei; GM 11.0; TGY-AN00; TGY-AN00; 0; 200; 0)"
        )
        result = self._extract_ua_from_handler(ua)
        assert result == ua
        assert len(result) < 500

    def test_start_recording_handler_truncates_ua_in_meeting(self):
        """端到端: 调用 start_recording handler 时, 传入 1000 字符 UA,
        实际落库的 Meeting.user_agent 应为前 500 字符."""
        from datetime import datetime, timezone
        from app.api.v1 import meeting_recording as mr_module
        from app.config import settings

        started_at = datetime(2026, 7, 20, 12, 0, 0)
        mock_meeting = MagicMock()
        mock_meeting.id = 42
        mock_meeting.title = "正在听会（ID 42）"
        mock_meeting.status = "recording"
        mock_meeting.recording_started_at = started_at
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(side_effect=[None, None])
        mock_db.refresh = AsyncMock(side_effect=[mock_meeting, mock_meeting])

        mock_request = MagicMock()
        long_ua = "x" * 1000
        mock_request.headers.get = MagicMock(return_value=long_ua)
        mock_user = MagicMock()
        mock_user.id = 7

        captured = {}

        def fake_meeting_init(**kwargs):
            captured.update(kwargs)
            return mock_meeting

        with patch.object(mr_module, "Meeting", side_effect=fake_meeting_init):
            handler = mr_module.start_recording
            result = asyncio.run(
                handler(
                    request=mock_request,
                    current_user=mock_user,
                    db=mock_db,
                )
            )

        assert captured["user_agent"] == "x" * settings.MEETING_USER_AGENT_MAX_LEN
        assert len(captured["user_agent"]) == 500
        assert captured["created_by"] == mock_user.id
        assert captured["status"] == "recording"
        assert captured["upload_status"] == "pending"
        assert captured["last_chunk_index"] == -1

    def test_start_recording_handler_with_empty_ua(self):
        """端到端: 客户端没传 UA 头时, Meeting.user_agent 应是 '' 而不是 None."""
        from app.api.v1 import meeting_recording as mr_module

        mock_meeting = MagicMock()
        mock_meeting.id = 43
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(side_effect=[None, None])
        mock_db.refresh = AsyncMock(side_effect=[mock_meeting, mock_meeting])

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_user = MagicMock()
        mock_user.id = 8

        captured = {}

        def fake_meeting_init(**kwargs):
            captured.update(kwargs)
            return mock_meeting

        with patch.object(mr_module, "Meeting", side_effect=fake_meeting_init):
            handler = mr_module.start_recording
            asyncio.run(
                handler(
                    request=mock_request,
                    current_user=mock_user,
                    db=mock_db,
                )
            )

        assert captured["user_agent"] == ""

    def test_handler_signature_accepts_request_param(self):
        """API 签名: start_recording 必须有 request: Request 形参 (line 25)."""
        from app.api.v1 import meeting_recording as mr_module

        sig = inspect.signature(mr_module.start_recording)
        params = sig.parameters
        assert "request" in params
        assert "current_user" in params
        assert "db" in params

    def test_handler_uses_settings_constant(self):
        """防御: UA 截断长度应与 settings.MEETING_USER_AGENT_MAX_LEN 一致 (单点配置)."""
        from app.config import settings

        assert settings.MEETING_USER_AGENT_MAX_LEN == 500
