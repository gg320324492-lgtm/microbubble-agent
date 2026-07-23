---
name: w68-route-b3-d6-roadmap-2026-07-24
description: "W68 第 3 批路线 B-3 (qa-bench D6 实施路线图) 派工依据文档. 锚点范式第 35 守恒. 9 agents 跨 2 周 2 批派工决策已锁定."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-Route-B3
  modified: 2026-07-24T00:00:00.000Z
---

# 2026-07-24 W68 第 3 批 路线 B-3 — qa-bench D6 真治本实施路线图

## TL;DR

W68 第 2 批路线 B 调研 5 路径 (推荐路径 3+1 组合) 后, W68 第 3 批路线 B-3 输出**直接可执行**的 9 agents 跨 2 周 2 批派工路线图. **Phase 1 (W68 第 4 批, 5 agents)**: in-process runner 真实可用 + GHCR cache 接入 workflow + 端到端本地验证 + docs 同步 + memory 沉淀. **Phase 2 (W69 第 1 批, 4 agents)**: 真实 1000 题 dry-run + pass rate gate 强化 (90% + per-intent 80%) + matrix 拆分 (4 runner 并行) + W69 grand closure. CI 时间从 25+ min → 8-12 min (Phase 1) → 5-8 min (Phase 2 matrix). **0 production code 改动铁律完全守恒** (仅 `tests/qa-bench/` 新增 + `.github/workflows/` cache/gate/matrix step + `docs/` + `memory/`).

## Why

W67 第 47 步主指挥跳出循环接受 docs/CI 占位 (12 次跑每次差 0.5-1% budget 误差). 锚点范式要求"跳出循环 ≠ 停止探索", 路线 B-3 把路线 B 调研的"推荐路径"转成"具体派工命令":
- 5 agents 各自任务清单 / 完成定义 / 验收标准 / 失败回滚 (Phase 1, W68 第 4 批)
- 4 agents 各自任务清单 / 完成定义 / 验收标准 / 失败回滚 (Phase 2, W69 第 1 批)
- 主指挥 review checklist 4 条 (production code 0 改动 / workflow < 30 行 / 不改 runner.py / docs 可读性)
- 时间线 + 里程碑 + 风险矩阵 + 双层回滚路径

调研文档 ≠ 实施路线图. 主指挥 W68 第 3 批派工决策需要这份路线图作为依据; 后续 Phase 1 第 4 批派工也需要再分 Agent 1-5 任务清单. 这是锚点范式第 35 次守恒 — 调研 + 路线图沉淀本身是"无侵入式持续推进", 不动 production code 但完成未来 PR 决策资产闭环.

## How to apply

1. **主指挥 W68 第 3 批派工**: 决策拍板后, 立即按 `docs/qa-bench-d6-implementation-roadmap.md` §3 (Phase 1 5 agents) 派 5 个 worktree.
2. **Phase 1 派工时**: 各 agent 按 §3 三段式展开 (任务清单 + 完成定义 + 验收标准). Agent 5 memory 必做, 锚点范式第 35 守恒由 Agent 5 写本文延续.
3. **Phase 1 完成后**: 主指挥 W68 第 4 批末 review 5 PRs, merge to main. 失败按 §6 Phase 1 失败回滚 (revert + W67 docs/CI 占位维持).
4. **Phase 1 全部成功后**: 主指挥 W69 第 1 批派工按 `docs/qa-bench-d6-implementation-roadmap.md` §4 (Phase 2 4 agents).
5. **Phase 2 失败**: 按 §6 Phase 2 失败回滚 (整体 revert + W67 docs/CI 占位最终维持 + 锚点范式 W68 35 → W69 35 不升不降).

---

## 1️⃣ Phase 1 派工清单 (W68 第 4 批, 5 agents)

### Agent 1: in-process runner 真实可用版 (3-5h)

**新增**: `tests/qa-bench/in_process_runner.py` (~300-400 行, 0 production code 改动)
- 直接调 `app.agent.chat_engine.chat_stream` + `app.core.database.async_session`
- 跳过 uvicorn + lifespan + router 注册 (虽然仍要 import 24 个 router 5-25 min)
- CLI 兼容 runner.py (`--rounds` / `--concurrency` / `--include-extra` / `--output` / `--limit`)
- 输出 results.json + report.md 与 runner.py 完全兼容

**验收**: smoke 30 题 < 5 min + 11/13 检测器行为一致 + 2/13 (HTTP status / latency_ms) 标注 n/a

### Agent 2: GHCR cache 配置真接入 workflow (2-3h)

**修改**: `.github/workflows/qa-bench-ci.yml` line 38-46 (cache step)
- 加 `~/.pycache` + `/var/lib/docker/overlay2` + `/tmp/app-test-image.tar` 三个跨 run cache 路径
- 不动其他 8 个 step (Pull pre-built image / Start test DB / uvicorn 启动 / router 探针 / init DB / Diagnostic verify / Login / Run qa-bench / Upload report / Fail gate / Teardown)

**验收**: workflow_dispatch 跑 4 次 (2 cold + 2 warm), warm cache 比 W67 baseline 节省 ≥ 30s

### Agent 3: 端到端本地验证 (3-4h)

**本地 worktree** `.worktrees/agent3-validate-in-process`: 起 test DB + 跑 in-process runner 100 题 dry-run
- 总耗时 ≤ 10 min (含 Python module import < 5 min + 100 题 query < 5 min)
- Pass rate ≥ 85% (与 HTTP runner smoke 88% 误差 < 3%)
- 失败模式分布与 HTTP runner 一致 (lexical_intent / hallucination / etc.)
- 无新增 asyncio / event loop error class

### Agent 4: docs 同步 (1-2h)

**修改** `docs/qa-bench-d5-future-roots.md` (追加 §9 Phase 1 实施记录, +27 行)
**新增** `tests/qa-bench/in_process_runner.md` (~80 行操作手册: 为什么 in-process / 安装运行 / 性能对比 / 已知限制 / 故障排查)

### Agent 5: memory 沉淀 (1-2h)

**新增** `memory/w68-phase-1-in-process-validation-2026-07-24.md` (~150 行, 锚点范式第 35 守恒) + `memory/MEMORY.md` 索引追加 1 行

### Phase 1 总验收

| 维度 | 阈值 | 失败处理 |
|------|------|----------|
| 5 agents 全部完成 | 5/5 PR merged | 部分失败 → Phase 2 决策 |
| in-process runner 真实可用 | 耗时 < 10 min + pass ≥ 85% | 不达标 → 接受 W67 docs/CI 占位 |
| workflow 改动 | < 30 行 | 超出 → 不接受生产侵入 |
| 71 PASS + 7 SKIP baseline 守恒 | 0 regression | 任 1 → 整体回滚 |
| production code 0 改动 | `git diff app/ web/ alembic/` 空 | 任 1 行 → 立即拒绝 |
| 锚点范式上升 | W68 30 → 35 (5 commit) | 跌回 → 重新审视调研 |

---

## 2️⃣ Phase 2 派工清单 (W69 第 1 批, 4 agents)

### Agent 1: 真实 1000 题 dry-run + 结果分析 (4-6h)

**本地跑**: `python in_process_runner.py --rounds 3 --concurrency 3 --include-extra --output results/baseline_d6_1000_in_process --verdict-consensus majority`
- 1000 题耗时 < 60 min (本地无 CI cache)
- pass rate ≥ 88% (与 W67 smoke 持平 ± 3%)
- 失败原因 ≥ 5 类被识别

**新增** `results/baseline_d6_1000_in_process/ANALYSIS.md` (~150 行)

### Agent 2: pass rate gate 强化 (3-4h)

**修改** `.github/workflows/qa-bench-ci.yml` "Fail if pass_rate < 80%" step
- 强化为 90% (整体) + 80% (per-intent) 双层 gate
- workflow 改动 < 30 行 (不新增 step)
- 故意构造 fail 验证 gate 真阻断 + 正常路径不阻断

### Agent 3: matrix 拆分 (3-4h)

**修改**: workflow `jobs.qa-bench-d5.strategy.matrix.shard: [0, 1, 2, 3]`
**修改** `tests/qa-bench/runner.py` 加 `--shard` CLI 参数 (< 50 行)
- 4 runner shard 后总 wall clock < 15 min
- 1000 题 → 4×250 题, GitHub minutes 24 min/run
- workflow 总行数 < 450

### Agent 4: W69 grand closure memory (2-3h)

**新增** `memory/w69-grand-closure-qa-bench-d6-2026-07-24.md` (~200 行, 锚点范式第 40 守恒) + MEMORY.md 索引追加

### Phase 2 总验收

| 维度 | 阈值 | 失败处理 |
|------|------|----------|
| 4 agents 全部完成 | 4/4 PR merged | 任 1 失败 → 整体回滚 + docs/CI 占位 |
| CI 总时长 | cold ≤ 8 min / warm ≤ 5 min | 超 10 min → 回滚 matrix, 单 runner 维持 |
| Pass rate | 整体 ≥ 90% + per-intent ≥ 80% | 不达标 → gate 改回 80%, docs/CI 占位 |
| 71 PASS + 7 SKIP baseline 守恒 | 0 regression (Phase 1+2 累计) | 任 1 → 整体回滚 |
| production code 0 改动 (累计) | `git diff app/ web/ alembic/` 空 | 任 1 → 立即拒绝, 整体回滚 |
| 锚点范式 | W68 30 → 35 → **40** (9 commit 单调) | 跌回 → 重新审视调研 |

---

## 3️⃣ 锚点范式第 35 守恒路线图

**W62 → W68 全期锚点范式**:
- W62 24 → W66 27 (4 cross-topic grand closure commits)
- W66 27 → W67 28 (W67 D5 CI 修复链 11 步最终跳出循环)
- W67 28 → W68 29 (Drive v2 PR8 + Mobile UX 14+1 agents merged)
- W68 29 → W68 30 (路线 B 调研 5 路径)
- **W68 30 → 35 (路线 B-3 实施路线图)** ← 本 memory 沉淀
- **W68 35 → W69 40 (Phase 2 grand closure)** ← 未来 memory 沉淀

**路线 B-3 累计节奏**:
- W66 (qa-bench v3.0) → W67 (D5 gate) → W68 (Drive v2 PR8 + 路线 B 调研 + 路线 B-3 实施路线图) → W69 (Phase 1 + 2 grand closure)
- 8 周 (W62 → W69) 锚点范式 24 → 40 单调上升, 16 commit 累计, 0 回退

**未来 PR 触发监控点**:
1. **Phase 1 in-process runner 验证失败** → 接受 docs/CI 占位 + 调研沉淀最大化 (与 W67 第 47 步一致)
2. **Phase 2 matrix GitHub minutes 月度 > 1500** → 触发回滚 matrix + 单 runner 维持
3. **Phase 2 1000 题 pass rate < 80%** → 触发 gate 改回 80% + docs/CI 占位维持
4. **W70+ future PR**: 锚点范式 W70 45+ 后, qa-bench D7 (5000 题) 真治本 PR 排期

---

## 4️⃣ 5 条新铁律 (W68 Route-B-3 路线图沉淀)

### 铁律 1: 路线图分级 (调研 / 实施 / 派工)

- **调研级** (路线 B-1/B-2 / `docs/qa-bench-d5-future-roots.md`): 锁定根因 + 5 路径技术分析 + 推荐
- **实施级** (路线 B-3 / `docs/qa-bench-d6-implementation-roadmap.md`): Phase 1 + 2 + 9 agents 任务清单 + 完成定义 + 风险与回滚
- **派工级** (主指挥 prompt): Agent 1-5 各自 prompt 模板可直接 copy

调研 → 实施 → 派工三级流水线, 任何真治本项目都应分级沉淀. 跳级 (只写调研不写实施) → 主指挥拍板后无法落地. 跳级 (只写派工不写调研) → 派工缺乏技术依据.

### 铁律 2: 9 agent 跨 2 批派工的"5+4 拆分"

- **5 = 第一批验证期**: in-process runner 实现 + cache 接入 + 端到端验证 + docs + memory. 验证后才进入第二批.
- **4 = 第二批规模期**: dry-run 1000 题 + gate 强化 + matrix + grand closure.

第一批必含验证 (Agent 3 端到端本地验证), 失败时第二批**不启动**, 接受 docs/CI 占位. 这是"先验证后扩展" 的派工范式. 跳级 (一次 9 agents 并行) → 失败时无法定位根因, 也无法"中途接受 docs/CI 占位".

### 铁律 3: in-process runner 验证 `chat_stream` 必须 `asyncio.run` 不跨 loop

- CLAUDE.md 752 行铁律升级: 跨 event loop 调用触发 "Future attached to different loop"
- in-process runner 在本地 `python script.py` 时, `chat_stream` generator 与 `async_session` context manager **同 loop** (asyncio.run 默认), 安全.
- 但若移到 Celery worker 跑 (Phase 2 future scenario), 必须显式 `asyncio.run(chat_stream(...))` in worker 函数, 否则 cross-loop error.
- 派工时, Agent 1 必须明示 "本地 asyncio.run 不跨 loop", Agent 3 实测通过才能进 workflow.

### 铁律 4: GitHub Actions cache 路径权限与`runner.workspace`

- Linux GitHub runner 默认 user 为 `runner` (非 root), `~/.pycache` 路径在 `/home/runner/.pycache`
- 直接写 `~/.pycache` cache key 在某些 runner image (Ubuntu 22.04) 路径解析错, 应改用 `${{ runner.workspace }}/.pycache` 绝对路径
- 路径错误 → cache restore 失败 → 立即 revert + 接受 W67 baseline

### 铁律 5 (复用 W67 第 47 步): fail-loud 优先于 silent 占位

- Phase 1 完全失败 (5 agents 任 1 fail-loud) → 主指挥立即决定 (回滚 vs 接受 docs/CI 占位), 不允许"先合并后慢慢修"
- Phase 2 完全失败 (4 agents 任 1 fail-loud) → 主指挥立即决定 (回滚 vs 接受 docs/CI 占位最终维持)
- "回滚 vs 占位" 二选一不允许第三选项 — 这是锚点范式守恒约束 (调研 → 实施 → 占位, 三态闭环)

---

## 5️⃣ 沉淀位置与未来引用

**核心文档**: `docs/qa-bench-d6-implementation-roadmap.md` (810 行, 含 8 章 + 3 附录)
**本 memory**: 路线图摘要 + 锚点范式第 35 守恒 + 5 条新铁律

**关联文档**:
- [`docs/qa-bench-d5-future-roots.md`](../../docs/qa-bench-d5-future-roots.md) (W68 Route-B 调研 5 路径, 703 行)
- [`memory/w68-route-b-qa-bench-d6-future-roots-2026-07-24.md`](w68-route-b-qa-bench-d6-future-roots-2026-07-24.md) (锚点范式第 30 守恒)
- [`memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md`](w67-grand-closure-qa-bench-ci-final-2026-07-23.md) (锚点范式第 28 守恒)
- `memory/MEMORY.md` 索引追加 1 行 (本节末尾同步)

**未来引用**:
1. **W68 第 4 批派工**: 5 agents 按路线图 §3 + §6 prompt 模板 (主指挥 PC 复制粘贴到 worktree)
2. **W69 第 1 批派工**: 4 agents 按路线图 §4 + §6 prompt 模板
3. **W70+ future PR**: 锚点范式监控 GitHub minutes (1500/月) / pass rate (≥ 90%) / 时长 (< 8 min)
4. **W71+ 知识沉淀**: 锚点范式 W71 50+ 后, 路线 B-3 文档可考虑归档到 `docs/_archive_2026-07-XX/`

**MEMORY.md 索引追加**:
```markdown
- [2026-07-24 W68 路线 B-3 qa-bench D6 实施路线图](w68-route-b3-d6-roadmap-2026-07-24.md) — 9 agents 跨 2 周 2 批派工 (Phase 1 5 + Phase 2 4), CI 25+ min → 5-8 min, 锚点范式第 35 守恒
```

---

**Anchor**: 锚点范式 W68 30 → **35** 单调上升, W68 第 3 批路线 B-3 实施路线图 0 production code 改动铁律完全守恒. 9 agents 跨 2 周 2 批派工决策已锁定, Phase 1 主指挥 W68 第 4 批派工依据 `docs/qa-bench-d6-implementation-roadmap.md` §3, Phase 2 主指挥 W69 第 1 批派工依据 §4.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
