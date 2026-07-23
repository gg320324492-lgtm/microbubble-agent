"""低占比发言人过滤 — W68 Plan 15-17-18 Part 2 (2026-07-24).

触发场景: 声纹强成员 (如王天志 384 samples) 在某场会议里只出现一两句
"只言片语、占比极低"的发言, 八成是误识. 应从 speaker_mapping 里剔除,
避免下游 summary / key_points / participant_names 引用错误人名.

阈值 (用户决策 2026-06-30 中等严格):
- 单段最大时长 < 1.5s  →  视为"嗯/啊/对"等只言片语
- 总发言时长  < 3.0s   →  视为"偶尔插嘴"
- 总时长占比  < 5%     →  视为"挂名非主发言"

三个条件**任一**触发即过滤.

同步回写:
- speaker_mapping 删 cluster_N entry
- transcript_segments[].speaker (filter 触发的 cluster) 回写 "发言人?"
- 不动 transcript_polished / summary / key_points / decisions (将由 LLM
  在过滤后的 participant_names 上重新生成)

不动 speaker_label (用于回溯 cluster→speaker 的 key), 只动 speaker.

参考:
- plan: ~/.claude/plans/15-17-18-cozy-bengio.md (Part 2)
- 触发 case: #167 段 13 "嗯" 0.48s 误识别为王天志 cos_dist 0.635
- 插入位置: post_meeting_tasks.py 阶段 1.8 (阶段 2.5 AI 润色之前)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger("microbubble.low_occupancy_filter")

# ===== 阈值常量 (用户决策 2026-06-30) =====
MIN_MAX_SEG_DUR: float = 1.5   # 单段最大时长阈值 (秒)
MIN_TOTAL_DUR: float = 3.0     # 总发言时长阈值 (秒)
MIN_RATIO: float = 0.05         # 总时长占会议时长比例阈值 (5%)
UNKNOWN_SPEAKER_LABEL: str = "发言人?"

# 留作 unit-test 覆盖的版本号常量 — e2e 测试断言此值
FILTER_VERSION: str = "v1-2026-07-24"


def compute_cluster_durations(
    transcript_segments: Iterable[Dict[str, Any]],
) -> Tuple[Dict[int, List[float]], float]:
    """聚合每个 cluster_id 的 (max_seg_dur, total_dur, seg_count).

    Args:
        transcript_segments: 转录段列表, 每段至少含
            - cluster_id (int|None)
            - start / end (float 秒)

    Returns:
        (cluster_stats, grand_total):
        - cluster_stats: cid -> [max_dur, total_dur, count]
        - grand_total: 所有段时长总和 (秒)
    """
    cluster_stats: Dict[int, List[float]] = {}
    grand_total: float = 0.0

    for seg in transcript_segments:
        cid = seg.get("cluster_id")
        if cid is None or cid < 0:
            continue
        try:
            seg_dur = float(seg.get("end", 0)) - float(seg.get("start", 0))
        except (TypeError, ValueError):
            continue
        if seg_dur <= 0:
            continue
        if cid not in cluster_stats:
            cluster_stats[cid] = [seg_dur, seg_dur, 1.0]  # max, total, count
        else:
            cluster_stats[cid][0] = max(cluster_stats[cid][0], seg_dur)
            cluster_stats[cid][1] += seg_dur
            cluster_stats[cid][2] += 1.0
        grand_total += seg_dur

    return cluster_stats, grand_total


def select_filtered_clusters(
    cluster_stats: Dict[int, List[float]],
    grand_total: float,
    *,
    min_max_seg_dur: float = MIN_MAX_SEG_DUR,
    min_total_dur: float = MIN_TOTAL_DUR,
    min_ratio: float = MIN_RATIO,
) -> List[int]:
    """按 3 阈值**任一**不满足即过滤的规则挑选 cluster.

    Args:
        cluster_stats: cid -> [max_dur, total_dur, count]
        grand_total: 会议总时长 (秒)
        min_max_seg_dur: 单段最大时长阈值
        min_total_dur: 总时长阈值
        min_ratio: 占比阈值

    Returns:
        触发过滤的 cluster_id 列表 (按 cid 升序)
    """
    filtered: List[int] = []
    for cid, (max_dur, total_dur, _count) in cluster_stats.items():
        ratio = total_dur / grand_total if grand_total > 0 else 0.0
        if max_dur < min_max_seg_dur or total_dur < min_total_dur or ratio < min_ratio:
            filtered.append(cid)
    filtered.sort()
    return filtered


def apply_low_occupancy_filter(
    transcript_segments: List[Dict[str, Any]],
    speaker_mapping: Dict[str, str],
    *,
    min_max_seg_dur: float = MIN_MAX_SEG_DUR,
    min_total_dur: float = MIN_TOTAL_DUR,
    min_ratio: float = MIN_RATIO,
    meeting_id: Optional[int] = None,
) -> Set[int]:
    """低占比发言人过滤主入口.

    在调用方已写好 speaker_mapping / transcript_segments 的前提下, 修改
    speaker_mapping (删除被过滤 cluster) + transcript_segments[].speaker
    (filter 触发的段回写 "发言人?").

    Args:
        transcript_segments: 会被原地修改, 被过滤段的 speaker 字段会回写
        speaker_mapping: 会被原地修改, 被过滤的 cluster_N 会被删除
        meeting_id: 可选, 用于日志追踪

    Returns:
        被过滤的 cluster_id 集合
    """
    cluster_stats, grand_total = compute_cluster_durations(transcript_segments)
    filtered = select_filtered_clusters(
        cluster_stats,
        grand_total,
        min_max_seg_dur=min_max_seg_dur,
        min_total_dur=min_total_dur,
        min_ratio=min_ratio,
    )

    if not filtered:
        return set()

    filtered_set: Set[int] = set(filtered)
    prefix = f"meeting_id={meeting_id}" if meeting_id is not None else "meeting"

    # 1) 从 speaker_mapping 删 cluster_N
    for cid in filtered:
        key = f"cluster_{cid}"
        if key in speaker_mapping:
            removed_name = speaker_mapping.pop(key)
            max_dur, total_dur, count = cluster_stats[cid]
            ratio = total_dur / grand_total if grand_total > 0 else 0.0
            logger.info(
                "[low_occupancy_filter] %s: removed %s=%s "
                "(max_seg=%.2fs, total=%.2fs, count=%d, ratio=%.3f)",
                prefix, key, removed_name,
                max_dur, total_dur, int(count), ratio,
            )

    # 2) 同步回写 transcript_segments[].speaker = "发言人?"
    synced = 0
    for seg in transcript_segments:
        if seg.get("cluster_id") in filtered_set:
            cur = seg.get("speaker")
            if cur and not cur.startswith("发言人"):
                seg["speaker"] = UNKNOWN_SPEAKER_LABEL
                synced += 1

    logger.info(
        "[low_occupancy_filter] %s: filtered %d clusters, rewrote %d segments",
        prefix, len(filtered), synced,
    )

    return filtered_set