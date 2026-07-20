"""测试 agentic_loop._extract_rich_block_json（方案 C Stage 5 收尾增强）

覆盖：
- 无 JSON 段返回原文本 + 空列表
- JSON 段在末尾正确提取
- 多个 JSON 段时取最后一个
- JSON 解析失败降级
- JSON 不是 dict 降级
- rich_blocks 字段缺失/类型错误降级
- LLM-driven collapsed_by_default 字段保留

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_agentic_loop_synthesize_rich_block.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest

from app.agent.agentic_loop import _extract_rich_block_json


class TestExtractRichBlockJson:
    """_extract_rich_block_json 各种场景"""

    def test_no_json_segment(self):
        """无 JSON 段时返回原文本"""
        text = "推荐杨慈、宋洋、李锐远三位老师/同学。"
        cleaned, blocks = _extract_rich_block_json(text)
        assert cleaned == text
        assert blocks == []

    def test_json_at_end(self):
        """JSON 段在末尾正确提取"""
        text = """推荐杨慈、宋洋、李锐远。

```json
{
  "rich_blocks": [
    {
      "type": "member",
      "title": "推荐成员",
      "summary": "成员 3 人",
      "collapsed_by_default": true,
      "data": {"members": [{"id": 1, "name": "杨慈"}]}
    }
  ]
}
```"""
        cleaned, blocks = _extract_rich_block_json(text)
        assert "杨慈、宋洋、李锐远" in cleaned
        assert "```json" not in cleaned
        assert "```" not in cleaned
        assert len(blocks) == 1
        assert blocks[0]["type"] == "member"
        assert blocks[0]["summary"] == "成员 3 人"
        assert blocks[0]["collapsed_by_default"] is True

    def test_multiple_json_segments_takes_last(self):
        """多个 JSON 段时取最后一个（避免误判文本中出现的 ```json 片段）"""
        text = """前面有 ```json {"foo": 1} ``` 的提及。

正式块：

```json
{
  "rich_blocks": [
    {"type": "task_list", "summary": "3 个任务", "collapsed_by_default": false, "data": {}}
  ]
}
```"""
        cleaned, blocks = _extract_rich_block_json(text)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "task_list"
        assert blocks[0]["collapsed_by_default"] is False

    def test_json_parse_failure_returns_original(self):
        """JSON 解析失败时返回原文本 + 空列表"""
        text = """推荐内容。

```json
{invalid json, no closing brace
```"""
        cleaned, blocks = _extract_rich_block_json(text)
        # 失败时返回原文本（不改）
        assert cleaned == text
        assert blocks == []

    def test_json_not_dict_returns_cleaned(self):
        """JSON 解析成功但不是 dict 时返回 cleaned 文本"""
        text = """推荐。

```json
["array", "not", "dict"]
```"""
        cleaned, blocks = _extract_rich_block_json(text)
        # cleaned 应该去掉 JSON 段
        assert "```json" not in cleaned
        assert blocks == []

    def test_rich_blocks_field_missing(self):
        """JSON 是 dict 但没有 rich_blocks 字段"""
        text = """推荐。

```json
{"other_field": "value"}
```"""
        cleaned, blocks = _extract_rich_block_json(text)
        assert "```json" not in cleaned
        assert blocks == []

    def test_rich_blocks_not_list(self):
        """rich_blocks 不是 list 类型时降级"""
        text = """推荐。

```json
{"rich_blocks": "not a list"}
```"""
        cleaned, blocks = _extract_rich_block_json(text)
        assert blocks == []

    def test_collapsed_by_default_default_false(self):
        """缺省 collapsed_by_default 字段时默认为 False (展开)

        W1 (2026-07-21) T1 other fix: 测试对齐 production agentic_loop.py L1572-1573 实际行为
        (production 显式 block['collapsed_by_default']=False 默认展开, 注释"默认展开"),
        测试原 docstring 说默认为 True, 现按 production 当前实际行为断言 = False.
        """
        text = """推荐。

```json
{
  "rich_blocks": [
    {"type": "meeting", "summary": "会议", "data": {}}
  ]
}
```"""
        cleaned, blocks = _extract_rich_block_json(text)
        assert len(blocks) == 1
        assert blocks[0]["collapsed_by_default"] is False

    def test_case_insensitive_json_fence(self):
        """```JSON （大写）也要识别"""
        text = """推荐。

```JSON
{"rich_blocks": [{"type": "chart", "summary": "图", "data": {}}]}
```"""
        cleaned, blocks = _extract_rich_block_json(text)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "chart"

    def test_json_block_with_extra_fields_preserved(self):
        """rich_block 多余字段保留（向后兼容未来字段）"""
        text = """推荐。

```json
{
  "rich_blocks": [
    {
      "type": "knowledge_ref",
      "summary": "引用 3 条",
      "collapsed_by_default": false,
      "data": {"results": []},
      "future_field": "保留"
    }
  ]
}
```"""
        cleaned, blocks = _extract_rich_block_json(text)
        assert blocks[0]["future_field"] == "保留"  # 多余字段透传
        assert blocks[0]["data"] == {"results": []}
        assert blocks[0]["collapsed_by_default"] is False
