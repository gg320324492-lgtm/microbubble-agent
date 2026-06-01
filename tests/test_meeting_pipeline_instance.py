"""测试 MeetingPipeline 接受注入依赖（不依赖全局单例）

Wave 2a 任务 4：验证 MeetingPipeline 构造函数支持依赖注入。
使用 MagicMock 完全避开真实模型（VAD/ASR/Voiceprint）调用。
"""

import asyncio
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.voice.pipeline import MeetingPipeline


@pytest.mark.asyncio
async def test_pipeline_uses_injected_vad():
    """验证 MeetingPipeline 接受注入的 VADEngine（不依赖全局单例）"""
    mock_vad = MagicMock()
    mock_vad.process_chunk = MagicMock(return_value=None)  # 无语音

    mock_asr = MagicMock()
    mock_asr.transcribe = AsyncMock(return_value={"text": ""})

    mock_vp = MagicMock()
    mock_vp.identify_speaker = AsyncMock(return_value=(None, None, 0.0))

    pipeline = MeetingPipeline(
        vad_engine=mock_vad,
        asr_service=mock_asr,
        voiceprint_service=mock_vp,
    )

    db = MagicMock()
    result = await pipeline.process_audio(b"\x00\x00" * 32000, db, elapsed=1.0)

    # VAD 被调用（注入的，不是全局的）
    mock_vad.process_chunk.assert_called()
    # 无语音 → 返回空 list
    assert result == []


@pytest.mark.asyncio
async def test_pipeline_returns_transcript_with_speaker():
    """完整流程：VAD 说话 → ASR 转录 → Voiceprint 识别 → 返回 entry"""
    mock_vad = MagicMock()
    mock_vad.process_chunk = MagicMock(return_value=np.random.uniform(-0.5, 0.5, 16000).astype(np.float32))

    mock_asr = MagicMock()
    mock_asr.transcribe = AsyncMock(return_value={"text": "你好世界"})

    mock_vp = MagicMock()
    mock_vp.identify_speaker = AsyncMock(return_value=("张三", 5, 0.85))

    pipeline = MeetingPipeline(
        vad_engine=mock_vad,
        asr_service=mock_asr,
        voiceprint_service=mock_vp,
    )

    db = MagicMock()
    result = await pipeline.process_audio(b"\x00\x00" * 32000, db, elapsed=2.0)

    assert len(result) == 1
    assert result[0]["speaker"] == "张三"
    assert result[0]["member_id"] == 5
    assert result[0]["confidence"] == 0.85
    assert result[0]["text"] == "你好世界"
