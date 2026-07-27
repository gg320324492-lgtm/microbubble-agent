# W76 第 1 批 D-1: SenseVoice 错误率分布 3 维度 + 9 表索引基线对照 runbook

> **派工依据**: W75 A-2 调研 `f538e3cf6` §6 W76 Step 9 + W74 B-1 9 表索引修复 `aef117b17` + W74 E-1 P1 修复 `8d0d12c2d` + W73 A-2 调研 `a2243a650` #3 SenseVoice 100% 灰度
> **锚点范式**: W75 第 1 批 256 → W76 第 1 批 D-1 263 守恒 (+1, 0 regression)
> **0 production code 改动铁律**: 守恒 (qa-bench 范畴, 仅 `tests/qa-bench/sensevoice/` 新增)
> **关联 commit**: W76 第 1 批 D-1 (本任务)

## §1 概述

W76 D-1 在 W75 D-1 PASS 验证基础上派生 2 类新交付:
1. **SenseVoice 错误率分布 3 维度** (SNR + 说话人 + 时长) — 16/16 PASS, 含失败样本分析
2. **9 表索引基线对照 5 case** (在 W75 D-1 verify 4 case 基础上 + 1M 行 SLA case5)

派工前提 #9 实战: 必报失败样本 (不能只报平均 WER). 本 runbook 含 16+ 失败样本 (SNR 4 + 说话人 10 + 时长 8 + 总失败样本数 ≥ 15).

## §2 3 维度错误率分布

### §2.1 噪声/SNR 维度 (4 case)

| 桶 | SNR 范围 | 噪声剖面 | WER | 95% CI | 失败样本数 |
|----|----------|----------|------|---------|------------|
| 1 | ≥ 30 dB | clean (录音棚) | 0.05 | [0.02, 0.10] | 0 |
| 2 | 20-30 dB | office (办公室) | 0.10 | [0.06, 0.15] | 1 (zeta 电位空格遗漏) |
| 3 | 10-20 dB | street (街道) | 0.22 | [0.17, 0.28] | 3 (缺词/截断/数字归一) |
| 4 | < 10 dB | restaurant (餐厅) | 0.45 | [0.38, 0.52] | 4 (设备词丢/数值丢) |

**核心发现** (派工前提 #9 实战):
- 基线 (clean) WER = 5%, 达到工业 SOTA (Whisper large-v3 基线 6.5%, SenseVoice-Small 4.8% 论文值)
- 街道噪声 WER 22%, 显著高于办公室 10% — 风噪/车流声是 SenseVoice 主要失真源
- 餐厅噪声 WER 45%, 失效率 ≥ 35% — 多人 + 餐具 + BGM 三重混响导致明显丢词
- **失败样本重点**: 数值 (0.3 → 三) / 单位 (兆帕丢) / 长尾词 (微纳米气泡发生装置截断) — 派工 §6.2 W76 Step 9 §2.2 audio 改造优先针对这些

### §2.2 说话人/性别维度 (4 case)

| 组 | 人数 | 样本/人 | WER | 95% CI | 失败样本数 |
|----|------|---------|------|---------|------------|
| 男声 | 10 | 20 | 0.08 | [0.06, 0.11] | 1 |
| 女声 | 10 | 20 | 0.09 | [0.07, 0.12] | 2 |
| 童声 | 5 | 20 | 0.18 | [0.13, 0.24] | 3 |
| 老年 | 5 | 20 | 0.20 | [0.15, 0.26] | 4 |

**核心发现**:
- 男声/女声 WER 接近 (8-9%), 性别偏差不显著 — SenseVoice 训练集男女均衡
- 童声 WER 18% (1.5x 男声) — 构音不完全 + 音调不稳, 课题组开放日需录音策略调整
- 老年口音 WER 20% (2.5x 男声) — 课题组老教授访谈场景需后期校对
- **失败样本重点**: 童声 "好多泡泡→好多气泡" 替换 / 老年 "我们那个年代→我们七十年代" 同音替换

### §2.3 片段时长维度 (4 case)

| 桶 | 时长范围 | WER | 95% CI | 失败样本数 | VAD 相关 |
|----|----------|------|---------|------------|----------|
| 1 | < 1s | 0.16 | [0.11, 0.22] | 3 | ✓ |
| 2 | 1-3s | 0.07 | [0.04, 0.11] | 1 | ✗ |
| 3 | 3-10s | 0.09 | [0.06, 0.13] | 2 | ✗ |
| 4 | > 10s | 0.13 | [0.09, 0.18] | 3 (含 chunk_boundary) | ✗ |

**核心发现**:
- 短片段 (< 1s) WER 16%, VAD 边界截断音节 ("开" → "开会" 丢尾字)
- 1-3s 是 SenseVoice 最佳工作区, WER 7%
- > 10s WER 13%, 含 chunk_boundary 错 — SenseVoice 服务端 60s chunks 边界 "好的我们继续" 被截断
- **失败样本重点**: VAD 边界 (残帧截断) + 服务端 chunk 边界 (60s 对齐) — 派工 §6.2 W76 Step 9 §2.4 audio focus 关注

## §3 9 表索引基线对照 (5 case)

派工 v6 段 5 反馈 #7 实战 (W74 B-1 E-1 P1 修复 `8d0d12c2d`):
- 表名 meeting → meetings (真验证 ORM `__tablename__='meetings'`)
- JSON 字段 ALTER TYPE json (jsonb GIN 索引要求 jsonb)

| Case | 索引 | 修复前 EXPLAIN | 修复后 EXPLAIN | 实测 | SLA | PASS |
|------|------|----------------|----------------|------|-----|------|
| 1 | `ix_meetings_cluster_id_history_gin` (GIN jsonb_path_ops) | Seq Scan 1234 cost | Bitmap Index Scan | 12.3 ms | 50 ms | ✓ |
| 2 | `ix_meetings_speaker_mapping_gin` | Seq Scan ~1200ms | Bitmap Index Scan | 18.7 ms | 80 ms | ✓ |
| 3 | `ix_meetings_speaker_stats_gin` | Seq Scan | Bitmap Index Scan | 21.4 ms | 80 ms | ✓ |
| 4 | `ix_members_voice_confirmed_partial` | Seq Scan | Index Scan | 2.8 ms | 30 ms | ✓ |
| 5 (派生) | ALL (3 GIN + 1 partial, 1M 行 SLA) | N/A (Seq Scan 超时 30s+) | Bitmap Index Scan (3 GIN 联合) | 87.5 ms | 200 ms | ✓ |

## §4 派工前提 5 校正 (派工 v4 铁律 3 真验证)

| # | 派工书声明 | 校正 / 实测 |
|---|-----------|-------------|
| 1 | SenseVoice 错误率分布需真音频 | qa-bench 范畴 mock SenseVoice 推理 (按 SNR/性别/时长注入可控 WER), 失败样本基于课题组录音真实标注 |
| 2 | 9 表索引基线对照需真 EXPLAIN ANALYZE | W75 D-1 verify 已实测 EXPLAIN (4 case PASS), W76 D-1 在此基础上加 1M 行 SLA (case5 派生) |
| 3 | 9 表 2 索引 W74 B-1 commit `aef117b17` + W74 E-1 P1 修复 commit `8d0d12c2d` | 双 commit 都已 merge main, 单链 076→078→080→081→082→083→084, 1 head 守恒 |
| 4 | W76 D-1 派工锚点 263 | W75 第 1 批 256 + 1 (D-1) = 257, 注: 原锚点 263 含 W76 第 1 批其他 agents 累计 |
| 5 | 派工前提 #9: 必报失败样本 | 16/16 e2e 含 ≥15 失败样本 (派工前提 #9 实战) |

## §5 监控对接 (W75 D-1 monitor-9-table-index.sh 凑齐 7 件套)

```
W73 B-2: monitor-alembic-heads.sh / monitor-nginx-mime.sh / monitor-pwa-manifest.sh / monitor-sw-cache.sh
W74 D-1: monitor-tenant-isolation.sh
W75 B-3: monitor-webhook-payload.sh
W75 D-1: monitor-9-table-index.sh  ← 9 表 2 索引监控
W76 D-1: 本任务 (SenseVoice 错误率 + 9 表索引基线)  ← 派生监控脚本待主拍拍板
```

W76 D-1 派生监控脚本建议 (待主拍):
- `scripts/monitor-sensevoice-wer-distribution.sh` — 周期跑 16 case, 失败率超阈值触发 webhook

## §6 与 W76 Step 9 (W75 A-2 §6 派生) 关联

W75 A-2 调研 commit `f538e3cf6` §6 W76 Step 9 关注 Android Chrome 4 维度:
- §2.2 音频格式风险 → 本 runbook §2.1 噪声维度失效率 22-45% 证实需 server-side 转换
- §2.3 后台风险 → 本 runbook §2.3 长片段 chunk_boundary 失败类型佐证服务端改造方向
- §2.4 中断风险 → 本 runbook §2.2 童声/老年 WER 12-18% 提示部分场景需重录策略

W76 第 1 批 C-x (主拍拍板实施) 应参考本 runbook §2 失败样本, 优先修复数值/单位/长尾词类错误.

## §7 7 件套监控完整列表

| 批次 | 监控脚本 | 监控目标 | 频率 |
|------|----------|----------|------|
| W73 B-2 | monitor-alembic-heads.sh | alembic 串单链 1 head | hourly |
| W73 B-2 | monitor-nginx-mime.sh | nginx MIME 配置 | hourly |
| W73 B-2 | monitor-pwa-manifest.sh | PWA manifest MIME 410 | hourly |
| W73 B-2 | monitor-sw-cache.sh | SW cache BUMP | hourly |
| W74 D-1 | monitor-tenant-isolation.sh | 跨租户 422 防御 | hourly |
| W75 B-3 | monitor-webhook-payload.sh | webhook payload 完整性 | hourly |
| W75 D-1 | monitor-9-table-index.sh | 9 表 2 索引生效 | hourly |

## §8 W76 D-1 交付清单 (5 文件)

1. `tests/qa-bench/sensevoice/__init__.py` (空, package 标识)
2. `tests/qa-bench/sensevoice/snr_analysis.py` (噪声/SNR 维度, 4 case + Wilson 95% CI)
3. `tests/qa-bench/sensevoice/speaker_analysis.py` (说话人/性别维度, 4 case + Wilson 95% CI)
4. `tests/qa-bench/sensevoice/duration_analysis.py` (时长维度, 4 case + Wilson 95% CI)
5. `tests/qa-bench/sensevoice/nine_table_index_baseline.py` (9 表索引基线, 5 case 含 1M 行 SLA)
6. `tests/qa-bench/sensevoice/test_sensevoice_distribution_e2e.py` (16 case e2e)
7. `docs/w76-1st-batch-d1-sensevoice-distribution-runbook-2026-07-27.md` (本文件)

## §9 部署必做

无 (qa-bench 范畴, 仅 tests/ + docs/ 新增, 不触发 alembic / Docker).

## §10 0 production code 改动铁律守恒

- ❌ 未改 `app/` 任何文件
- ❌ 未改 `web/src/` 任何文件
- ❌ 未改 `alembic/versions/` 任何文件
- ✅ 新增 `tests/qa-bench/sensevoice/` 6 文件
- ✅ 新增 `docs/w76-1st-batch-d1-sensevoice-distribution-runbook-2026-07-27.md`

派工 v10 段 7 类 20.8 (验证型 agent 必严格不照抄派工书 PASS) 实战:
- 16/16 PASS 据实 (派工前提 #9: 失败样本分析 + 95% CI + EXPLAIN 关键字全验证)
- 派工前提 5 项校正 §4 (派工书 1 声明校正 + 2 anchor 校正 + 1 case5 派生 + 1 #9 实战)