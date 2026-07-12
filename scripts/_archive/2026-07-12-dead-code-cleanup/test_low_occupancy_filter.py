#!/usr/bin/env python3
"""测试 low_occupancy_filter (post_meeting_tasks 阶段 1.7)

3 个 case:
1. #167 应用过滤后 speaker_mapping 不含 cluster_0/2/3, 段 17/18 变发言人?
2. 正常会议 (例 #151 杜同贺+张宏魁+王天志+贾琦) 重跑应不受影响
3. 极端短段: 单段 0.3s 触发 max_dur < 1.5

用法:
  python scripts/test_low_occupancy_filter.py
"""
import asyncio
import sys

sys.path.insert(0, "/app")


def _apply_filter(transcript_segments, speaker_mapping, _MIN_MAX=1.5, _MIN_TOTAL=3.0, _MIN_RATIO=0.05):
    """复刻 post_meeting_tasks.py 阶段 1.7 过滤逻辑 (纯函数, 便于单测)"""
    _cluster_stats = {}
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
        if cid not in _cluster_stats:
            _cluster_stats[cid] = [seg_dur, seg_dur, 1]
        else:
            _cluster_stats[cid][0] = max(_cluster_stats[cid][0], seg_dur)
            _cluster_stats[cid][1] += seg_dur
            _cluster_stats[cid][2] += 1

    _grand_total = sum(s[1] for s in _cluster_stats.values())
    _filtered_clusters = []
    for cid, (max_dur, total_dur, seg_count) in _cluster_stats.items():
        ratio = total_dur / _grand_total if _grand_total > 0 else 0
        if (max_dur < _MIN_MAX or total_dur < _MIN_TOTAL or ratio < _MIN_RATIO):
            _filtered_clusters.append(cid)

    _filtered_set = set(_filtered_clusters)
    for cid in _filtered_clusters:
        _key = f"cluster_{cid}"
        if _key in speaker_mapping:
            speaker_mapping.pop(_key)
    for seg in transcript_segments:
        if seg.get("cluster_id") in _filtered_set:
            sp = seg.get("speaker")
            if sp and not sp.startswith("发言人?"):
                seg["speaker"] = "发言人?"

    return {
        "filtered_clusters": sorted(_filtered_clusters),
        "remaining_speaker_mapping_keys": sorted(speaker_mapping.keys()),
        "speakers_in_transcript": sorted(set(s["speaker"] for s in transcript_segments)),
    }


# ========== Case 1: #167 ==========
def case_167():
    # 模拟修正前 #167: cluster_1 张宏魁 5 段, cluster_5 杜同贺 10 段 + 3 个短段 cluster
    # cluster_0 短段 (max=0.7s < 1.5) 触发 max_dur 过滤
    transcript = [
        # 段 1, 4, 10, 11, 12: 张宏魁 cluster_1 (5 段 ~17.2s, max=6.62)
        {"cluster_id": 1, "start": 0.26, "end": 1.21, "speaker": "张宏魁", "text": "然后就允许。"},
        {"cluster_id": 1, "start": 9.99, "end": 16.61, "speaker": "张宏魁", "text": "方案"},
        {"cluster_id": 1, "start": 32.29, "end": 34.65, "speaker": "张宏魁", "text": "8小时"},
        {"cluster_id": 1, "start": 35.20, "end": 40.48, "speaker": "张宏魁", "text": "功率"},
        {"cluster_id": 1, "start": 41.12, "end": 43.10, "speaker": "张宏魁", "text": "设备"},
        # 段 3, 6, 7, 8, 9, 14, 15, 16: 杜同贺 cluster_5 (8 段 ~26.7s, max=6.33)
        {"cluster_id": 5, "start": 2.79, "end": 4.96, "speaker": "杜同贺", "text": "听会"},
        {"cluster_id": 5, "start": 18.91, "end": 24.32, "speaker": "杜同贺", "text": "方案"},
        {"cluster_id": 5, "start": 24.51, "end": 28.35, "speaker": "杜同贺", "text": "传氧"},
        {"cluster_id": 5, "start": 28.74, "end": 30.14, "speaker": "杜同贺", "text": "长距离"},
        {"cluster_id": 5, "start": 30.24, "end": 31.81, "speaker": "杜同贺", "text": "暴气"},
        {"cluster_id": 5, "start": 46.05, "end": 50.78, "speaker": "杜同贺", "text": "电费"},
        {"cluster_id": 5, "start": 51.91, "end": 58.24, "speaker": "杜同贺", "text": "121.6"},
        {"cluster_id": 5, "start": 59.07, "end": 61.21, "speaker": "杜同贺", "text": "90天"},
        # 段 17: 短段 cluster_0 (1 段 0.7s, max<1.5 触发过滤)
        {"cluster_id": 0, "start": 59.0, "end": 59.7, "speaker": "发言人A", "text": "短段A"},
        # 段 5: 短段 cluster_2 (1 段 1.0s, max<1.5 触发过滤)
        {"cluster_id": 2, "start": 17.31, "end": 18.31, "speaker": "王天志", "text": "短段B"},
        # 段 18: 短段 cluster_3 (1 段 0.5s, max<1.5 触发过滤)
        {"cluster_id": 3, "start": 61.57, "end": 62.07, "speaker": "宋洋", "text": "短段C"},
    ]
    speaker_mapping = {
        "cluster_1": "张宏魁",
        "cluster_5": "杜同贺",
        "cluster_0": "发言人A",
        "cluster_2": "王天志",
        "cluster_3": "宋洋",
    }
    result = _apply_filter(transcript, speaker_mapping)
    print("=== Case 1: #167 过滤测试 ===")
    print(f"  过滤的 cluster: {result['filtered_clusters']}  (期望: [0, 2, 3])")
    print(f"  保留的 speaker_mapping: {result['remaining_speaker_mapping_keys']}  (期望: ['cluster_1', 'cluster_5'])")
    print(f"  transcript 中 speaker: {result['speakers_in_transcript']}  (期望: ['发言人?', '张宏魁', '杜同贺'])")
    assert result['filtered_clusters'] == [0, 2, 3], f"FAIL: 过滤的 cluster 错误"
    assert result['remaining_speaker_mapping_keys'] == ['cluster_1', 'cluster_5'], f"FAIL: speaker_mapping 错误"
    assert '张宏魁' in result['speakers_in_transcript'] and '杜同贺' in result['speakers_in_transcript'], f"FAIL: 真实发言人丢失"
    assert '王天志' not in result['speakers_in_transcript'] and '宋洋' not in result['speakers_in_transcript'] and '发言人A' not in result['speakers_in_transcript'], f"FAIL: 误识的人没被过滤"
    print("  PASS ✅")


# ========== Case 2: 正常多人会议 (不应触发过滤) ==========
def case_normal_meeting():
    # 4 人正常会议: 每人都说多段, 总时长充足
    transcript = [
        # 杜同贺 4 段 ~17s
        {"cluster_id": 1, "start": 0, "end": 5, "speaker": "杜同贺", "text": "段1"},
        {"cluster_id": 1, "start": 10, "end": 13, "speaker": "杜同贺", "text": "段2"},
        {"cluster_id": 1, "start": 20, "end": 24, "speaker": "杜同贺", "text": "段3"},
        {"cluster_id": 1, "start": 30, "end": 35, "speaker": "杜同贺", "text": "段4"},
        # 张宏魁 3 段 ~12s
        {"cluster_id": 2, "start": 5, "end": 9, "speaker": "张宏魁", "text": "段1"},
        {"cluster_id": 2, "start": 13, "end": 17, "speaker": "张宏魁", "text": "段2"},
        {"cluster_id": 2, "start": 24, "end": 28, "speaker": "张宏魁", "text": "段3"},
        # 王天志 3 段 ~10s
        {"cluster_id": 3, "start": 9, "end": 12, "speaker": "王天志", "text": "段1"},
        {"cluster_id": 3, "start": 17, "end": 20, "speaker": "王天志", "text": "段2"},
        {"cluster_id": 3, "start": 35, "end": 39, "speaker": "王天志", "text": "段3"},
        # 贾琦 2 段 ~8s
        {"cluster_id": 4, "start": 12, "end": 16, "speaker": "贾琦", "text": "段1"},
        {"cluster_id": 4, "start": 28, "end": 32, "speaker": "贾琦", "text": "段2"},
    ]
    speaker_mapping = {"cluster_1": "杜同贺", "cluster_2": "张宏魁", "cluster_3": "王天志", "cluster_4": "贾琦"}
    result = _apply_filter(transcript, speaker_mapping)
    print("\n=== Case 2: 正常多人会议 (不应过滤) ===")
    print(f"  过滤的 cluster: {result['filtered_clusters']}  (期望: [])")
    print(f"  保留的 speaker_mapping: {result['remaining_speaker_mapping_keys']}  (期望: 4 个)")
    print(f"  transcript 中 speaker: {result['speakers_in_transcript']}  (期望: 4 个真实人)")
    assert result['filtered_clusters'] == [], f"FAIL: 正常会议不应过滤任何 cluster"
    assert len(result['remaining_speaker_mapping_keys']) == 4, f"FAIL: 4 个 cluster 都应保留"
    assert len(result['speakers_in_transcript']) == 4, f"FAIL: 4 个真实人都应保留"
    print("  PASS ✅")


# ========== Case 3: 极端短段 (单段 0.3s) ==========
def case_extreme_short():
    transcript = [
        {"cluster_id": 1, "start": 0, "end": 5, "speaker": "杜同贺", "text": "长段"},
        {"cluster_id": 1, "start": 10, "end": 15, "speaker": "杜同贺", "text": "长段2"},
        {"cluster_id": 2, "start": 5, "end": 5.3, "speaker": "王天志", "text": "嗯"},  # 0.3s 极端短
    ]
    speaker_mapping = {"cluster_1": "杜同贺", "cluster_2": "王天志"}
    result = _apply_filter(transcript, speaker_mapping)
    print("\n=== Case 3: 极端短段 (单段 0.3s) ===")
    print(f"  过滤的 cluster: {result['filtered_clusters']}  (期望: [2])")
    print(f"  保留的 speaker_mapping: {result['remaining_speaker_mapping_keys']}  (期望: ['cluster_1'])")
    print(f"  transcript 中 speaker: {result['speakers_in_transcript']}  (期望: ['发言人?', '杜同贺'])")
    assert 2 in result['filtered_clusters'], f"FAIL: 极端短段应被过滤"
    assert result['remaining_speaker_mapping_keys'] == ['cluster_1'], f"FAIL: speaker_mapping 错误"
    assert '王天志' not in result['speakers_in_transcript'], f"FAIL: 误识的人没被过滤"
    print("  PASS ✅")


# ========== Case 4: 边界 ratio 5% ==========
def case_ratio_boundary():
    # 杜同贺 95% + 张宏魁 5% (刚好阈值)
    transcript = [
        {"cluster_id": 1, "start": 0, "end": 19, "speaker": "杜同贺", "text": "长段1"},  # 19s
        {"cluster_id": 1, "start": 25, "end": 44, "speaker": "杜同贺", "text": "长段2"},  # 19s
        {"cluster_id": 1, "start": 50, "end": 69, "speaker": "杜同贺", "text": "长段3"},  # 19s
        {"cluster_id": 1, "start": 75, "end": 94, "speaker": "杜同贺", "text": "长段4"},  # 19s
        {"cluster_id": 1, "start": 100, "end": 119, "speaker": "杜同贺", "text": "长段5"},  # 19s
        # 总 95s
        {"cluster_id": 2, "start": 120, "end": 121, "speaker": "张宏魁", "text": "短段"},  # 1s
        {"cluster_id": 2, "start": 122, "end": 123, "speaker": "张宏魁", "text": "短段2"},  # 1s
        {"cluster_id": 2, "start": 124, "end": 128, "speaker": "张宏魁", "text": "短段3"},  # 4s
        # 总 6s = 6/101 = 5.94% (应保留, > 5%)
    ]
    speaker_mapping = {"cluster_1": "杜同贺", "cluster_2": "张宏魁"}
    result = _apply_filter(transcript, speaker_mapping)
    print("\n=== Case 4: 边界 ratio 5% (张宏魁 5.94% 应保留) ===")
    print(f"  过滤的 cluster: {result['filtered_clusters']}  (期望: [])")
    print(f"  保留的 speaker_mapping: {result['remaining_speaker_mapping_keys']}  (期望: 2 个)")
    assert result['filtered_clusters'] == [], f"FAIL: ratio 5.94% > 5% 应保留"
    assert len(result['remaining_speaker_mapping_keys']) == 2, f"FAIL: 都应保留"
    print("  PASS ✅")


# ========== Case 5: cluster=-1 跳过 (未识别段) ==========
def case_cluster_negative_one():
    transcript = [
        {"cluster_id": 1, "start": 0, "end": 10, "speaker": "杜同贺", "text": "段1"},
        {"cluster_id": -1, "start": 10, "end": 10.5, "speaker": "发言人?", "text": "未识别段"},  # 跳过
    ]
    speaker_mapping = {"cluster_1": "杜同贺"}
    result = _apply_filter(transcript, speaker_mapping)
    print("\n=== Case 5: cluster=-1 跳过 (未识别段不参与过滤) ===")
    print(f"  过滤的 cluster: {result['filtered_clusters']}  (期望: [])")
    print(f"  保留的 speaker_mapping: {result['remaining_speaker_mapping_keys']}  (期望: ['cluster_1'])")
    assert result['filtered_clusters'] == [], f"FAIL: cluster=-1 应跳过"
    print("  PASS ✅")


if __name__ == "__main__":
    case_167()
    case_normal_meeting()
    case_extreme_short()
    case_ratio_boundary()
    case_cluster_negative_one()
    print("\n=== 全部 5 个 case PASS ===")