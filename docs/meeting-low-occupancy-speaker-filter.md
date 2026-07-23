# 会议低占比发言人过滤规则

> W68 Plan 15-17-18 Part 2 (2026-07-24) 闭环. 锚点范式第 43 守恒.
> Plan: `~/.claude/plans/15-17-18-cozy-bengio.md` (Part 2)
> 实现: `app/services/low_occupancy_filter.py` + `app/services/post_meeting_tasks.py` 阶段 1.7
> 测试: `tests/e2e/test_low_occupancy_speaker_filter.py` (16 tests)

## 一、问题背景

课题组 20 人声纹库中, **王天志 (384 samples)** 属于声纹强成员. 会议后处理阶段 (`post_meeting_tasks` 阶段 1.6 声纹识别) 在聚类 + 余弦相似度匹配时, 会因为向量空间中"距离最近"误把他识别为某些**只言片语**短段的发言人. 例:

- 会议 #167 段 13: "嗯" 0.48s, 系统判为王天志 cos_dist 0.635 (实际是另一人)
- 会议 #167 段 17: "90天按照10000元算" 2.14s, 系统判为 cluster_0 占比 3.4% (实际是杜同贺)

这些**占比极低**的识别结果如果流入下游, 会污染:
- `summary` (AI 总结) — 引用错误的"王天志"
- `key_points` (讨论要点) — 同上
- `decisions` (决议事项) — 同上
- `meeting_participants` 表 — 把误识成员加为会议参与者, 后续任务分配 / 通知都错
- `participant_names` (AI 润色上下文) — LLM 看到的参会列表含错误人名

## 二、规则定义

### 阈值 (用户决策 2026-06-30 中等严格)

| 阈值 | 值 | 含义 |
|------|------|------|
| `MIN_MAX_SEG_DUR` | **1.5 秒** | 该 speaker 单段最大时长 < 1.5s 视为"嗯/啊/对"等只言片语 |
| `MIN_TOTAL_DUR` | **3.0 秒** | 该 speaker 所有段总时长 < 3s 视为"偶尔插嘴" |
| `MIN_RATIO` | **5%** | 该 speaker 总时长 / 会议总时长 < 5% 视为"挂名非主发言" |

**任一条件触发即过滤** (用 strict `<` 比较, 等于阈值不算触发).

### 同步回写范围

| 对象 | 是否修改 |
|------|---------|
| `speaker_mapping` 的 `cluster_N` entry | **删除** |
| `transcript_segments[].speaker` (filter 触发的 cluster) | **回写** `"发言人?"` |
| `transcript_segments[].speaker_label` | **不动** (用于 audit / reprocess 反查) |
| `transcript_segments[].cluster_id` | **不动** (用于审计) |
| `transcript_polished` | 不直接动, 由下游 LLM 在过滤后的 `participant_names` 上重新生成 |
| `summary` / `key_points` / `decisions` | 不回写, 已生成或将由 LLM 在过滤后列表上重生成 |

### 触发位置

`post_meeting_tasks.py` **阶段 1.7**, 在阶段 1.6 声纹识别 + speaker_mapping 构建**完成后**, 阶段 1.8 标点补充 / 阶段 2.5 AI 润色**之前**:

```
阶段 1.6: 声纹识别完成, speaker_mapping 含所有 cluster
阶段 1.7: 低占比发言人过滤 (新增)
阶段 1.8: 规则标点补充
阶段 2.5: AI 润色 (看 participant_names = speaker_mapping.values())
阶段 3:   AI 分析 (summary / key_points / decisions)
阶段 3.5: 同步 transcript_segments → DB
阶段 3.6: 同步 transcript_polished → DB
```

**为什么必须早于阶段 2.5**: AI 润色的 `participant_names` 从 `speaker_mapping.values()` 取. 如果过滤在阶段 2.5 之后, LLM 已经看到错误的人名列表, prompt 污染不可逆.

## 三、代码实现

### 模块拆分

`app/services/low_occupancy_filter.py` 是**纯函数模块** (无 DB / Redis / Celery 依赖), 三个导出:

1. `compute_cluster_durations(transcript_segments)` — 聚合 `(max_dur, total_dur, count)` per cluster
2. `select_filtered_clusters(cluster_stats, grand_total)` — 按 3 阈值过滤
3. `apply_low_occupancy_filter(transcript_segments, speaker_mapping, *, meeting_id=None)` — 主入口, 原地修改 + 返回被过滤 cid 集合

### 接入点 (`post_meeting_tasks.py:591-609`)

```python
logger.info(f"声纹识别完成: {len(set(seg.get('speaker','') for seg in transcript_segments))} 位发言人")

# ===== 阶段 1.7: 低占比发言人过滤（2026-06-30 铁律: 王天志只言片语误识） =====
from app.services.low_occupancy_filter import apply_low_occupancy_filter
_filtered_cids = apply_low_occupancy_filter(
    transcript_segments, speaker_mapping, meeting_id=meeting_id
)
if _filtered_cids:
    logger.info(
        f"低占比发言人过滤命中: {sorted(_filtered_cids)}, "
        f"speaker_mapping 现有 {len(speaker_mapping)} 人"
    )

# ===== 阶段 1.8: 规则标点补充 =====
```

### 日志格式

```python
logger.info(
    "[low_occupancy_filter] meeting_id=167: removed cluster_7=王天志 "
    "(max_seg=1.40s, total=1.40s, count=1, ratio=0.014)"
)
logger.info(
    "[low_occupancy_filter] meeting_id=167: filtered 1 clusters, rewrote 1 segments"
)
```

便于后续 audit / dashboard 拉日志统计"每月过滤多少误识".

## 四、E2E 覆盖矩阵

`tests/e2e/test_low_occupancy_speaker_filter.py` 共 **16 个测试** (5 必需场景 + 11 边界 / 单元测试):

| # | 测试名 | 场景 | 期望 |
|---|--------|------|------|
| 1 | `test_single_short_segment_1_4s_is_filtered_by_max_seg_dur` | 单段 1.4s < 1.5s | cluster_7 过滤, speaker → "发言人?" |
| 2 | `test_low_ratio_3_segments_filtered_by_total_ratio` | 3 段共 5s 占比 4% < 5% | cluster_7 过滤, 3 段回写 |
| 3 | `test_normal_meeting_with_substantial_speaker_is_kept` | 10 段共 60s 占比 30% | 全部保留 |
| 4 | `test_wang_tian_zhi_384_samples_not_filtered_when_substantial` | 王天志 2 段共 6s 占比 5.2% > 5% | 保留 |
| 5 | `test_boundary_values_exact_threshold_are_kept` | 边界 1.5s + 3.0s + 5% | 全部保留 |
| 6 | `test_compute_cluster_durations_aggregates_correctly` | 聚合函数正确性 | max/total/count 对 |
| 7 | `test_compute_cluster_durations_ignores_invalid_segments` | 无效段 (无 cid / 负时长 / 字符串) | 静默跳过 |
| 8 | `test_select_filtered_clusters_returns_sorted_cids` | 返回值排序 | 升序 |
| 9 | `test_apply_filter_with_meeting_id_none_does_not_log_meeting_id` | meeting_id=None 边界 | 不抛错 |
| 10 | `test_apply_filter_empty_inputs_returns_empty_set` | 空输入 | set() |
| 11 | `test_apply_filter_is_idempotent` | 二次调用相同输入 | 相同结果 |
| 12 | `test_filter_version_constant_for_observability` | FILTER_VERSION 锁定 | "v1-2026-07-24" |
| 13 | `test_thresholds_constants_unchanged` | 阈值常量锁定 | 1.5 / 3.0 / 0.05 |
| 14 | `test_speaker_label_kept_for_backtracking` | speaker_label 不动 | 保留 audit 链 |
| 15 | `test_filter_handles_cluster_id_minus_one` | cluster_id=-1 边界 | 不抛 KeyError |
| 16 | `test_filter_with_no_segments_after_id_keeps_speaker_mapping` | 正常 speaker_mapping 保持原样 | 无修改 |

### 运行

```bash
# 本地 (无需 Docker / Postgres / Redis):
SKIP_DB_SETUP=1 python -m pytest tests/e2e/test_low_occupancy_speaker_filter.py -v

# 输出: 16 passed in 0.05s
```

## 五、用户场景决策表

| 场景 | 期望 | 行为 |
|------|------|------|
| 真实小发言 (王天志只 1 段 "嗯" 0.5s) | 过滤 | max_seg=0.5 < 1.5 触发 |
| 真实小发言 (王天志 1 段 3s + 总占比 3%) | 过滤 | total=3 ≥ 3 通过, 但 ratio=3% < 5% 触发 |
| 真实正常发言 (王天志 5 段共 30s 占比 25%) | 保留 | 三阈值全通过 |
| 真实长发言者 (杜同贺 30 段共 90s) | 保留 | 三阈值全通过 |
| 会议主讲 (杜同贺 + 张宏魁 + 王天志 4 段共 20s 占比 18%) | 保留 | 三阈值全通过 |
| 边界 (单段刚好 1.5s + 总刚好 3s + 占比刚好 5%) | 保留 | strict `<` 不触发 |
| 声纹强成员 (王天志 384 samples) 偶尔插嘴 | 过滤 | 占比极低 |
| 声纹弱成员 (新人 5 samples) 正常发言 | 保留 | 阈值看时长不看声纹强度 |

## 六、风险评估

| 风险 | 影响 | 缓解 |
|------|------|------|
| 阈值过严误杀真实短发言人 | 高 — 误把真实"嗯/对/是"剔除 | 5% 阈值够宽松; 用户后续可按实际反馈调阈值常量 |
| 阈值写死不易调 | 中 | 留作 constants 顶部集中定义; 未来可加 settings flag 覆盖 |
| 已生成 meeting 重跑 post_meeting_process 会重新过滤 | 中 | 这是预期行为; 老会议 DB 不动 |
| 过滤规则不向后兼容老会议 | 低 | 只影响未来生成的 speaker_mapping; 老 DB 不动 |
| `meeting.transcript` 落盘后再 filter 时序错乱 | 高 | 已确保 filter 在 `meeting.transcript = transcript_segments` 之前 (阶段 3.5 line 721) |

## 七、部署

本规则**纯函数 + 无 DB 迁移**, 部署只需:

```bash
# 1. 部署新代码 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 2. 验证 (端到端)
#    - 跑下一个会议后处理, 看日志:
#      [low_occupancy_filter] meeting_id=N: filtered M clusters, rewrote K segments
#    - 查 DB 确认:
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "SELECT id, speaker_mapping::text FROM meetings WHERE id = N;"
#    应看到被过滤的 cluster_N 不在 speaker_mapping 里
```

无需 alembic 迁移.

## 八、相关 commit / plan / memory

- **plan**: `~/.claude/plans/15-17-18-cozy-bengio.md` (Part 2)
- **memory**: `memory/w68-route-plan1-low-occupancy-speaker-filter-2026-07-24.md`
- **2026-06-30 触发 case**: 会议 #167 段 13 / 17 / 18 误识
- **2026-07-24 闭环 commit**: 本次