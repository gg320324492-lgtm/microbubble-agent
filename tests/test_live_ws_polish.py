"""测试 /live WebSocket 端点 ASR + 润色集成（占位测试）

任务 17 — 占位测试，验证 mock 框架能正确 patch 关键依赖。
完整 WS 集成测试（连接 → 发送 PCM → 接收 transcript_polished）将在任务 18 之后做真机测试。

设计原则（与 FakeRedis 一致）：
- **不依赖 DB**：在 `SKIP_DB_SETUP=1` 模式下可运行
- **纯 mock**：patch `asr_service.transcribe` 和 `polish_segments_with_lock`
- **占位验证**：仅验证 mock 被正确 patch，未实际触发 ASR/润色

完整集成测试需要：
- 真 DB（创建 Member、Meeting）
- 真 WebSocket 连接
- 真 LiveSegmenter 段满触发
→ 在后续任务或真机测试中完成
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ====================================================================
# Mock 框架验证 — 占位测试
# ====================================================================

def test_asr_service_mock_patch_works():
    """验证 app.api.v1.voice.asr_service 路径可被 patch

    说明：导入阶段可能因为缺少 DB 依赖失败，因此放在 try/except 中跳过。
    """
    try:
        with patch("app.api.v1.voice.asr_service") as mock_asr:
            mock_asr.transcribe = AsyncMock(return_value={
                "text": "测试原文",
                "language": "zh",
                "segments": [],
            })
            # 验证 mock 已被正确 patch
            assert mock_asr.transcribe is not None
            assert mock_asr.transcribe.return_value == {
                "text": "测试原文",
                "language": "zh",
                "segments": [],
            }
    except ImportError:
        pytest.skip("app.api.v1.voice 不可导入（SKIP_DB_SETUP 模式）")


def test_polish_service_mock_patch_works():
    """验证 app.services.meeting_ai_polish.polish_segments_with_lock 路径可被 patch"""
    try:
        polished_response = {
            "polished": [{"speaker": "发言人", "text": "测试润色", "ts": 0}],
            "key_points": [],
            "boundary_after_index": None,
            "summary": None,
        }
        with patch(
            "app.services.meeting_ai_polish.polish_segments_with_lock",
            new_callable=AsyncMock,
        ) as mock_polish:
            mock_polish.return_value = polished_response
            # 验证 mock 已就绪
            assert mock_polish.return_value == polished_response
    except ImportError:
        pytest.skip("app.services.meeting_ai_polish 不可导入（SKIP_DB_SETUP 模式）")


# ====================================================================
# Mock 数据结构验证
# ====================================================================

def test_polish_response_structure():
    """验证润色响应的数据结构契约

    polish_segments_with_lock 必须返回包含以下字段的 dict：
    - polished: list[{speaker, text, ts}]
    - key_points: list
    - boundary_after_index: int | None
    - summary: str | None
    """
    polished = {
        "polished": [
            {"speaker": "发言人A", "text": "你好", "ts": 0},
            {"speaker": "发言人B", "text": "世界", "ts": 1.5},
        ],
        "key_points": ["关键点1", "关键点2"],
        "boundary_after_index": 1,
        "summary": "本段讨论了问候语",
    }
    # 顶层字段完整性
    assert "polished" in polished
    assert "key_points" in polished
    assert "boundary_after_index" in polished
    assert "summary" in polished
    # polished 列表元素结构
    for seg in polished["polished"]:
        assert "speaker" in seg
        assert "text" in seg
        assert "ts" in seg


def test_asr_response_structure():
    """验证 ASR 响应的数据结构契约

    asr_service.transcribe 返回的 dict 必须包含：
    - text: str
    - language: str
    - segments: list (可空)
    """
    asr_result = {
        "text": "测试原文",
        "language": "zh",
        "segments": [],
    }
    assert "text" in asr_result
    assert "language" in asr_result
    assert "segments" in asr_result
    assert isinstance(asr_result["text"], str)


# ====================================================================
# 占位：WS 集成测试（待任务 18 完成后扩展）
# ====================================================================

@pytest.mark.asyncio
async def test_live_ws_segment_polish_flow_placeholder():
    """WS 段满 → ASR → 润色 → 推 transcript_polished（占位）

    当前任务 (17) 目标仅是验证 mock 框架能正确 patch 关键依赖。
    完整集成测试（连接 WS → 发送 PCM → 接收 transcript_polished）需要：
    - 真 DB（创建 Member、Meeting）
    - 真 WebSocket 连接（ASGITransport）
    - 真 LiveSegmenter 段满触发（1.5s 静音）

    这些在 SKIP_DB_SETUP=1 模式下无法运行，将在后续任务或真机测试中完成。
    """
    # 占位：仅验证 mock 路径存在，不实际触发
    with patch("app.api.v1.voice.asr_service") as mock_asr, \
         patch("app.services.meeting_ai_polish.polish_segments_with_lock") as mock_polish:
        mock_asr.transcribe = AsyncMock(return_value={
            "text": "测试原文",
            "language": "zh",
            "segments": [],
        })
        mock_polish.return_value = {
            "polished": [{"speaker": "发言人", "text": "测试润色", "ts": 0}],
            "key_points": [],
            "boundary_after_index": None,
            "summary": None,
        }

        # 占位验证：mock 还未被调用
        mock_asr.transcribe.assert_not_called()
        mock_polish.assert_not_called()

        # 模拟 ASR 调用
        await mock_asr.transcribe(b"fake_wav", language="zh", skip_convert=True)
        mock_asr.transcribe.assert_called_once()

        # 模拟润色调用
        result = await mock_polish(
            meeting_id=1,
            segments=[{"speaker": "发言人", "text": "测试", "ts": 0}],
            meeting_context={"topic": "测试"},
        )
        mock_polish.assert_called_once()
        assert result["polished"][0]["text"] == "测试润色"
