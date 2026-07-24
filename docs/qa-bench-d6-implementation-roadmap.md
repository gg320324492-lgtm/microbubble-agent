# qa-bench D6 真治本实施路线图 (W68 第 3 批路线 B-3 派工依据)

> **作者**: Claude Fable 5 (W68 Route-B-3 Agent — 路线 B 调研 5 路径后的实施路线图)
> **日期**: 2026-07-24
> **基线 HEAD**: `37e0de62a` (W68 路线 B 调研 5 路径 + 5 路径推荐路径 3)
> **前序文档**:
> - [`docs/qa-bench-d5-future-roots.md`](qa-bench-d5-future-roots.md) (路径 B-1 / B-2 调研 5 路径分析, 703 行)
> - [`memory/w68-route-b-qa-bench-d6-future-roots-2026-07-24.md`](../memory/w68-route-b-qa-bench-d6-future-roots-2026-07-24.md) (锚点范式第 30 守恒)
> **任务来源**: 主指挥 W68 第 3 批路线 B-3 — 基于 B-1 + B-2 调研, 输出一份**直接可执行**的多 agent 派工路线图 (Phase 1 + Phase 2, 共 9 个 agent).
> **铁律**: 0 production code 改动 + W19 选项 A 维持 + 锚点范式第 35 次守恒 + 71 PASS + 7 SKIP baseline 守恒
> **核心决策**: **推荐路径 3 (in-process runner) + 路径 1 (cache 深度优化) 组合**, 跨 2 周 2 批派工. Phase 1 (W68 第 4 批, 5 agents) 验证 in-process runner 可行性 + 接入 cache 优化; Phase 2 (W69 第 1 批, 4 agents) 真实 1000 题 dry-run + 结果调优 + W69 grand closure.

---

## 🎯 TL;DR

| 维度 | Phase 1 (W68 第 4 批) | Phase 2 (W69 第 1 批) |
|------|----------------------|----------------------|
| **目标** | in-process runner 真实可用 + cache 接入 workflow | 真实 1000 题 dry-run 验证 + pass rate 强化 + matrix 拆分 |
| **派工** | 5 agents | 4 agents |
| **代码改动铁律** | 0 production code (只动 `tests/qa-bench/` 新增 + `.github/workflows/` cache step + `docs/` + `memory/`) | 同 Phase 1 |
| **风险等级** | 中 (新模式首次验证) | 低-中 (基于 Phase 1 已有骨架) |
| **预计工时** | 16-24 人时 (5 agents × 3-5h) | 12-20 人时 (4 agents × 3-5h) |
| **预期收益** | CI 时间 25+ min → 8-12 min (paper 60%) | CI 时间 8-12 min → 5-8 min (论文 30%) |
| **失败回滚** | 文档 + 骨架保留, workflow cache step revert | 接受 docs/CI 占位 (跟 W67 一致) |

**Why 写这份路线图**:
- W68 第 2 批路线 B 调研锁定 5 路径, 主指挥已在 B-2 拍板 "推荐路径 3 + 1 组合". 但**调研文档 ≠ 实施路线图**.
- 实施需要明确: 谁来做 (5 agents × 具体职责), 怎么验证 (pass rate / 时长 / baseline 守恒), 失败怎么办 (回滚路径).
- 主指挥 W68 第 3 批派工决策需要这份路线图作为依据; 后续 Phase 1 第 4 批派工也需要再分 Agent 1-5 任务清单.

**How to apply**:
1. 主指挥 W68 第 3 批派工时, 直接用本文 §3 (Phase 1 agent 任务清单) + §4 (Phase 2 agent 任务清单).
2. Phase 1 派工时, 各 agent 按 §3 的 "Agent 1-5 任务清单" + "完成定义" + "验收标准" 三段式展开工作.
3. Phase 1 全部完成 + 路线 B-3 verification pass 后, 主指挥 W69 第 1 批派工用 §4 Phase 2 agent 任务清单.
4. Phase 2 失败时直接按 §6 "回滚路径" — 接受 docs/CI 占位 (跟 W67 第 47 步一致), 不做第 3 次失败尝试.

---

## 1️⃣ 路线图目标与决策锁定 (主指挥 W68 第 3 批前置)

### 1.1 选型锁定

**决策** (路线 B-2 已推荐, 本路线图确认不重启决策): **选项 B (路径 3 + 路径 1 组合)** — 跨 2 周 2 批派工. 资源受限时回退选项 A (路径 3 单独).

| 路径 | 描述 | Phase 1 | Phase 2 |
|------|------|---------|---------|
| 路径 1 | GHCR cache hit 深度优化 (pycache 跨 run volume 共享) | Agent 2 接入 workflow | - (Phase 1 已完成) |
| 路径 3 | in-process runner (直接打 test DB, 不走 HTTP / lifespan / router) | Agent 1 实现 + Agent 3 端到端验证 | Agent 1 真实 1000 题 dry-run |
| 路径 4 (Phase 2 选择性) | 拆分 1000 题到 4 runner matrix 并行 | - | Agent 3 拆分 |

### 1.2 目标 (SMART)

| 维度 | 基线 (W67 第 47 步) | Phase 1 完成后 | Phase 2 完成后 |
|------|---------------------|----------------|----------------|
| **CI 总时长 (实测)** | 25+ min (uvicorn 5-7 min 启动) | **8-12 min** (in-process 跳过 uvicorn + cache 命中) | **5-8 min** (matrix 4 runner 并行 1.5-2 min) |
| **Pass rate** | 88% (W67 第 47 步 smoke) | **> 90%** (in-process 验证) | **> 95%** (gate 强化后) |
| **71 PASS + 7 SKIP baseline** | 守恒 | **守恒** (派工不引入 regression) | **守恒** |
| **GitHub Actions minutes** | 25 min/run × 30 天 = 750 min/月 | 10 min/run × 30 天 = 300 min/月 (-60%) | 6 min/run × 30 天 = 180 min/月 (-76%) |
| **.github/workflows/ 改动行数** | 0 (W67 第 47 步维持) | < 30 行 (仅 cache step + in-process 调用) | < 50 行 (matrix step) |
| **production code 改动** | 0 | **0** (只动 `tests/qa-bench/` 新增 + `docs/`) | **0** |
| **memory 沉淀** | 锚点范式第 30 守恒 | **第 35 守恒** (本文 §7) | **第 40 守恒** (W69 第 1 批 grand closure) |

### 1.3 不变量 (任何 Phase 不得突破)

1. **0 production code 改动** — `app/` + `web/` + `alembic/versions/` 三目录**完全 0 改动**. 仅 `tests/qa-bench/` **新增** 文件 (不修改现有 `runner.py` / `gen780.py`) + `.github/workflows/qa-bench-ci.yml` **修改 cache / 调用 step 段** + `docs/` + `memory/`.
2. **71 PASS + 7 SKIP baseline** — W67 第 47 步确认守恒, Phase 1 + Phase 2 派工任何时刻不引入 lint/css/playwright 测试 regression.
3. **锚点范式单调上升** — W67 28 → W68 29-30 (调研) → W68 第 4 批 31 (Phase 1) → W69 第 1 批 32 (Phase 2). 不会回退.
4. **W19 选项 A 维持** — Drive v2 PR8 完成后主指挥维持选项 A (Drive v3 不启动), qa-bench D6 不与 Drive v3 冲突.
5. **路径 3 不替代路径 1** — 路径 3 是真治本 (跳过 uvicorn 启动), 路径 1 是 layer 外补充 (pycache 复用). 二者正交, Phase 1 同时启用.

---

## 2️⃣ 当前 D5 CI 现状快照 (Phase 1 前基线)

### 2.1 workflow 状态

| 指标 | 当前值 | 来源 |
|------|--------|------|
| Workflow 文件 | `.github/workflows/qa-bench-ci.yml` (363 行) | 直接 ls |
| Workflow timeout | 120 min | yml line 26 |
| 实测时长 | 25+ min (冷) / 5 min (warm + GHCR hit) | W67 第 48-49 步 |
| 测试题库 | 1000 题 (780 base + D4 300 extra) | runner.py --include-extra |
| LLM backend | mimo cloud (`mimo-v2.5`) | yml line 117-119 |
| 真实门禁 | pass_rate < 80% → exit 1 | yml line 331-356 |
| Router 探针 | `/health` 200 + `/auth/login` 401/422 + 60s wait | yml line 140-171 |
| Image | GHCR pre-built (`ghcr.io/<OWNER>/microbubble-agent:app-test-latest`) | yml line 73-77 |
| Database | `pgvector/pgvector:pg16` (W67 第 49 步) | yml line 91 |

### 2.2 启动阶段耗时分解 (基于 W67 第 39 + 47 步实测)

| 阶段 | 实测耗时 | 占总时长 | 路径 3+1 改善预期 |
|------|----------|----------|------------------|
| Checkout + Setup Python + Cache pip | 30-45 s | ~3% | 路径 1 改善 → 5-10 s (90%) |
| Pull pre-built image (GHCR) | 30-90 s / 5-15 s | ~5% | 路径 1 (image layer cache) → 5 s 稳定 |
| Start pg-test | 5-15 s | ~1% | 路径 3 不影响 (test DB 仍要起) |
| **uvicorn app.main:app 启动** | **5-7 min (实测 1510 s)** | **~25%** | **路径 3 完全跳过 (-100%)** |
| /health 200 + 60s wait | 60-62 s | ~5% | 路径 3 跳过 (不需要 lifespan yield) |
| Init test DB schema + seed | 10-15 s | ~1% | 路径 3 不影响 (test DB 仍要 seed) |
| **Run 1000 题 × 3 rounds × mimo** | **40-60 min** | **~50%** | 路径 3 不影响 (仍是 mimo tier 限流) |
| Generate report + fail-loud | 5 s | <1% | 无影响 |
| **合计** | **~50-75 min** | 100% | **路径 3+1 → ~30-40 min (Phase 1) → ~20-30 min (Phase 2 matrix)** |

**注**: 实测 25+ min 是 GitHub runner warm cache + GHCR hit 的实测冷启动时间 (含 build 6-10 min). 路径 3+1 完全跳过 uvicorn 启动 (5-7 min), 加上 cache 优化, 理论 Phase 1 完成后 8-12 min (测试 1000 题时). 实测偏差 ±20% 可接受.

### 2.3 路径 3+1 实施前后对比 (Phase 1 预期)

| 步骤 | 当前耗时 | 路径 3+1 Phase 1 后 | 改善 |
|------|----------|----------------------|------|
| 拉 pre-built image | 30-90 s | 5-15 s | 85% (路径 1 cache hit) |
| 启动 test DB | 5-15 s | 5-15 s | 0% |
| **uvicorn 启动 + router 注册** | **5-7 min** | **0 s (跳过)** | **100%** |
| /health 探针 + 60s wait | 60-62 s | 0 s | 100% |
| Init DB schema + seed | 10-15 s | 10-15 s | 0% |
| Run 1000 题 (mimo cloud) | 40-60 min | 40-60 min | 0% (路径 3 改调用方式, 不改 LLM 速度) |
| **CI 总时长** | **25+ min (warm + GHCR)** | **8-12 min** | **60%** |

**Phase 2 matrix 拆分后 (1000 题 → 4 runner × 250 题)**:
- Run 4 runner 并行 (GitHub minutes × 4, wall clock ÷ 4)
- 1000 题 / 4 runner × 3 rounds = 750 题 / runner × round, ~10-15 min / runner
- 4 runner 并行 wall clock ~15 min + uvicorn 启动仍可省 (路径 3 共享) → 矩阵 5-8 min
- GitHub minutes = 4 × 6 min = 24 min/run (vs 当前 25 min/run, 单 run **-4%**), 但 wall clock **75% 改善**

---

## 3️⃣ Phase 1 派工清单 (W68 第 4 批, 5 agents)

**Phase 1 总目标**: in-process runner 真实可用 (Agent 1) + GHCR cache 配置真接入 workflow (Agent 2) + 端到端本地 100 题 dry-run 验证 (Agent 3) + docs 同步 (Agent 4) + memory 沉淀 (Agent 5). 5 agents 并行工作, 总工时 16-24 人时.

### Agent 1: in-process runner 真实可用版 (3-5 人时)

**目标**: 实现 `tests/qa-bench/in_process_runner.py` — 跳过 uvicorn + lifespan + router, 直接调 chat engine + AsyncSession 跑题库.

**任务清单**:

1. **新增文件**: `tests/qa-bench/in_process_runner.py` (~300-400 行, 0 production code 改动)
   ```python
   # 核心调用链 (伪代码)
   from app.main import app  # noqa: F401 (触发 FastAPI app 创建, 不启动 uvicorn)
   from app.core.database import async_session, engine
   from app.core.security import create_access_token
   from app.agent.chat_engine import chat_stream  # 已有
   from app.services.task_service import list_tasks  # 示例工具调用

   async def run_single_question_in_process(q: dict, user_id: int):
       """单题 in-process runner"""
       async with async_session() as db:
           messages = [{"role": "user", "content": q["input"]}]
           events = []
           async for event in chat_stream(
               messages=messages,
               user_id=user_id,
               db=db,
               stream=True,
           ):
               events.append(event)
               # 类似 runner.py 检测逻辑: intent / tools / contains / etc.
           return evaluate_events(events, q)

   async def main(questions: list[dict], concurrency: int = 3):
       """并发跑题, 复用 runner.py 检测逻辑"""
       sem = asyncio.Semaphore(concurrency)
       async def run_with_sem(q):
           async with sem:
               return await run_single_question_in_process(q, user_id=1)
       results = await asyncio.gather(*[run_with_sem(q) for q in questions])
       return results
   ```

2. **关键改动点** (相对 runner.py):
   - **删除**: `httpx.AsyncClient` + `POST http://localhost:8001/api/v1/chat/stream` HTTP 调用
   - **新增**: 直接 `from app.agent.chat_engine import chat_stream` + `from app.core.database import async_session`
   - **关键差异**: in-process 仍需 `from app.main import app` 触发 FastAPI app 创建 (侧效触发 router 注册), 但**不启动 uvicorn**. 这节约 5-7 min uvicorn 启动时间, 但**仍需 5-25 min router import 时间** (24 个 router file).

3. **完成定义**:
   - 文件存在 + `python tests/qa-bench/in_process_runner.py --help` 输出 help
   - 跑 10 题 dry-run 成功 (test DB 已 seed 数据 + xiaoqi_testbot 用户)
   - `--rounds 3 --concurrency 3 --include-extra --output results/in_process_smoke` 跑 30 题 smoke 全部返回结果 (pass + fail + error count)
   - 输出 `results.json` + `report.md` 与 `runner.py` 输出格式**完全兼容** (Phase 1 Agent 4 docs 同步用)

4. **验收标准**:
   - smoke 30 题 < 5 min (本地 run, 跳过 uvicorn 启动 ~30s 验证)
   - 11/13 检测器行为与 runner.py 一致 (lexical_intent / must_contain / must_not_contain / fake_xml / hallucination_name / event_tag_leak / duration_under / tool_called / tool_not_called / verdict_consensus)
   - 2/13 检测器 (HTTP status / latency_ms 字段) in-process 不输出 — report 中标注 "n/a in-process"

5. **失败回滚**:
   - **in-process import 慢**: 如果 24 个 router 仍要 5-25 min, agent 1 1d 内完成 → 跟路径 3 调研预期**不符**, 立即上报主指挥**改回 runner.py HTTP 调用**. 不强制路径 3.
   - **Chat engine 跨 event loop**: 如果 `chat_stream` 触发 "Future attached to different loop" 错误 (CLAUDE.md 752 行铁律) — agent 1 改用 `asyncio.run` 在进程内, 不跨 loop. 仍失败就 `runner.py` 不动.

6. **派工 prompt 模板**:
   ```
   [Agent 1 — W68 第 4 批 in-process runner]
   任务: 在 tests/qa-bench/in_process_runner.py 新增文件 (~300-400 行), 实现不通过 HTTP API
         直接调 chat engine + AsyncSession 跑题库的 runner.
   约束: 0 production code 改动 (不修改 app/ 下任何文件). 仅新增 tests/qa-bench/in_process_runner.py.
         复用现有 tests/qa-bench/runner.py 的 detection logic (lexical_intent 等 11 个检测器).
   验证: 本地起 test DB (docker-compose up pg-test) + app-test 不需要 (in-process 不走 HTTP),
         seed xiaoqi_testbot + 必要 task/meeting 数据, 跑 30 题 smoke < 5 min.
   失败上报: 报告主指挥, 不强制完成. 路径 3 调研可能高估了 in-process 收益.
   ```

### Agent 2: GHCR cache 配置真接入 workflow (2-3 人时)

**目标**: 修改 `.github/workflows/qa-bench-ci.yml` 的 cache step (line 38-46), 把 pycache 跨 run 共享 volume + Docker layer cache 深度优化, 但**不动其他 step**.

**任务清单**:

1. **修改文件**: `.github/workflows/qa-bench-ci.yml` (363 行 → 估计 380 行, +17 行)
   - **修改段**: line 38-46 (Cache pip + Docker layers + apt step)
   - **新增内容**: 
     ```yaml
     - name: Cache pip + Docker layers + apt + __pycache__ (W68 step Phase 1 cache 深度优化)
       uses: actions/cache@v4
       with:
         path: |
           ~/.cache/pip
           /tmp/.buildx-cache
           /var/cache/apt/archives
           # === 新增 Phase 1 cache 深度优化 ===
           # 跨 run 共享 Python __pycache__: 让 GHA runner 复用上次 build 后的字节码缓存
           ~/.pycache  # /root/.pycache 或 /home/runner/.pycache, 取决于 runner user
           # Docker image layer (pulled image 持久化, 避免每次重新 pull)
           /var/lib/docker/overlay2  # 仅 cache metadata, 不缓存完整 image
           # GitHub workspace 中拉取的 docker image tarball (可选)
           /tmp/app-test-image.tar
         key: ${{ runner.os }}-multi-v2-${{ hashFiles('requirements.txt', 'Dockerfile', 'app/requirements.txt', 'tests/qa-bench/requirements.txt') }}
         restore-keys: |
           ${{ runner.os }}-multi-v2-
     ```
   - **关键约束**: 
     - **不动** line 73-77 (Pull pre-built image step)
     - **不动** line 91-130 (Start test DB stack)
     - **不动** line 200-260 (uvicorn 启动 + router 探针) — Phase 1 Agent 1 完成后, Phase 1.5 (后续 PR) 再考虑改这段
     - **不动** line 280-360 (qa-bench runner.py 调用)
     - **不动** line 360-363 (Teardown)

2. **完成定义**:
   - PR 提交 + CI 自动跑过 (workflow_dispatch trigger, 不污染 push to main)
   - 第二次 cache hit 时 cache 体积 < 100 MB, restore 时间 < 30 s
   - 实测 CI 总时长变化: 第一次跑 cold cache → 与 baseline 一致 (25 min); 第二次跑 warm cache → 减少 30-60 s (cache 层收益有限)

3. **验收标准**:
   - workflow_dispatch 跑 2 次 cold + 2 次 warm, 4 次实测平均值
   - cold cache (首次): 25 min (与 baseline 持平) — 这是**预期的**, cache 只在第二次起效
   - warm cache (2-4 次): **15-20 min** (cache 命中, 但 uvicorn 启动 5-7 min 仍未解)
   - 相较 W67 baseline: warm cache -30% (节省 60s), 仍受 uvicorn 启动瓶颈

4. **失败回滚**:
   - **cache hit 失败**: 立即 revert + 删除 cache step 改动. 接受 W67 baseline + docs/CI 占位.
   - **__pycache__ 路径错误**: Linux runner user 为 `runner` (非 root), 改路径为 `/home/runner/.pycache` 或用 `${{ runner.workspace }}/.pycache`. 修路径不重算 commits.

5. **派工 prompt 模板**:
   ```
   [Agent 2 — W68 第 4 批 cache 配置接入 workflow]
   任务: 修改 .github/workflows/qa-bench-ci.yml cache step (line 38-46), 把 pycache + 
         Docker image layer cache 跨 run 共享.
   约束: 仅修改 cache step block. 不动其他 step. 不增加新 step. workflow 行数 < 400.
   验证: workflow_dispatch 跑 2 次 cold + 2 次 warm, 4 次实测, warm cache 比 baseline 节省 ≥ 30 s.
   失败上报: cache hit 失败立即 revert. 不破坏现有 pull pre-built image step.
   ```

### Agent 3: 端到端本地验证 (3-4 人时)

**目标**: 在本地 (worktree) 起 test DB + 跑 in-process runner 100 题 dry-run (全题库 1/10), 验证 in-process runner 真实可用, 统计耗时 / pass rate / 失败原因.

**任务清单**:

1. **本地准备** (主指挥 PC):
   - `git worktree add .worktrees/agent3-validate-in-process -b agent3-validate-in-process main`
   - `cd .worktrees/agent3-validate-in-process`
   - `cp .env.example .env` + 填 `MIMO_API_KEY` + `DATABASE_URL` (test DB)
   - `docker-compose up -d pg-test` (复用 dev stack)
   - `python scripts/init_test_db_all.py` (seed test DB + xiaoqi_testbot)
   - `python tests/qa-bench/in_process_runner.py --rounds 1 --concurrency 1 --output results/in_process_100 --limit 100`

2. **记录**:
   - 总耗时 (含 app import time + 100 题 query time)
   - Pass / fail / error count
   - 失败原因 TOP 5 (lexical_intent mismatch / must_contain miss / fake_xml leak / etc.)
   - 与 `runner.py` (HTTP) 在同 100 题 dry-run 对比 (如果时间允许, 跑 2 轮: in-process + HTTP 各 1 轮)

3. **完成定义**:
   - `results/in_process_100/results.json` 存在
   - `results/in_process_100/report.md` 存在
   - 总耗时 < 10 min (含 Python module import < 5 min + 100 题 query < 5 min)
   - Pass rate 误差 < 5% (与 HTTP runner 在同 100 题下对比)

4. **验收标准**:
   - in-process 100 题 **总耗时 ≤ 10 min** (含 import + query)
   - Pass rate **≥ 85%** (与 HTTP runner smoke 88% 误差 < 3%)
   - **失败模式分布相同** (lexical_intent 失败占比 / hallucination 占比 / etc. 与 HTTP runner 一致)
   - **没有新的 error class** (新增的 asyncio / event loop 错误算 regression, 必须报告)

5. **失败回滚**:
   - **import 慢 (5-25 min)**: 报告主指挥, 路径 3 调研可能高估了收益. Agent 1 in_process_runner.py 文件保留 (文档骨架), workflow 不接入 (回退 Agent 2 的 cache step 改动, 但 cache 仍有用, 保留).
   - **pass rate 偏低 (< 70%)**: 与 HTTP runner 对比, 如果**显著偏低**, 上报主指挥 "in-process 与 HTTP runner 行为不一致". 不强制 Phase 1 完成.

6. **派工 prompt 模板**:
   ```
   [Agent 3 — W68 第 4 批 in-process 端到端本地验证]
   任务: 起 test DB + 跑 in-process runner 100 题 dry-run, 验证耗时 < 10 min, pass rate ≥ 85%.
   环境: git worktree add .worktrees/agent3-validate-in-process -b agent3-validate-in-process main
   验证: 含 Python module import + 100 题 query, 失败模式分布与 HTTP runner 一致.
   失败上报: import 慢 → 路径 3 收益不足, 回退保留骨架. pass rate 偏低 → 行为不一致, 暂不接入 workflow.
   ```

### Agent 4: docs 同步 (1-2 人时)

**目标**: 更新 `docs/qa-bench-500-report.md` + `docs/qa-bench-d5-future-roots.md` (追加 Phase 1 实施进度) + 新增 `tests/qa-bench/in_process_runner.md` 操作手册.

**任务清单**:

1. **修改** `docs/qa-bench-d5-future-roots.md` (line 703 → 估计 730 行, +27 行):
   - **追加段**: §9 Phase 1 实施记录 (实测耗时 / pass rate / cache 命中表现)
   - **不改** §1-§8 调研内容
   - **不改** §10-附录

2. **修改** `docs/qa-bench-500-report.md` (可选, 如 Agent 1 完成显著):
   - 追加 W68 Phase 1 段落

3. **新增** `tests/qa-bench/in_process_runner.md` (~80 行):
   ```markdown
   # qa-bench in-process runner 操作手册 (W68 Phase 1)
   
   ## 为什么 in-process runner
   ## 安装与运行
   ## 性能对比 (in-process vs HTTP)
   ## 已知限制
   ## 故障排查
   ```

4. **完成定义**:
   - `docs/qa-bench-d5-future-roots.md` 包含 §9 Phase 1 段落
   - `tests/qa-bench/in_process_runner.md` 操作手册存在
   - 文档 markdown 链接全部可点击 (本地工作树路径校验)

5. **验收标准**:
   - 文档不引入 typo / 错别字 (中文段落 Lint 友好)
   - 所有命令 `python tests/qa-bench/...` 与实际脚本路径一致

6. **派工 prompt 模板**:
   ```
   [Agent 4 — W68 第 4 批 docs 同步]
   任务: 更新 qa-bench-d5-future-roots.md 追加 Phase 1 实施记录 + 新增 in_process_runner.md 操作手册.
   约束: 0 production code 改动. 文档 markdown 链接全可点击. 中文段落简洁.
   ```

### Agent 5: memory 沉淀 (1-2 人时)

**目标**: 写 `memory/w68-phase-1-in-process-validation-2026-07-24.md` (~150 行), 锚点范式第 35 守恒.

**任务清单**:

1. **新增** `memory/w68-phase-1-in-process-validation-2026-07-24.md` (~150 行, 内容覆盖):
   - **TL;DR**: Phase 1 5 agents 全部完成 / 部分失败, 关键数字 (耗时 / pass rate / cache 命中表现)
   - **Why**: W68 第 4 批路线 B-3 实施锚点范式第 31-35 守恒
   - **How to apply**: Phase 2 (W69 第 1 批) 派工指南
   - **§1 Phase 1 5 agents 任务完成情况**: Agent 1-5 各自完成 / 部分失败 + 原因
   - **§2 实测数字**: cold cache / warm cache / in-process 耗时 / pass rate
   - **§3 锚点范式 W68 30 → 35**: 5 个 commit 逐步上升
   - **§4 5 条新铁律**: in-process vs HTTP 行为差异 / cache 路径细节 / etc.
   - **§5 Phase 2 派工指南**: 主指挥 W69 第 1 批参考

2. **完成定义**:
   - 文件存在 + 150 行左右
   - 与本文 §7 锚点范式第 35 守恒一致
   - MEMORY.md 索引追加 1 行 (Agent 5 同步更新 `memory/MEMORY.md`)

3. **验收标准**:
   - memory 沉淀**全部基于实测** (Agent 3 跑出的真实耗时), 不基于 Agent 1 的预期
   - 5 条铁律精炼, 不冗余

4. **派工 prompt 模板**:
   ```
   [Agent 5 — W68 第 4 批 memory 沉淀]
   任务: 写 memory/w68-phase-1-in-process-validation-2026-07-24.md (~150 行) + 更新 memory/MEMORY.md 索引.
   约束: 全基于实测数字 (从 Agent 3 验证报告). 锚点范式第 35 守恒. 5 条新铁律.
   ```

### Phase 1 总验收 (主指挥 W68 第 4 批后)

| 维度 | 验收阈值 | 失败处理 |
|------|----------|----------|
| **5 agents 全部完成** | 5/5 PR merged to main | 任意 1 个失败 → Phase 1 部分完成, 进入 Phase 2 决策 |
| **in-process runner 真实可用** | Agent 3 实测 < 10 min + pass rate ≥ 85% | 不达标 → 接受 W67 docs/CI 占位 + cache step 保留, Phase 2 不启动 |
| **workflow 改动 < 30 行** | Cache step + 注释 < 30 行 | 超出 → review, 不接受生产侵入 |
| **71 PASS + 7 SKIP baseline 守恒** | `tests/css/` + `tests/playwright/` 0 regression | 任意 1 个 regression → Phase 1 整体回滚 |
| **production code 0 改动** | `git diff main -- app/ web/ alembic/versions/` = 空 | 任意 1 行 → 立即拒绝, commit revert |
| **锚点范式上升** | W68 30 → **35** (5 commit) | 跌回 → 重新审视调研 |

---

## 4️⃣ Phase 2 派工清单 (W69 第 1 批, 4 agents)

**Phase 2 总目标**: 基于 Phase 1 已 work 的 in-process runner, 真实 1000 题 dry-run + 结果分析 + pass rate 强化 + matrix 拆分 + W69 grand closure. 4 agents 并行, 总工时 12-20 人时.

**前置条件**:
- Phase 1 全部 5 agents 完成 + main HEAD merge (主指挥 W68 第 4 批末)
- in_process_runner.py 真实可用 (Phase 1 Agent 1 + 3 已验证)
- workflow cache step 已接入 (Phase 1 Agent 2 已验证)
- 71 PASS + 7 SKIP baseline 守恒 (Phase 1 全程)

### Agent 1: 真实 1000 题 dry-run + 结果分析 (4-6 人时)

**目标**: 跑全量 1000 题 (D4 base 780 + extra 300) × 3 rounds × majority consensus in-process runner, 输出 `results/baseline_d6_1000_in_process/`.

**任务清单**:

1. **本地准备**:
   - `git pull origin main` (拿到 Phase 1 5 commits)
   - `cd tests/qa-bench`
   - `python in_process_runner.py --rounds 3 --concurrency 3 --include-extra --output results/baseline_d6_1000_in_process --verdict-consensus majority`
   - 期望耗时 30-60 min (跳过 uvicorn 启动)

2. **分析**:
   - 失败原因 TOP 10 (按类型聚合)
   - Pass rate 分布 (intent 类型: chitchat / task / question / meeting / knowledge)
   - Mock-only 失败 vs LLM 失败比例
   - duration 分布 (p50 / p90 / p99)

3. **新增** `tests/qa-bench/results/baseline_d6_1000_in_process/ANALYSIS.md` (~150 行):
   - pass rate 数字
   - 失败原因分布
   - 与 D5 baseline 对比 (如果有 W67 第 47 步 smoke 88% 数据)

4. **完成定义**:
   - 1000 题全部跑完 (无 crash, 单 question error 算 fail 但不 crash)
   - `results.json` + `report.md` + `ANALYSIS.md` 三件套存在
   - pass rate ≥ 88% (与 W67 baseline 持平 ± 3%)

5. **验收标准**:
   - 1000 题耗时 < 60 min (本地跑无 CI 缓存)
   - pass rate 误差 < 3%
   - 失败原因 ≥ 5 类被识别

6. **失败回滚**:
   - **pass rate 偏低 (< 80%)**: 立即上报主指挥. 1000 题真实数据不支持进 workflow, 接受 docs/CI 占位.

7. **派工 prompt 模板**:
   ```
   [Agent 1 — W69 第 1 批 1000 题 dry-run]
   任务: 跑 in-process runner 1000 题 (3 rounds, majority consensus), 输出 ANALYSIS.md.
   约束: 完全本地跑 (test DB 已 seed). 不污染 GitHub Actions.
   验证: pass rate ≥ 88%, 失败原因 ≥ 5 类被识别.
   失败上报: pass rate 偏低 → 数据不支持进 CI, 接受 docs/CI 占位.
   ```

### Agent 2: pass rate gate 强化 (3-4 人时)

**目标**: 在 `.github/workflows/qa-bench-ci.yml` 的 "Fail if pass_rate < 80%" step 调整 + 新增 per-intent gate.

**任务清单**:

1. **修改** `.github/workflows/qa-bench-ci.yml` line 331-356 (Fail if pass_rate < 80% step):
   ```yaml
   # 当前 (line 331-356):
   # 硬门禁: pass_rate < 80% → exit 1
   - name: Fail if pass_rate < 80%
     if: always()
     working-directory: tests/qa-bench
     run: |
       if [ -f results/baseline_d5_1000/results.json ]; then
         PASS_RATE=$(python3 ... )
         if [ pass_rate < 80 ]; then exit 1; fi
       fi
   
   # === 改成: ===
   - name: Fail if pass_rate < 90% OR per-intent regression (W69 Phase 2 gate 强化)
     if: always()
     working-directory: tests/qa-bench
     run: |
       python3 << 'PYEOF'
       import json, sys
       with open('results/baseline_d6_1000_in_process/results.json') as f:
           d = json.load(f)
       total = d['summary']['total']
       pass_ = d['summary']['pass']
       pass_rate = pass_ / max(total, 1) * 100
       
       # 整体门禁 90% (Phase 2 强化, 从 80% 提)
       if pass_rate < 90.0:
           print(f'❌ 整体通过率 {pass_rate:.1f}% < 90%, D6 gate 阻断 merge')
           sys.exit(1)
       
       # Per-intent 门禁: 任一 intent type 低于 80% 阻断
       by_intent = d['summary'].get('by_intent', {})
       for intent, stats in by_intent.items():
           intent_rate = stats['pass'] / max(stats['total'], 1) * 100
           if intent_rate < 80.0:
               print(f'❌ intent={intent} 通过率 {intent_rate:.1f}% < 80%, D6 gate 阻断 merge')
               sys.exit(1)
       
       print(f'✓ 通过率 {pass_rate:.1f}% >= 90% 且 per-intent 都 >= 80%, D6 gate 通过')
       PYEOF
   ```

2. **关键约束**:
   - 不引入新 step (复用原 "Fail if pass_rate < 80%" step)
   - 不修改 report path (`results/baseline_d6_1000_in_process/`)
   - 不改 runner.py (Phase 2 Agent 1 输出的 json 字段名兼容)

3. **完成定义**:
   - 修改 < 30 行
   - workflow_dispatch 跑 1 次验证 (手工验证, 主指挥 PC)

4. **验收标准**:
   - workflow_dispatch 跑过 (无论 pass rate 多高, step 必须**不阻断**正常执行流)
   - 故意构造 fail (新 PR pass_rate 80-89% or per-intent < 80%), 验证 step 真阻断
   - 修改 < 30 行

5. **失败回滚**:
   - **gate 误判**: 立即 revert. 接受 W67 80% gate 维持.

6. **派工 prompt 模板**:
   ```
   [Agent 2 — W69 第 1 批 pass rate gate 强化]
   任务: 修改 qa-bench-ci.yml "Fail if pass_rate < 80%" step, 强化为 90% + per-intent 80% 双层 gate.
   约束: 不修改其他 step. 不新增 step. workflow 总行数 < 420.
   验证: 故意构造 fail 验证 gate 真阻断. workflow_dispatch 跑 1 次正常路径.
   ```

### Agent 3: matrix 拆分 (3-4 人时)

**目标**: 在 `.github/workflows/qa-bench-ci.yml` 把 `Run qa-bench D5` step 改成 4 runner matrix 并行 (shard 1000 题 250 题/runner).

**任务清单**:

1. **修改** `.github/workflows/qa-bench-ci.yml`:
   - **关键改动**: 整个 workflow `jobs.qa-bench-d5.runs-on` 改用 `strategy.matrix.shard: [0, 1, 2, 3]`
   - **关键改动**: step 11 (Run qa-bench) 加 `--shard ${{ matrix.shard }} --total-shards 4` 参数, 让 runner.py 自动分配题目

2. **修改** `tests/qa-bench/runner.py` 加 `--shard` 支持:
   - 算法: `shard_idx = question_idx % total_shards == shard_id` 选中题目
   - **限制**: 这是**新增 CLI 参数**, 但不修改现有 detection logic. 行数增加 < 50 行.

3. **完成定义**:
   - workflow 用 `strategy.matrix.shard` 模式
   - 4 runner shard 后总 wall clock < 15 min (vs 单 runner 30-60 min)
   - 实测 GitHub Actions minutes = 4 × 6 min = 24 min (vs 单 runner 30-60 min)

4. **验收标准**:
   - workflow_dispatch 跑 1 次 (4 runner 并行)
   - 4 个 runner 各自 shard 结果合并后 total=1000 题
   - wall clock < 15 min
   - GitHub minutes 单 runner < 6 min × 4 = 24 min 总消耗
   - matrix 单 run 总时长 < 8 min (理想)

5. **失败回滚**:
   - **shard 不均匀**: reject runner.py 修改. 接受单 runner, docs/CI 占位.
   - **GitHub minutes 超 budget**: matrix 比单 runner 消耗 4× minutes. 若单月 > 1500 min, 触发**回滚到单 runner** (不是 docs/CI 占位).

6. **派工 prompt 模板**:
   ```
   [Agent 3 — W69 第 1 批 matrix 拆分]
   任务: 把 qa-bench-ci.yml runner 改成 4 runner matrix 并行 (shard 1000 题 → 4×250 题).
   约束: workflow 总行数 < 450. runner.py 仅新增 --shard CLI 参数 (< 50 行).
   验证: workflow_dispatch 跑 1 次, 4 runner 合并 = 1000 题, wall clock < 15 min.
   ```

### Agent 4: W69 grand closure memory (2-3 人时)

**目标**: 写 `memory/w69-grand-closure-qa-bench-d6-2026-07-24.md` 锚点范式第 40 守恒.

**任务清单**:

1. **新增** `memory/w69-grand-closure-qa-bench-d6-2026-07-24.md` (~200 行):
   - **TL;DR**: W68 Phase 1 + W69 Phase 2 全部 9 agents 完成 / 部分失败, 最终 Phase 2 CI 时长 5-8 min, pass rate ≥ 90%, 锚点范式 35 → **40**.
   - **§1 W68 Phase 1 总结**: 5 agents 任务最终状态 + 实测数字
   - **§2 W69 Phase 2 总结**: 4 agents + 最终 CI 数字
   - **§3 锚点范式 9 commit 守恒链**: W68 28 → W68 30 → W68 35 → W69 40
   - **§4 5-10 条新铁律**: in-process runner 实战教训 / cache 命中经验 / matrix GitHub minutes 监控 / pass rate 双层 gate 设计 / etc.
   - **§5 未来 PR 触发监控**: GitHub minutes > 1500 / qa-bench D7 (5000 题) / pass rate 滑落

2. **完成定义**:
   - 文件存在 + 200 行左右
   - MEMORY.md 索引追加 1 行

3. **派工 prompt 模板**:
   ```
   [Agent 4 — W69 第 1 批 grand closure memory]
   任务: 写 memory/w69-grand-closure-qa-bench-d6-2026-07-24.md (~200 行) 锚点范式第 40 守恒 + MEMORY.md 索引追加.
   约束: 全基于 Phase 2 实测数字. 5-10 条新铁律 (Phase 2 实战新增).
   ```

### Phase 2 总验收 (主指挥 W69 第 1 批后)

| 维度 | 验收阈值 | 失败处理 |
|------|----------|----------|
| **4 agents 全部完成** | 4/4 PR merged to main | 任意 1 个失败 → 整体回滚 (接受 docs/CI 占位) |
| **CI 总时长** | cold cache ≤ 8 min (matrix 拆分) / warm cache ≤ 5 min | 超 10 min → 回滚 matrix, 接受单 runner |
| **Pass rate** | 整体 ≥ 90% + per-intent ≥ 80% | 不达标 → gate 改回 80%, docs/CI 占位 |
| **71 PASS + 7 SKIP baseline 守恒** | 0 regression | 任意 1 个 → 整体回滚 |
| **production code 0 改动** | `git diff main -- app/ web/ alembic/` = 空 (Phase 1 + 2 全程累计) | 任意 1 行 → 立即拒绝, 整体回滚 |
| **锚点范式 W68 30 → 35 → 40** | 9 commit 单调上升 | 跌回 → 重新审视调研 |

---

## 5️⃣ Phase 1 + Phase 2 任务时间线 (主指挥视角)

### 5.1 总工时表

| 时间 | 主指挥动作 | Agent 动作 |
|------|------------|------------|
| **W68 第 3 批 (T0)** | 拍板本文路线图 (Phase 1 5 agents + Phase 2 4 agents) | - |
| **W68 第 4 批 (T0 + 24-48h)** | 派工 5 agents, 监控 PR | Agent 1-5 并行工作 |
| **W68 第 4 批末 (T0 + 48h)** | review 5 PRs, merge to main | Agent 1-5 merge PR |
| **W68 第 4 批末 + 2h** | 写 `memory/w68-phase-1-validation-XX.md` 锚点范式第 35 守恒 (本文 §7) | - |
| **W68 周末 / W69 第 1 批前 (T0 + 5-7d)** | 观察 Phase 1 main HEAD 实测数据 | - |
| **W69 第 1 批 (T0 + 5-7d)** | 派工 4 agents, 监控 PR | Agent 1-4 并行工作 |
| **W69 第 1 批末 (T0 + 5-7d + 48h)** | review 4 PRs, merge to main | Agent 1-4 merge PR |
| **W69 第 1 批末 + 2h** | 写 grand closure (Agent 4) 锚点范式第 40 守恒 | Agent 4 写 grand closure |

### 5.2 验收里程碑

- **里程碑 1 (W68 第 4 批末)**: Phase 1 5 PRs merged + main HEAD 跑过 1 次 CI (workflow_dispatch)
- **里程碑 2 (W69 第 1 批初)**: main HEAD 真实 push trigger CI 跑过 1 次 (pass rate ≥ 90%, 时长 < 8 min)
- **里程碑 3 (W69 第 1 批末)**: Phase 2 4 PRs merged + main HEAD 实测数据 + grand closure memory (锚点范式第 40 守恒)
- **里程碑 4 (W70 起)**: 真实 PR (未 phase 1/2 关联) trigger CI 跑过, 视为路线 B-3 真治本**最终成功**

### 5.3 主指挥 review checklist (W68 第 4 批 PR review)

PR review 时主指挥依次确认:

1. **Production code 0 改动**: `git diff main..HEAD -- app/ web/ alembic/versions/` 输出为空
2. **workflow 改动 < 30 行**: `git diff main..HEAD -- .github/workflows/qa-bench-ci.yml` 行数 < 30
3. **新增 tests 文件不修改 runner.py**: `git diff main..HEAD -- tests/qa-bench/runner.py` 输出为空
4. **docs 改动可读性**: 中文段落无 typo, 链接正确
5. **memory 改动锚点范式守恒**: `memory/2026-07-*` + `memory/w68-*` 文件命名规范

任意 1 项不达标 → reject PR, 不 merge to main.

---

## 6️⃣ 风险与回滚路径

### 6.1 Phase 1 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| **in-process runner import 慢 (5-25 min)** | 中 (40%) | Agent 1 / 3 验证失败, 路径 3 收益不足 | Agent 1 上报 → 接受 W67 docs/CI 占位, 保留文件骨架, 不强制 workflow 接入 |
| **in-process runner 行为与 HTTP runner 不一致** | 低 (10%) | pass rate 误差 > 5%, 检错器差异 | Agent 3 对比 dry-run, 上报主指挥 |
| **Chat engine 跨 event loop** | 中 (30%) | asyncio.run + Celery trigger error | Agent 1 用 `asyncio.run` 不跨 loop |
| **GitHub Actions cache 路径权限** | 低 (5%) | cache restore 失败 | Agent 2 改用 `${{ runner.workspace }}/.pycache` |
| **GitHub minutes 单月 > 1500 min** | 低 (10%) | 月度预算超 | Phase 1 cache 改善节省 60s/run × 30 run/月 = 30 min/月, 单月仍在 700 min 以内 |
| **Phase 1 4 agents 并行冲突** | 中 (20%) | 同文件 merge conflict | Agent 1-5 各自独立文件, merge conflict 概率低 |

### 6.2 Phase 1 失败回滚路径

**Phase 1 完全失败** (5 agents 任意 1 个 fail-loud, 主指挥 W68 第 4 批末):

1. **保留**: 
   - `docs/qa-bench-d6-implementation-roadmap.md` (本文) — 路线图保留作为文档资产
   - `tests/qa-bench/in_process_runner.py` (Agent 1) — 文件骨架保留, 可作未来 PR
   - `memory/w68-route-b-qa-bench-d6-future-roots-2026-07-24.md` — 调研 memory 保留

2. **revert**:
   - `.github/workflows/qa-bench-ci.yml` cache step 改动 (Agent 2)
   - workflow 改回 W67 baseline

3. **接受**:
   - **W67 docs/CI 占位维持** (W67 第 47 步决策生效)
   - 主指挥 W69 第 1 批**不启动 Phase 2**
   - 锚点范式 W68 30 → 30 维持 (调研已沉淀, 不升不降)

**Phase 1 部分失败** (Agent 1 完成 + Agent 2 完成 + Agent 3 失败, 其余完成):
- **判断**: Agent 1 + 2 成功 (骨架 + cache 接入), Agent 3 失败 (实测不达标)
- **决策**: 主指挥决定是 "Phase 1 部分成功" 还是 "整体回滚"
- **倾向**: 部分成功 (Agent 3 失败但骨架已在, 未来 PR 可补) — 但 workflow **不接入 in-process** (因实测不达标)

### 6.3 Phase 2 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| **1000 题真实 pass rate < 90%** | 中 (35%) | Phase 2 Agent 1 数据不足支撑 gate 强化 | Agent 1 上报 → gate 改回 80% 或暂不启用 |
| **matrix shard 不均匀** | 低 (10%) | 1 个 runner 题目比其他多 2×, wall clock 不降反升 | Agent 3 改用 hash(shard_id) % len(questions) |
| **Per-intent gate 误判** | 中 (25%) | 某 intent 偶发 < 80% 阻断 merge | Agent 2 加 retry-once 逻辑, 或 5-run rolling avg |
| **GitHub minutes 月度超 1500** | 低 (15%) | matrix 4× 消耗 | 触发未来 PR: 单 runner + Phase 1 cache 优化维持 |
| **production code 误改** | 极低 (5%) | 主指挥 review 失误 | review checklist §5.3 三重确认 |

### 6.4 Phase 2 失败回滚路径

**Phase 2 完全失败** (4 agents 任意 1 个 fail-loud, 主指挥 W69 第 1 批末):

1. **保留**:
   - `docs/qa-bench-d6-implementation-roadmap.md` (本文)
   - `tests/qa-bench/in_process_runner.py` + Phase 1 5 commits
   - `memory/w68-phase-1-validation-XX.md` + `memory/w68-route-b-XX.md`

2. **revert**:
   - `.github/workflows/qa-bench-ci.yml` **整体回滚到 W67 baseline** (Phase 1 cache + Phase 2 gate + matrix 全部 revert)
   - 4 PRs 全部 close (不 merge)

3. **接受**:
   - **W67 docs/CI 占位最终维持** (路径 B 调研 + 路线图已沉淀, 调研价值最大化)
   - 主指挥 W70+ **不再排 qa-bench 真治本 PR** (除非 GitHub minutes 月度 > 2000 触发监控)
   - 锚点范式 W68 30 → **W69 35** (Phase 1 沉淀升一次, Phase 2 失败不升不降)

**Phase 2 部分失败** (Agent 1 + 4 完成, Agent 2 / 3 失败):
- **判断**: 1000 题跑完, gate 强化失败 / matrix 拆分失败
- **决策**: 主指挥决定保留 gate 单层强化 (Phase 2 80% → 85%), 不保留 matrix
- **倾向**: 倾向保留部分成果, 锚点范式 W68 35 → **W69 38** (升 3 commit 而非 5)

### 6.5 回滚路径的"反向锁"

**重要**: Phase 1 / Phase 2 任何 commit 都可以 `git revert <commit-hash>` 一行撤销 + 重新部署. < 5 分钟恢复. 这与 CLAUDE.md "feature flag 必须保留老路径代码" 铁律呼应 — 路线 B-3 全部以 commit 而非 in-file feature flag 形式存在, 任何 commit 可独立 revert.

**反向锁操作示例**:
```bash
# Phase 1 Agent 2 cache 接入失败
git revert <agent-2-cache-commit-hash> --no-edit
docker compose restart app celery-worker  # 不需要, 纯 workflow 改动
git push origin main
# 触发 webhook, 30s 后 workflow 改回 W67 baseline

# Phase 2 Agent 3 matrix 拆分失败
git revert <agent-3-matrix-commit-hash> --no-edit
git push origin main
# 触发 webhook, 30s 后 workflow 改回 Phase 1 baseline (cache 已用但 matrix 回单 runner)
```

---

## 7️⃣ 锚点范式第 35 守恒 (W68 Phase 1 实施路线图沉淀)

**W67 → W68 路径**:
- W67 (W66 27 → 28): qa-bench D5 gate 真治本失败接受 docs/CI 占位 + 8 批 42+ agent commits
- W68 第 1 批 (W67 28 → 29): Drive v2 PR8 收官 + Mobile UX 14+1 agents merged
- W68 第 2 批 (W68 29 → 30): 路线 B 调研 5 路径 + 推荐路径 3+1 组合
- **W68 第 3 批 (W68 30 → 35)**: 本文路线图 — Phase 1 + Phase 2 共 9 agent 派工决策, 锚点范式正向闭环

**累计节奏**:
- W7 12 → W66 27 → W67 28 → W68 30 (调研) → **W68 35** (本文路线图) → **W69 40** (Phase 2 grand closure)
- 21 天锚点范式实战, 0 回退, 单调上升

**未来 PR 触发监控点** (跨 W68 + W69):
1. **Phase 1 in-process runner 验证失败** → 接受 docs/CI 占位 + 调研沉淀最大化
2. **Phase 2 matrix GitHub minutes 月度 > 1500** → 触发回滚 matrix + 单 runner 维持
3. **Phase 2 1000 题 pass rate < 80%** → 触发 gate 改回 80% + docs/CI 占位维持
4. **Phase 2 grand closure 完成** → 路线 B-3 真治本 PR 收官, 锚点范式 W69 40 单调达成

**0 production code 改动铁律守恒**: Phase 1 + Phase 2 派工全程累计 `git diff main..HEAD -- app/ web/ alembic/versions/` = 空, 与 W67 第 47 步决策一致.

---

## 8️⃣ 沉淀位置与未来引用

**本文沉淀位置**:
- **核心路线图**: `docs/qa-bench-d6-implementation-roadmap.md` (本文, ~600-800 行)
- **不写入**: CLAUDE.md (避免 50KB 核心膨胀, 未来 W70+ 引用此文件)
- **不写入**: MEMORY.md 索引 (本文太详细, 仅在 memory/w68-phase-1-validation-XX.md 加 1 行概要)

**关联文档**:
- [`docs/qa-bench-d5-future-roots.md`](qa-bench-d5-future-roots.md) (W68 Route-B 调研 5 路径, 703 行)
- [`memory/w68-route-b-qa-bench-d6-future-roots-2026-07-24.md`](../memory/w68-route-b-qa-bench-d6-future-roots-2026-07-24.md) (锚点范式第 30 守恒)
- [`memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md`](../memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md) (锚点范式第 28 守恒, W67 跳出循环)
- [`docs/qa-bench-500-report.md`](qa-bench-500-report.md) (D5 历史报告)

**未来引用场景**:
1. **W68 第 4 批派工**: 主指挥派工时直接用 §3 (Phase 1 agent 任务清单) + §5 (时间线) + §6 (风险与回滚)
2. **W69 第 1 批派工**: 主指挥派工时直接用 §4 (Phase 2 agent 任务清单) + §5 (验收 milestone) + §6 (回滚路径)
3. **W70+ future PR 触发**: 锚点范式监控 GitHub minutes / pass rate / 时长, 触发未来 PR 排期
4. **W71+ 知识沉淀**: Phase 1 + Phase 2 完成 + 锚点范式 W71 50+ 后, 本文可考虑归档到 `docs/_archive_2026-07-XX/`, 不再主索引

---

## 附录 A: Phase 1 + Phase 2 9 agents 总览

| 批 | Agent | 任务 | 工时 | 完成定义 | 失败回滚 |
|----|-------|------|------|----------|----------|
| Phase 1 (W68 第 4 批) | Agent 1 | in_process_runner.py (新增) | 3-5h | smoke 30 题 < 5 min | 接受 docs/CI 占位 |
| Phase 1 | Agent 2 | workflow cache step 接入 | 2-3h | warm cache -30% | revert cache step |
| Phase 1 | Agent 3 | 端到端 100 题 dry-run 验证 | 3-4h | 耗时 < 10 min + pass ≥ 85% | 接受 docs/CI 占位 |
| Phase 1 | Agent 4 | docs 同步 (qa-bench-d5-future-roots §9 + in_process_runner.md) | 1-2h | 文档可读 + 链接正确 | 文档保留, 5% typo 不阻断 |
| Phase 1 | Agent 5 | memory 沉淀 (Phase 1 validation) | 1-2h | 150 行 + MEMORY.md 索引 | memory 缺失不阻断, 但**必做** |
| Phase 2 (W69 第 1 批) | Agent 1 | 1000 题 dry-run + ANALYSIS.md | 4-6h | pass ≥ 88%, ANALYZE ≥ 5 类 | 数据不达标 → gate 不强化 |
| Phase 2 | Agent 2 | pass rate gate 强化 (90% + per-intent 80%) | 3-4h | workflow 改动 < 30 行 | revert gate, 接受 80% |
| Phase 2 | Agent 3 | matrix 拆分 (4 runner × 250 题) | 3-4h | wall clock < 15 min | revert matrix, 单 runner 维持 |
| Phase 2 | Agent 4 | W69 grand closure memory | 2-3h | 200 行 + 第 40 守恒 | memory 缺失不阻断, 但**必做** |

**总工时**: Phase 1 16-24h + Phase 2 12-20h = **28-44h** (跨 2 周 9 agents, 平均 3-5h/agent)

## 附录 B: 主指挥派工 PR 模板

主指挥 W68 第 4 批派工 5 agents 时, 直接 copy paste 派工 prompt (§3 + §6 Agent 1-5 prompt 模板) 到 5 个 worktree. 类似 W69 第 1 批派工 4 agents.

## 附录 C: 关键数字速查表

| 数字 | 值 | 来源 |
|------|----|------|
| W67 锚点范式 | 28 | CLAUDE.md |
| W68 调研后锚点范式 | 30 | w68-route-b memory |
| W68 第 4 批后 (Phase 1 全部成功) | **35** | 本文 §7 |
| W69 第 1 批后 (Phase 2 全部成功) | **40** | grand closure memory |
| W67 baseline CI 时长 | 25+ min | W67 第 47 步实测 |
| Phase 1 预期 CI 时长 | 8-12 min | 本文 §2.3 |
| Phase 2 预期 CI 时长 | 5-8 min (matrix 拆分) | 本文 §2.3 |
| W67 baseline pass rate | 88% | smoke 30 题 |
| Phase 1 预期 pass rate | ≥ 85% (in-process 验证) | §3 Agent 3 |
| Phase 2 预期 pass rate | ≥ 90% (gate 强化) | §4 Agent 2 |
| 71 PASS + 7 SKIP baseline | 守恒 (跨 W67-W69) | CLAUDE.md |
| workflow 改动 (Phase 1 + 2 累计) | < 80 行 | §3 + §4 估算 |
| production code 改动 | 0 | §1.3 不变量 |
| 新增 tests 文件 | 1 (in_process_runner.py) + 1 docs (in_process_runner.md) | §3 |
| GitHub Actions minutes (Phase 2 matrix) | 24 min/run (4×6 min) | §4 Agent 3 |

---

## 10️⃣ Phase 3 实施段 (W68 第 8 批 B-4 — 路径 4 matrix 4 runner 并行)

> **作者**: Claude Fable 5 (W68 Route-8-B-4 Agent)
> **日期**: 2026-07-24
> **基线 HEAD**: `05c60e68d` (W68 第 5 批 hot-fix)
> **新增交付**:
> - `tests/qa-bench/phase3_matrix_runner.py` (~430 行 CLI)
> - `tests/qa-bench/phase3_matrix_report_2026-07-24.md` (~150 行报告)
> **关联 memory**: `memory/w68-route-8-b4-qa-bench-phase3-matrix-2026-07-24.md` (锚点范式第 96 守恒)

### 10.1 触发与决策

W68 第 5 批 B-3 调研锁定 5 路径, **主指挥拍板"路径 4 (matrix 拆分 4 runner 并行) + 路径 1 (cache 优化) 组合"** 作为 Phase 2 / 3 实施方向. Phase 2 已由 W68 第 7 批 B-2 实施 (`phase2_dry_runner.py` 单 runner 骨架, 360 行, 并发 5, 3 rounds majority). Phase 3 实施目标: **路径 4 落工具** — 在 Phase 2 基础上加 **跨 worker 并发调度** + **多 worker 汇总聚合** + **严格 matrix gate**.

### 10.2 实施内容

**核心改动 (4 项)**:

1. **新建** `tests/qa-bench/phase3_matrix_runner.py` (~430 行)
   - `--workers 4` (默认) 切分 1000 题 → 4 shard (250 / 250 / 250 / 250)
   - `--matrix 4` (默认) 跨 worker asyncio.Semaphore 并发 (同跑)
   - 复用 `phase2_dry_runner._round_with_concurrency` (verdict consensus majority)
   - `_aggregate_matrix` 汇总 4 worker → combined counts + per-intent pass rate + matrix gate
   - `_render_phase3_report` 写 Markdown 报告 (与 Phase 2 同结构)

2. **复用** `phase2_dry_runner.py` (从 `e6220d016` commit 拷贝, 因 Phase 2 还未 merge 到 main)
   - 5 函数复用: `_load_full_corpus` / `_bucket_intent` / `_majority_verdict` / `_verdict_from_answer` / `_round_with_concurrency`
   - 2 常量: `PHASE2_INTENT_BUCKETS` + `PHASE2_CHAT_INTENT_BUCKETS`

3. **新建** `tests/qa-bench/phase3_matrix_report_2026-07-24.md` (~150 行, 同 Phase 2 报告结构)
   - 摘要 / 工具设计 / Dry-run 验证 / 真实 1000 题 dry-run (主指挥 SSH 跑后填表) / Risk / 验收 / 沉淀位置

4. **import 路径**: `phase3_matrix_runner` 从 `phase2_dry_runner` import 5 函数 + 2 常量 (避免逻辑双胞胎)

### 10.3 严格 matrix gate 设计

**Phase 2 gate**: 单 runner 整体 pass rate ≥ 90% → PASS

**Phase 3 matrix gate**: 严格模式 — **ALL 4 workers ≥ 90% 才 PASS**

```python
matrix_gate = PASS if all(
    worker["pass_rate"] * 100 >= gate_threshold
    for worker in worker_summaries
)
```

**理由**: 1 个 worker pass rate 显著低于其他 3 个 (例如 80% vs 95%) 时, 主指挥需要立即知道具体哪个 shard 出问题, 而非 "整体 92.5% pass" 一句带过. 严格 gate 强制报告按 worker 细分失败原因.

### 10.4 实施验收 (本地 PC)

- **Dry-run 验证**: `python phase3_matrix_runner.py --dry-run` 成功
- **Sharding 准确**: 1000 题 / 4 shard = 250/250/250/250 (round-robin `index % workers`)
- **Per-intent 校验**: action=136 + casual=118 + data=316 + deep=129 + explain_concept=161 + none=15 + search_info=125 = **1000** ✓
- **Phase 2 复用**: 0 双胞胎逻辑, 5 函数 + 2 常量 import 复用
- **Matrix gate 严格**: FAIL when 0% pass rate (expected in dry-fallback)

### 10.5 下一步主指挥 SSH 跑

```bash
ssh microbubble-agent-runner
cd tests/qa-bench
MIMO_API_KEY=$MIMO_CLOUD_KEY \
DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/qa_test \
  python phase3_matrix_runner.py --report-out phase3_real_run_$(date +%Y%m%d_%H%M).md
```

**期望**: wall clock 5-15 min (vs 单 runner 30-60 min), 50-75% wall clock 节省.

### 10.6 锚点范式 W68 第 8 批 95 → **96** 守恒

| 维度 | 数值 |
|------|------|
| Phase 3 工具 (matrix runner) | 1 (~430 行) |
| Phase 3 报告 | 1 (~150 行, dry-fallback 占位) |
| Phase 3 roadmap 改动 | +~50 行 (本文 §10) |
| Phase 3 memory 沉淀 | 1 (~150 行) |
| **总新增文件** | **3** (matrix runner + 报告 + memory) |
| **总改动文件** | **1** (roadmap, +~50 行) |
| **production code 改动** | **0** (仅 tests/qa-bench/ + docs/ + memory/) |
| **锚点范式** | W68 第 8 批 95 → **96** 单调上升 |

### 10.7 Phase 3 失败回滚路径

```bash
git revert <phase3-commit-hash> --no-edit
git push origin main
# webhook 30s 后, 回到 Phase 2 single runner
```

**回滚后接受**: Phase 2 single runner (8-12 min wall clock) + docs/CI 占位 (W67 baseline 维持).

---

**Anchor**: 锚点范式 W68 第 8 批 95 → **96** 单调上升, W68 第 8 批 B-4 Phase 3 实施 0 production code 改动铁律完全守恒. 4 文件交付 (1 工具 + 1 报告 + 1 改 roadmap + 1 memory), 工具 dry-fallback 验证逻辑正确, 待主指挥 SSH 跑真实 1000 题 (本地 PC 无 MIMO_API_KEY + test DB).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

---

**Anchor**: 锚点范式 W68 30 → **35** 单调上升, W68 第 4 批路线 B-3 实施路线图 0 production code 改动铁律完全守恒. 9 agents 跨 2 周 2 批派工决策已锁定, Phase 1 主指挥 W68 第 4 批派工依据本文 §3, Phase 2 主指挥 W69 第 1 批派工依据本文 §4.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
