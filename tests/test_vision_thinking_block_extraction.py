"""VisionService._analyze_direct 取块逻辑回归测试 (2026-10-09, agent19)

背景事故
--------
切 `VISION_MODEL` 到带思维链的模型（`MiniMax-M3.1-Flash-Preview`）时，
`app/services/vision_service.py::_analyze_direct` 取的是 `response.content[0]`。
思维链模型在 Anthropic 端点返回的是**多块**：

    content[0] = ThinkingBlock(thinking="We need inspect image...", signature="...")
    content[1] = TextBlock(text="绿色")

旧写法命中 thinking 块 → 既无 `.text` 又非 dict → 走 `str(content_block)` 分支，
把 `ThinkingBlock(thinking='...', signature='...')` 的 repr 当成图片描述返回，
**思维链直接写进 ocr_text / visual_summary**，污染全部 OCR 结果。

本测试锁定修复后的行为：
- thinking 块 + text 块并存 → 必须返回 text 块内容，绝不返回 thinking
- 纯 text 块（旧行为）→ 返回值不变
- 只有 thinking 块 → 回退 thinking（对齐 app/core/llm.py::extract_text_from_response）
- dict 形态（代理端点常返回裸 dict）与 SDK 对象形态都要覆盖

变异测试（见文件末注释）：把取块逻辑退回 `response.content[0]`，下列
*thinking-first* 用例会红。
"""
import os

import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# Mock 响应构造：SDK 对象形态 + 裸 dict 形态
# ============================================================================


def _sdk_thinking(text, signature="2645d05a"):
    """Anthropic SDK ThinkingBlock 对象形态"""
    return SimpleNamespace(type="thinking", thinking=text, signature=signature)


def _sdk_text(text):
    """Anthropic SDK TextBlock 对象形态"""
    return SimpleNamespace(type="text", text=text)


def _make_response(blocks):
    return SimpleNamespace(content=blocks)


async def _run_analyze_direct(blocks):
    """跑 _analyze_direct，patch 掉 client，返回解析出的字符串"""
    from app.services import vision_service as vs

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_response(blocks))

    with patch.object(vs, "get_anthropic_client", return_value=client):
        with patch.object(vs, "get_default_model", return_value="test-model"):
            return await vs.vision_service._analyze_direct(
                b"\x89PNG\r\n\x1a\nfake", "ZmFrZQ==", "image/png", "描述这张图"
            )


# ============================================================================
# 1. 核心回归：thinking 在前、text 在后 → 必须取 text（本次修复的主 bug）
# ============================================================================


class TestThinkingFirstReturnsText:
    async def test_sdk_thinking_then_text(self):
        blocks = [
            _sdk_thinking("We need inspect image. The user asks for color."),
            _sdk_text("绿色"),
        ]
        result = await _run_analyze_direct(blocks)
        assert result == "绿色"
        # 反向断言：思维链任何片段都不得出现在返回值里
        assert "We need inspect image" not in result
        assert "ThinkingBlock" not in result
        assert "signature" not in result

    async def test_dict_thinking_then_text(self):
        """代理端点返回裸 dict 的形态"""
        blocks = [
            {"type": "thinking", "thinking": "We need inspect image.", "signature": "2645d05a"},
            {"type": "text", "text": "绿色"},
        ]
        result = await _run_analyze_direct(blocks)
        assert result == "绿色"
        assert "We need inspect image" not in result

    async def test_multiple_text_blocks_concatenated(self):
        """多个 text 块应拼接（长 OCR 输出常被模型切成多块）"""
        blocks = [
            _sdk_thinking("reasoning..."),
            _sdk_text("第一段"),
            _sdk_text("第二段"),
        ]
        result = await _run_analyze_direct(blocks)
        assert result == "第一段第二段"

    async def test_thinking_before_and_after_text(self):
        """thinking 夹在 text 中间也不能被返回"""
        blocks = [
            _sdk_thinking("思考开始"),
            _sdk_text("正文"),
            _sdk_thinking("思考结束"),
        ]
        result = await _run_analyze_direct(blocks)
        assert result == "正文"
        assert "思考" not in result


# ============================================================================
# 2. 旧行为不变：纯 text 块（thinking:disabled 的普通模型）
# ============================================================================


class TestPlainTextUnchanged:
    async def test_single_text_block_sdk(self):
        result = await _run_analyze_direct([_sdk_text("一张蓝色管道的照片")])
        assert result == "一张蓝色管道的照片"

    async def test_single_text_block_dict(self):
        result = await _run_analyze_direct([{"type": "text", "text": "一张蓝色管道的照片"}])
        assert result == "一张蓝色管道的照片"

    async def test_empty_content_returns_placeholder(self):
        """空 content 保持原有占位文案"""
        result = await _run_analyze_direct([])
        assert result == "无法解析图片分析结果"


# ============================================================================
# 3. 只有 thinking 块 → 回退 thinking（对齐 extract_text_from_response）
# ============================================================================


class TestThinkingOnlyFallback:
    async def test_sdk_thinking_only(self):
        result = await _run_analyze_direct([_sdk_thinking("这张图是一张管道照片")])
        assert result == "这张图是一张管道照片"

    async def test_dict_thinking_only(self):
        result = await _run_analyze_direct(
            [{"type": "thinking", "thinking": "这张图是一张管道照片", "signature": "abc"}]
        )
        assert result == "这张图是一张管道照片"

    async def test_empty_text_blocks_fall_back_to_thinking(self):
        """text 块存在但全是空白串 → 仍回退 thinking"""
        blocks = [_sdk_thinking("有效内容"), _sdk_text("   ")]
        result = await _run_analyze_direct(blocks)
        assert result == "有效内容"


# ============================================================================
# 4. 无任何可提取内容的块 → 退回原 repr（不抛异常）
# ============================================================================


class TestUnusableBlocksFallbackToRepr:
    async def test_opaque_block_returns_repr(self):
        """既无 text 又无 thinking 的块：保持旧的 repr 兜底，不崩"""
        blocks = [SimpleNamespace(type="redacted_thinking", data="xxx")]
        result = await _run_analyze_direct(blocks)
        assert "redacted_thinking" in result


# ============================================================================
# 变异测试（人工执行，勿提交改动）
# ============================================================================
#
# 把 app/services/vision_service.py 里的取块段落临时替换为旧写法：
#
#     if response.content and len(response.content) > 0:
#         content_block = response.content[0]
#         if hasattr(content_block, 'text'):
#             return content_block.text
#         elif isinstance(content_block, dict) and 'text' in content_block:
#             return content_block['text']
#         else:
#             return str(content_block)
#
# 预期变红的用例（实测 7 failed / 4 passed）：
#   TestThinkingFirstReturnsText::test_sdk_thinking_then_text
#   TestThinkingFirstReturnsText::test_dict_thinking_then_text
#   TestThinkingFirstReturnsText::test_multiple_text_blocks_concatenated
#   TestThinkingFirstReturnsText::test_thinking_before_and_after_text
#   TestThinkingOnlyFallback::test_sdk_thinking_only
#   TestThinkingOnlyFallback::test_dict_thinking_only
#   TestThinkingOnlyFallback::test_empty_text_blocks_fall_back_to_thinking
# （thinking-only 也红是**预期的更强证明**：旧写法连"只有 thinking 块"都对不了，
#   因为它既不看 thinking 属性又落到 str() repr 上。）
#
# 不应变红的 4 个（回归护栏，证明测试没有一刀切，见实跑输出）：
#   TestPlainTextUnchanged::test_single_text_block_sdk
#   TestPlainTextUnchanged::test_single_text_block_dict
#   TestPlainTextUnchanged::test_empty_content_returns_placeholder
#   TestUnusableBlocksFallbackToRepr::test_opaque_block_returns_repr
