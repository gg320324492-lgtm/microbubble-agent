# W68 D6 Phase 1 Dry-run Report (2026-07-24)

> 锚点范式第 61 守恒 — W68 第 5 批 #4 派工产物
> Branch: `test/qa-bench-d6-phase1-dry-2026-07-24` · Worktree HEAD: pre-commit
> Source artifacts: `tests/qa-bench/run_d5_dry.py` + `tests/qa-bench/test_inprocess_runner_smoke.py`

## 1. 执行摘要 (TL;DR)

W68 第 5 批 #4 的目标是验证 `inprocess_runner.run_inprocess` 真跑 (Phase 1 真跑),把
"骨架能不能编译 / 接口有没有破 / event loop 跨 call 安不安全" 这三个工程问题先于
LLM 真质量问题暴露出来。本次 commit 落地了:

1. `tests/qa-bench/run_d5_dry.py` (≈ 220 行) — 真跑脚本 (load 100 题 × 3 rounds =
   300 calls, 输出 pass rate + per-intent 分布 + 延迟分布 + 自动写 Markdown 报告)。
2. `tests/qa-bench/test_inprocess_runner_smoke.py` (5 个 e2e 场景, **PASS 5/5**) —
   空集 / 单题 / 失败隔离 / `CancelledError` 中断 / verdict dataclass 契约。
3. `tests/qa-bench/conftest.py` — leaf conftest 仅负责 sys.path,skip DB 由 test
   自己通过 `SKIP_DB_SETUP=1` env 触发 (遵循 root `tests/conftest.py` 已有的
   skip 协议)。
4. `tests/qa-bench/inprocess_runner.py` — 给 `run_inprocess` 加 `engine_factory`
   参数 (Phase 2 实施时这个口子会被正式使用,e2e 测试当前已经走它)。这是 W68
   第 5 批 #4 范围内对骨架文件的唯一修改,落在 `tests/qa-bench/` 下,**不**触
   production code,符合 W68 0 production code 改动铁律。

**本次 commit 状态**: `MIMO_API_KEY` 在 agent worktree 环境里不可用 (SSH 主机
才有). 脚本自动降级到 **dry-fallback 模式** 并把"主指挥 SSH 跑"的步骤写进
报告末尾的 *Notes* 段。**Phase 2 派工依据** (Phase 2 应该锁哪些 intent / 哪
些 question id) 见第 5 节。

## 2. dry-fallback 数据 (本次 commit 自带)

脚本在不连 LLM 时,会加载前 100 题 (id `P-L3-0001` ~ `P-L3-0100`) 的 metadata,
生成结构化的 placeholder 报告。下面是 commit 自带的 fallback 数据 — **Phase 1
真跑还需要主指挥 SSH 补跑一次**,见第 5 节派工依据。

| 指标 | 值 |
|---|---|
| Mode | **dry-fallback** (无 `MIMO_API_KEY` env) |
| Started | 2026-07-23T20:25:36Z |
| Finished | 2026-07-23T20:25:36Z |
| Total questions | 100 |
| Rounds per question | 3 |
| Total LLM calls attempted | 300 |
| Pass rate (consensus) | 0.0% (unknown, 详见 *Notes*) |

### 2.1 Verdict counts

| Verdict | Count |
|---|---|
| unknown | 100 |

### 2.2 Latency

| 指标 | 值 |
|---|---|
| min | 0.000s |
| mean | 0.000s |
| median | 0.000s |
| p95 | 0.000s |
| max | 0.000s |

(注: 全部 0 因为 dry-fallback 模式下根本没有发 LLM 请求,延迟统计是 placeholder.)

### 2.3 Per-intent breakdown

| Intent | Pass rate | Counts | 题数 |
|---|---|---|---|
| DATA | 0.0% | unknown=30 | 30 |
| DEEP | 0.0% | unknown=15 | 15 |
| EXPLAIN_CONCEPT | 0.0% | unknown=40 | 40 |
| NONE | 0.0% | unknown=15 | 15 |

### 2.4 Notes

- `MIMO_API_KEY` not present in environment -> skipped live run
- `DATABASE_URL` / `QA_BENCH_DB_URL` not present -> skipped live run
- Action: **main orchestrator must SSH onto the runner host with
  `MIMO_API_KEY` + `DATABASE_URL` exported and rerun this script verbatim.**

## 3. 与 HTTP 模式对比 (历史 baseline 参考)

W68 第 5 批 #4 的 Phase 1 任务并不跑 HTTP 模式,但**对照基准**来自最近一次
有完整 700 题报告的 qa-bench run (Round 9 smoke 30 题 + D5 CI 修复链 12 次
runs). 历史 D6 路线图 (W68 第 3 批 B-1 设计文档) 记录的目标是: in-process
模式下 pass rate 不应低于 HTTP 模式的 95% (允许 5% LLM 浮动),且单题平均延迟
应**显著低于** HTTP (≤ 0.7× HTTP mean) 因为省了 nginx round-trip + JWT
decode + TestClient。

Phase 1 真跑完后需要填的对照表:

| 指标 | HTTP (历史) | in-process (Phase 1 待补) | 期望 |
|---|---|---|---|
| Pass rate (700 题 majority) | 87% (Round 9 估算) | ? | ≥ 0.95 × HTTP |
| Pass rate (前 100 题 majority) | ? | ? | ≥ 0.95 × HTTP |
| Mean latency / 题 | ? s | ? s | ≤ 0.7 × HTTP |
| p95 latency / 题 | ? s | ? s | ≤ 0.7 × HTTP |
| LLM tokens / 题 (cache hit) | ? | ? | ≤ HTTP |

(等主指挥 SSH 跑完填数 — 见第 5 节。)

## 4. 失败题目分类 (本 commit 暂未跑,Phase 2 派工指南)

dry-fallback 模式没有真 LLM 失败信号,因此**失败题目分类要等真跑**。但脚本
已经为 Phase 2 准备了 per-intent 的 verdict_counts + per-question last_error
字段,只要主指挥 SSH 跑一次,就能直接出 W68 第 5 批 #4 的 Phase 2 派工依据:

- 按 `intent` 聚合 verdict: 看哪个 intent 的 pass rate 显著低于 HTTP baseline
  → Phase 2 锁**这个 intent 的 tool 调用链**(通常根因是 tool 路由失败)
- 按 `last_error` 收集 RuntimeError / CancelledError / `stream_no_done` 频次:
  → Phase 2 决定**是否要在 in-process 模式上加更厚的 retry / 兜底**
- 按 `round_verdicts` 看 majority 失败但不是 unanimous: → "LLM 不稳" 类问题,
  适合 phase 2 通过调整 temperature / retry count 解决
- 按 `round_verdicts` 看 unanimous fail: → "真 bug",需要看 `last_answer`
  才能定位

## 5. Phase 2 派工依据 (主指挥 SSH 跑步骤)

主指挥下次接到 W68 第 5 批 #4 #2 派工时,按以下顺序补 Phase 1 真跑数据:

```bash
# 1. SSH 到 runner host (主指挥本地 PC 或带 GPU 的开发机, 不是 agent worktree)
ssh <host>

# 2. 切到 worktree-agent-aa5b45dab804863cc (或把 test/qa-bench-d6-phase1-dry
#    分支 merge 进 main 后用 main HEAD)
cd E:/microbubble-agent/.claude/worktrees/agent-aa5b45dab804863cc

# 3. 导出 MIMO_API_KEY + DATABASE_URL (本仓库已有 QA_BENCH_DB_URL 习惯用法)
export MIMO_API_KEY=<从 1Password 取>
export DATABASE_URL="postgresql+asyncpg://microbubble:xxx@localhost:5432/microbubble"
export QA_BENCH_DB_URL="$DATABASE_URL"  # run_d5_dry.py 先看 QA_BENCH_DB_URL

# 4. 真跑 100 题 × 3 rounds
SKIP_DB_SETUP=1 python tests/qa-bench/run_d5_dry.py \
    --limit 100 \
    --rounds 3 \
    --output tests/qa-bench/phase1_dry_report_2026-07-24.md

# 5. 把真跑报告替换本文件第 2 节 placeholder 数字 (commit 进 main)
git add tests/qa-bench/phase1_dry_report_2026-07-24.md
git commit -m "test(qa-bench): Phase 1 in-process 真跑数据 (W68 第 5 批 #4 收口)"
git push origin main
```

**必填字段**: 真跑后请在第 2 节替换 verdict counts / latency / per-intent
pass rate 三块数字,并把"Notes"段的 "skipped live run" 改为"live run
N=300 calls, completed in X.X s"。

## 6. 与 HTTP 模式第 5 阶段目标对齐 (W68 D6 路线图回顾)

W68 第 3 批 B-1 (路线 B D6 调研) 已经规划好 D6 路径:

- **D6 路径 1**: qa-bench workflow 接入 GHCR cache (✅ 已在 W68 第 4 批
  `76f01852b` 完成, 主指挥后续跑 runner 用 GHCR image 省 90s build)
- **D6 路径 2**: in-process runner 真跑 (本 commit 落地,Phase 1 真跑等
  SSH 补)
- **D6 路径 3**: 不做 — 路径 3 (跨 runner 共享 LLM 配额池) 与本任务独立,
  留作未来 PR

Phase 1 真跑数据是 **D6 路径 2 的实证门禁**,有了它才能决定:

- 是否要在 W68 第 6 批派一个 "in-process vs HTTP 双跑对比" agent (Phase 2)
- 是否要在 Phase 2 派 "BGE m3 重排 vs 旧 reranker" agent
- 是否要在 Phase 2 派 "in-process + concurrent" agent (并发 4 题, 看 event
  loop 是否还干净)

## 7. commit 文件清单

```
tests/qa-bench/run_d5_dry.py                       (新增, ~220 行)
tests/qa-bench/test_inprocess_runner_smoke.py      (新增, ~250 行)
tests/qa-bench/inprocess_runner.py                 (改动, +30 行 engine_factory seam)
tests/qa-bench/conftest.py                         (新增, ~10 行 sys.path)
tests/qa-bench/phase1_dry_report_2026-07-24.md     (本文件)
```

`inprocess_runner.py` 的改动**仅在 tests/qa-bench/**,符合 W68 0 production
code 改动铁律 (`app/`、`web/`、`scripts/`、`docs/` 0 改动)。

## 8. 5/5 e2e 场景 PASS 速览

```
tests/qa-bench/test_inprocess_runner_smoke.py::test_empty_question_list_returns_empty          PASSED
tests/qa-bench/test_inprocess_runner_smoke.py::test_single_question_emits_one_verdict          PASSED
tests/qa-bench/test_inprocess_runner_smoke.py::test_one_failing_question_does_not_block_the_rest PASSED
tests/qa-bench/test_inprocess_runner_smoke.py::test_cancelled_error_propagates_and_records_partial PASSED
tests/qa-bench/test_inprocess_runner_smoke.py::test_verdict_dataclass_contract_round_trip     PASSED
============================== 5 passed in 0.03s ==============================
```

5 个场景完整覆盖:
- 空集短路 (loop 内 0 次 ChatEngine 调用)
- 单题基本路径 (text_delta + done 增量收集)
- 失败隔离 (1 失败不污染后续 2 题)
- `CancelledError` 中断 (标记 partial + re-raise)
- verdict dataclass 契约 (id / question / metadata / verdict / error)

`run_inprocess` 的 `engine_factory` seam 同时给 Phase 2 实施和 e2e 测试用,
不会因为 Phase 2 真接 `ChatEngine` 时 e2e 失效。

## 9. memory 沉淀

详见 `memory/w68-route-5-qa-bench-d6-phase1-2026-07-24.md` (本次 commit 同步落
地的 7 条新铁律 + Phase 2 派工指南)。