"""测试 _strip_qwen3_section_markers (2026-07-15 #P2)

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_strip_qwen3_markers.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

from app.agent.agentic_loop import _strip_qwen3_section_markers


class TestStripQwen3SectionMarkers:
    """qwen3:8b 走 ollama 时输出内部 section marker 泄露到用户界面, 需剥除"""

    def test_strips_tool_start(self):
        """剥 | tool___start | 行"""
        text = """| tool___start |
| tool_context |

- 课题组成员包括**王天志**、**杜同贺**等
"""
        result = _strip_qwen3_section_markers(text)
        assert "tool___start" not in result
        assert "tool_context" not in result
        assert "**王天志**" in result  # 真实内容保留

    def test_strips_topic_overview(self):
        """剥 | topic overview | 行"""
        text = """| topic overview |
用户的问题是关于课题组成员的信息。

| problem statement |
课题组共有 27 名成员。

| relevance analysis |
用户需要明确的数据支持。
"""
        result = _strip_qwen3_section_markers(text)
        assert "topic overview" not in result
        assert "problem statement" not in result
        assert "relevance analysis" not in result
        assert "27 名成员" in result  # 真实内容保留
        assert "明确的数据支持" in result

    def test_strips_thinking_detail(self):
        """剥 | thinking detail | 行"""
        text = """| thinking detail |
1. **确定问题**: 用户问成员数量
2. **数据**: 共 27 人
3. **整理**: 列出前 5 名
"""
        result = _strip_qwen3_section_markers(text)
        assert "thinking detail" not in result
        assert "确定问题" in result
        assert "**数据**" in result

    def test_strips_comment_form(self):
        """剥 `//| xxx |` 注释形式"""
        text = """//| toolcontext |
课题组有 28 人
//| topic overview |
"""
        result = _strip_qwen3_section_markers(text)
        assert "toolcontext" not in result
        assert "28 人" in result

    def test_preserves_markdown_table(self):
        """不影响正常 markdown 表格 (| col1 | col2 |)"""
        text = """| 姓名 | 年级 | 研究方向 |
| --- | --- | --- |
| 王天志 | 副教授 | 微纳米气泡 |
| 杜同贺 | 研一 | 水质 |
"""
        result = _strip_qwen3_section_markers(text)
        # markdown 表格的列头是字段名+空格+列名, 不是单一 marker
        # 由于我的 regex 只剥整行都是 marker 的, 表格应保留
        assert "姓名" in result
        assert "王天志" in result

    def test_preserves_underscore_in_sentence(self):
        """不影响正文中含下划线的内容"""
        text = "用户问题涉及 micro_nano_bubble 研究"
        result = _strip_qwen3_section_markers(text)
        assert result == text  # 不变

    def test_short_text_preserved(self):
        """过短文本不剥除 (兜底防误杀)"""
        text = "你好"  # < 30 字符
        result = _strip_qwen3_section_markers(text)
        assert result == text

    def test_strip_results_in_short_kept(self):
        """剥除后剩 < 30 字符保留原文 (兜底)"""
        text = "| tool___start |\n短文本"
        result = _strip_qwen3_section_markers(text)
        # 剥除后只剩 "短文本" (< 30 字符), 兜底返原文
        assert result == text

    def test_real_case_from_screenshot(self):
        """用户截图中的实际污染文本"""
        text = """| tool___start |
| tool_context |
- **问题**: 课题组组成员有多少名？具体有哪些成员？
- **背景信息**:
  - 本课题组现有成员包括：
  - 学术成员（高、低年级）：130 人
  - 现任项目负责人：王天志（高级研究员）
  - 现任管理同事：测试小助手（未明确身份，但已参与多个项目）
- **具体成员情况**：
  - **成员统计**: 课题组共有27名成员
  - **年级分布**: 大三、研一、研二、博士等
  - **研究方向**: 藻华控制、盐碱土修复、水产养殖等
- **其他限制**:
  - 不要添加无关内容
  - 使用中文输出
  - 回复风格需专业、简洁
< / | toolcontext | >

| topic overview |
用户的问题是关于课题组成员的数量和具体成员信息，需要从背景信息中提取数据并整理出来。

| problem statement |
用户询问有多少名成员，以及具体有哪些成员。
"""
        result = _strip_qwen3_section_markers(text)
        # 关键: 内部 marker 应全部剥除
        assert "tool___start" not in result
        assert "tool_context" not in result
        assert "toolcontext" not in result
        assert "topic overview" not in result
        assert "problem statement" not in result
        # 真实内容应保留
        assert "课题组现有成员" in result
        assert "王天志" in result
        assert "27名成员" in result
        assert "藻华控制" in result