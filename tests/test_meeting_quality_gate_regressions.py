"""质量门禁回归测试 —— 2026-10-30 实测踩到的三个"假失败"。

① **`ai_polish_skipped` 漏传（重跑路径）**
   `MEETING_AI_POLISH_ENABLED=False` 时 transcript_polished 只是原文副本 ⇒
   润色差异必然为 0 ⇒ 质量门禁稳定误报 `polish_no_effective_change` fail
   ⇒ 每场 >5min 的会议 quality_status 被钉死成 fail。
   2026-10-09 的修复只覆盖了原始流水线（`post_meeting_tasks.py`），
   重跑路径（`meeting_reprocessing_service.py`）没跟上 ⇒ 没有任何测试抓到。

② **转录完全没有时间戳时覆盖率"算不出来"（不是 0%）**
   会议 242 的 591 段只有 text+speaker ⇒ 覆盖率被算成 0% ⇒
   稳定误报 `transcript_low_coverage` fail。
   ⇒ 算不出来就**不判覆盖率**，并显式记 `transcript_no_timestamps` warn（可见，不隐藏）。

③ **音频证据必须跨所有 run 找，不能只看最近一次 run**
   会议 250 的证据在原始流水线的 run 57；最近一次 run 73 是重跑 run
   （没有 downloading_audio 阶段）⇒ 只看最近一次 ⇒ 证据丢失
   ⇒ 长空窗被误判"疑似漏抓" fail（人工听辨已确认那段是唱歌，不是漏抓）。
   ⇒ 判据 = **证据在哪个 run 里**，不是"哪个 run 最新"。

本文件是纯函数 + mock 测试，不连 DB。
"""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.meeting_quality_service import evaluate_meeting
from app.services.meeting_reprocessing_service import (
    MeetingReprocessingService,
    ReprocessRequest,
    recover_audio_gap_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- ② 覆盖率


def _seg(text="内容", speaker="王天志", start=None, end=None):
    s = {"speaker": speaker, "text": text}
    if start is not None:
        s["start"] = start
    if end is not None:
        s["end"] = end
    return s


def _meeting(transcript, audio_duration=3600, polished=None):
    return {
        "audio_url": "recordings/x.webm",
        "audio_duration": audio_duration,
        "media_duration_seconds": audio_duration,
        "transcript": transcript,
        "transcript_polished": polished if polished is not None else list(transcript),
        "summary": "摘要",
        "key_points": ["【王天志】要点"],
        "decisions": ["【王天志】决议"],
    }


def test_no_timestamps_does_not_emit_low_coverage_fail():
    """没有任何时间戳 ⇒ 覆盖率算不出来 ⇒ 不能判 fail（这是假失败）。"""
    m = _meeting([_seg(f"第{i}段") for i in range(50)])
    result = evaluate_meeting(m)
    codes = result["issue_codes"]
    assert "transcript_low_coverage" not in codes, "无时间戳时不得报覆盖率不足"
    assert "transcript_no_timestamps" in codes, "必须显式记一条（可见，不隐藏）"
    assert result["metrics"]["transcript_coverage_ratio"] is None
    assert result["metrics"]["transcript_has_timestamps"] is False


def test_no_timestamps_issue_is_warn_not_fail():
    # ai_polish_skipped=True ⇒ 排除润色门禁的干扰, 只看"无时间戳"这一条的影响
    m = _meeting([_seg(f"第{i}段") for i in range(50)])
    m["ai_polish_skipped"] = True
    result = evaluate_meeting(m)
    issue = next(i for i in result["issues"] if i["code"] == "transcript_no_timestamps")
    assert issue["level"] == "warn"
    assert result["status"] != "fail"
    assert [i["level"] for i in result["issues"]] == ["warn"]


def test_real_low_coverage_still_fails():
    """有时间戳但真的只覆盖 17% ⇒ 真低覆盖率 ⇒ 必须仍然 fail（别把真门禁一起放过）。"""
    transcript = [_seg(f"第{i}段", start=i * 1.0, end=i * 1.0 + 0.9) for i in range(60)]
    m = _meeting(transcript, audio_duration=3600)
    result = evaluate_meeting(m)
    assert "transcript_low_coverage" in result["issue_codes"]
    issue = next(i for i in result["issues"] if i["code"] == "transcript_low_coverage")
    assert issue["level"] == "fail"
    assert result["metrics"]["transcript_has_timestamps"] is True


def test_coverage_boundary_at_30_percent_not_flagged():
    """覆盖率恰好 30% ⇒ 不报 fail（阈值边界不含）。"""
    # 10 段 × 3.0s = 30.0s, 媒体时长 100s ⇒ 覆盖率恰好 0.3
    # (3.0 / 100.0 都是二进制精确值, 30.0/100.0 的舍入结果与字面量 0.3 相同)
    transcript = [_seg(f"第{i}段", start=i * 3.0, end=i * 3.0 + 3.0) for i in range(10)]
    m = _meeting(transcript, audio_duration=100)
    result = evaluate_meeting(m)
    assert result["metrics"]["transcript_coverage_ratio"] == 0.3
    assert "transcript_low_coverage" not in result["issue_codes"]


# ---------------------------------------------------------------- ① 润色门禁


def test_ai_polish_skipped_suppresses_polish_false_fail():
    """ai_polish 被配置关掉 ⇒ transcript_polished 是原文副本 ⇒ 不得误报 fail。"""
    # 400 段 × 0.9s ≈ 360s, 媒体时长 360s ⇒ 覆盖率 100% (别让覆盖率门禁来抢戏)
    transcript = [_seg(f"第{i}段", start=i * 1.0, end=i * 1.0 + 0.9) for i in range(400)]
    m = _meeting(transcript, audio_duration=360)
    m["ai_polish_skipped"] = True
    result = evaluate_meeting(m)
    assert "polish_no_effective_change" not in result["issue_codes"]


def test_ai_polish_enabled_zero_change_still_fails():
    """ai_polish 开着但真的 0 段变化 ⇒ 仍要 fail（真门禁不被削弱）。"""
    transcript = [_seg(f"第{i}段", start=i * 1.0, end=i * 1.0 + 0.9) for i in range(400)]
    m = _meeting(transcript, audio_duration=360)
    m["ai_polish_skipped"] = False
    result = evaluate_meeting(m)
    assert "polish_no_effective_change" in result["issue_codes"]


# ------------------------------------------- ③ 音频证据：跨所有 run 找回


def test_recover_gap_evidence_skips_rows_without_evidence():
    """最新的 stage 没有证据时，要继续往更早的 stage 找（不能只看第一行）。"""
    db = MagicMock()
    rows = MagicMock()
    rows.all = MagicMock(return_value=[
        ({},),                                                   # 最新的一行：没有证据
        ({"audio_gap_evidence": {"speech_like_gap_count": 0,
                                 "long_gap_count": 1}},),         # 更早的一行：有证据
    ])
    db.execute = AsyncMock(return_value=rows)
    ev = asyncio.run(recover_audio_gap_evidence(db, 250))
    assert ev["speech_like_gap_count"] == 0
    assert ev["long_gap_count"] == 1


def test_recover_gap_evidence_returns_empty_when_none():
    db = MagicMock()
    rows = MagicMock()
    rows.all = MagicMock(return_value=[({},), ({},)])
    db.execute = AsyncMock(return_value=rows)
    assert asyncio.run(recover_audio_gap_evidence(db, 999)) == {}


# ------------------------------------- 重跑路径真的传了这两个键（结构守卫）


def _module_ast(rel_path):
    return ast.parse((REPO_ROOT / rel_path).read_text(encoding="utf-8"))


def test_reprocess_path_passes_polish_and_gap_evidence():
    """重跑路径的 meeting_dict 必须同时带 ai_polish_skipped 与 audio_gap_evidence。

    这是 2026-10-09 修复漏掉的那一处 —— 没有任何行为测试抓到，
    因为要跑通重跑路径需要真 DB。⇒ 用 AST 守住"这两个键还在"。
    """
    tree = _module_ast("app/services/meeting_reprocessing_service.py")
    dicts_with_polish = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
        if "ai_polish_skipped" in keys:
            dicts_with_polish.append(set(keys))
    assert dicts_with_polish, "重跑路径的 meeting_dict 必须带 ai_polish_skipped"
    assert any("audio_gap_evidence" in ks for ks in dicts_with_polish), \
        "重跑路径的 meeting_dict 必须带 audio_gap_evidence"


def test_reeval_script_uses_shared_gap_evidence_helper():
    """独立脚本必须复用同一个实现（两处各写一遍 ⇒ 迟早漂移）。"""
    tree = _module_ast("scripts/reeval_meeting_quality.py")
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "recover_audio_gap_evidence" in called, \
        "scripts/reeval_meeting_quality.py 必须调用 recover_audio_gap_evidence"


# ----------------------------------------------------- 重跑路径的行为测试


def _reprocess_meeting():
    return SimpleNamespace(
        id=242, title="T", summary="摘要", key_points=["要点"], decisions=["决议"],
        transcript=[_seg(f"第{i}段") for i in range(50)],   # 无时间戳
        transcript_polished=[_seg(f"第{i}段") for i in range(50)],
        speaker_mapping={}, speaker_stats=None, error_reason=None, status="completed",
        audio_url="recordings/x.webm", audio_duration=3600, media_duration_seconds=3600,
        quality_status=None,
    )


@pytest.mark.asyncio
async def test_reprocess_quality_stage_does_not_write_false_fail():
    """走重跑路径（production path）算质量：>5min + 无时间戳 ⇒ 不能写成 fail。"""
    db = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    svc = MeetingReprocessingService(db)
    meeting = _reprocess_meeting()
    run = MagicMock(id=777, metrics={}, overall_status="", finished_at=None,
                    error_summary=None, warning_count=0)

    with patch.object(svc, "get_meeting", AsyncMock(return_value=meeting)), \
         patch.object(svc, "start_reprocess_run", AsyncMock(return_value=(run, False))), \
         patch.object(svc, "snapshot_derived_fields", AsyncMock(return_value={})), \
         patch.object(svc, "_recover_audio_gap_evidence", AsyncMock(return_value={})):
        await svc.execute(ReprocessRequest(
            meeting_id=242, requested_stages=["quality"], force=True))

    issues = (run.metrics or {}).get("quality_issues") or []
    codes = [i.get("code") for i in issues]
    assert "polish_no_effective_change" not in codes, \
        "重跑路径必须传 ai_polish_skipped，否则 >5min 的会议被钉死成 fail"
    assert "transcript_low_coverage" not in codes, \
        "无时间戳时覆盖率算不出来，不得报 fail"
    assert meeting.quality_status != "fail"
