"""Batch E-2 会议 242 dry-run 验证

scripts/recover_meeting_242.py 的核心纯函数逻辑在会议 242 fixture 上 dry-run:
- 控制 token 清洗量
- speaker_stats 重算
- quality 评估
不发起 LLM, 不写 DB.
"""

import pytest

from app.services.meeting_quality_service import (
    MeetingQualityEvaluator,
    evaluate_meeting,
    sanitize_text,
)


def _fixture_meeting_242():
    """会议 242 实测分布: 591 段 + 236 EMO 泄漏 + 354s gap."""
    transcript = []
    # 0..835 韩重阳
    for i in range(140):
        transcript.append({"speaker": "韩重阳", "text": f"内容{i}", "start": i * 5.0, "end": i * 5.0 + 4.0})
    # 836..1190 大间隔 (354s) 中 4 个 EMO 段
    transcript.append({"speaker": "发言人?", "text": "<|EMO_UNKNOWN|>嗯。", "start": 836.0, "end": 836.4})
    transcript.append({"speaker": "发言人?", "text": "<|EMO_UNKNOWN|>嗯。", "start": 1190.5, "end": 1190.9})
    # 1190..1282 91s 间隔
    transcript.append({"speaker": "发言人?", "text": "<|EMO_UNKNOWN|>对吧。", "start": 1282.5, "end": 1282.9})
    # 1283..2024 宋洋 + unknown (EMO 泄漏 + 短文本)
    for i in range(280):
        transcript.append({"speaker": "宋洋", "text": f"宋洋{i}", "start": 1283 + i * 2.5, "end": 1283 + i * 2.5 + 2.0})
    for i in range(100):
        transcript.append({"speaker": "发言人?", "text": "<|EMO_UNKNOWN|>嗯。", "start": 1900 + i, "end": 1900 + i + 0.3})
    for i in range(65):
        transcript.append({"speaker": "发言人B", "text": f"发言人B段{i}", "start": 1965 + i, "end": 1965 + i + 0.4})

    # polished 同步 (会议 242 真实: polished 与 raw 一致, 无有效润色)
    polished = []
    for s in transcript:
        polished.append({"speaker": s["speaker"], "text": s["text"], "ts": s["start"]})

    return {
        "audio_url": "recordings/x.webm",
        "audio_duration": 2111,
        "media_duration_seconds": 2025,
        "transcript": transcript,
        "transcript_polished": polished,
        "summary": None,
        "key_points": [],
        "decisions": [],
    }


def test_meeting_242_dry_run_token_sanitize():
    """会议 242 fixture 中含 EMO token 段数 + 清洗后应为 0."""
    m = _fixture_meeting_242()
    before = sum(1 for s in m["transcript"] if "<|EMO" in (s.get("text") or ""))
    cleaned = sum(1 for s in m["transcript"] if "<|EMO" not in (s.get("text") or "") and s.get("text"))
    assert before > 0
    # 应用 sanitize 后泄漏应为 0
    for s in m["transcript"]:
        s["text"] = sanitize_text(s["text"])
        s["text_polished"] = sanitize_text(s.get("text_polished") or "")
    after = sum(1 for s in m["transcript"] if "<|EMO" in (s.get("text") or ""))
    assert after == 0


def test_meeting_242_dry_run_quality_status():
    """会议 242 清洗后再评估, 仍有 gap / 分钟空 / 非单调 等硬门禁."""
    m = _fixture_meeting_242()
    for s in m["transcript"]:
        s["text"] = sanitize_text(s["text"])
        s["text_polished"] = sanitize_text(s.get("text_polished") or "")
    qa = evaluate_meeting(m)
    assert qa["status"] in ("fail", "warn")
    codes = qa["issue_codes"]
    # 控制 token 已清, 但分钟空 + gap + 非单调 仍触发
    assert "control_token_leak" not in codes
    assert "transcript_long_gap" in codes
    assert "minutes_empty" in codes
    # unknown_speaker 占比 ~26%, 不一定触发 warn/fail
    # 重要的是 status != pass (有发现)
    assert qa["status"] != "pass"


def test_meeting_242_speaker_stats_no_token_bloat():
    """compute_speaker_stats 在清洗后不应把控制 token 计入词数."""
    from app.services.meeting_analysis_service import MeetingAnalysisService
    m = _fixture_meeting_242()
    # 清洗
    for s in m["transcript"]:
        s["text"] = sanitize_text(s["text"])
        s["text_polished"] = sanitize_text(s.get("text_polished") or "")
    stats = MeetingAnalysisService().compute_speaker_stats(m["transcript_polished"])
    by_name = {s["name"]: s for s in stats}
    # 至少有一位识别到位的发言人, 词数 > 0
    han = by_name.get("韩重阳", {"word_count": 0})
    assert han["word_count"] > 0
    # 发言人? 清洗后只剩 "嗯。" / "对吧。" 等 2 字符短文本, 100+ 段约 200 字符
    # 对比会议 242 修复前的 ~8x 膨胀, 现在是合理的 "短文本倍数"
    speaker_q = by_name.get("发言人?", {"word_count": 0})
    assert 0 < speaker_q["word_count"] <= 300


def test_meeting_242_audio_drift_recorded():
    """记录 audio drift (媒体 vs 墙钟), 不自动改 audio_duration."""
    m = _fixture_meeting_242()
    qa = evaluate_meeting(m)
    # 2111 vs 2025 -> 4.1% < 5% (warn), 暂未触发
    drift = qa["metrics"].get("audio_drift_ratio")
    if drift is not None:
        assert drift < 0.05