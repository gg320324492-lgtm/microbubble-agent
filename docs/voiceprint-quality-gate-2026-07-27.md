# 声纹 B+C 方案 Runbook (W75 第 1 批 B-1)

> 日期: 2026-07-27  
> 性质: B+C 方案完整 runbook (确定性渐进质量门 + 文档口径修正)  
> 依据: A-2 W74 调研 §5 主拍必拍 (B+C 方案, 拒绝方案 A 字面改 0.9)  
> 锚点范式: W74 第 1 批 249 → W75 第 1 批 B-1 253 守恒 (+1)  
> 0 production code 改动铁律守恒: `app/services/voiceprint_service.py` 老 `MATCH_THRESHOLD = 0.7` 不动

## 0. 三层指标口径澄清 (C 方案核心)

历史 MEMORY 把 `0.7 / 0.55 / 90%` 混写成同一常量, 这是"60 百分点差距"假冲突的真根因. 本 runbook 把三层指标语义边界明确固化:

| 指标 | 数值 | 语义 | 代码锚点 |
|------|------|------|---------|
| 单段 cosine distance 上限 | **0.7** | 在线 matcher 接受阈值 (`<MATCH_THRESHOLD>` 才返回成员) | `app/services/voiceprint_service.py:26` **不动** |
| 跨会议单段命中 | **0.55** | strict merge 验证: `cos_dist ≤ 0.55` 视为该段命中 | `docs/CLAUDE-history.md:5459-5464` |
| 跨会议总体识别率 | **90%** | 新 embedding/变更前自动跑 ≥90% 回归, 否则 rollback | `app/services/voiceprint_cross_meeting_regression.py` |

### 派工 v6 段 5 反馈 #6 实战 (错误方案 A 反思)

**方案 A 字面改 MATCH_THRESHOLD=0.9 的两个致命错误**:

1. **距离方向与 confidence 反向**: 0.7 是 cosine **距离**上限 (越小越相似). 把 0.7 改成 0.9 等于让 matcher 接受距离更大 (= 更不相似的) 匹配, 完全反向错误.
2. **若目标是 confidence≥0.9**: 应等价于 distance≤0.1 (因为 confidence = 1 - distance). 这与 0.9 数值无任何关系.

**B+C 方案实战态度**:

- **B 方案**: 引入确定性渐进质量门 (4 子门禁), LLM 最多解释歧义, **不得**越过门禁. 不靠 LLM 改数值.
- **C 方案**: 只修文档/MEMORY 口径, 明确三层指标量纲不同. 0 production code 改动铁律守恒.

**真实历史锚点** (王天志 #151 rollback): #135 94.6% + #151 83.5% → 加权 88.1% < 90% → 自动 rollback sample_count 583→384. 这是 acceptance gate 真实执行证据, 永久保留在案.

## 1. B 方案: 确定性渐进质量门 (4 子门禁)

### 1.1 子门禁定义

| # | 名称 | 阈值 | 公式 | 代码 |
|---|------|------|------|------|
| 1 | 单段距离门禁 | ≤ 0.7 | `cosine_dist ≤ SINGLE_DISTANCE_MAX` | `voiceprint_quality_gate.evaluate_single_distance_gate` |
| 2 | top1-top2 margin 门禁 | ≥ 0.05 | `top2_distance - top1_distance ≥ TOP1_TOP2_MARGIN_MIN` | `voiceprint_quality_gate.evaluate_top1_top2_margin_gate` |
| 3 | cluster votes 门禁 | ≥ 3 | `votes ≥ CLUSTER_VOTES_MIN` (跨会议累积) | `voiceprint_quality_gate.evaluate_cluster_votes_gate` |
| 4 | anchor 状态门禁 | True | `voice_confirmed_at IS NOT NULL` (CLAUDE.md v60-v67 永久锚点) | `voiceprint_quality_gate.evaluate_anchor_state_gate` |

注意: 距离语义是 "越小越相似", 因此 margin 应为 `top2 - top1` (差距越大越能区分), **不是** `top1 - top2`. 测试 case_03 真验证此语义.

### 1.2 4 子门禁评估总流程

```python
from app.services.voiceprint_quality_gate import (
    evaluate_quality_gate,
    CandidateScore,
    should_rollback,
)

candidates = [
    CandidateScore(member_id=42, member_name="王天志", distance=0.40, votes=5,
                   is_anchor=True, voice_confirmed_at=datetime.now()),
    CandidateScore(member_id=99, member_name="其他", distance=0.60, votes=3,
                   is_anchor=True, voice_confirmed_at=datetime.now()),
]
result = evaluate_quality_gate(candidates)
if should_rollback(result):
    # 任一子门禁失败 → rollback
    return await voiceprint_service.rollback_to_previous_embedding(member_id=42)
```

### 1.3 综合评估: 全部通过才确认成员

- 任一子门禁失败 → `rollback_recommended = True` (W74 D-1 派工 v6 段 5 反馈 #7 实战).
- 全部 4 子门禁通过 → `passed = True`, `rollback_recommended = False`, 返回 top1 候选.

## 2. B 方案核心: 跨会议 90% regression gate

### 2.1 自动化 acceptance gate

```python
from app.services.voiceprint_cross_meeting_regression import (
    compute_meeting_recognition_rate,
    aggregate_cross_meeting_rate,
)

reports = []
for mid, title in REPROCESS_12_MEETINGS:
    distances = await voiceprint_service.extract_distances_for_meeting(mid)
    reports.append(compute_meeting_recognition_rate(mid, title, distances))

result = aggregate_cross_meeting_rate(reports)
if result.rollback_recommended:
    await voiceprint_service.rollback_to_previous_embedding_and_alert()
elif result.decision_band == "user_decide":
    await prompt_user_for_decision(result)
else:
    await voiceprint_service.commit_new_embedding()
```

### 2.2 三段决策表

| 加权识别率 | decision_band | rollback_recommended | next_action |
|-----------|---------------|---------------------|-------------|
| `< 0.90` | `rollback` | True | `rollback_to_previous_embedding_and_alert` |
| `[0.90, 0.92)` | `user_decide` | False | `require_user_decision` |
| `≥ 0.92` | `accept` | False | `commit_new_embedding` |

> 注: 历史锚点 90-95% 是 MEMORY 区间, 实现层采用 0.90-0.92 (避免 LLM "略低于 90% 仍可通过" 灰色地带).

### 2.3 12 会议音频样本池 (W73 A-2 调研实战)

`REPROCESS_12_MEETINGS`: 135, 151, 208-216, 227 — 必含 #151 rollback 重演.

### 2.4 真实历史锚点 (王天志 #151 rollback)

```python
HISTORICAL_CASE_WANG_TIANZHI = {
    "name": "王天志",
    "meeting_135_rate": 0.946,
    "meeting_151_rate": 0.835,
    "weighted_overall_rate": 0.881,
    "decision": "rollback",
    "rollback_target": "sample_count 583 → 384",
}
```

详见 `docs/CLAUDE-history.md:5483-5492`.

## 3. 12 会议音频 reprocess + #151 rollback 重演 (实战脚本)

### 3.1 reprocess_12_meetings.py

```bash
# dry-run (仅打印任务清单, 不实际 reprocess)
python scripts/voiceprint/reprocess_12_meetings.py --dry-run

# real-run (接入 voiceprint_service.reprocess_meeting, 不在本 runbook 范围)
python scripts/voiceprint/reprocess_12_meetings.py
```

### 3.2 replay_meeting_151.py

```bash
# dry-run
python scripts/voiceprint/replay_meeting_151.py --dry-run
```

### 3.3 期望结果

- reprocess 12/12 完成 + 加权跨会议识别率 ≥ 90% → 全局 accept
- #151 rollback 重演: 期望 meeting_151_rate ≈ 0.835, 加权 ≈ 0.881 < 90% → rollback

## 4. 质量门禁实时监控 (凑齐 6 件套)

### 4.1 Celery beat schedule 30 分钟

```python
from app.services.voiceprint_quality_monitor import build_celery_beat_schedule_entry

celery_app.conf.beat_schedule.update(build_celery_beat_schedule_entry())
# 入口: app.services.voiceprint_quality_monitor.run_quality_gate_monitor
```

### 4.2 6 件套监控凑齐

| 来源 | 名称 | 周期 |
|------|------|------|
| W73 B-2 | 4 类 hot-fix 监控 | 3600s |
| W74 D-1 | 多租户监控 | 3600s |
| W75 B-1 (本 runbook) | 声纹质量门监控 | 1800s (30min) |

## 5. 部署必做 (新模块 production 化)

### 5.1 镜像打包

无 alembic migration, 无 frontend 改动. 仅后端新模块 + 新 e2e. 打包已包含在主镜像内.

### 5.2 Celery beat 重启

新 module 在 `app/services/voiceprint_quality_monitor.py` 注册了 Celery task. **必跑**:

```bash
docker compose restart app celery-worker celery-beat
```

### 5.3 验证

```bash
# 1. e2e 13/13 PASS
SKIP_DB_SETUP=1 python -m pytest tests/test_voiceprint_quality_gate_e2e.py -v

# 2. 12 会议 reprocess dry-run
python scripts/voiceprint/reprocess_12_meetings.py --dry-run

# 3. #151 rollback replay dry-run
python scripts/voiceprint/replay_meeting_151.py --dry-run

# 4. 验证 MATCH_THRESHOLD=0.7 未动
grep -n "MATCH_THRESHOLD = " app/services/voiceprint_service.py
# 期望: 26:MATCH_THRESHOLD = 0.7

# 5. 监控入口可达
docker exec microbubble-agent-app-1 python -c "
from app.services.voiceprint_quality_monitor import build_celery_beat_schedule_entry
import json; print(json.dumps(build_celery_beat_schedule_entry(), indent=2))
"
```

## 6. 4 类 hot-fix 链预案 (B 方案生产化)

| hot-fix 触发 | 处理动作 | 代码位置 |
|-------------|---------|---------|
| `voiceprint_service.MATCH_THRESHOLD` 被修改 | 立即报警 + 启动 git revert | `app/services/voiceprint_service.py:26` |
| 4 子门禁任一参数被 LLM 改写 | 立即 rollback LLM 调用 + 报警 | `voiceprint_quality_gate.py:24-28` |
| 跨会议回归未跑就 commit | 拦截 commit + 报警 | `voiceprint_cross_meeting_regression.py` |
| 监控 6 件套缺失 | 报警 + 强制恢复 | `voiceprint_quality_monitor.SIX_PIECE_MONITORING` |

## 7. 锚点范式守恒

- **W74 第 1 批 249** (W74 grand closure) → **W75 第 1 批 B-1 253 守恒** (+1, 0 regression).
- **0 production code 改动铁律 守恒**: 仅新增 3 module + 2 script + 1 runbook + 1 e2e + CLAUDE.md 添加 1 节.
- **6 件套监控守恒**: W73 B-2 + W74 D-1 + W75 B-1 全部纳入 `SIX_PIECE_MONITORING` 字典聚合.

## 8. 5 条铁律 (W75 B-1 永久沉淀)

1. **不动 `MATCH_THRESHOLD = 0.7`** — 派工 v6 段 5 反馈 #6 实战, 距离方向与 confidence 反向, 字面改 0.9 = 更宽松, 完全错误.
2. **B 方案质量门必确定性** — LLM 最多解释歧义, 不得越过门禁 (派工 v6 段 5 反馈 #6 实战: 拒绝 LLM 改数值).
3. **跨会议 90% acceptance gate 自动化** — 任一 embedding/变更**前自动跑** ≥90% 回归, 否则 rollback + 报警. 不靠人工执行.
4. **三层指标语义不可混写** — 0.7 (distance) / 0.55 (hit) / 90% (cross-meeting) 是不同维度, 任何文档/代码引用必分明.
5. **历史锚点永久保留** — 王天志 #151 rollback (88.1% < 90%) 案例是 acceptance gate 真实执行证据, 必须出现在所有 runbook 与文档.

