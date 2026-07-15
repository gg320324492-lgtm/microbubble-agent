"""测试 _strip_json_envelope (2026-07-15 #P2 续)

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_strip_json_envelope.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

from app.agent.agentic_loop import _strip_json_envelope


class TestStripJsonEnvelope:
    """LLM synthesis 阶段偶尔会幻觉写出 raw tool_result JSON envelope,
    直接泄露到用户 UI (用户截图实测: {"status":"success","content":"组里..."}).
    4 个老 sanitizer 全漏, 必须专门处理."""

    def test_extracts_content_field(self):
        """截图原案例: 剥 envelope, 抽取 content 字段"""
        text = '{"status":"success","content":"组里最年轻和最年长的成员分别是？\\n\\n## 最年轻的成员..."}'
        result = _strip_json_envelope(text)
        assert "{" not in result.split("\n\n")[0]  # envelope 结构消失
        assert "组里最年轻和最年长的成员" in result
        assert '"status"' not in result
        assert "## 最年轻的成员" in result

    def test_extracts_multiple_fields(self):
        """envelope 含多个可读字段, 都抽取"""
        text = '{"status":"success","content":"主要内容","markdown":"# 标题\\n正文","summary":"一行摘要"}'
        result = _strip_json_envelope(text)
        assert "主要内容" in result
        assert "# 标题" in result
        assert "一行摘要" in result
        assert '"status"' not in result

    def test_extracts_content_with_tail(self):
        """envelope 后还有 LLM 写的正文尾巴"""
        text = '{"status":"success","content":"包内内容"}后续正文段落...'
        result = _strip_json_envelope(text)
        assert "包内内容" in result
        assert "后续正文段落" in result
        assert '"status"' not in result

    def test_preserves_normal_json_in_middle(self):
        """正文中间嵌入的 JSON 示例不动 (只剥前 4 KB 开头)"""
        text = '正文内容 {"data": "中间示例"} 更多正文'
        result = _strip_json_envelope(text)
        # 不以 { 开头 → 不剥
        assert result == text

    def test_preserves_leading_json_without_status(self):
        """envelope 必须有 status ∈ {success, error}, 否则不动"""
        text = '{"foo": "bar", "items": [1, 2, 3]}正文'
        result = _strip_json_envelope(text)
        # 无 status 字段 → 保留 (可能是普通数据 JSON, 误剥会破坏内容)
        assert result == text

    def test_preserves_error_status_too(self):
        """error 状态的 envelope 也剥 (但只对 status 字段白名单有效)"""
        text = '{"status":"error","content":"查询失败: 数据库连接超时"}'
        result = _strip_json_envelope(text)
        assert "查询失败" in result
        assert "数据库连接超时" in result
        assert '"status"' not in result

    def test_handles_nested_json(self):
        """嵌套 JSON (成员列表含对象数组) 正确解析"""
        text = '{"status":"success","content":"找到 3 位成员","members":[{"name":"王天志"},{"name":"杜同贺"},{"name":"宋洋"}]}'
        result = _strip_json_envelope(text)
        assert "找到 3 位成员" in result
        assert '"status"' not in result
        assert '"members"' not in result

    def test_handles_escaped_quotes_in_content(self):
        """content 字段含转义引号不被破坏"""
        text = r'{"status":"success","content":"他说：\"你好\"，然后离开"}'
        result = _strip_json_envelope(text)
        assert "他说" in result
        assert "你好" in result
        assert '"status"' not in result

    def test_handles_braces_in_string(self):
        """字符串内含未转义花括号不影响平衡计数 (in_string 守卫)"""
        text = '{"status":"success","content":"JSON 示例 {a: 1, b: 2}"}'
        result = _strip_json_envelope(text)
        assert "JSON 示例" in result
        assert "{a: 1, b: 2}" in result

    def test_short_text_preserved(self):
        """过短文本不动 (兜底防误杀)"""
        text = '{"a":1}'
        result = _strip_json_envelope(text)
        # < 20 字符直接返原文
        assert result == text

    def test_incomplete_json_preserved(self):
        """不完整 JSON (括号不平衡) 保留原文"""
        text = '{"status":"success","content":"正文内容"'
        result = _strip_json_envelope(text)
        # depth 不归零 → 不剥
        assert result == text

    def test_invalid_json_preserved(self):
        """语法错误 JSON 保留原文"""
        text = '{"status":"success","content":"正文内容" 坏字符}'
        result = _strip_json_envelope(text)
        # JSON 解析失败 → 保留
        assert result == text

    def test_preserves_leading_whitespace(self):
        """前导空白保留 (用户原始文本可能有缩进)"""
        text = '  \n  {"status":"success","content":"这是完整的正文内容"}'
        result = _strip_json_envelope(text)
        assert "这是完整的正文内容" in result
        assert '"status"' not in result
        # 保留 leading 空白
        assert result.startswith(("  ", "\n"))

    def test_real_case_from_screenshot(self):
        """用户截图中的实际泄露内容"""
        text = '{"status":"success","content":"组里最年轻和最年长的成员分别是？\\n\\n## 最年轻的成员\\n**孟祥琪**（研一）...\\n\\n## 最年长的成员\\n..."}'
        result = _strip_json_envelope(text)
        # envelope 结构消失
        assert '"status"' not in result
        assert '"content"' not in result
        # 真实内容保留
        assert "组里最年轻和最年长的成员分别是？" in result
        assert "## 最年轻的成员" in result
        assert "孟祥琪" in result
        assert "## 最年长的成员" in result