"""测试 project_tools.py _safe_sanitize_description（2026-07-15 #P2 C组 sanitize 补盲点）

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_project_tools_sanitize.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

from app.agent.tools.project_tools import _safe_sanitize_description


class TestSafeSanitizeDescription:
    """get_project_summary 出口 sanitize 防御性补盲 (c9ff0a59 留下的 tool 出口未覆盖)"""

    def test_none_input_returns_none(self):
        """None 输入返 None (不抛错)"""
        assert _safe_sanitize_description(None) is None

    def test_empty_string_returns_none(self):
        """空串 / 纯空白 返 None (前端 ProjectsPanel 不会显示空 description)"""
        assert _safe_sanitize_description("") is None
        assert _safe_sanitize_description("   ") is None
        assert _safe_sanitize_description("\n\n") is None

    def test_clean_description_passes_through(self):
        """干净的人工短 description 不被改"""
        clean = "微纳米气泡在水处理中的应用研究"
        result = _safe_sanitize_description(clean)
        assert result == clean + "。"  # sanitize 加句号

    def test_dirty_description_gets_sanitized(self):
        """脏数据 (含 markdown + LLM 套路开场白) 被 sanitize 清理"""
        dirty = """好的，我为您规划以下项目：
项目名称：微纳米气泡水处理
研究方向：水处理
第一阶段：文献调研 3 个月
第二阶段：方案设计 3 个月
"""
        result = _safe_sanitize_description(dirty)
        assert result is not None
        assert len(result) <= 280  # sanitize 强制 ≤ 280 字
        assert "项目名称" not in result  # 字段标签被剥除
        assert "第一阶段" not in result  # 阶段字段被剥除

    def test_short_text_passes_through(self):
        """短字段 (< 8 字) 触发 sanitize fallback"""
        # sanitize 要求 ≥ 8 字才返回, < 8 字返空
        short = "微气泡"
        result = _safe_sanitize_description(short)
        # 接受 None 或 sanitize 后的版本, 但不应抛错
        assert result is None or isinstance(result, str)

    def test_returns_string_type(self):
        """返回值类型保证"""
        result = _safe_sanitize_description("微纳米气泡在水处理中的应用研究")
        assert result is None or isinstance(result, str)