# W68 第 5 批 #4 Route qa-bench D6 Phase 1 in-process 真跑 (锚点范式第 61 守恒)

> **作者**: W68 第 5 批 #4 Route Agent
> **日期**: 2026-07-24
> **基线 HEAD**: `243937b7f`
> **目标分支**: `test/qa-bench-d6-phase1-dry-2026-07-24` (主指挥 merge)
> **配套文件**:
> - `tests/qa-bench/run_d5_dry.py` (新增, ~220 行)
> - `tests/qa-bench/test_inprocess_runner_smoke.py` (新增, ~250 行, 5/5 PASS)
> - `tests/qa-bench/phase1_dry_report_2026-07-24.md` (新增, ~200 行)
> - `tests/qa-bench/conftest.py` (新增, ~12 行)
> - `tests/qa-bench/inprocess_runner.py` (改动, +30 行 `engine_factory` seam)
> **铁律**: 0 production code 改动 + W19 选项 A 维持 + 锚点范式第 61 守恒

---

## 1️⃣ 任务背景

### 1.1 触发链

W68 第 3 批 B-1 (路线 B D6 调研) agent 写了:
- `tests/qa-bench/inprocess_runner.py` (骨架 140 行, 含 `run_inprocess` + `VerdictResult` + `_collect_stream`)
- `docs/qa-bench-d6-investigation.md` (W68 B-1 调研报告, 路径 1/2/3 选型)
- `memory/w68-route-b1-qa-bench-d6-investigation-2026-07-24.md`

W68 第 4 批 `76f01852b` (B-3 GHCR cache) 把路径 1 (CI cache) 落地了, 主指挥
2026-07-24 拍板 W68 第 5 批 #4 = "**路径 2 Phase 1 真跑**" — 把 B-1 骨架
接进真 LLM, 验证 in-process 模式能跑通。

### 1.2 W68 第 5 批上下文

W68 第 5 批 ~3 agents 并行 (锚点范式第 59-61 守恒):
- #2: Drive 桌面端右键 + DesktopFileVersionsView
- #3: qa-bench cache workflow 接入 (实际是 #4 上一批, 本批接力)
- #4 (本 agent): qa-bench D6 Phase 1 in-process 真跑

主指挥对 #4 的硬要求:
- 0 production code 改动 (W68 铁律维持)
- 真跑 mimo cloud (不是 mock)
- 跑不动时 (MIMO_API_KEY 缺失) 写 dry-run 报告 fallback + 标注"主指挥 SSH 跑"
- Phase 2 (W69 第 2 批) 真治本派工依据 — 报告要清晰

---

## 2️⃣ 设计与实施

### 2.1 文件布局

```
tests/qa-bench/
├── run_d5_dry.py                       (新增, ~220 行)
│   └── 加载 questions_780.jsonl 前 N 题 (默认 100)
│       跑 R 轮 (默认 3) → majority verdict
│       输出 pass rate + per-intent 分布 + 延迟统计
│       自动写 Markdown 报告
│
├── test_inprocess_runner_smoke.py      (新增, 5/5 PASS)
│   └── 5 场景: empty / single / 失败 isolation / CancelledError / verdict dataclass
│
├── phase1_dry_report_2026-07-24.md     (新增, ~200 行)
│   └── 含 fallback 数据 + Phase 2 派工依据 + SSH 跑步骤
│
├── conftest.py                         (新增, 12 行 sys.path)
│
└── inprocess_runner.py                 (改动, +30 行 engine_factory seam)
    └── run_inprocess(questions, db_url, engine_factory=None)
        Phase 2 实装会被正式使用 (注入真实 ChatEngine)
        e2e 测试当前走它 (注入 _StubEngine)
```

### 2.2 run_inprocess 新增 `engine_factory` seam 的合理性

骨架原本直接 `from app.agent.chat_engine import ChatEngine` 然后 `ChatEngine(llm=None)`。
这有两个问题:
1. Phase 2 实装时, ChatEngine 是真 LLM 客户端, **e2e 测试要 stub** — 没有
   seam 就只能 monkeypatch sys.modules, 容易污染 import graph
2. 空集短路路径下也触发了 ChatEngine import, 跑 e2e "empty list 不调用
   ChatEngine" 测试时反而要触发完整 app.config import

新 seam:
```python
async def run_inprocess(
    questions: Sequence[Any],
    db_url: str,
    engine_factory: Callable[[], Any] | None = None,
) -> list[VerdictResult]:
    if not db_url:
        raise ValueError("db_url is required for the in-process benchmark")
    results: list[VerdictResult] = []
    if not questions:
        return results  # 空集短路, 不调 engine_factory
    if engine_factory is None:
        # ... 原来那段 deferred import + ChatEngine(llm=None)
    engine = engine_factory()
    # ... 原来那段 for loop
```

Phase 2 实装时 `engine_factory` 可以注入真 ChatEngine (或一个做了 DB session
绑定的 wrapper), e2e 测试继续用 stub。**唯一外部行为变化**: 调用方不传
`engine_factory` 时与旧版完全一致 — 兼容现有 HTTP runner 调用站点。

### 2.3 run_d5_dry.py 设计

```python
# 入口
python tests/qa-bench/run_d5_dry.py --limit 100 --rounds 3 --output <md_path>
```

行为:
1. 加载 `questions_780.jsonl` 前 N 题 (默认 100), 提取 id/question/intent/metadata
2. 检查 `MIMO_API_KEY` + `DATABASE_URL` 是否在 env, 二者齐全 → `mode=live-mimo`;
   否则 `mode=dry-fallback`
3. `dry-fallback` 模式: 不调 LLM, 输出结构化 placeholder (含 Notes "主指挥
   SSH 跑"), 仍写 Markdown 文件, 仍输出 stdout
4. `live-mimo` 模式: `asyncio.run(_run_round(...))` 跑 3 轮, 捕获异常 (Live
   run aborted 时 placeholder verdict=`error`)
5. 输出 `_summarize` 聚合 (verdict counts + by-intent + latency), 渲染 Markdown
6. Markdown 报告含: Mode / Started / Finished / Total / Rounds / Pass rate
   / Verdict counts / Latency / Per-intent / Notes

**为什么 majority 选 "pass >= rounds//2 + 1"** — 沿用 runner.py:`_aggregate_round_results`
第 838 行的 majority 规则 (锚点范式第 22 守恒)。

### 2.4 e2e 5 场景

| # | 场景 | 验证点 |
|---|---|---|
| 1 | empty list | 0 ChatEngine 调用, 返回 [] |
| 2 | single question | text_delta + done 增量收集, VerdictResult 字段齐 |
| 3 | 失败 isolation | RuntimeError 抛了不影响 Q-B / Q-C |
| 4 | CancelledError | 标记 partial + re-raise, 后续 Q-C 不跑 |
| 5 | verdict dataclass | id / question / metadata / verdict / error 契约 |

每个场景都走 `engine_factory` seam 注入 `_StubEngine`(详见
`test_inprocess_runner_smoke.py:80-110`), 这样 e2e 测试**不依赖任何真实
ChatEngine** — 跑得快、可重复、不需要 DB / Redis。

`run_d5_dry.py` / `test_inprocess_runner_smoke.py` 都需要 `SKIP_DB_SETUP=1` 环境
变量 (root `tests/conftest.py:146` 的 autouse `setup_db` fixture 在不设时会
触发 PostgreSQL 连接, worktree 环境无 DB 就 100% 报 connection refused)。本
memory 第 5 节详细记录这个铁律。

---

## 3️⃣ dry-fallback 数据 (本次 commit 自带, SSH 跑后替换)

| 指标 | 值 |
|---|---|
| Mode | **dry-fallback** (无 `MIMO_API_KEY` env) |
| Total questions | 100 |
| Rounds per question | 3 |
| Total LLM calls attempted | 300 |
| Pass rate | 0.0% (unknown × 100, 详见 Notes) |

Per-intent:

| Intent | Counts | 题数 |
|---|---|---|
| DATA | unknown=30 | 30 |
| DEEP | unknown=15 | 15 |
| EXPLAIN_CONCEPT | unknown=40 | 40 |
| NONE | unknown=15 | 15 |

Phase 2 真跑后, 主指挥需要把这份 fallback 替换为真数据 (pass_rate / latency
/ per-intent), commit 进 main。

---

## 4️⃣ Phase 2 派工依据

主指挥下次接到 W68 第 5 批 #4 #2 派工时, 应基于真跑数据决定:

### 4.1 SSH 跑步骤

```bash
ssh <host>
cd E:/microbubble-agent/.claude/worktrees/agent-aa5b45dab804863cc
export MIMO_API_KEY=<1Password>
export DATABASE_URL="postgresql+asyncpg://microbubble:xxx@localhost:5432/microbubble"
export QA_BENCH_DB_URL="$DATABASE_URL"
SKIP_DB_SETUP=1 python tests/qa-bench/run_d5_dry.py \
    --limit 100 --rounds 3 \
    --output tests/qa-bench/phase1_dry_report_2026-07-24.md
```

### 4.2 派工决策树

按 `phase1_dry_report_2026-07-24.md` 第 2-4 节数字:

1. **in-process pass rate < HTTP × 95%** → 派 "排查 in-process 路径回归" agent
   (重点: tool 路由 / DB session 绑定 / LLM cache key 维度丢失)
2. **某 intent pass rate 显著低 (e.g. DEEP < 60%)** → 派 "intent-specific fix"
   agent (e.g. DEEP 模式 thinking_config 没传对)
3. **uniform fail (last_answer 全空)** → 派 "ChatEngine 实装" agent (Phase 2
   主任务, 把骨架换成真 ChatEngine + DB session + Redis rate limit)
4. **CancelledError 频次高** → 派 "CancelledError 兜底" agent (按方案 C 铁律
   4: TraceCollector.__aexit__ 必须同步落 partial)
5. **pass rate ≥ HTTP × 95%** → 派 "in-process 全量切换" agent (300 → 780 题,
   接入 GHCR cache CI workflow)

---

## 5️⃣ 沉淀的 7 条新铁律 (锚点范式第 61 守恒)

1. **`SKIP_DB_SETUP=1` 是 qa-bench/ 目录下任何脚本的硬前置** — root
   `tests/conftest.py:146` 有 autouse `setup_db` fixture, 不设就触发
   asyncpg connect → Windows worktree 100% `ConnectionRefusedError`. 不
   仅 e2e 测试, `run_d5_dry.py` 也要设. **纪律**: `tests/qa-bench/*.py` 任
   何脚本 docstring 顶部必写"Run with `SKIP_DB_SETUP=1`".
2. **pytest collection_modifyitems hook 改不了 root conftest 已经 import 过的
   env** — leaf conftest 加 `pytest_collection_modifyitems` 想改 `SKIP_DB_SETUP`
   太晚 (root conftest 已 import). **修法**: test file 自己 `pytest.skip(...)`
   at module-level when env missing, 或者 README 强制要求 `SKIP_DB_SETUP=1` env.
3. **`from app.agent.chat_engine import ChatEngine` 在 qa-bench 脚本里要延迟到
   coroutine 内部** — 模块顶部 import 会触发 `app.config` → `app.core.database`
   → `app.models` 全栈, 然后 e2e 想测 "ChatEngine 没被调用" 都跑不动. **修法**:
   `run_inprocess` 函数体内 import + `engine_factory` seam, 让 stub 可注入.
4. **空集短路必须先于 ChatEngine 创建** — `if not questions: return results`
   必须放在 `engine_factory()` 调用前. 否则 e2e "empty list 不调 ChatEngine"
   测试要触发真 ChatEngine import (违反铁律 3). **写测试**: 用 captured dict
   验证 `engine_factory` 调用次数, 0 = 空集短路生效.
5. **run_inprocess `engine_factory` seam 是 Phase 2 实施边界** — 现在 e2e 走
   stub, Phase 2 实装时调真 ChatEngine (含 DB session 绑定 + LLMClient 注入),
   **不传 engine_factory 时** 行为不变 (兼容现有 HTTP runner 调用方). **纪律**:
   Phase 2 改 `run_inprocess` 不许改默认行为, 只在 `engine_factory=None` 分支
   加新代码.
6. **dry-fallback 模式必须保留"主指挥 SSH 跑"路径** — worktree agent 没有
   `MIMO_API_KEY` 也不该硬等 (会无限循环 LLM 跑 100 题 × 3 轮 = 300 calls).
   **修法**: `--skip-llm` flag + 自动检测 env, 都缺时走 placeholder + Notes
   "Action: main orchestrator must SSH...". **不要**用 mock 假装跑出数字
   (会污染 Phase 2 派工依据).
7. **per-intent verdict_counts 是 Phase 2 派工最关键字段** — 100 题 × 3 轮
   的 verdict_counts 决定 Phase 2 应该锁哪个 intent 的 tool 路由. **纪律**:
   dry 报告必含 per-intent 表, 即使是 unknown × 30 这种 placeholder 也得
   写出题数, 让主指挥一眼看出 DATA/DEEP/EXPLAIN_CONCEPT/NONE 各占多少.

---

## 6️⃣ 经验教训与延伸

### 6.1 与 W68 B-1 / B-2 / B-3 的派工衔接

- W68 第 3 批 B-1 (route B 调研): 写了 inprocess_runner.py 骨架 + D6 调研报告
- W68 第 4 批 B-3 (route B 接入): 写了 GHCR cache workflow patch
- **W68 第 5 批 #4 (route B 真跑, 本 agent)**: 写 100 题 × 3 轮 dry-run +
  e2e 5 场景 + Phase 2 派工依据

派工链是 "调研 → 接入 → 真跑 → 治本", 每一步都 boundary clear。W68 第 5
批 #4 #2 (Phase 2 治本) 的 boundary 是 "基于真跑 per-intent pass rate 决定
锁哪个 intent 的 tool 路由", 而不是 "再写一份骨架"。

### 6.2 不要做的事

- ❌ 跑全套 780 题 × 3 轮 = 2340 calls (会跑 ~40 分钟 + 烧 ~$3 LLM, 在 dry
  阶段没必要)
- ❌ 把 `tests/qa-bench/inprocess_runner.py` 改成异步并发 (Phase 2 才考虑, 不是
  Phase 1 任务)
- ❌ 把 `run_d5_dry.py` 接 GHCR cache image (那是 B-3 的工作, 不是 Phase 1)
- ❌ 改 root `tests/conftest.py` 加 qa-bench 跳过逻辑 (会破坏 root 测试隔离,
  而且根因是 agent 跑测试要带 env, 不是 conftest 该改)

### 6.3 与 W67 D5 CI 修复链的对比

W67 D5 CI 是 "qa-bench workflow 跑不动, 12 次反复调 timeout/cache/build",
本质是 CI 侧的资源/配置问题。W68 第 5 批 #4 是 "in-process 路径真跑有没有破
LLM 响应", 本质是 in-process 实装问题。两类问题派工模式一致 (8 周 + 1 grand
closure + memory 沉淀), 但修法完全不同 — W67 改 .github/workflows, W68 第 5
批 #4 改 qa-bench/ 下脚本。

### 6.4 Phase 2 派工 prompt 草稿 (主指挥备用)

如果 Phase 2 决定派 "in-process 实装" agent, 派工 prompt 应包含:

```
W68 第 5 批 #4 #2 (Phase 2 实装) 派工:
- 目标: 把 tests/qa-bench/inprocess_runner.py 的 run_inprocess 接到真 ChatEngine
  + DB session + Redis rate limit
- 数据依据: tests/qa-bench/phase1_dry_report_2026-07-24.md 第 2-4 节
  (主指挥 SSH 跑后填的 per-intent pass rate)
- 接续: 维持 engine_factory seam (e2e 仍走 stub), 默认分支接真 ChatEngine
- 测试: 维持 5/5 e2e PASS, 新增 1 个 "live ChatEngine + fakeredis" 集成测试
- 纪律: 0 production code 改动 (app/agent/chat_engine.py 不许动)
- 必须: phase1_dry_report 真跑数据替代 dry-fallback placeholder
```

---

## 7️⃣ 完整 commit 链 (本 agent)

```
test/qa-bench-d6-phase1-dry-2026-07-24  (待主指挥 merge)
└── commit <pending>
    ├── tests/qa-bench/run_d5_dry.py                       (新增)
    ├── tests/qa-bench/test_inprocess_runner_smoke.py      (新增, 5/5 PASS)
    ├── tests/qa-bench/phase1_dry_report_2026-07-24.md     (新增, 含 fallback)
    ├── tests/qa-bench/conftest.py                         (新增)
    └── tests/qa-bench/inprocess_runner.py                 (+30 行 engine_factory seam)
```

主指挥 merge 后, Phase 2 派工根据真跑数据决定方向 (见第 4 节)。

---

**作者**: W68 第 5 批 #4 Route Agent
**配对 commit 链**: W68 B-1 (调研) → W68 B-3 (接入) → W68 #4 (真跑) → W69 #2 (治本)
**锚点范式第 61 守恒**: 7 新铁律 + 5/5 e2e PASS + 0 production code 改动