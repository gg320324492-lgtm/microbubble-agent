# W2-4 声纹 12 会议 acceptance gate 复演（2026-08-04）

## 1. 结论

**PASS (with WARN)**

- **测试**: 43/43 PASS（voiceprint_quality_gate_e2e 13 case + voiceprint_reprocess_e2e 30 case）
- **Acceptance gate 按段数加权**: **0.9007 (90.07%)** — 跨过 0.90 门禁线，落入 `user_decide` 区
- **0 production code diff**：voiceprint_service / quality_gate / cross_meeting_regression / quality_monitor 全部不变
- **三层指标 0.7 / 0.55 / 0.90 守恒**

## 2. 关键数字（三口径）

| 口径 | 数值 | 解读 |
|------|------|------|
| 按段数加权 (#135 583 段 + #151 384 段) | **0.9007 (90.07%)** | 跨 0.90 门禁线, user_decide 区 |
| e2e 简单算术平均 | 0.8905 (89.05%) | 仍 rollback 决策, 守恒 |
| 历史锚点 CLAUDE-history.md | 0.881 (88.1%) | +1.97pp 漂移, 需 reconcile |

## 3. WARN 列表

1. **10/12 会议无 DB 数据**（#208-#216 + #227）—— 完整 12 会议复演未真跑；仅 #135 + #151 真复演
2. **88.1% 锚点漂移** —— 与当前加权 90.07% 不一致，需主拍 reconcile
3. **user_decide 区** —— 90.07% 落在 0.90-0.92 区间，当前 `aggregate_cross_meeting_rate` 推荐 `next_action="require_user_decision"`

## 4. Acceptance gate 触发逻辑守恒

- 单段距离阈值: 0.7
- 跨会议命中阈值: 0.55
- 总体识别率门禁: 0.90

三层指标语义分明（在线 matcher / 跨会议命中 / 跨会议总体），0 diff，未擅自放宽。

## 5. 后续建议

- 主拍对 90.07% user_decide 区决策：直接接受 / 调阈值 / 重做 embedding / 接受现状
- 补 #208-#216 + #227 真实 audio 数据后，再做一次完整 12 会议 acceptance gate
- reconcile CLAUDE-history.md 88.1% 锚点漂移

## 6. 测试覆盖

| 套件 | case | 状态 |
|------|------|------|
| voiceprint_quality_gate_e2e.py | 13 | PASS |
| voiceprint_reprocess_e2e.py | 30 | PASS |
| 合计 | 43 | 0 FAILED / 0 SKIPPED |

mock fixture 100% 覆盖 12 会议 enumerate + 12 DB state + #151 rollback re-enact + 4 子门禁监控。

## 7. 关联沉淀

- `app/services/voiceprint_cross_meeting_regression.py` (REPROCESS_12_MEETINGS + aggregate_cross_meeting_rate)
- `app/services/voiceprint_quality_gate.py` (4 子门禁 GATE_SINGLE_DISTANCE_MAX=0.7 / GATE_TOP1_TOP2_MARGIN_MIN=0.05 / GATE_CLUSTER_VOTES_MIN=3 / CROSS_MEETING_THRESHOLD=0.90)
- `tests/test_voiceprint_quality_gate_e2e.py` + `tests/test_voiceprint_reprocess_e2e.py`
