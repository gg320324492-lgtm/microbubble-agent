---
name: w68-route-10-b1-qa-bench-7d-scoring-2026-07-24
description: "W68 第 10 批 B-1 qa-bench 7 维评分算法落地. 锚点范式第 124 守恒. 5 新铁律 (7 维归一化 / entropy 阈值 / verdict confidence / 多 rounds 同步 / 跟 phase1-3 集成)."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-Route-10-B1
  modified: 2026-07-24T00:00:00.000Z
---

# 2026-07-24 W68 第 10 批 B-1 — qa-bench 7 维评分算法

## TL;DR

W68 第 9 批 D-5 W69 派工拍板的子项 ② **qa-bench 7 维评分** 落地完成. 单点 pass rate (W66 v3.0 baseline) 拆解为 **7 个互补维度** (准确率 / 召回率 / 精确率 / F1 / 一致性 / 信息熵 / 时延), 配套 **v2 consensus confidence** (entropy 反向 → answered / declined 二元决策). 5 个新文件全部归位 `tests/qa-bench/scoring/` + 修改 phase2_dry_runner.py + 新建 phase3_matrix_runner.py. **0 production code 改动铁律完全维持**. 11 个单元测试 PASS. 锚点范式第 124 守恒.

## Why

qa-bench v3.0 一直用单点 pass rate 做门禁, 但单维度均化掩盖了根因:
- **accuracy 高 + recall 低** → 模型不答 (empty 多, 漏答)
- **accuracy 高 + precision 低** → 模型乱猜 (fail 多但命中率高)
- **consistency 低** → 多 rounds 答案漂移 (模型不确定)
- **entropy 高** → 答案分布发散 (行为不稳)
- **latency P99 高** → 长尾耗时 (cache miss 或 provider 抖)

W67 Round 9 实证 pass rate 0.94 但 recall 仅 0.72 → 模型漏答严重, 单维度掩盖. W68 D6 (W69 第 1 批) 派工拍板把单点 pass rate 升级为 7 维综合门禁, 防止 "pass rate 漂亮但 recall 烂" 误 promote.

## How to apply

主指挥拍板后由 W68 Route-10-B1 Agent 实施:
1. 拍板 7 维归一化公式 (5 维 0-1 + entropy 归一化 + latency ms 原始)
2. 拍板 v2 consensus confidence 阈值 (默认 0.5)
3. 派工实施 5 文件 (3 新建 + 2 改)
4. 主指挥 review 11 单元测试 PASS 后 merge

**已完成**: 实施 5 文件 + 11 测试 + docs + memory, 待主指挥 merge.

---

## 1️⃣ 实施范围 (5 文件)

### 新建 (3)

1. **`tests/qa-bench/scoring/seven_d_scoring.py` (~350 行)**
   - 核心 dataclass: `VerdictRecord` (单轮) + `LatencyStats` (聚合) + `SevenDimScore` (7 维输出)
   - 核心函数: `score_records(records)` 一站式计算 7 维
   - 内部 helpers: `_percentile` (linear-interpolated) + `_normalize_verdict` + `_group_by_question` + `_question_consistency` + `_question_entropy` (Shannon, base e) + `_aggregate_latency` + `_score_subset`
   - CLI: `python -m seven_d_scoring --input results.jsonl --output 7d_score.json`

2. **`tests/qa-bench/scoring/verdict_consensus_v2.py` (~130 行)**
   - 核心 dataclass: `ConsensusV2` (majority_verdict + confidence + decision + entropy + round_count + verdict_counts)
   - 核心函数: `confidence_for_question` (`1 - entropy/max_entropy`) + `majority_verdict` (字母序 tie-break) + `confidence_verdict` (返回 decision "answered"/"declined")
   - 默认阈值: `DEFAULT_CONFIDENCE_THRESHOLD = 0.5`
   - 依赖: `from seven_d_scoring import VerdictRecord`

3. **`tests/qa-bench/scoring/test_seven_d_scoring.py` (~300 行, 11 测试)**
   - 11 场景全部 PASS:
     1. 完美答 (3 rounds 全 pass) → 7 维全满分
     2. 全错 (3 rounds 全 error) → accuracy/recall/precision/F1 全 0
     3. 一半对一半空 (4 rounds 2 pass + 2 empty) → F1 = 0.6667
     4. 熵 = 0 (5 rounds 全 pass) → entropy_normalized = 0
     5. 熵 = 最大 (4 rounds 4 不同 verdict) → entropy_normalized = 1.0, confidence = 0
     6. 混合 intents (data/knowledge/meeting) → per_intent 拆解正确
     7. 时延 P99 (100 samples 1..100) → p99 = 99.01
     8. 单 round → 7 维稳定输出 (degenerate)
     9. 3 rounds (2 pass + 1 fail) → accuracy 0.6667, confidence 0.4206 (< 0.5)
     10. 多 intents (pass/fail/empty 混合) → verdict_counts 正确
     11. CLI round-trip → 临时 JSONL → 7d_score.json 验证

### 修改 (2)

4. **`tests/qa-bench/phase2_dry_runner.py`** (W68 第 8 批 B-2 已建, 本批加 `--scoring 7d` flag)
   - 新常量: `DEFAULT_SCORING = "none"` (向后兼容, 默认不改行为)
   - 新 helper: `_phase2_results_to_records` (phase2 row format → VerdictRecord)
   - 新 helper: `_run_seven_d_scoring` (扁平化 phase2 结果 → 7d score + 写 JSON)
   - 新参数: `--scoring {none,7d}` + `--seven-d-out <path>`
   - `_run` 在 summary 渲染后调 `_run_seven_d_scoring`, 结果并入 payload 返回值
   - dry-run fallback 路径: 当 `aggregated` 为空时, 用 `_dry_placeholder_results(questions)` 喂给 scorer, 保证 dry-run 也能产出 7d_score.json
   - `main` 在 `report` 打印后追加 7d 摘要行

5. **`tests/qa-bench/phase3_matrix_runner.py` (新建, ~600 行)**
   - 矩阵 driver: Cartesian product of `(provider, model, cache_mode, rounds)`
   - 默认 providers: `mimo + ollama`; 默认 models: `{mimo: mimo-v2.5, ollama: qwen3:8b}`
   - 默认 cache_modes: `hit + miss`; 默认 rounds: `(3,)`
   - 默认 max_questions: `200` (subsample 1000 题, 防止 matrix 跑爆 CI budget)
   - 单 cell 复用 `phase2_dry_runner._round_with_concurrency` (W68 第 8 批已有 seam)
   - 矩阵聚合: per-cell `pass_rate + verdict_counts + duration_s + by_intent`
   - 矩阵 verdict: 任一 cell `pass_rate < gate_threshold` 即整体 FAIL
   - **同 `--scoring 7d`**: 7 维评分按 cell 拆分 (`question_id` 拼上 `::cell` 后缀), 跨 cell 聚合输出 `phase3_7d_score.json`
   - 新 helper: `_matrix_to_records` + `_run_seven_d_scoring` + `_aggregate_cell` + `_render_phase3_report`
   - **3 个新导入路径修改**: phase2/phase3 在 import 时同步注入 `scoring/` 到 `sys.path` (避免 ModuleNotFoundError)

## 2️⃣ 7 维归一化设计

| 维度 | 输出 | 范围 | 归一化方法 |
|---|---|---|---|
| 1. accuracy | `hits / total` | [0, 1] | 直接 |
| 2. recall | `hits / ground_truth_positive` | [0, 1] | 直接 (避免除 0) |
| 3. precision | `hits / answered` | [0, 1] | 直接 (answered = pass + fail) |
| 4. F1 | `2PR/(P+R)` | [0, 1] | 调和 |
| 5. consistency | `mean(majority_share)` | [0, 1] | 直接 |
| 6. entropy | `mean(Σ -p log p)` | [0, ln N] | 同时输出 `entropy_normalized = entropy / log(max_rounds)` |
| 7. latency | `avg/p50/p95/p99` ms | [0, ∞) | 原始 ms (per-round wall-clock) |

**answered verdict 集合** = `(pass, fail)` (模型明确回答).
**declined verdict 集合** = `(empty, error, skipped)` (模型未回答).
**unknown** 计入 total 但不参与命中率 (兼容老 runner).

## 3️⃣ v2 consensus confidence 设计

```
confidence = 1 - entropy / max_entropy
decision = "answered" if confidence >= 0.5 else "declined"
max_entropy = log(round_count)
```

- 3 rounds 全 pass → entropy = 0 → confidence = 1 → answered
- 3 rounds (2 pass + 1 fail) → entropy ≈ 0.6365 → confidence ≈ 0.42 → **declined**
- 4 rounds (pass/fail/empty/error) → entropy = ln 4 ≈ 1.386 → confidence = 0 → declined

**关键设计**: declined 仍参与 `verdict_counts` 和 `latency` 聚合 (可观测性), 但**不**进入 `accuracy / recall / precision / F1` 的命中分母 (避免未答惩罚过重). 这与 W67 round 9 "未答 0% pass rate 拖累整体" 的真根因对齐.

## 4️⃣ 5 新铁律 (W68 Route-10-B1 沉淀)

### 铁律 1: 7 维归一化必须双输出 (entropy + entropy_normalized)

**why**: entropy 原始范围 `[0, ln N]` 随 rounds 变化, 跨实验不可比. `entropy_normalized = entropy / log(max_rounds)` 归一化到 `[0, 1]` 便于阈值判定. 同时输出两者, 既保留原始单位又便于比较.

**纪律**: 任何新维度同时输出"原始 + 归一化", 不要只输出归一化 (丢失单位信息). CI gate 用归一化, 报告用原始.

### 铁律 2: answered / declined verdict 二元决策

**why**: W67 round 9 实证单维度 pass rate 把 "未答" 当成 "答错", 拖累整体均分. declined verdict 不进入命中分母 (避免误扣), 但仍计入总数 (可观测性).

**纪律**: 任何 verdict 评分必须明确 "answered" vs "declined" 边界. 默认 `confidence >= 0.5` 为 answered. CI gate 用 confidence-weighted 指标, 不要裸用 pass rate.

### 铁律 3: 多 rounds verdict 必须按 question_id 聚合, 不是全局聚合

**why**: 单 question 多 rounds 的 entropy 是**问题级**指标 (模型对**这题**确定度), 全局聚合会丢信息. 必须 `group_by(question_id)` 后算 entropy, 再 `mean` 跨问题.

**纪律**: 任何 per-question 聚合 (consistency / entropy) 必须先 `groupby`, 再聚合. 全局聚合只用于 verdict_counts + latency (per-round 指标).

### 铁律 4: phase2/3 集成 7d 评分必须 fallback 兼容 dry-run

**why**: dry-run 模式下没有真实 LLM, `aggregated` 为空. 但 CI smoke 必须能跑出 `7d_score.json` (否则 dry-run 路径下 `--scoring 7d` 静默失败).

**纪律**: 任何集成 `--scoring 7d` 的 runner, dry-run fallback 必须用 `_dry_placeholder_results` 喂给 scorer, 保证 CI smoke 全路径通过. 真实 live run 走真实 aggregated.

### 铁律 5: scoring 子目录必须在 sys.path 里, 否则 ModuleNotFoundError

**why**: `tests/qa-bench/phase2_dry_runner.py` 与 `tests/qa-bench/phase3_matrix_runner.py` 都是 `from seven_d_scoring import VerdictRecord` 跨目录 import, Python 默认不会扫 `scoring/` 子目录. 必须**双路径注入** `_QA_BENCH_DIR + _SCORING_DIR` 到 `sys.path`.

**纪律**: 任何新增 `tests/qa-bench/scoring/*.py` 与 `tests/qa-bench/*.py` 跨目录 import 时, 必须在模块顶部 `_p in sys.path` 循环注入 `scoring/` 子目录. 不可依赖 `__init__.py` (qa-bench 是 flat dir, 不是 package).

## 5️⃣ 端到端验证

```bash
# 1. 11 单元测试
SKIP_DB_SETUP=1 python -m pytest tests/qa-bench/scoring/ -v
# → 11 passed

# 2. 19 集成测试 (含原 phase2_dry_smoke 8 个, 0 regression)
SKIP_DB_SETUP=1 python -m pytest tests/qa-bench/scoring/ tests/qa-bench/test_phase2_dry_smoke.py -v
# → 19 passed

# 3. phase2 dry-run + 7d 评分
python tests/qa-bench/phase2_dry_runner.py --dry-run --scoring 7d \
    --report-out /tmp/phase2_test.md
# → 输出 tests/qa-bench/phase2_7d_score.json (1000 题 × 3 rounds = 3000 records)

# 4. phase3 matrix dry-run + 7d 评分
python tests/qa-bench/phase3_matrix_runner.py --dry-run --max-questions 50 \
    --scoring 7d --report-out /tmp/phase3_test.md
# → 4 cells (mimo×2 + ollama×2) × 50 题 × 3 rounds = 600 records

# 5. CLI 评分 (输入 JSONL → 输出 JSON)
python -m tests.qa-bench.scoring.seven_d_scoring \
    --input results.jsonl --output 7d_score.json --print
```

## 6️⃣ 锚点范式第 124 守恒

**W68 路径**:
- W68 第 1 批 (W67 28 → 29): Drive v2 PR8 收官 + Mobile UX 14 agents
- W68 第 2 批 (W68 29 → 30): D6 调研 + 文档同步 + baseline 守恒
- W68 第 3 批 (W68 30 → 42): Drive v2 PR9 + 评论 thread + 文件版本 + qa-bench D6 + Mobile UX v3.1
- W68 第 4 批 (W68 42 → 57): Drive PR9 后续 + Plan 闭环 2 + 视觉回归 1
- W68 第 5 批 (W68 57 → 72): 15 agents 路线驱动 + plans 优先基调
- W68 第 6 批 (W68 72 → 73): 5 agent plans 实战审计
- W68 第 7 批 (W68 73 → 87): plans 闭环 15 agents + Status 修正
- W68 第 8 批 (W68 87 → 104): Drive PR11/12 + Mobile v3.2 + qa-bench D6 matrix
- W68 第 9 批 (W68 104 → 119): 15 agents grand closure + 文档同步
- **W68 第 10 批 B-1 (W68 119 → 124)**: 本任务 qa-bench 7 维评分落地 (锚点范式第 124 守恒)

**未来 PR 触发监控点**:
1. W69 第 1 批派工后, D6 CI gate 升级为 7 维复合门禁时, 用 `phase2_7d_score.json` 作为 gate 输入
2. D1 LLM config 切模型时, 跑 `--scoring 7d` 输出 per_intent diff, 量化模型差异
3. D3 retrieval cache hit/miss matrix, 用 phase3 matrix runner + `--scoring 7d` A/B

## 7️⃣ 沉淀位置

- **核心算法**: `tests/qa-bench/scoring/seven_d_scoring.py` (~350 行) + `verdict_consensus_v2.py` (~130 行)
- **测试**: `tests/qa-bench/scoring/test_seven_d_scoring.py` (11 测试 PASS)
- **集成**: `tests/qa-bench/phase2_dry_runner.py` (`--scoring 7d` flag) + `tests/qa-bench/phase3_matrix_runner.py` (新建)
- **文档**: `docs/qa-bench-7d-scoring.md` (~200 行)
- **本 memory**: 实施汇总 + 锚点范式第 124 守恒 + 5 新铁律
- **不写入**: CLAUDE.md (避免 50KB 核心膨胀) / MEMORY.md 索引 (仅在主仓库 + 用户级索引各加 1 行)

## 8️⃣ 后续待办 (留 W69 第 1 批派工)

1. **D6 CI gate 升级**: 读 `7d_score.json` 校验 7 维全部 >= 失败阈值才 PASS. W69 第 1 批 D 路线派工.
2. **per_intent 阈值调优**: 当前阈值 (warning 0.85 / fail 0.75) 是经验值, 跑完 1000 题实测后微调.
3. **consensus confidence 阈值 0.5 验证**: 当前默认, W69 第 1 批 D 路线实证 recall/precision 平衡点.
4. **phase3 matrix 跑通真实 LLM**: 当前 dry-run 路径, W69 第 1 批真实 SSH 上去跑 4 cells × 200 题.

---

**Anchor**: 锚点范式 W68 119 → **124** 单调上升, W68 第 10 批 B-1 qa-bench 7 维评分落地 0 production code 改动铁律完全守恒.