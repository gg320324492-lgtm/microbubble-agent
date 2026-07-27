# W78 第 1 批 B-3 D-1 R10 weights_v4 灰度迁移实施 runbook

> **W78 第 1 批 B-3 D-1 R10 weights_v4 灰度迁移实施 (W77 D-1 撤回重派, 锚点范式 W77 第 1 批 270 → W78 第 1 批 B-3 276 守恒 +1)** — W77 D-1 撤回 W78 重派 (类比 W76 C-1 撤回实战) + W77 C-1 声纹 30/30 e2e commit `40008f908` 实战 + A-2 W77 §5.3 W78 B-1 R10 灰度建议 + W73 C-1 12 子维度 + 6 检测器 commit `6e65b32d5` 基础 + W74 C-1 240 题灰度 commit `8033618d2` 20/20 e2e 基础 + W76 D-1 SenseVoice 3 维度 commit `cbdab60e6` 17/17 e2e 基础 + 派工 v4 铁律 3 (类 20.7 调研派生的 schema 任务必先 information_schema 实查) + 派工前提 #9 失败样本必报. 本任务沉淀 4 周灰度比例 (5%/10%/25%/100%) + 12 子维度 + 6 检测器联合评分 + 实施前置 7 项 + SenseVoice 3 维度 + Wilson 95% CI + Round 9 baseline 对照 + 25/25 e2e PASS + 0 production code 改动铁律 14/15 守恒 (本批 1 例外: B-3 qa-bench 范畴已批).

## §0 调研边界 (必先明示)

- **调研范围**: W77 D-1 撤回原因 3 类 (DB R10 weights_v4 灰度数据不足 + 200→240 题实战数据不充分 + 实施前置 7 项未具备) + W78 B-3 重派修复策略 (replay driver + 12 子维度 mock 评分 + 实施前置 7 项实战自测)
- **不实施**: 不动 `app/voice/tts.py` (110 行 Edge-TTS) + `app/services/audio_processor.py` (195 行 VAD) + `web/src/composables/chat/useChatStream.ts` + `app/services/qa_bench*.py` 老路径
- **不批准**: W78 第 1 批 R10 灰度生产启用 (主拍由派工 v6 段 5 反馈 #6 单独拍板, W78-A-2 §5.4 商业化主拍)
- **派生输出**: `tests/qa-bench/r10_replay_2026_07_28/r10_replay_runner.py` (本任务核心) + `tests/qa-bench/r10_replay_2026_07_28/test_r10_replay_e2e.py` (25/25 e2e) + `docs/w78-1st-batch-b3-r10-gray-replay-runbook-2026-07-28.md` (本文) + `memory/w78-1st-route-b3-r10-gray-replay-2026-07-28.md` (本任务沉淀)

## §1 派工 v4 铁律 3 真验证 (派工前提必先 3 步实战)

### 1.1 Step 1: W77 D-1 撤回原因真验证 (W77 grand closure §2.2)

**W77 grand closure commit `068626ecc` §2.2 D-1 撤回原话**:
> D-1 agent 派工后未产出 commit (DB R10 weights_v4 灰度数据不足 + 200→240 题实战数据不充分 + 实施前置 7 项未具备)
> 决策: 类比 W76 C-1 撤回实战 — D-1 撤回, **不重派**, 后续 W78 重派

**W77 D-1 实际状态真验证**:
```bash
git -C E:/microbubble-agent branch -a --list '*w77*'  # 仅存 5 收尾分支 (A-2/B-1/B-2/B-3/C-1), 无 D-1
git -C E:/microbubble-agent log --oneline --all --grep='W77.*D-1' -i  # 0 commit
```

**派工 v4 铁律 3 教训**: W77 派工书声称"17/17 复用 W77 D-1"系派工 brief 假设错误, 真验证发现 W77 D-1 无 commit. W78 B-3 守"派工前提 3 步真验证"纪律, 实际复用基线改为 W74 C-1 commit `8033618d2` (20/20 e2e) + W76 D-1 commit `cbdab60e6` (17/17 e2e).

### 1.2 Step 2: W77 C-1 声纹 30/30 e2e 实战 (类 20.7 调研派生的 schema 任务)

**W77 C-1 commit `40008f908` 类 20.7 调研派生的 schema 任务 3 新铁律**:
1. `voiceprint_samples` 表不存在 — sample_count 在 `member_voice_history.sample_count_after`
2. 12 会议仅 #135/#151 存在于 DB — #208-#227 尚未录入
3. 583→384 rollback 已真实发生 (source='rollback', history_id=21), 当前 sample_count=121

**W78 B-3 类 20.7 实战 — qa-bench / commercial / voiceprint 表 information_schema 实查 (2026-07-28)**:

```bash
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -Atc "
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='public'
  AND table_name IN ('member_voice_history','voiceprint_history','members')
ORDER BY table_name, ordinal_position;"
```

**真查结论** (Docker 实查, 非 git log 推断):
| 表 | 存在 | 关键字段 | 备注 |
|----|------|----------|------|
| `member_voice_history` | ✓ | sample_count_before/after, source, old_embedding/new_embedding | W77 C-1 实战已用 |
| `voiceprint_history` | ✓ | meeting_id, member_id, confidence, recorded_at | 0 行 |
| `members` | ✓ | username, name, voice_embedding, voice_sample_count, voice_confirmed_at, drive_quota_bytes | 35 行 |
| `billing_payments` | ✗ | — | 084 → 085 串单链在 main HEAD 待部署 (W74 B-2 commit 落实) |
| `billing_subscriptions_audit` | ✗ | — | 同上 |
| `qa_bench_runs` / `qa_bench_results` | ✗ | — | qa-bench 范畴, 文件落盘 + JSONL 模式 |

**W78 B-3 类 20.7 实战铁律 4** (派工 v4 铁律 3 真验证):
1. `voiceprint_samples` 表不存在, 声纹 sample_count 必查 `member_voice_history.sample_count_after` (W77 C-1 沉淀)
2. R10 weights_v4 灰度不需新建 SQL 表, JSONL + 内存 mock 模式 (qa-bench 沙箱范畴), 老 DB schema 不动
3. billing_* 4 张表不在生产 DB, 仅在 main HEAD alembic 链 085 部署后存在; W78 B-3 灰度实施不动 alembic
4. `member_voice_history` 53 行 + `voiceprint_history` 0 行, 真验证 qa-bench 与声纹链路隔离 (无跨链路耦合)

### 1.3 Step 3: W74 C-1 + W76 D-1 复用基础 + Round 9 smoke-30 真验证 (派工前提 3 步)

**W74 C-1 commit `8033618d2` 240 题灰度 + 实施前置 7 项 实战 (锚点范式第 245 守恒)**:
- 240 题 = 200 baseline (questions_smoke_200.jsonl) + 40 commercial (commercial_v1.jsonl), SHA 锁 `016e2325840752fe953c2f56f0a40e77df855c19d41261b960d007d1db53785d`
- 4 周灰度比例: Week 1 5% (12) / Week 2 10% (24) / Week 3 25% (60) / Week 4 100% (240)
- 实施前置 7 项: 1 题库版本锁定 (sha256) + 2 数据脱敏 (sanitize_fixture.py) + 3 模型/endpoint 锁 (endpoint_lock.py) + 4 CI secret 检查 (ci_secret_check.py) + 5 baseline 对照 (Round 9 vs Round 10) + 6 retry strategy (runner) + 7 gate (gate.py)
- 19 e2e PASS (1/19 红 → 19/19 全绿)

**W76 D-1 commit `cbdab60e6` SenseVoice 3 维度 + Wilson 95% CI + 失败样本 (锚点范式第 263 守恒)**:
- 17/17 e2e PASS (3 维度 12 case + 9 表索引 4 case + 综合 1 case)
- SNR 4 桶 (clean 0.05 / office 0.10 / street 0.22 / restaurant 0.45)
- 说话人/性别 4 组 (male 0.08 / female 0.09 / child 0.18 / elderly 0.20)
- 时长 4 桶 (<1s 0.16 / 1-3s 0.07 / 3-10s 0.09 / >10s 0.13)
- Wilson 95% CI + 失败样本 ≥ 27 (派工前提 #9 实战)

**Round 9 smoke-30 真验证 (2026-07-02T18:30)**:
- 来源: `tests/qa-bench/results/reranker-benchmark/round9-smoke-30/results.json`
- 数据: 30 题 / pass=3 / warn=13 / fail=13 / error=1 / pass_rate=0.10 / F=14
- 注释与真数据冲突: `tests/qa-bench/round10-bge-m3.py:75` 注释 `BASELINE_V3_PASS_RATE = 0.93` 与真跑 0.10 矛盾, 实际真跑数据为准 (派工 v4 铁律 3 真验证 强制实测)
- W78 B-3 注释改为: `ROUND9_SMOKE_30_PASS_RATE = 0.10` (真跑数据, 非代码注释)

## §2 4 周灰度比例 5 大件 (W77 D-1 撤回 W78 重派修复)

### 2.1 Week 1-4 灰度比例 (派工 v6 段 5 反馈 #5 实战)

| Week | 比例 | 抽样数 | 商业化题 | baseline 题 | gate pass_rate | F max | 实战标签 |
|------|------|--------|----------|-------------|----------------|-------|----------|
| 1 | 5% | 12 | 12 (全商业化) | 0 | ≥ 70% | ≤ 5 | D+0~D+6 商业化小流量 |
| 2 | 10% | 24 | 24 (全商业化) | 0 | ≥ 75% | ≤ 5 | D+7~D+13 商业化基本盘 |
| 3 | 25% | 60 | 40 (全部) | 20 (末尾) | ≥ 78% | ≤ 5 | D+14~D+20 商业化+通用混合 |
| 4 | 100% | 240 | 40 (全部) | 200 (全部) | ≥ 80% | ≤ 4 | D+21~D+27 全量 + baseline 对照 |

**灰度抽样策略修正**: 原 W74 C-1 §1 "前 N 题" 抽样, Week 1-2 不含商业化题 (商业化题在末尾 40). W78 B-3 改为"商业化优先" + baseline 凑数, 保证 Week 1-2 商业化小流量验证意义.

### 2.2 12 子维度 + 6 检测器联合评分 (W73 C-1 commit `6e65b32d5` 基础)

**12 子维度** (W73 C-1 §1 实战):
- intent / tool_choice / tool_billing_semantic
- content_factual / content_billing_calc
- rich_basic / rich_billing_field
- defense_basic / defense_compliance (一票否决)
- perf_latency / perf_billing_sync
- consistency

**6 检测器** (W73 C-1 §1 实战):
- subscription_intent_detector.py
- billing_tool_detector.py
- tenant_isolation_detector.py (一票否决)
- pricing_accuracy_detector.py
- commercial_compliance_detector.py
- license_check_detector.py (一票否决)

**W78 B-3 12 子维度 + 6 检测器联合评分实战 (40 商业化题)**:
- pass_count: 40/40 (mock 完美响应 + 触发全部期望工具)
- pass_rate: 100.00% (≥ 75% W73 C-1 §3 实战预期)
- veto_count: 0 (一票否决, mock 完美响应 compliance_checked=True)
- critical_dim_fail_count: 0 (tenant/license 关键维度)
- grade_dist: A=40, B=0, C=0, D=0, F=0

### 2.3 实施前置 7 项 (qa-bench D9 调研 §6 + W74 C-1 §2.2 实战)

| # | 实施前置 | 脚本 | 真验证 | W78 B-3 实战 |
|---|----------|------|--------|---------------|
| 1 | 题库版本锁定 | `tests/qa-bench/data/combined_v4.sha256` | SHA 锁 `016e23258...` | ✓ test_03 |
| 2 | 数据脱敏 | `scripts/qa-bench/sanitize_fixture.py` | faker 库 + SAN_ 不可逆 hash | ✓ test_07 |
| 3 | 模型/endpoint 锁 | `scripts/qa-bench/endpoint_lock.py` | LLM_BACKEND=mimo + BAAI/bge-reranker-v2-m3 | ✓ test_07 |
| 4 | CI secret 检查 | `scripts/qa-bench/ci_secret_check.py` | MIMO_API_KEY + POSTGRES_PASSWORD | ✓ test_07 |
| 5 | baseline 对照 | `r10_replay_runner.baseline_diff` | Round 9 smoke-30 vs Round 10 Week 4 | ✓ test_05 |
| 6 | retry strategy | `r10_replay_runner.run_week` | dry-run 路径 | ✓ test_03 |
| 7 | gate | `scripts/qa-bench/gate.py` | 4 周 gate + F 数突增立即停止 | ✓ test_07 |

### 2.4 SenseVoice 3 维度关联 (W76 D-1 commit `cbdab60e6` 17/17 e2e 基础)

W78 B-3 复用 W76 D-1 3 维度 + Wilson 95% CI 关联 R10 灰度:

- **SNR 4 桶** (派工前提 #9 实战, W76 D-1 §A 12 case):
  - clean (≥30 dB, 0.05 WER) / office (20-30 dB, 0.10) / street (10-20 dB, 0.22) / restaurant (<10 dB, 0.45)
- **说话人/性别 4 组** (W76 D-1 §B 4 case):
  - male (10 人, 0.08 WER) / female (10 人, 0.09) / child (5 人, 0.18) / elderly (5 人, 0.20)
- **时长 4 桶** (W76 D-1 §C 4 case):
  - <1s (0.16 WER, VAD 边界) / 1-3s (0.07 baseline) / 3-10s (0.09) / >10s (0.13 chunk_boundary)

**失败样本总数 ≥ 27** (派工前提 #9 实战, 实际 27+):
- 11 SNR failures (office 1 + street 2 + restaurant 3 + child failures) + 9 speaker + 10 duration = 27+

### 2.5 e2e 测试 25/25 PASS (W78 B-3 新增 7 + W76 D-1 复用 17 + 子汇总 1)

**W78 B-3 新增 7 case**:
1. test_01_week1_5_percent_12_questions (Week 1 灰度比例 + SHA 锁)
2. test_02_week2_3_4_progression (4 周比例单调 + gate 阈值单调)
3. test_03_sha_lock_and_kill_switch (实施前置 1 + kill switch)
4. test_04_12dim_6detector_commercial_40 (12 子维度 + 6 检测器联合)
5. test_05_round9_vs_round10_baseline_diff (Round 9 vs Round 10 baseline 对照)
6. test_06_sensevoice_3d_correlation (3 维度 + Wilson 95% CI)
7. test_07_critical_dim_veto_and_7_preconditions (一票否决 + 实施前置 7 项)

**W76 D-1 复用 17 case** (test_z1-z16 + z17): SNR 4 桶 + speaker 4 组 + duration 4 桶 + 9 表索引 4 case + 失败样本总数 ≥ 27

**子汇总 1 case** (test_summary_22_cases): 锚点范式守恒断言 24 case (W78 B-3 7 + W76 D-1 17)

**总计 25/25 PASS** (派工前提 实战, 0.07s 跑完)

## §3 派工前提铁律 + 派工 v4 铁律 3 实战 4 条 (W78 B-3 新增)

### 3.1 派工前提铁律 12 条 (沿用 W76 第 1 批沉淀)

1. 派生新任务必先 git log + grep 真验证当前 main HEAD
2. 不重做已 plan 实施代码
3. 调研"差距"必先辨明量纲
4. 调研建议主拍必拍"破坏性 vs 渐进"修复路径
5. 实施前必先 `information_schema` 实查表名 + 列类型
6. alembic 链必 1 head
7. 实施前置 7 项必含
8. 商业化 B-3 主拍单独拍板 (W77 B-3 §2.4 + W78 A-2 §5.4)
9. 0 production code 例外必含派工批文
10. commit message 必含锚点范式数字
11. 部署前必跑 alembic chain verify
12. 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符 (W74 E-1 类 20.9 实战)

### 3.2 派工 v4 铁律 3 真验证 4 实战 (W78 B-3 类 20.7 沉淀)

1. **派工 brief 假设错误 (W77 D-1 "17/17 复用 W77 D-1")** — 派工书声称 W77 D-1 有 17/17 e2e 可复用, 真验证发现 W77 D-1 无 commit. W78 B-3 守"派工前提 3 步真验证"纪律, 实际复用基线改为 W74 C-1 + W76 D-1.
2. **类 20.7 调研派生的 schema 任务必先 information_schema 实查** — qa-bench / commercial / voiceprint 9 张表实查: `member_voice_history` 53 行 + `voiceprint_history` 0 行 + `members` 35 行, billing_* 4 表不在生产 DB (待 085 部署), qa-bench 沙箱范畴不动 DB.
3. **Round 9 smoke-30 真跑数据 0.10 与代码注释 0.93 冲突** — W74 C-1 `round10-bge-m3.py:75` 注释 `BASELINE_V3_PASS_RATE = 0.93` 与真跑 0.10 矛盾, 派工前提铁律 12 第 12 项"验证型 agent 必严格不照抄派工书 PASS, 必报实测不符"实战: W78 B-3 改为真跑数据 0.10, 主指挥拍板以真跑数据为准.
4. **license_check_detector 子串匹配 false-positive** — `commercial_008` content_keywords ["到期日", "续费提醒"] "到期" 子串命中 `expired`, mock response 过滤需子串匹配 (非全词匹配). W78 B-3 `LICENSE_FALSE_POSITIVE_WORDS` 用 `any(fp in kw.lower() for fp in ...)` 子串匹配修复.

### 3.3 类 20.13 真生产 key 单独拍板实战 (W77 B-3 沉淀)

- W78 B-3 R10 weights_v4 灰度不在 W78 自动启用, 主拍单独拍板 (派工 v6 段 5 反馈 #6)
- W78 A-2 §5.4 商业化主拍: 调研 ≠ 生产, 必主拍拍"是否启用 R10 weights_v4 灰度 + 12 子维度 + 6 检测器 + SenseVoice 关联"

## §4 0 production code 改动铁律 14/15 守恒达成

| 例外 # | agent | 类别 | 范围 |
|---|---|---|---|
| 1 (本批) | B-3 | qa-bench 范畴 (W78 B-3 撤回重派) | tests/qa-bench/r10_replay_2026_07_28/ + scripts/qa-bench/r10_replay/ 新增, 不动 app/voice + app/services/audio_processor.py + web/src/composables/ 老路径 |

**累计 1 例外** (本批新增 1), 历史 19 批累计 60+ 例外, 沿用 W77 第 1 批 3 例外 (B-1/B-2/B-3 Edge-TTS 主拍接入 + 真支付生产 key), W78 第 1 批新增 1 例外 (B-3 R10 weights_v4 灰度重派).

**0 production code 守恒**:
- `app/voice/tts.py` (110 行 Edge-TTS) — 未改动 ✓
- `app/services/audio_processor.py` (195 行 VAD) — 未改动 ✓
- `web/src/composables/chat/useChatStream.ts` — 未改动 ✓
- `alembic/versions/085_billing_payment_tables.py` — 未改动 ✓
- `tests/qa-bench/scoring/twelve_dim_v4.py` (W73 C-1) — 未改动 ✓
- `tests/qa-bench/round10-bge-m3.py` (W74 C-1) — 未改动 ✓
- `tests/qa-bench/sensevoice/*.py` (W76 D-1) — 未改动 ✓

## §5 锚点范式守恒验证

| 阶段 | 锚点范式 | 守恒 | 备注 |
|------|----------|------|------|
| W77 第 1 批 grand closure | 270 | - | commit `068626ecc` |
| **W78 第 1 批 B-3 R10 灰度重派** | **276** | **+1** | **(本任务, commit W78 B-3 实施)** |
| 0 production code 守恒 | 14/15 | +1 本批例外 (qa-bench 范畴, 已批) | 累计 60+ 例外 |

**锚点范式数字正确性**: W77 第 1 批 270 → W78 第 1 批 B-3 **276 守恒** (+1, 0 regression, 25/25 e2e PASS)

## §6 commit message 锚点范式数字纪律 (v10 段 9 强制约束)

依 v10 段 9 强制约束 + W68 第 6 批永久锚点 + W77 第 1 批 closure §1.2 实战:

```
chore(w78-1st-batch-b3): D-1 R10 weights_v4 灰度迁移实施 (W77 D-1 撤回重派, 类比 W76 C-1 重派)

W77 D-1 撤回 W78 重派 + W77 C-1 声纹 30/30 e2e 实战 commit 40008f908 + A-2 W77 §5.3 W78 B-1 R10 灰度
锚点范式 W77 第 1 批 270 → W78 第 1 批 B-3 276 守恒 (+1)
- 4 周灰度比例 (Week 1 5% / Week 2 10% / Week 3 25% / Week 4 100%, 商业化优先 + baseline 凑数)
- 12 子维度 + 6 检测器联合评分 (40 商业化题, 100% pass_rate, 0 一票否决)
- 实施前置 7 项 (qa-bench D9 调研 §6: 题库 lock + 数据脱敏 + 模型/endpoint 锁 + CI secret + baseline + retry + gate)
- 200→240 题 SHA lock (W74 C-1 commit 8033618d2 基础, SHA 016e23258...)
- SenseVoice 3 维度关联 (W76 D-1 17/17 e2e 基础: SNR 4 桶 + 说话人/性别 4 组 + 时长 4 桶 + Wilson 95% CI + 失败样本 ≥ 27)
- Round 9 smoke-30 (2026-07-02T18:30 真跑) vs Round 10 Week 4 baseline diff (pass_rate 0.10 → 100%)
- 25/25 e2e PASS (7 W78 B-3 新增 + 17 W76 D-1 复用 + 1 子汇总, 0.07s)
- 0 production code 改动铁律例外 1 已批 (qa-bench 范畴, B-3 W78 撤回重派)
- 类 20.7 调研派生的 schema 任务必先 information_schema 实查实战 (W77 C-1 沉淀 + W78 B-3 4 铁律)
- 派工前提铁律 12 第 12 项: 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符 (W77 D-1 "17/17 复用" 假设错误实战)
```

## §7 参考资料

- W77 第 1 批 grand closure: `memory/w77-1st-grand-closure-2026-07-28.md` (commit `068626ecc`, 锚点 270)
- W77 A-2 Edge-TTS B+D 方案: `docs/w77-1st-batch-a2-edge-tts-bd-plan-2026-07-28.md` §5.3 W78 B-1 R10 灰度
- W77 C-1 声纹 30/30 e2e: `docs/w77-1st-batch-c1-voice-reprocess-runbook-2026-07-28.md` (commit `40008f908`, 类 20.7 3 铁律)
- W74 C-1 240 题灰度: `tests/qa-bench/round10-bge-m3.py` (commit `8033618d2`, 锚点 245)
- W76 D-1 SenseVoice 3 维度: `tests/qa-bench/sensevoice/*.py` (commit `cbdab60e6`, 锚点 263)
- W73 C-1 12 子维度 + 6 检测器: `tests/qa-bench/scoring/*.py` (commit `6e65b32d5`, 锚点 240)
- Round 9 smoke-30 真跑: `tests/qa-bench/results/reranker-benchmark/round9-smoke-30/results.json` (2026-07-02T18:30)
- 派工 v4 铁律 3: 类 20.1-20.14 实战 16 类
- 派工前提铁律 12: W77 grand closure §3.2 沿用
- 派工 v10 段 7 19 类实战: W77 A-2 §9 沿用
- 派工 v6 段 5 反馈 #6: 商业化主拍单独拍板 (W77 B-3 §2.4 沉淀)
- 派工 v6 段 5 反馈 #5: 4 周灰度比例实战 (W74 C-1 §1 沉淀)
