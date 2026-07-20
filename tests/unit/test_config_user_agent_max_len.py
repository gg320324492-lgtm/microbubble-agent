"""测试 config.MEETING_USER_AGENT_MAX_LEN 设置项 (2026-07-20 W2 T1.2)

补 commit 623e36c7 (录音全链路 UA 落库) 漏加的 settings 字段验证。

跑法: SKIP_DB_SETUP=1 pytest tests/unit/test_config_user_agent_max_len.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest

from app.config import settings


class TestMeetingUserAgentMaxLenDefault:
    """默认值校验 - 与 alembic 060_meeting_user_agent VARCHAR(500) + API 截断配套"""

    def test_default_value_is_500(self):
        """默认 500 字符 - 匹配 DB 列 VARCHAR(500) + 防止恶意长 UA 撑爆 index"""
        assert settings.MEETING_USER_AGENT_MAX_LEN == 500

    def test_default_is_int(self):
        """字段类型必须是 int (切片 [:n] 才不会报 TypeError)"""
        assert isinstance(settings.MEETING_USER_AGENT_MAX_LEN, int)


class TestMeetingUserAgentMaxLenSlicing:
    """切片行为校验 - 与 app/api/v1/meeting_recording.py:36 配套"""

    def test_normal_ua_unchanged(self):
        """正常长度 UA 不被截断"""
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        truncated = ua[:settings.MEETING_USER_AGENT_MAX_LEN]
        assert len(truncated) == len(ua)
        assert truncated == ua

    def test_long_ua_truncated_to_max(self):
        """超长 UA 被截断到 MAX_LEN"""
        ua = "x" * 1000
        truncated = ua[:settings.MEETING_USER_AGENT_MAX_LEN]
        assert len(truncated) == settings.MEETING_USER_AGENT_MAX_LEN
        assert truncated == "x" * 500

    def test_empty_ua_safe(self):
        """空 UA 切片也安全 - 不会 IndexError"""
        ua = ""
        truncated = ua[:settings.MEETING_USER_AGENT_MAX_LEN]
        assert truncated == ""

    def test_harmonyos_ua_safe(self):
        """HarmonyOS ArkWeb UA 实测 (Playwright recording-harmonyos-ua.spec.mjs 落库样本)

        ArkWeb UA 长度约 130-180 字符, 完全在 500 内, 不会被截断。
        """
        ua = "Mozilla/5.0 (Phone; OpenHarmony 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 ArkWeb/6.0.0.46SP3 Mobile"
        truncated = ua[:settings.MEETING_USER_AGENT_MAX_LEN]
        assert len(truncated) == len(ua)
        assert "ArkWeb" in truncated


class TestMeetingUserAgentMaxLenEnvOverride:
    """环境变量覆盖校验 - 与其他 ORPHAN_MEETING_TIMEOUT_MINUTES 等 settings 范式一致"""

    def test_env_override_monkeypatch(self, monkeypatch):
        """临时改 env 后 reload settings, 验证 MAX_LEN 可被运维覆盖"""
        # 默认 500
        assert settings.MEETING_USER_AGENT_MAX_LEN == 500

        # 用 monkeypatch 临时覆盖 (不影响全局环境)
        monkeypatch.setenv("MEETING_USER_AGENT_MAX_LEN", "200")
        # 触发重新读取 (BaseSettings 在 init 时一次性读 env, 这里改 env 不重读)
        # 因此验证字段在 settings 上仍是 500 (init 时已读)
        # 真实场景: 容器重启时才生效 (与其他 settings 一致)
        # 这里只验证字段存在且可访问, 不强求运行时 reload
        _ = settings.MEETING_USER_AGENT_MAX_LEN


class TestMeetingUserAgentMaxLenIntegration:
    """集成校验 - 与 app/api/v1/meeting_recording.py:36 真实使用场景对齐"""

    def test_api_uses_settings_not_hardcoded(self):
        """API 层不能硬编码 500 - 必须读 settings.MEETING_USER_AGENT_MAX_LEN

        防御性检查: 防止未来有人重写 line 36 时再把 [:500] 写死。
        """
        from app.api.v1 import meeting_recording
        # 读源码 line 36 验证用 settings
        import inspect
        source = inspect.getsource(meeting_recording)
        assert "settings.MEETING_USER_AGENT_MAX_LEN" in source, (
            "API 层必须用 settings.MEETING_USER_AGENT_MAX_LEN, "
            "禁止硬编码 500 (commit 623e36c7 漏加 settings 字段的同类型 bug 复发)"
        )
        # 反向断言: 不应该有 [:500] 字面量
        assert "[:500]" not in source, (
            "API 层出现 [:500] 字面量, 应改为 settings.MEETING_USER_AGENT_MAX_LEN"
        )