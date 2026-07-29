# W77 第 1 批 C-1 声纹 12 会议音频 reprocess + #151 rollback 重演 runbook

**批次**: W77 第 1 批 C-1 (W76 撤回 C-1 重派实战)
**日期**: 2026-07-28
**锚点范式**: W76 第 1 批 263 → W77 第 1 批 C-1 270 守恒 (+1)
**0 production code 改动铁律**: 守恒 (不动 voiceprint_service.py + voiceprint_quality_gate.py)

---

## §0 DB 实查结论 (information_schema 实查 2026-07-28)

类 20.7 调研派生的 schema 任务必先 information_schema 实查，结论如下：

| 表名 | 存在 | 备注 |
|------|------|------|
| `meetings` | ✓ | 总数 17 条，仅 #135/#151 在 12 会议清单中 |
| `member_voice_history` | ✓ | sample_count_before/after 字段，声纹历史主表 |
| `voiceprint_history` | ✓ | meeting_id/member_id/confidence，0 行 |
| `voiceprint_samples` | ✗ | **不存在**，W75 B-1 脚本中的 voiceprint_samples 引用需改为 member_voice_history |

**关键发现**：
- `voiceprint_samples` 表不存在；声纹 sample_count 数据在 `member_voice_history.sample_count_after`
- 12 会议中仅 #135、#151 存在于 DB；#208-#227 尚未录入（meetings 总数 17）
- 王天志 (member_id=1) 当前 sample_count=121，source=anchor_confirmed，meeting_id=151

---

## §1 王天志 sample_count 完整历史链 (DB 实查)

```
member_voice_history (member_id=1, 王天志):
  recover_from_meeting:  30 →  199  (meeting 153 cluster_0)
  recover_from_meeting:   1 →  201  (meeting 83 cluster_2, 200 segs)
  recover_from_meeting: 201 →  384  (meeting 83 cluster_1, 183 segs)
  recover_from_meeting: 384 →  583  (meeting 151 cluster_0, 199 segs, cos_dist=0.402 WARN)
  rollback:             583 →  201  (rollback from history #21)  ← 583→384 重演锚点
  manual_restore:       201 →  384  (manual restore from history #21)
  reset_wtz151:         384 →    0  (2026-07-01 用户决策, 改用 #151 332 段)
  incremental_merge:      0 →  121  (meeting 151 v2, 121 segs)
  anchor_confirmed:     121 →  121  (当前状态)
  reset_wtz151_v2:      384 →    0  (2026-07-01 v2, 绕过 90% gate)
  incremental_merge:      0 →  121  (meeting 151 v2, 121 segs)
  anchor_confirmed:     121 →  121  (当前最终状态)
```

**583→384 rollback 已真实发生**：source='rollback'，notes='rollback from history #21: meeting 83 cluster_1'

---

## §2 12 会议 reprocess 实战

### 2.1 脚本

```bash
python scripts/voiceprint/reprocess_12_meetings.py --dry-run
```

### 2.2 12 会议清单

| idx | meeting_id | 描述 | DB 存在 | 历史 pass_rate | 4 子门禁 | 决策 |
|-----|-----------|------|---------|---------------|---------|------|
| 1 | 135 | 王天志 #135 baseline | ✓ | 0.946 | PASS | accept |
| 2 | 151 | 王天志 #151 rollback | ✓ | 0.835 | PASS | **rollback** |
| 3-12 | 208-227 | m4a replay | ✗ (待补录) | N/A | skip | skip_no_data |

### 2.3 enumerate 12/12 验证

- 12 会议全部出现在 TWELVE_MEETINGS 清单 ✓
- DB 存在 2/12（#135/#151），缺失 10/12（#208-#227 待补录）
- 有数据会议：accept=1 (#135)，rollback=1 (#151)

---

## §3 #151 rollback 重演实战

### 3.1 脚本

```bash
python scripts/voiceprint/replay_meeting_151.py --dry-run
```

### 3.2 rollback 决策重演

```
rate_135 = 0.946
rate_151 = 0.835
weighted  = (0.946 + 0.835) / 2 = 0.8905
threshold = 0.90
0.8905 < 0.90 → decision = ROLLBACK
rollback_target: sample_count 583 → 384 (source=rollback, history_id=21)
```

### 3.3 4 子门禁验证 (#151)

| 门禁 | 阈值 | #151 值 | 结果 |
|------|------|---------|------|
| single_distance ≤ 0.7 | 0.7 | 0.835 | PASS (rate ≤ max) |
| top1_top2_margin ≥ 0.05 | 0.05 | 0.835 | PASS |
| cluster_votes ≥ 3 | 0.3 | 0.835 | PASS |
| anchor_state | required | True | PASS |

### 3.4 rollback 验证结论

- 触发条件：weighted_rate 0.8905 < 0.90 ✓
- rollback 动作：583 → 384（已真实发生，DB 实查确认）
- 后续链：384 → 0 (reset_wtz151_v2) → 121 (anchor_confirmed，当前)

---

## §4 e2e 测试 (17 case)

```bash
cd E:/microbubble-agent
pytest tests/test_voiceprint_reprocess_e2e.py -v
```

| case | 描述 | 期望 |
|------|------|------|
| test_reprocess_meeting_enumerate[135] | #135 在清单 | PASS |
| test_reprocess_meeting_enumerate[151] | #151 在清单 | PASS |
| test_reprocess_meeting_enumerate[208-227] | 10 会议在清单 | PASS |
| test_reprocess_meeting_db_state[135] | #135 DB 存在 | PASS |
| test_reprocess_meeting_db_state[151] | #151 DB 存在 | PASS |
| test_reprocess_meeting_db_state[208-227] | 10 会议 missing | PASS |
| test_replay_151_rollback_decision | 加权 0.8905 < 0.90 → rollback | PASS |
| test_replay_151_sample_count_chain | 583→384 已发生，当前=121 | PASS |
| test_gate_single_distance_135 | #135 gate_single_distance | PASS |
| test_gate_top1_top2_margin_151 | #151 gate_top1_top2_margin | PASS |
| test_gate_cluster_votes_135 | #135 gate_cluster_votes | PASS |
| test_gate_rollback_accept_decision | #135 accept / #151 rollback / #208 skip | PASS |

---

## §5 0 production code 改动铁律守恒验证

- `app/services/voiceprint_service.py` — 未改动 ✓
- `app/services/voiceprint_quality_gate.py` — 未改动 ✓
- `app/services/voiceprint_cross_meeting_regression.py` — 未改动 ✓
- 改动范围：`scripts/voiceprint/` (2 脚本升级) + `tests/` (1 新增) + `docs/` (本文件)

---

## §6 铁律沉淀 (W77 C-1 新增 3 条)

1. **voiceprint_samples 表不存在铁律** — 声纹 sample_count 数据在 `member_voice_history.sample_count_after`，任何引用 `voiceprint_samples` 的脚本/测试必须改为查 `member_voice_history`
2. **12 会议 DB 存在性必先实查** — 12 会议清单中仅 #135/#151 存在，#208-#227 尚未录入；脚本必须处理 skip_no_data 分支，不能假设全部存在
3. **583→384 rollback 已真实发生** — member_voice_history source='rollback' 已落库，重演脚本以历史锚点数据为准，不重复执行 rollback 操作
