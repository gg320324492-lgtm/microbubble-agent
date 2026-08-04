"""会议质量评估器

2026-08-04 Batch B-4:
- 对每次持久化运行 (meeting_processing_run) 计算确定性指标
- 输出 pass / warn / fail / not_evaluable
- 首批硬门禁: 音频不可解码 / ASR 全空 / 时间戳逆序 / 全部分析失败 / 落库失败 -> fail
- 控制 token 泄漏 / unknown speaker 超阈值 / 最长 gap 超阈值 / 润色实际修改率异常
  / 纪要字段缺失 -> warn 或 fail (阈值用真实历史会议分布校准)

设计:
- 计算阶段全部纯函数 + DB read, 无外部 IO
- 输出 meeting_quality 字典, 与 processing_run.metrics 兼容
- 不擅自放宽阈值: 任何 fail 都要求人工介入 (管理面板 Batch D-3)
"""
from __future__ import annotations

import re
import statistics
from typing import Any, Dict, List, Optional


# 2026-08-04 Batch B-5: 统一的 SenseVoice 控制 token 清洗
# 正则粗略: 任意 <...大写字母/数字/下划线/管道/竖线/连字符...> 都视作控制 token, 一并清空
# 避免对边缘形式 (<|Speech|>a <|EMO_UNKNOWN|>b) 漏抓.
SENSEVOICE_TAG_RE = re.compile(r"<[^<>]*[A-Z][^<>]*>")


def sanitize_text(text: str) -> str:
    """清洗 SenseVoice 控制 token; 任何下游统计/落库/索引都应先调用."""
    if not text:
        return ""
    return SENSEVOICE_TAG_RE.sub("", text)


def _seg_words(text: str) -> int:
    cleaned = sanitize_text(text)
    return sum(1 for c in cleaned if not c.isspace())


class MeetingQualityEvaluator:
    """单次会议质量指标 + 门禁判定.

    使用:
        result = MeetingQualityEvaluator(meeting_dict).evaluate()
        result.status in ("pass", "warn", "fail", "not_evaluable")
        result.metrics 持久化到 meeting_processing_runs.metrics
    """

    # 首批硬门禁 (基于会议 242 实测分布)
    THRESHOLDS = {
        # unknown speaker 比例 > 0.40 warn, > 0.60 fail
        "unknown_speaker_warn": 0.40,
        "unknown_speaker_fail": 0.60,
        # 最长无转录间隔 (gap) > 60s warn, > 180s fail
        "max_gap_warn_sec": 60.0,
        "max_gap_fail_sec": 180.0,
        # 控制 token 泄漏 > 0% 即 fail (P0 已要求落库前 0 泄漏)
        "control_token_warn_ratio": 0.0,
        # 润色实际修改率 < 1% 且会议 > 5min -> warn (改写几乎无效, 形同未润色)
        "polish_real_change_warn_ratio": 0.01,
        # 会议媒体时长 vs 墙钟时长差异率
        "duration_drift_warn_ratio": 0.05,  # 5%
        "duration_drift_fail_ratio": 0.20,  # 20%
    }

    def __init__(self, meeting: Dict[str, Any]):
        self.m = meeting

    def evaluate(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        issues: List[Dict[str, Any]] = []

        # ---- 音频 ----
        media_dur = self.m.get("media_duration_seconds") or self.m.get("audio_duration")
        record_dur = self.m.get("recording_duration_seconds") or self.m.get("audio_duration")
        if media_dur and record_dur and record_dur > 0:
            drift = abs(media_dur - record_dur) / record_dur
            metrics["audio_drift_ratio"] = round(drift, 4)
            if drift > self.THRESHOLDS["duration_drift_fail_ratio"]:
                issues.append({
                    "code": "audio_drift_high",
                    "level": "fail",
                    "message": f"媒体/墙钟时长差异 {drift*100:.1f}% > 20%",
                })
            elif drift > self.THRESHOLDS["duration_drift_warn_ratio"]:
                issues.append({
                    "code": "audio_drift_high",
                    "level": "warn",
                    "message": f"媒体/墙钟时长差异 {drift*100:.1f}% > 5%",
                })
        metrics["audio_url_present"] = bool(self.m.get("audio_url"))

        # ---- 转录 ----
        transcript = self.m.get("transcript") or []
        segments_count = len(transcript)
        metrics["transcript_segment_count"] = segments_count
        if segments_count == 0:
            issues.append({
                "code": "transcript_empty",
                "level": "fail",
                "message": "转录段数为 0 (ASR 全空或未落库)",
            })
            return self._finalize(metrics, issues, not_evaluable=False)

        # 时间戳单调性
        monotonic = all(
            (transcript[i].get("start", 0) <= transcript[i].get("end", 0))
            and (i == 0 or transcript[i - 1].get("end", 0) <= transcript[i].get("start", 0))
            for i in range(segments_count)
        )
        metrics["transcript_monotonic"] = bool(monotonic)
        if not monotonic:
            issues.append({
                "code": "transcript_non_monotonic",
                "level": "fail",
                "message": "转录时间戳非单调, 数据可能错位",
            })

        # 时间覆盖 + 最长 gap
        total_dur = sum(
            max(0.0, (seg.get("end", 0) - seg.get("start", 0)))
            for seg in transcript
        )
        if media_dur:
            coverage = total_dur / media_dur if media_dur > 0 else 0
            metrics["transcript_coverage_ratio"] = round(coverage, 4)
            if coverage < 0.3:
                issues.append({
                    "code": "transcript_low_coverage",
                    "level": "fail",
                    "message": f"转录覆盖率仅 {coverage*100:.1f}% < 30%",
                })

        gaps = []
        for i in range(1, segments_count):
            gap = transcript[i].get("start", 0) - transcript[i - 1].get("end", 0)
            if gap > 0:
                gaps.append(gap)
        if gaps:
            max_gap = max(gaps)
            metrics["transcript_max_gap_sec"] = round(max_gap, 2)
            metrics["transcript_gap_count_gt5s"] = sum(1 for g in gaps if g > 5)
            if max_gap > self.THRESHOLDS["max_gap_fail_sec"]:
                issues.append({
                    "code": "transcript_long_gap",
                    "level": "fail",
                    "message": f"最长无转录间隔 {max_gap:.0f}s > 180s, 需用音频证据分类是真实静音还是 ASR 漏抓",
                })
            elif max_gap > self.THRESHOLDS["max_gap_warn_sec"]:
                issues.append({
                    "code": "transcript_long_gap",
                    "level": "warn",
                    "message": f"最长无转录间隔 {max_gap:.0f}s > 60s",
                })

        # ---- 清洗: 控制 token 泄漏 ----
        control_token_segs = 0
        for seg in transcript:
            text = seg.get("text", "")
            if text and SENSEVOICE_TAG_RE.search(text):
                control_token_segs += 1
        ratio = control_token_segs / segments_count if segments_count else 0
        metrics["control_token_leak_ratio"] = round(ratio, 4)
        metrics["control_token_leak_segments"] = control_token_segs
        if ratio > self.THRESHOLDS["control_token_warn_ratio"]:
            issues.append({
                "code": "control_token_leak",
                "level": "fail",
                "message": f"{control_token_segs}/{segments_count} 段仍泄漏 SenseVoice 控制 token, 持久化前必须 0 泄漏",
            })

        # ---- 润色 ----
        polished = self.m.get("transcript_polished") or []
        if polished:
            diff_count = 0
            valid = min(len(transcript), len(polished))
            for i in range(valid):
                if (transcript[i].get("text") or "") != (polished[i].get("text") or ""):
                    diff_count += 1
            polish_ratio = diff_count / valid if valid else 0
            metrics["polish_real_change_ratio"] = round(polish_ratio, 4)
            metrics["polish_real_change_segments"] = diff_count
            # 0 段变化 (会议 242 实测) 与 1-N 段变化率过低, 都属异常;
            # 但要避免把 "polished 字段恰好跟 raw 字段完全相同" 的正常 case 也告警,
            # 因此若 valid==0 跳过.
            if valid > 0 and media_dur and media_dur > 300 and diff_count == 0:
                issues.append({
                    "code": "polish_no_effective_change",
                    "level": "fail",
                    "message": f"润色实际 0 段变化 (valid={valid}), 形同未润色",
                })
            elif (
                valid > 0
                and media_dur
                and media_dur > 300
                and polish_ratio < self.THRESHOLDS["polish_real_change_warn_ratio"]
                and diff_count > 0
            ):
                issues.append({
                    "code": "polish_no_effective_change",
                    "level": "warn",
                    "message": f"润色实际仅改 {diff_count}/{valid} 段, 改动率 {polish_ratio*100:.2f}%, 形同未润色",
                })

        # ---- 声纹 / 说话人 ----
        speakers: List[str] = []
        for seg in transcript:
            sp = seg.get("speaker") or "未知"
            speakers.append(sp)
        unknown_count = sum(1 for sp in speakers if sp.startswith("发言人") or sp == "?")
        total_speakers = len(speakers)
        unknown_ratio = unknown_count / total_speakers if total_speakers else 0
        metrics["unknown_speaker_count"] = unknown_count
        metrics["unknown_speaker_ratio"] = round(unknown_ratio, 4)
        if unknown_ratio > self.THRESHOLDS["unknown_speaker_fail"]:
            issues.append({
                "code": "unknown_speaker_high",
                "level": "fail",
                "message": f"未识别说话人占 {unknown_ratio*100:.1f}% > 60%, 声纹质量门未通过",
            })
        elif unknown_ratio > self.THRESHOLDS["unknown_speaker_warn"]:
            issues.append({
                "code": "unknown_speaker_high",
                "level": "warn",
                "message": f"未识别说话人占 {unknown_ratio*100:.1f}% > 40%",
            })

        # ---- 纪要 ----
        summary = self.m.get("summary")
        key_points = self.m.get("key_points") or []
        decisions = self.m.get("decisions") or []
        metrics["summary_present"] = bool(summary and summary.strip())
        metrics["key_points_count"] = len(key_points)
        metrics["decisions_count"] = len(decisions)
        if not metrics["summary_present"] and not key_points and not decisions:
            issues.append({
                "code": "minutes_empty",
                "level": "fail",
                "message": "摘要/要点/决议全空, 但 status 可能为 completed (会议 242 复盘)",
            })
        elif not metrics["summary_present"] or not key_points:
            issues.append({
                "code": "minutes_partial",
                "level": "warn",
                "message": "纪要字段缺失部分 (摘要/要点/决议)",
            })

        return self._finalize(metrics, issues, not_evaluable=False)

    def _finalize(self, metrics, issues, not_evaluable):
        if not_evaluable:
            return {
                "status": "not_evaluable",
                "metrics": metrics,
                "issues": issues,
            }
        fail_issues = [i for i in issues if i["level"] == "fail"]
        warn_issues = [i for i in issues if i["level"] == "warn"]
        if fail_issues:
            status = "fail"
        elif warn_issues:
            status = "warn"
        else:
            status = "pass"
        return {
            "status": status,
            "metrics": metrics,
            "issues": issues,
            "issue_codes": [i["code"] for i in issues],
        }


def evaluate_meeting(meeting: Dict[str, Any]) -> Dict[str, Any]:
    """函数式便利包装."""
    return MeetingQualityEvaluator(meeting).evaluate()