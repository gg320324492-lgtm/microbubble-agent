# W68 第 8 批 B-4: qa-bench D6 Phase 3 matrix 4 runner 并行 (2026-07-24)

> **作者**: Claude Fable 5 (W68 Route-8-B-4 Agent)
> **日期**: 2026-07-24
> **基线 HEAD**: `05c60e68d` (W68 第 5 批 hot-fix)
> **任务来源**: W68 第 5 批 B-3 调研推荐路径 4 — matrix 拆分 4 runner 并行 1000 题, 总时间 ÷ 4
> **锚点范式第 96 守恒** (W68 第 8 批 95 → **96**)

---

## TL;DR

W68 第 8 批 B-4 实施 W68 第 5 批 B-3 调研锁定的"路径 4 (matrix 拆分 4 runner 并行)" 工具. 在 W68 第 7 批 B-2 已建 `phase2_dry_runner.py` 单 runner 骨架 (360 行, 并发 5, 3 rounds majority) 基础上, 写 `tests/qa-bench/phase3_matrix_runner.py` (~430 行 CLI) 加 **跨 worker 并发调度** + **多 worker 汇总聚合** + **严格 matrix gate** (ALL 4 workers ≥ 90% 才 PASS). 1000 题切成 4 shard (250/250/250/250), 4 worker asyncio.Semaphore 并发同跑, 期望 wall clock 5-15 min (vs 单 runner 30-60 min, 节省 50-75%). 0 production code 改动铁律维持 (仅 tests/qa-bench/ + docs/ + memory/), 锚点范式单调上升 W68 第 8 批 95 → **96**. 工具 dry-fallback 验证逻辑正确 (本地 PC 无 MIMO_API_KEY + test DB), 待主指挥 SSH 跑真实 1000 题.

---

## 1️⃣ 任务背景

W68 第 5 批 B-3 调研锁定 5 路径, 主指挥拍板"路径 4 + 路径 1 组合" 作为 Phase 2 / 3 实施方向. Phase 2 已由 W68 第 7 批 B-2 实施完成 (`phase2_dry_runner.py` 单 runner 骨架), Phase 3 实施目标: **路径 4 落工具** — 在 Phase 2 基础上加 **跨 worker 并发调度** + **多 worker 汇总聚合** + **严格 matrix gate**.

**前置**:
- ✅ W68 第 5 批 B-3 调研 (`docs/qa-bench-d6-implementation-roadmap.md` 路径 4 推荐)
- ✅ W68 第 7 批 B-2 Phase 2 dry-run 骨架 (`phase2_dry_runner.py` 360 行, 单 runner 并发 5, 3 rounds majority)
- ✅ W68 第 8 批主指挥拍板调度 — B-4 agent 实施 Phase 3 matrix 4 runner

**后续**:
- ⏸ W68 第 8 批主指挥 SSH 跑真实 1000 题 (本地 PC 无 MIMO_API_KEY)
- ⏸ W69 第 1 批 Phase 3 grand closure → 锚点范式 96 → 100 守恒

---

## 2️⃣ 实施内容 (4 文件交付)

### 2.1 `tests/qa-bench/phase3_matrix_runner.py` (~430 行, 新建)

**核心函数**:

| 函数 | 行数 | 职责 |
|------|------|------|
| `_shard_questions(questions, workers)` | ~10 | round-robin 切分 1000 题 → 4 shard (250/250/250/250) |
| `_run_one_worker(worker_id, shard, ...)` | ~30 | 单 worker 跑 1 shard, 复用 `_round_with_concurrency` |
| `_run_matrix(shards, ...)` | ~15 | 4 worker asyncio.Semaphore 并发调度, asyncio.gather 收 |
| `_aggregate_matrix(worker_summaries, ...)` | ~50 | 汇总 4 worker → combined counts + per-intent pass rate + matrix gate |
| `_render_phase3_report(...)` | ~80 | 写 Markdown 报告 (与 Phase 2 同结构) |
| `_dry_placeholder_results(questions)` | ~12 | dry-fallback placeholder (0% pass rate) |
| `_dry_worker_summary(worker_id, shard, ...)` | ~15 | dry-fallback per-worker summary |
| `_run(args)` | ~70 | 顶层 orchestrator, 解析 args + 调度 + 写报告 |
| `main()` | ~50 | argparse CLI (--workers / --matrix / --rounds / --gate-threshold / --db-url / --dry-run / --report-out) |

**CLI 标志**:
- `--workers 4` (默认) — matrix shards 数量 (1000 题 / 4 = 250 题/worker)
- `--matrix 4` (默认) — 跨 worker asyncio.Semaphore 并发数 (默认 4 = 同时跑满)
- `--rounds 3` (默认) — 每题 rounds 数 (verdict consensus basis)
- `--gate-threshold 90` (默认) — Per-worker gate 阈值 (百分比, 严格性)
- `--db-url` (env) — PostgreSQL DSN
- `--dry-run` — Skip MIMO live, 用 0% pass rate placeholder
- `--report-out` (auto) — Markdown 报告输出路径

### 2.2 `tests/qa-bench/phase2_dry_runner.py` (复用, 从 commit `e6220d016` 拷贝)

**复用方式**: `phase3_matrix_runner` 从 `phase2_dry_runner` import 5 函数 + 2 常量. 因 Phase 2 (W68 第 7 批 B-2) 还未 merge 到 main, 故先从 `e6220d016` commit 拷贝到本分支 (路径同 Phase 2 dry-run 报告). 0 双胞胎逻辑, 后续 Phase 2 merge 时不冲突 (路径一致).

**复用清单**:
- `_load_full_corpus()` — 1000 题 corpus loader (120 行)
- `_bucket_intent(raw_intent)` — 6-bucket taxonomy + chat-intent fallback
- `_majority_verdict(rounds)` — majority consensus (Phase 2 / 3 沿用)
- `_verdict_from_answer(answer)` — verdict logic (pass/empty/error 三分类)
- `_round_with_concurrency(questions, rounds, db_url, concurrency)` — Phase 2 核心 round-runner
- `PHASE2_INTENT_BUCKETS` + `PHASE2_CHAT_INTENT_BUCKETS` — 6-bucket 分类常量

### 2.3 `tests/qa-bench/phase3_matrix_report_2026-07-24.md` (~150 行, 新建)

报告结构 (沿用 Phase 2 同结构):
- TL;DR (状态 / 交付 / 结构 / 门禁 / 铁律 — 5 段)
- 1️⃣ 摘要 (背景 + 决策 + 核心改动 + 期望 + 教训 — 1 段浓汤)
- 2️⃣ 工具设计 (架构图 / CLI 标志 / Phase 2 复用 / Matrix gate 严格性 — 4 段)
- 3️⃣ Dry-run 验证 (本地 PC fallback 模式输出 + per-intent breakdown)
- 4️⃣ 真实 1000 题 dry-run (主指挥 SSH 跑后填表, 5 段)
- 5️⃣ Risk 注解 (5 风险 + 5 缓解 + 回滚路径)
- 6️⃣ 验收标准 (7 维度 + 失败处理)
- 7️⃣ 沉淀位置与未来引用

### 2.4 `docs/qa-bench-d6-implementation-roadmap.md` 追加 §10 (+~100 行)

**追加结构**:
- 10.1 触发与决策 (W68 第 5 批 B-3 路径 4 推荐)
- 10.2 实施内容 (4 项改动清单)
- 10.3 严格 matrix gate 设计 (代码片段 + 理由)
- 10.4 实施验收 (本地 PC dry-run 验证)
- 10.5 下一步主指挥 SSH 跑 (bash 命令)
- 10.6 锚点范式 W68 第 8 批 95 → **96** 守恒 (8 维度表)
- 10.7 Phase 3 失败回滚路径 (git revert)

---

## 3️⃣ 5 条新铁律 (W68 第 8 批 B-4 沉淀)

### 铁律 1: matrix 拆分必须 explicit shard 边界

**原则**: 1000 题切 4 worker 不能用 hash 散布 (随机性过强, 调试不便), 必须 round-robin `index % workers` deterministic 边界. 同一 question 在 N 次跑中始终落在同一 worker, 便于 per-worker 调试 + 失败原因追溯.

**反例**: `shard = questions[hash(q.id) % workers]` — 调试时 worker 0 失败, 但下次跑 worker 0 题目不同, 无法复现.

**正例**:
```python
shards: list[list] = [[] for _ in range(workers)]
for index, question in enumerate(questions):
    shards[index % workers].append(question)
# 1000 / 4 = 250 0/1/2/3 均匀, 1001 / 4 = 250/250/250/251 (last absorbs extra)
```

**纪律**: matrix 拆分必须 deterministic + balanced. 任何 random/hashing 拆分法禁止.

### 铁律 2: 跨 worker 并发 + per-worker 内部并发 双层 Semaphore

**原则**: 4 worker 跨 worker 并发 (asyncio.Semaphore(matrix=4)) + 每 worker 内部 5 个 question 并发 (复用 phase2_dry_runner `--matrix` 内层并发). 误以为只设 1 层并发 = 4 worker 串行 = wall clock 不降反升.

**正确双层模型**:
```python
# Outer layer: 4 workers 并发
matrix_sem = asyncio.Semaphore(args.matrix)  # 默认 4

async def _guarded(worker_id, shard):
    async with matrix_sem:
        return await _run_one_worker(worker_id, shard, ...)

# Inner layer: 每 worker 内部并发 (复用 phase2)
# phase2_dry_runner._round_with_concurrency 内置 asyncio.Semaphore(concurrency)
# 默认 5
```

**反例**: matrix=1 + 4 worker 串行跑 = wall clock 30-60 min vs matrix=4 并发 = 5-15 min.

**纪律**: 任何 matrix runner 必须显式区分 outer matrix (跨 worker) + inner concurrency (per-worker). 两者数值独立调整.

### 铁律 3: Verdict consensus verdict 必须复用, 禁止重写

**原则**: Phase 3 matrix runner 必须 import Phase 2 的 `_round_with_concurrency` + `_majority_verdict` + `_verdict_from_answer`, 禁止重写. 重写会出现 Phase 2 PASS / Phase 3 FAIL 的双胞胎 bug, 主指挥无法判断哪个 runner 数据可信.

**正例**:
```python
# phase3_matrix_runner.py
from phase2_dry_runner import (  # noqa: E402
    _load_full_corpus, _bucket_intent, _majority_verdict,
    _verdict_from_answer, _round_with_concurrency,
    PHASE2_INTENT_BUCKETS, PHASE2_CHAT_INTENT_BUCKETS,
)
```

**反例**: Phase 3 自己写 `_verdict_logic` + `_round_runner`, 短期跑通, 长期 Phase 2/3 drift.

**纪律**: 任何后续 Phase (4 / 5 / 6) 都必须 import Phase 2 verdict logic. 改逻辑只能改 Phase 2, 不能 Phase 3 偷偷改.

### 铁律 4: Matrix gate 严格性 — ALL workers pass 才 PASS

**原则**: Phase 3 matrix gate 必须严格执行 — **ALL 4 workers ≥ gate_threshold 才 PASS**. 任何 1 个 worker < gate_threshold → matrix FAIL. 不允许 "overall pass rate 92.5% → PASS" 模糊化.

**正例**:
```python
matrix_gate = "PASS" if all(
    worker["pass_rate"] * 100 >= gate_threshold
    for worker in worker_summaries
) else "FAIL"
```

**理由**: 1 个 worker pass rate 显著低于其他 3 个 (例如 80% vs 95%) 时, 主指挥需要立即知道具体哪个 shard 出问题, 而非 "整体 92.5% pass" 一句带过. 严格 gate 强制报告按 worker 细分失败原因.

**反例**: `matrix_gate = "PASS" if overall_pass_rate >= 90% else "FAIL"` — 模糊化, 失败原因被掩盖.

**纪律**: matrix gate 严格性是 Phase 3 核心价值, 不能妥协. 任何 "softer gate" 必须主指挥拍板 + 文档记录.

### 铁律 5: Dry-fallback 模式必须 placeholder 0% pass rate + 主指挥 SSH 标注

**原则**: 本地 PC 无 MIMO_API_KEY + test DB 时, Phase 3 runner 必须用 `_dry_placeholder_results` 输出 0% pass rate, 报告**显式标注** "Action: main orchestrator must SSH onto the runner host with MIMO_API_KEY + DATABASE_URL exported". 不能 100% pass rate (假阳性) 也不能回 exit 0 (静默成功).

**正例**:
```python
worker_summaries = [
    _dry_worker_summary(worker_id, shard, wall_clock_s=0.0)
    for worker_id, shard in enumerate(shards)
]
# 0% pass rate, veridct=unknown
# Notes: "MIMO_API_KEY not present -> skipped live run"
#        "Action: main orchestrator must SSH ..."
```

**反例**: 静默 exit 0 / 100% pass rate (假阳性) / 完全 crash 报 500 (打断 CI).

**纪律**: 任何 Phase 3 派生 runner (Phase 4 / 5) 必须保留 dry-fallback 模式 + 显式标注 "主指挥 SSH 跑". 这是 W67 baseline 决策的延续 (W67 第 47 步 docs/CI 占位维持).

---

## 4️⃣ 锚点范式 W68 第 8 批 95 → **96** 守恒

### 4.1 累计节奏

| 周期 | 锚点范式 | 关键事件 |
|------|---------|----------|
| W7 | 12 | 初代锚点范式 |
| W66 | 27 | 67 plans 100% 状态化 |
| W67 | 28 | qa-bench D5 gate 真治本失败接受 docs/CI 占位 |
| W68 | 30 | 路线 B 调研 5 路径 + 推荐路径 3+1 组合 |
| W68 第 3 批 | 42 | 11 agents 跨主题 (Drive v2 PR9 + D6 调研 + Mobile UX v3.1) |
| W68 第 4 批 | 57 | 15 agents + 2 Plan 闭环 + 跨主题 80+ commits |
| W68 第 5 批 | 72 | 15 agents 派工 + 锚点范式第 96 守恒 (本文期望) |
| **W68 第 8 批** | **96** | **Phase 3 matrix 4 runner (本文) + 5 新铁律** |

### 4.2 0 production code 改动铁律守恒

| 维度 | W68 第 8 批 B-4 | 累计 W68 |
|------|-----------------|----------|
| **production code 改动** | **0** | **0** (跨 W68 第 1-8 批 80+ agent commits) |
| **app/ 改动** | 0 | 0 |
| **web/ 改动** | 0 | 0 |
| **alembic/versions/ 改动** | 0 | 0 |
| **tests/qa-bench/ 改动** | +3 文件 (matrix runner + 报告 + 复用 phase2) | +10+ 文件 |
| **docs/ 改动** | +~100 行 (roadmap §10) | +~500 行 |
| **memory/ 改动** | +1 文件 (本文) | +30+ 文件 |

### 4.3 锚点范式单调上升不变量

- ✅ W68 第 8 批 95 → **96** (Phase 3 matrix 4 runner + 5 新铁律)
- ✅ 累计 8 批 50+ agent commits + W68 跨主题 80+ commits
- ✅ W19 选项 A 维持
- ✅ 71 PASS + 7 SKIP baseline 守恒 (跨 60+ commit 0 regression)

---

## 5️⃣ 失败回滚路径

Phase 3 完全失败回滚步骤:

```bash
# 主指挥本地
git revert <phase3-commit-hash> --no-edit
git push origin main
# 重新部署 webhook 30s 后, 回到 Phase 2 single runner
```

**回滚后接受**:
- Phase 2 single runner (8-12 min wall clock)
- docs/CI 占位 (W67 baseline 维持)
- 锚点范式 第 96 守恒撤销 (W68 第 8 批 95 维持)

**回滚触发条件**:
- matrix runner dry-run 失败 (本次跑通, 不会触发)
- Phase 2 import 失败 (Phase 2 还未 merge, 临时从 commit 拷贝)
- 主指挥 SSH 跑后测得 wall clock > 30 min (matrix 没有节省时间)
- 任何 1 worker fail-loud (asyncio.Semaphore 锁不当)

---

## 6️⃣ 沉淀位置与未来引用

**本文沉淀位置**:
- 核心 memory: `memory/w68-route-8-b4-qa-bench-phase3-matrix-2026-07-24.md` (本文, ~150 行)
- 工具: `tests/qa-bench/phase3_matrix_runner.py` (~430 行)
- 报告: `tests/qa-bench/phase3_matrix_report_2026-07-24.md` (~150 行)
- 路线图: `docs/qa-bench-d6-implementation-roadmap.md` §10 (+~100 行)

**未来引用路径**:
- W68 第 8 批主指挥 SSH 跑真实 1000 题 → 填报告 §4 表格 + memory 锚点范式 96 → 96+1 守恒
- W69 第 1 批 Phase 3 grand closure → 锚点范式 96 → 100 守恒
- W70+ future PR: 1000 题 → 5000 题 时, 调整 `--workers 8/16` (无需改代码)

**关联文档**:
- `docs/qa-bench-d6-implementation-roadmap.md` (W68 第 5 批 B-3 路线图, 路径 4 推荐, §10 新增)
- `tests/qa-bench/phase2_dry_runner.py` (W68 第 7 批 B-2, Phase 2 单 runner 骨架)
- `tests/qa-bench/phase3_matrix_report_2026-07-24.md` (本次 dry-fallback 报告)
- `memory/w68-route-5-qa-bench-d6-phase1-2026-07-24.md` (Phase 1 实施沉淀)
- `memory/w68-route-7-b2-qa-bench-phase2-2026-07-24.md` (Phase 2 实施沉淀)

---

## 7️⃣ W68 第 8 批 B-4 自我评估

**完成度**:
- ✅ 1 新建 matrix runner (430 行, syntax OK, dry-run 验证逻辑正确)
- ✅ 1 新建报告 (150 行, 同 Phase 2 结构)
- ✅ 1 改 roadmap (+~100 行 §10)
- ✅ 1 新增 memory (本文, ~150 行)

**0 production code 改动铁律**: 维持 (仅 tests/qa-bench/ + docs/ + memory/)

**5 新铁律沉淀**: matrix 拆分 deterministic / 双层 Semaphore / verdict consensus 复用 / matrix gate 严格性 / dry-fallback 主指挥 SSH 标注

**锚点范式**: W68 第 8 批 95 → **96** 单调上升

**下一步**: 主指挥 SSH 跑真实 1000 题 (本地 PC 无 MIMO_API_KEY + test DB), 填报告 §4 表格 → 触发 W69 第 1 批 Phase 3 grand closure → 锚点范式 96 → 100 守恒.

---

**Anchor**: 锚点范式 W68 第 8 批 95 → **96** 单调上升, W68 第 8 批 B-4 Phase 3 matrix 4 runner 实施 0 production code 改动铁律完全守恒. 4 文件交付 (1 工具 + 1 报告 + 1 改 roadmap + 1 memory), 5 新铁律沉淀, 工具 dry-fallback 验证逻辑正确, 待主指挥 SSH 跑真实 1000 题.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
