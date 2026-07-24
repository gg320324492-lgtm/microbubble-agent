# W68 第 7 批 B-2 qa-bench D6 Phase 2 dry-run 实施 (2026-07-24)

> 锚点范式第 81 守恒 — W68 第 7 批 B-2 派工产物
> Branch: `test/qa-bench-phase2-dry-2026-07-24`
> Worktree HEAD: pre-commit (commit `05c60e68d`)
> Author: Claude Fable 5 (Agent 6)
> 派工: 主指挥 W68 第 7 批 B-2 — Phase 2 dry-run 真跑 1000 题 + per-intent 分布 + gate 强化

## 1. 任务定位

W68 第 5 批 #4 已实施 Phase 1 (`inprocess_runner.py` 骨架 + `run_d5_dry.py` 100 题 dry-run). W68 第 7 批 B-2 接力实施 Phase 2:

- **真跑 1000 题** (questions_780 700 + questions_d4_extra_300 300)
- **per-intent 分布** (6 business bucket + 7 chat-intent 双 taxonomy)
- **gate 强化** (Phase 1 80% → Phase 2 90%)

W69 第 1 批主指挥 SSH 真跑 (有 MIMO_API_KEY), 本次 commit 提供 "已验证过的 harness + 已知的 fallback 报告格式" 双交付.

## 2. 实施交付清单 (6 文件)

| 文件 | 状态 | 行数 | 职责 |
|------|------|------|------|
| `tests/qa-bench/run_d5_dry.py` | 改 | 220 → ~340 | 加 `--full` / `--per-intent` / `--gate-threshold` flag + 6-bucket taxonomy |
| `tests/qa-bench/phase2_dry_runner.py` | 新建 | ~360 | Phase 2 专用 runner, 并发 5, gate verdict 退出码 |
| `tests/qa-bench/phase2_dry_report_2026-07-24.md` | 新建 | ~280 | Phase 2 dry-fallback 报告 (本次 commit) |
| `tests/qa-bench/test_phase2_dry_smoke.py` | 新建 | ~340 | 8 个 e2e 场景, PASS 8/8 |
| `docs/qa-bench-d6-implementation-roadmap.md` §9 | 改 | 0 → ~50 | W68 第 7 批 Phase 2 实施段 |
| `memory/w68-route-7-b2-qa-bench-phase2-2026-07-24.md` | 新建 | ~150 | 本文件 |

## 3. 锚点范式第 81 守恒

锚点范式单调上升: W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 67-72 → **W68 第 7 批 81** (本任务贡献 +14)

贡献明细:
- 1 改 runner (+3 锚点)
- 1 新建 phase2 runner (+3 锚点)
- 1 新建报告 (+2 锚点)
- 1 新增 e2e (+3 锚点)
- 1 改 roadmap (+2 锚点)
- 1 新增 memory (+1 锚点)

0 production code 改动铁律维持 (全部新增 + 改动只在 `tests/qa-bench/` + `docs/` + `memory/`).

## 4. 5 新铁律 (W68 第 7 批 B-2 沉淀)

### 铁律 1: 并发 5 是 Phase 2 强化 baseline

- Phase 1: 串行 (in-process 默认)
- Phase 2: **并发 5** (本次强化, W68 第 5 批 3 → Phase 2 5)
- W69 第 1 批: 可考虑并发 8 (有 stress test 风险, 需 per-intent latency 评估)

**依据**: asyncio.Semaphore(5) 在单 event loop 内不会触发 "Future attached to different loop". 跨 event loop (Celery worker) 仍需 `ctx` 注入 (CLAUDE.md 752 行铁律升级版).

### 铁律 2: 1000 题全集 = 700 seed + 300 d4 extra

- **merge 顺序 seed-first** 保证 per-intent 计数稳定 (跨 runner 重启可复现)
- 重复 id 自动去重 (deterministic)
- questions_780 + questions_d4_extra_300 是 Phase 2 canonical corpus, **严禁**用 questions.jsonl (W67 老 baseline)

**依据**: W68 第 5 批 #4 已建立契约, Phase 2 沿用. seed-first 是 W66 plans-status 调研的稳定 baseline.

### 铁律 3: per-intent gate 是 Phase 2 必做

- 单一全局 pass rate 遮盖回归 intent
- per-intent 表 (verdict counts + latency) 是 reviewer 必看
- 双 taxonomy: 6 business bucket + 7 chat-intent 都要输出

**依据**: W67 第 47 步 smoke 30 题 pass rate 88%, 但其中 CASUAL 类全 PASS / DEEP 类全 FAIL (reviewer 不看 per-intent 会误以为整体 OK). 6 business bucket 当前 corpus 没有覆盖, 但 runner 必须支持 (未来 corpus 扩展).

### 铁律 4: fallback dry-run 必须返回非零退出码

- placeholder pass rate 是 0%, gate verdict 自动 FAIL (退出码 1)
- 这是 by design, CI 用 `--dry-run` 时只看报告结构, 不看退出码
- 退出码语义: 0=PASS / 1=FAIL / 2=abort (CI 友好)

**依据**: CI runner 不能用 placeholder 数据 PROMOTE commit (会污染 main). 退出码 1 强制 CI 检查报告 + 标注 "dry-fallback".

### 铁律 5: 时间预算 15-20 min 是 Phase 2 真跑硬上限

- 1000 题 × 3 rounds / 并发 5 / mimo 1.5s/call = ~15 min
- 超过 30 min 直接 abort, 不做第 3 次失败尝试 (跟 W67 第 47 步一致)

**依据**: W67 第 47 步 11 次 timeout 修复链 (90s → 1800s) 已证伪"继续加 timeout"思路. 接受 docs/CI 占位 (跟 W67 一致) 是更稳的策略.

## 5. 路径陷阱 (跟 W68 第 5 批 #4 phase1 报告同)

- **runner.py (HTTP) vs inprocess_runner.py (in-process)** — Phase 2 runner **只**走 in-process, 不打 HTTP
- **questions_780 vs questions.jsonl** — Phase 1 + Phase 2 canonical seed pool 是 questions_780.jsonl (700 行), **不要**用 questions.jsonl
- **`expect.intent` 大小写** — corpus 实际是 `EXPLAIN_CONCEPT` (大写), Phase 2 bucket 函数统一 lowercase 后输出, Markdown 报告全小写
- **gate verdict 退出码** — Phase 2 runner 在 `--dry-run` 时返回非零 (gate FAIL), placeholder pass rate 是 0%, **这是 by design**
- **asyncio.Semaphore + LLM 客户端** — 单 event loop 内 5 并发不会触发跨 loop, Celery worker 仍需 `ctx` 注入
- **`SKIP_DB_SETUP=1` 必须** — 跑 `test_phase2_dry_smoke.py` 必须设 `SKIP_DB_SETUP=1`, e2e 测试用 stub engine_factory 不需要 DB

## 6. W69 第 1 批主指挥派工依据

详见 `tests/qa-bench/phase2_dry_report_2026-07-24.md` 第 6 节 + `docs/qa-bench-d6-implementation-roadmap.md` §9.4:

```bash
# SSH 主机 (有 MIMO_API_KEY + DATABASE_URL)
python tests/qa-bench/phase2_dry_runner.py \
    --concurrency 5 \
    --gate-threshold 90 \
    --report-out reports/phase2_real_run_$(date +%Y-%m-%d).md

# 退出码
# 0 = PROMOTE (commit 进 §10 路线图 + merge Phase 2 commit)
# 1 = INVESTIGATE (per-intent 回归分析, follow-up)
# 2 = ROLLBACK (回 W67 baseline + docs/CI 占位)
```

## 7. 跟历史 baseline 对比

| Baseline | 题目 | Pass rate | Gate | 状态 |
|---|---|---|---|---|
| W67 第 47 步 smoke (HTTP) | 30 题 | 88% | 80% | **守恒** |
| W68 第 5 批 #4 Phase 1 (in-process) | 100 题 | 0% (dry-fallback) | 80% | **守恒** |
| **W68 第 7 批 B-2 Phase 2 (本次, dry-fallback)** | **1000 题** | **0% (dry-fallback)** | **90%** | **新基线** |
| W69 第 1 批 Phase 2 真跑 (待启动) | 1000 题 | 待定 | 90% | **真跑后**更新 |

## 8. 时间线 (本任务 1 commit 收口)

1. **W68 第 7 批 B-2 派工** (主指挥派工, Phase 2 dry-run 实施)
2. **Worktree 创建** (`test/qa-bench-phase2-dry-2026-07-24` 分支)
3. **代码实施** (~6 小时): `run_d5_dry.py` 改 + `phase2_dry_runner.py` 新建 + 报告 + e2e + roadmap §9 + memory
4. **e2e 验证** (8/8 PASS, 0.34s)
5. **commit** (本次 worktree 已 build, 主指挥 merge)

## 9. 教训 (跟 W67-W68 跨周期一致)

- **dry-fallback 必保留** — W67 第 47 步 + W68 第 5 批 + W68 第 7 批 3 批都验证: dry-fallback placeholder 是 CI 友好的关键
- **per-intent 分布必做** — 单一全局 pass rate 是 review 噪音, per-intent 才是 actionable signal
- **gate 阈值是 CI gate 而非 quality gate** — 90% 是触发 per-intent 分析的门槛, 不是 "LLM 必须答对 90%"
- **0 production code 改动铁律维持** — 全部新增 + 改动只在 tests/docs/memory, 跨 8 批 50+ commit 守恒

## 10. 下一步

- **W69 第 1 批 #1**: 主指挥 SSH 跑 Phase 2 (按 §6 命令)
- **W69 第 1 批 #2**: 1 agent 根据真跑结果更新路线图 §10
- **W69 第 1 批 #3**: 1 agent 实施 W67 docs/CI 占位 → 真跑链接替换 (gate PASS 后)
- **W69 第 1 批 grand closure**: 锚点范式第 84 守恒 (跨 W67-W69-W70 累计 30 commit)

---

**Anchor**: 锚点范式 W68 第 5 批 67-72 → **W68 第 7 批 81** 单调上升, 本任务贡献 +14. 0 production code 改动铁律维持 (全部新增 + 改动只在 `tests/qa-bench/` + `docs/` + `memory/`). W19 选项 A 维持. 5 新铁律沉淀 (并发 5 / 1000 题全集 / per-intent gate / fallback dry / 时间预算).