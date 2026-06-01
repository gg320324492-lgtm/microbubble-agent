"""测试 /live WS per-WS pipeline 构造

验证 /live 端点可以为每个 WS 连接构造独立的 MeetingPipeline 实例，
避免 VAD 共享状态污染（第二波 wave 2a 任务 5）。
"""

import pytest
from unittest.mock import MagicMock


def test_pipeline_can_be_constructed_for_ws():
    """验证 /live 端点可以构造 per-WS MeetingPipeline 实例"""
    from app.voice.vad import VADEngine
    from app.voice.pipeline import MeetingPipeline

    vad = VADEngine()
    pipeline = MeetingPipeline(
        vad_engine=vad,
        asr_service=MagicMock(),
        voiceprint_service=MagicMock(),
    )

    # 验证 VAD 是注入的实例（不是 module-level 单例）
    assert pipeline.vad is vad
    # 验证与 get_vad_engine() 工厂不同对象（per-instance）
    from app.voice.vad import get_vad_engine
    default_vad = get_vad_engine()
    assert pipeline.vad is not default_vad


def test_two_pipelines_have_independent_vad():
    """验证两次构造的 pipeline 各自拥有独立的 VAD（互不影响）"""
    from app.voice.vad import VADEngine
    from app.voice.pipeline import MeetingPipeline

    vad1 = VADEngine()
    vad2 = VADEngine()

    p1 = MeetingPipeline(vad_engine=vad1, asr_service=MagicMock(), voiceprint_service=MagicMock())
    p2 = MeetingPipeline(vad_engine=vad2, asr_service=MagicMock(), voiceprint_service=MagicMock())

    assert p1.vad is not p2.vad
    assert p1.vad is vad1
    assert p2.vad is vad2
    assert vad1 is not vad2


def test_pipeline_uses_injected_asr_and_voiceprint():
    """验证 ASR / 声纹服务被注入而非默认"""
    from app.voice.vad import VADEngine
    from app.voice.pipeline import MeetingPipeline

    asr_mock = MagicMock(name="custom_asr")
    vp_mock = MagicMock(name="custom_vp")

    p = MeetingPipeline(
        vad_engine=VADEngine(),
        asr_service=asr_mock,
        voiceprint_service=vp_mock,
    )

    assert p.asr is asr_mock
    assert p.vp is vp_mock
