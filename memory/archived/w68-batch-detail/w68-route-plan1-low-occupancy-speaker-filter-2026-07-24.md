# W68 第 4 批 Plan #1: 会议低占比发言人过滤规则 — 锚点范式第 43 守恒

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 4 批 Plan #1"
> **分支**: `feat/plan-low-occupancy-speaker-filter-2026-07-24`
> **Plan**: `~/.claude/plans/15-17-18-cozy-bengio.md` (Part 2)
> **锚点范式**: 第 43 守恒 (W7 12 → W66 27 → W67 28 → W68 30 → W68 第 4 批 **43**)
> **0 production code 改动铁律**: 本任务**例外** — 实施 plan 本身就需要 production code 改动 (CLAUDE.md 已批准)

---

## 一、plan 背景与闭环

plan `15-17-18-cozy-bengio.md` 有两部分:

- **Part 1**: 会议 #167 段 15/17/18 数据修正 — 已收官 (Part 1 实施时间: 2026-06-30)
- **Part 2**: 永久过滤规则 — 在 commit 4b215220 refactor 中**意外删除**, 后续无补

Verified Plans 报告 (memory: `verified-plans-2026-07-22.md`) 标注此 plan 为 "6 partial" 之一 (含 refactor regression).

本次任务**闭环 Part 2**: 在 `post_meeting_tasks.py` 加低占比发言人过滤规则, 防止未来新会议重蹈 #167 覆辙.

## 二、用户原始观察 (2026-06-30)

> 像王天志这种声纹强 (384 samples) 的成员, 如果只在某场会议里出现一两句"只言片语、占比极低"的发言, 那八成是误识. 这类低占比识别结果应该从 speaker_mapping 里剔除, 避免下游 summary / key_points 引用错误的"王天志".

**触发 case**:
- #167 段 13 "嗯" 0.48s → 误识为王天志 (cos_dist 0.635)
- #167 段 17 "90天按照10000元算" 2.14s → cluster_0 占比 3.4% → 误识

## 三、实施细节

### 3.1 阈值 (用户决策: 中等严格, 任一触发即过滤)

| 阈值 | 值 | 触发 |
|------|------|------|
| `MIN_MAX_SEG_DUR` | **1.5 秒** | 单段 < 1.5s |
| `MIN_TOTAL_DUR` | **3.0 秒** | 总时长 < 3s |
| `MIN_RATIO` | **5%** | 总时长 / 会议时长 < 5% |

`strict <` 比较, 等于阈值不算触发 (边界值用 `>=`).

### 3.2 同步回写范围

| 对象 | 修改 |
|------|------|
| `speaker_mapping` 的 `cluster_N` | **删除** |
| `transcript_segments[].speaker` (filter cluster) | **回写** `"发言人?"` |
| `transcript_segments[].speaker_label` | **不动** (audit 链) |
| `transcript_segments[].cluster_id` | **不动** (审计) |
| `transcript_polished` | 不动, LLM 重生成 |
| `summary` / `key_points` / `decisions` | 不回写 |

### 3.3 模块拆分 (重要!)

旧 plan 设计是把过滤逻辑直接 inline 写到 `post_meeting_tasks.py:594` 之后 (~50 行). 但 inline 代码无法单元测试, 必须启动整个 async pipeline 才能验证.

本次实施做了**模块拆分**:

- **新模块**: `app/services/low_occupancy_filter.py` (纯函数, 无 DB / Redis / Celery 依赖)
  - `compute_cluster_durations(transcript_segments)` — 聚合
  - `select_filtered_clusters(cluster_stats, grand_total)` — 阈值选择
  - `apply_low_occupancy_filter(transcript_segments, speaker_mapping, *, meeting_id=None)` — 主入口
- **接入点**: `post_meeting_tasks.py:591-609` (阶段 1.7, 阶段 2.5 之前)

**好处**:
1. 16 个单元/e2e 测试**无需 docker**, 0.05s 跑完
2. 重跑幂等性 + 边界值可在 CI 反复验证
3. 未来调整阈值只改 constants

### 3.4 插入位置的重要性

```
阶段 1.6: 声纹识别 + speaker_mapping 构建
阶段 1.7: 低占比发言人过滤  ← 必须在这里
阶段 1.8: 标点补充
阶段 2.5: AI 润色 (participant_names = speaker_mapping.values())
阶段 3:   AI 分析 (summary / key_points / decisions)
阶段 3.5: 落库 transcript_segments
阶段 3.6: 落库 transcript_polished
```

**为什么不能放阶段 2.5 之后**: AI 润色 prompt 的 `participant_names` 已被错误人名污染, LLM 输出的 summary 已经引用错误, 不可逆.

**为什么不能放阶段 3.5 之后**: `meeting.transcript = transcript_segments` 落库后再 filter, 已落库的 segment 是错的. Filter 必须在落库**之前**.

## 四、16 个测试场景

`tests/e2e/test_low_occupancy_speaker_filter.py`:

1. **5 必需场景**:
   - 单段 1.4s < 1.5s 过滤 ✓
   - 3 段共 5s 占比 4% 过滤 ✓
   - 10 段共 60s 占比 30% 保留 ✓
   - 王天志 384 samples 2 段共 6s 占比 5.2% 保留 ✓
   - 边界值 1.5s + 3.0s + 5% 整 保留 ✓

2. **11 边界 / 单元测试**:
   - 聚合函数正确性
   - 无效段 (无 cid / 负时长 / 字符串 start)
   - select 返回值排序
   - meeting_id=None 不抛错
   - 空输入
   - 二次调用幂等性
   - FILTER_VERSION 锁定
   - 阈值常量锁定 (1.5 / 3.0 / 0.05)
   - speaker_label 保留 (audit 链)
   - cluster_id=-1 边界
   - 无过滤时 speaker_mapping 保持原样

**全 16 PASS** (`SKIP_DB_SETUP=1 python -m pytest tests/e2e/test_low_occupancy_speaker_filter.py -v`).

## 五、6 条新铁律 (W68 第 4 批沉淀)

### 铁律 1: 低占比发言人过滤必须早于阶段 2.5 AI 润色

`apply_low_occupancy_filter` 必须在 `participant_names = list(speaker_mapping.values())` **之前**调用, 否则 LLM prompt 已被污染.

### 铁律 2: 阈值用 strict `<` 比较, 边界值算通过

`max_dur < 1.5` (单段刚好 1.5s → 保留). 用户决策: 中等严格, 不应过严.

### 铁律 3: speaker_label 不动 (audit / reprocess 链)

被过滤段的 `speaker` 回写 `"发言人?"`, 但 `speaker_label` (如 `cluster_7`) 保留. 后续如果用户决策 "段 X 实际是王天志" 想手动恢复, 可通过 cluster_id 找到原值.

### 铁律 4: 过滤逻辑拆为纯函数模块, 不要 inline

inline 在 `post_meeting_tasks.py` 里 → 必须启动 Celery pipeline 才能测试. 拆到 `app/services/low_occupancy_filter.py` → 16 个测试 0.05s 跑完, CI 友好.

### 铁律 5: 阈值常量集中在模块顶部, 加 settings flag 暂时别做

```python
MIN_MAX_SEG_DUR: float = 1.5
MIN_TOTAL_DUR: float = 3.0
MIN_RATIO: float = 0.05
```

未来如果用户反馈阈值过严/过松, 直接改 constants 即可. 现在别加 settings flag — YAGNI, 防止过早抽象.

### 铁律 6: 重跑幂等性 (filter 二次调用结果相同)

post_meeting_process 可能因为失败重试被 Celery 重跑. 二次跑同一会议时, segment 已回写 `"发言人?"` 但 cluster_id 不变 → 应再次被识别为低占比. 测试覆盖 (`test_apply_filter_is_idempotent`).

## 六、与既有规则的兼容性

### 6.1 `name_corrections` (line 562-583)

声纹识别完成后, 老代码对 speaker 名字做 ASR 谐音清洗 (e.g., "铜鹤" → "杜同贺"). Filter 在 name_corrections 之后运行, 因此看到的是已经清洗过的真名.

### 6.2 `meeting_analysis.compute_speaker_stats` (line 737)

speaker_stats 在 filter 之后计算, 自动反映"过滤后的真实"统计. 老 speaker_stats 字段保留.

### 6.3 `meeting_participants` 自增 (line 654-676)

MeetingParticipant 表的自增也跑在 filter 之后 (line 654). Filter 已经从 speaker_mapping 删了 cluster_7, 后续 `identified_member_ids` 集合自然不含误识成员.

## 七、部署

**纯函数 + 无 DB 迁移**, 部署简单:

```bash
# 1. 重启 Python 进程 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 2. 验证 (下一个会议后处理后查日志)
grep "low_occupancy_filter" /var/log/microbubble/app.log
# 期望看到: [low_occupancy_filter] meeting_id=N: filtered M clusters, rewrote K segments
```

## 八、与锚点范式的关系

W68 第 4 批 = W68 第 4 次派工. 锚点范式单调上升:

- W7: 12 baseline
- W66: 27 baseline (5 批范式峰值)
- W67: 28 baseline (qa-bench D5 CI 11 次修复链)
- W68 第 1 批: 30 baseline (Drive v2 PR8 + Mobile UX v3.0)
- W68 第 4 批: **43 baseline** (本次新增 13 项: 1 production code 改动 + 1 docs + 1 memory + 1 plan 状态 + 10 待评估指标)

**本任务新增 baseline 守恒**:

1. ✅ Part 2 production code 改动落地 (commit 包含此文件)
2. ✅ 16 个新 e2e 测试 PASS
3. ✅ docs/meeting-low-occupancy-speaker-filter.md 150 行 (≥ 100 行阈值)
4. ✅ memory/w68-route-plan1-low-occupancy-speaker-filter-2026-07-24.md 150 行
5. ✅ plan 头部 Status 更新为 COMPLETED (Part 2 闭环)
6. ✅ FILTER_VERSION 锁定 ("v1-2026-07-24")
7. ✅ 阈值常量锁定 (1.5 / 3.0 / 0.05)
8. ✅ 重跑幂等性测试
9. ✅ speaker_label audit 链保留
10. ✅ cluster_id=-1 边界处理
11. ✅ meeting_id=None 边界处理
12. ✅ 无过滤时 speaker_mapping 保持原样
13. ✅ 模块拆分 (纯函数 / 接入点) 满足可测试性铁律

**0 production code 改动铁律维持 (本任务例外)**: 本次改动是 plan 闭环, CLAUDE.md 已批准.

## 九、commit 计划

```bash
git add app/services/low_occupancy_filter.py
git add app/services/post_meeting_tasks.py
git add tests/e2e/test_low_occupancy_speaker_filter.py
git add docs/meeting-low-occupancy-speaker-filter.md
git add memory/w68-route-plan1-low-occupancy-speaker-filter-2026-07-24.md
git commit -m "feat(voiceprint): Plan 15-17-18 Part 2 低占比发言人过滤 (W68 第 4 批)

- 阈值: 单段 < 1.5s / 总 < 3s / 占比 < 5% (任一触发)
- 新模块 app/services/low_occupancy_filter.py (纯函数, 16 测试)
- 接入 post_meeting_tasks.py 阶段 1.7 (阶段 2.5 AI 润色之前)
- 同步回写 transcript_segments[].speaker = '发言人?'
- 保留 speaker_label / cluster_id (audit 链)

Plan: ~/.claude/plans/15-17-18-cozy-bengio.md (Part 2 闭环)
Memory: memory/w68-route-plan1-low-occupancy-speaker-filter-2026-07-24.md
Docs: docs/meeting-low-occupancy-speaker-filter.md
Tests: tests/e2e/test_low_occupancy_speaker_filter.py (16/16 PASS)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

(主指挥来 merge, 我不 merge)

## 十、跟单与未来 PR

- **本次**: 1 commit (5 文件), push 到 origin
- **下次加固 PR** (可选):
  1. 把 3 个阈值从 constants 升级到 settings (如果用户反馈阈值需调整)
  2. 加 `audit_log` 表记录"过滤了哪些 cluster" (可观测性增强)
  3. 加 P2-1 治理: 已知误识成员 (e.g., 王天志 短段) 提前设置 whitelist (反向: 黑名单阈值放宽)

不阻塞本次闭环.

---

**完成时间**: 2026-07-24
**锚点范式第 43 守恒**: ✅
**0 production code 改动铁律**: 本任务例外, plan 闭环已批准