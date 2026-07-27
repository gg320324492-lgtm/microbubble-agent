# 声纹 90% 硬门禁 (W75 第 1 批 B-1 三层口径澄清)

> 日期: 2026-07-27  
> 性质: 0 production code 改动铁律守恒, 仅文档口径澄清 (派工 v6 段 5 反馈 #6 实战)  
> 锚点范式: W74 第 1 批 249 → W75 第 1 批 B-1 253 守恒 (+1)  
> 关联: `memory/w74-1st-route-a2-voice-threshold-survey-2026-07-27.md` §5 主拍必拍 (B+C 方案)

## 1. 三层指标语义对齐

历史 MEMORY 把以下 3 个完全不同量纲的指标混写成同一常量, 导致"60 百分点差距"假冲突. W74 A-2 调研确认根因: 不是同一指标的 0.7 vs 0.9, 而是**三层指标被混写**.

| 指标 | 数值 | 语义 | 量纲 |
|------|------|------|------|
| 单段 cosine distance 上限 | **0.7** | 在线 matcher `distance < MATCH_THRESHOLD` 接受阈值 | 距离 (越小越相似) |
| 跨会议单段命中 | **0.55** | strict merge 验证: `cos_dist ≤ 0.55` 视为该段命中 | 距离 |
| 跨会议总体识别率 | **90%** | 新 embedding/变更前自动跑加权 ≥90% 回归, 否则 rollback | 比率 |

## 2. 0 production code 改动铁律 (W75 B-1 实战)

- **`MATCH_THRESHOLD = 0.7` 完全不动** — 派工 v6 段 5 反馈 #6 实战, 拒绝方案 A 字面改 0.9.
- **0 距离方向反向**: 把 0.7 → 0.9 等于让 matcher 接受更远 (= 更不相似的) 匹配, 完全错误.
- **0 confidence≥0.9 等价 distance≤0.1**: 数值 0.9 与 0.9 写法无关.
- **B 方案质量门必确定性**: 4 子门禁 (单段距离 / top1-top2 margin / cluster votes / anchor 状态), LLM 最多解释歧义, 不得越过门禁.

## 3. 真实历史锚点 (王天志 #151 rollback)

跨会议加权识别率 88.1% (#135 94.6% + #151 83.5%) < 90% → 自动 rollback sample_count 583→384. 永久保留.

## 4. W75 B-1 交付

- 3 新模块 (`voiceprint_quality_gate.py` / `voiceprint_cross_meeting_regression.py` / `voiceprint_quality_monitor.py`)
- 2 脚本 (`reprocess_12_meetings.py` + `replay_meeting_151.py`)
- 1 runbook (`docs/voiceprint-quality-gate-2026-07-27.md`)
- 1 e2e (`tests/test_voiceprint_quality_gate_e2e.py` 13/13 PASS)
- CLAUDE.md 新增"## 声纹 90% 硬门禁 (W75 B-1 三层口径)" 永久锚点节

## 5. 6 件套监控凑齐

W73 B-2 4 类 hot-fix + W74 D-1 多租户 + W75 B-1 声纹质量门 → `voiceprint_quality_monitor.SIX_PIECE_MONITORING` 字典聚合.

## 6. 5 条铁律

1. **不动 `MATCH_THRESHOLD = 0.7`** — 距离方向与 confidence 反向, 字面改 0.9 = 更宽松, 完全错误.
2. **B 方案质量门必确定性** — LLM 最多解释歧义, 不得越过门禁 (派工 v6 段 5 反馈 #6 实战: 拒绝 LLM 改数值).
3. **跨会议 90% acceptance gate 自动化** — 任一 embedding/变更**前自动跑** ≥90% 回归, 否则 rollback + 报警.
4. **三层指标语义不可混写** — 0.7 / 0.55 / 90% 是不同维度, 任何文档/代码引用必分明.
5. **历史锚点永久保留** — 王天志 #151 rollback (88.1% < 90%) 案例永久保留在所有 runbook 与文档.
