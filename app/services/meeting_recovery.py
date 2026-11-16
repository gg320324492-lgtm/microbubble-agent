"""会议录音失败恢复状态机（纯函数，无 DB / 无 IO）。

2026-11-16 会议 278 事故：orphan cleanup 误杀后只剩 4 秒静音分片，
旧 reprocess 守卫仅凭 last_chunk_index>=0 就放行，用静音片段跑完整流水线。
本模块把「什么状态该做什么」收敛成一个可单测的判定函数，供 API 层复用。

判定输入只需要 meeting 对象上的 4 个字段：
    status / audio_url / last_chunk_index / media_duration_seconds

设计原则：
- 纯函数：不改对象、不查库、不抛异常，任何输入都返回结构一致的 dict。
- 宁可未识别也不要猜错：chunks-only 的 error 会议**不能** reprocess，
  因为分片可能是 4 秒空静音（会议 278），必须先合并并验时长或补传完整录音。
- 未知状态一律不开放任何动作（fail closed）。
"""

from typing import Any, Dict, List, Optional

# 短于该时长的合并产物视为「疑似空/静音」，不能作为重跑音频
MIN_REPROCESS_AUDIO_SECONDS = 30

STATE_RECORDING = "recording"
STATE_PROCESSING = "processing"
STATE_COMPLETED = "completed"
STATE_ERROR_WITH_AUDIO = "error_with_audio"
STATE_ERROR_WITHOUT_AUDIO = "error_without_audio"
STATE_UNKNOWN = "unknown"

ACTION_NONE = "none"
ACTION_RESUME = "resume"
ACTION_REPROCESS = "reprocess"
ACTION_REUPLOAD = "reupload"
ACTION_MERGE_FIRST = "merge_first"


def _has_chunks(meeting: Any) -> bool:
    idx = getattr(meeting, "last_chunk_index", None)
    return isinstance(idx, int) and idx >= 0


def normalize_media_duration(value: Any) -> Optional[float]:
    """把 media_duration_seconds 安全地转成 float；非数值（含 Mock）一律视为未知。

    纯函数与 API 守卫共用，避免 `float(MagicMock()) == 1.0` 这类假短音频误判。
    """
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _result(
    state: str,
    action: str,
    can_upload: bool,
    can_merge: bool,
    can_reprocess: bool,
    reasons: List[str],
) -> Dict[str, Any]:
    return {
        "state": state,
        "recommended_action": action,
        "can_upload": can_upload,
        "can_merge": can_merge,
        "can_reprocess": can_reprocess,
        "reasons": reasons,
    }


def evaluate_recovery(meeting: Any) -> Dict[str, Any]:
    """判定会议当前该走哪条恢复路径（纯函数）。

    Returns:
        dict: state / recommended_action / can_upload / can_merge /
              can_reprocess / reasons
    """
    status = getattr(meeting, "status", None)
    audio_url = getattr(meeting, "audio_url", None)

    if status == "recording":
        return _result(
            STATE_RECORDING, ACTION_RESUME,
            can_upload=True, can_merge=True, can_reprocess=False,
            reasons=["录音中：可继续上传分片、可合并；流水线尚未启动"],
        )

    if status in ("processing", "completed"):
        return _result(
            status, ACTION_NONE,
            can_upload=False, can_merge=False, can_reprocess=False,
            reasons=[f"status={status}：流水线在处理或已完成，禁止改动录音数据"],
        )

    if status == "error":
        has_audio = bool(audio_url)
        duration: Optional[float] = getattr(meeting, "media_duration_seconds", None)
        chunks = _has_chunks(meeting)

        if has_audio:
            # 有合并产物时按真实媒体时长分档（None 兼容历史会议）。
            duration_value = normalize_media_duration(duration)
            if duration_value is not None:
                if duration_value is not None and 0 < duration_value < MIN_REPROCESS_AUDIO_SECONDS:
                    return _result(
                        STATE_ERROR_WITH_AUDIO, ACTION_REUPLOAD,
                        can_upload=True, can_merge=True, can_reprocess=False,
                        reasons=[
                            f"音频疑似空/静音（media_duration_seconds={duration}s "
                            f"< {MIN_REPROCESS_AUDIO_SECONDS}s），请补传完整录音",
                        ],
                    )
            return _result(
                STATE_ERROR_WITH_AUDIO, ACTION_REPROCESS,
                can_upload=False, can_merge=False, can_reprocess=True,
                reasons=[
                    "status=error 且有合并后的完整录音（或历史会议未记录时长），可重新处理",
                ],
            )

        # 无 audio_url：即便有分片也不视为有可用录音（会议 278：4 秒静音分片）。
        if chunks:
            return _result(
                STATE_ERROR_WITHOUT_AUDIO, ACTION_MERGE_FIRST,
                can_upload=True, can_merge=True, can_reprocess=False,
                reasons=[
                    "status=error 且无合并录音，仅有分片；分片可能是空/静音，"
                    "必须先合并并确认时长或补传完整录音，禁止直接 reprocess",
                ],
            )
        return _result(
            STATE_ERROR_WITHOUT_AUDIO, ACTION_REUPLOAD,
            can_upload=True, can_merge=False, can_reprocess=False,
            reasons=["status=error 且无录音、无分片：请补传完整录音"],
        )

    # scheduled / cancelled / None / 任意未知值：一律不改数据
    return _result(
        STATE_UNKNOWN, ACTION_NONE,
        can_upload=False, can_merge=False, can_reprocess=False,
        reasons=[f"未知或非录音链路状态 (status={status!r})，禁止自动恢复"],
    )
