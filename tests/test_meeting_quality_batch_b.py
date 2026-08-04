"""Batch B 回归测试 — 持久化阶段记录 + 质量评估器

覆盖:
- meeting_quality_service 评估逻辑 (会议 242 fixture)
- sanitize_text 清洗 SenseVoice 控制 token
- 各种硬门禁: transcript_empty / control_token_leak / unknown_speaker_high
- processing_log service 基础读写
"""

import pytest

from app.services.meeting_quality_service import (
    MeetingQualityEvaluator,
    evaluate_meeting,
    sanitize_text,
)


def _make_segment(text, speaker="韩重阳", start=0.0, end=1.0):
    return {"speaker": speaker, "text": text, "start": start, "end": end}


def _meeting_242_fixture():
    """会议 242 真实分布 fixture: 591 段 + 236 段 EMO + 30% unknown + 354s gap.

    unknown_speaker 比例被调到 > 40% 以触发 warn 门禁, 因为 Polished 部分与 raw
    几乎一致, 0 真实润色会触发 fail; 但 unknown 真实分布 27.9% 也应该警告,
    测试用扩大的 fixture 模拟 "unknown 超过 warn 阈值" 的更糟情况."""
    transcript = []
    for i in range(140):
        transcript.append(_make_segment(f"韩重阳段{i}", speaker="韩重阳", start=i * 5.0, end=i * 5.0 + 4.0))
    transcript.append(_make_segment("<|EMO_UNKNOWN|>嗯。", speaker="发言人?", start=836.0, end=836.4))
    transcript.append(_make_segment("<|EMO_UNKNOWN|>嗯。", speaker="发言人?", start=1190.5, end=1190.9))
    transcript.append(_make_segment("<|EMO_UNKNOWN|>对吧。", speaker="发言人?", start=1282.5, end=1282.9))
    for i in range(150):
        transcript.append(_make_segment(f"宋洋段{i}", speaker="宋洋", start=1283 + i * 2.5, end=1283 + i * 2.5 + 2.0))
    for i in range(180):  # 扩到 180 段发言人? 触发 > 40% unknown warn
        transcript.append(_make_segment("<|EMO_UNKNOWN|>嗯。", speaker="发言人?", start=1700 + i, end=1700 + i + 0.3))
    for i in range(120):  # 加上发言人B
        transcript.append(_make_segment(f"发言人B段{i}", speaker="发言人B", start=1880 + i, end=1880 + i + 0.4))

    return {
        "audio_url": "recordings/x.webm",
        "audio_duration": 2111,
        "media_duration_seconds": 2025,
        "transcript": transcript,
        "transcript_polished": [{"speaker": s["speaker"], "text": s["text"], "ts": s["start"]} for s in transcript],
        "summary": None,
        "key_points": [],
        "decisions": [],
    }


def test_sanitize_text_strips_control_tokens():
    assert sanitize_text("hello <|EMO_UNKNOWN|>world") == "hello world"
    assert sanitize_text("<|NEUTRAL|>嗯。") == "嗯。"
    assert sanitize_text("<|Speech|>a <|EMO_UNKNOWN|>b") == "a b"
    assert sanitize_text("") == ""
    assert sanitize_text(None) == ""


def test_sanitize_text_handles_chinese_and_punct():
    assert sanitize_text("<|EMO_UNKNOWN|>对吧。") == "对吧。"
    assert "。" in sanitize_text("<|EMO_UNKNOWN|>嗯。")


def test_quality_evaluator_detects_control_token_leak_fail():
    m = _meeting_242_fixture()
    result = evaluate_meeting(m)
    assert any(i["code"] == "control_token_leak" for i in result["issues"])
    leak_issue = next(i for i in result["issues"] if i["code"] == "control_token_leak")
    assert leak_issue["level"] == "fail"
    assert result["metrics"]["control_token_leak_segments"] > 0


def test_quality_evaluator_detects_long_gap_fail():
    m = _meeting_242_fixture()
    result = evaluate_meeting(m)
    gap_issues = [i for i in result["issues"] if i["code"] == "transcript_long_gap"]
    assert gap_issues, "354s gap 必须触发告警"
    assert gap_issues[0]["level"] == "fail"
    assert result["metrics"]["transcript_max_gap_sec"] > 300


def test_quality_evaluator_detects_unknown_speaker_warn_or_fail():
    m = _meeting_242_fixture()
    result = evaluate_meeting(m)
    assert any(i["code"] == "unknown_speaker_high" for i in result["issues"])
    assert result["metrics"]["unknown_speaker_ratio"] > 0.40


def test_quality_evaluator_detects_minutes_empty():
    m = _meeting_242_fixture()
    result = evaluate_meeting(m)
    assert any(i["code"] == "minutes_empty" for i in result["issues"])
    minutes_issue = next(i for i in result["issues"] if i["code"] == "minutes_empty")
    assert minutes_issue["level"] == "fail"


def test_quality_evaluator_audio_drift_warn():
    m = _meeting_242_fixture()
    result = evaluate_meeting(m)
    drift = result["metrics"].get("audio_drift_ratio")
    # 2111 vs 2025 -> 4.1% < 5%, 不应触发
    assert drift is None or drift < 0.05


def test_quality_evaluator_clean_meeting_passes():
    m = {
        "audio_url": "ok",
        "audio_duration": 600,
        "media_duration_seconds": 600,
        "transcript": [
            _make_segment("大家好", "张三", t * 10, t * 10 + 4) if t % 2 == 0 else _make_segment("同意", "李四", t * 10, t * 10 + 4)
            for t in range(60)
        ],
        "transcript_polished": [
            {"speaker": "张三", "text": "大家好, 我们开始吧。", "ts": t * 10} if t % 2 == 0 else {"speaker": "李四", "text": "同意。", "ts": t * 10}
            for t in range(60)
        ],
        "summary": "围绕实验展开讨论, 达成多项共识",
        "key_points": ["【张三】提出实验方案", "【李四】补充细节"],
        "decisions": ["【全组决定】下周开始实验"],
    }
    result = evaluate_meeting(m)
    assert result["status"] == "pass", f"issues={result['issues']}"
    assert result["issues"] == []


def test_quality_evaluator_empty_transcript_fails():
    m = {"audio_url": "x", "transcript": [], "transcript_polished": []}
    result = evaluate_meeting(m)
    assert any(i["code"] == "transcript_empty" for i in result["issues"])
    fail_issue = next(i for i in result["issues"] if i["code"] == "transcript_empty")
    assert fail_issue["level"] == "fail"


def test_quality_evaluator_non_monotonic_fails():
    m = {
        "audio_url": "x",
        "transcript": [
            _make_segment("a", "张三", 10, 12),
            _make_segment("b", "李四", 5, 7),  # 时间戳回退
        ],
        "transcript_polished": [],
    }
    result = evaluate_meeting(m)
    assert any(i["code"] == "transcript_non_monotonic" for i in result["issues"])


def test_quality_evaluator_polish_no_real_change_warns():
    """长会议 (media > 300s) 但润色实际 0 段差异 -> fail (会议 242 真实场景)"""
    m = {
        "audio_url": "x",
        "audio_duration": 2100,
        "media_duration_seconds": 2025,
        "transcript": [_make_segment(f"text {i}", "张三", i * 2.0, i * 2.0 + 1.5) for i in range(500)],
        "transcript_polished": [{"speaker": "张三", "text": f"text {i}", "ts": i * 2.0} for i in range(500)],
        "summary": "ok",
        "key_points": ["要点1"],
        "decisions": ["决议1"],
    }
    result = evaluate_meeting(m)
    polish_issues = [i for i in result["issues"] if i["code"] == "polish_no_effective_change"]
    assert polish_issues, "会议 242 真实场景: 0 段变化必须触发告警"
    assert polish_issues[0]["level"] == "fail"


def test_quality_evaluator_returns_status_codes_list():
    m = _meeting_242_fixture()
    result = evaluate_meeting(m)
    assert "issue_codes" in result
    assert isinstance(result["issue_codes"], list)
    assert all(isinstance(c, str) for c in result["issue_codes"])