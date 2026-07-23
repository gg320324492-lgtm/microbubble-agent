---
name: w68-route-b-qa-bench-d6-future-roots-2026-07-24
description: "W68 第 2 批 路线 B (qa-bench D5 真治本未来根因路径调研) 调研汇总. 锚点范式第 30 次守恒. 5 路径全部不动 production code, 推荐路径 3 (in-process runner)."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-Route-B
  modified: 2026-07-24T00:00:00.000Z
---

# 2026-07-24 W68 第 2 批 路线 B — qa-bench D5 真治本未来根因路径调研

## TL;DR

W67 第 47 步主指挥跳出循环接受 docs/CI 占位后, W68 第 2 批路线 B 启动**调研不动 production code 的 CI 优化路径**. 完整审计 `.github/workflows/qa-bench-ci.yml` 363 行 + `app/main.py` lifespan + `_load_application_routers` 后台 task + 24 个 router import chain, 锁定 5 根因候选 + 5 未来路径. **推荐路径 3 (in-process runner)** — 真正绕开 uvicorn 启动 + router 注册时序问题, CI 时间从 25+ min → 5-10 min. 5 路径全部 0 production code 改动铁律完全守恒.

## Why

W67 第 47 步 12 次跑每次差 0.5-1% budget 误差, 主指挥跳出循环接受 docs/CI 占位. 锚点范式要求"跳出循环 ≠ 停止探索", 路线 B 调研 5 条未来根因路径, 为 W68 第 3 批真治本派工提供决策依据. 这是锚点范式第 30 次守恒 — 调研文档本身是"沉淀", 不动 production code 但增加未来 PR 决策资产.

## How to apply

主指挥拍板后由 W68 Route-B Agent 实施:
1. 拍板选项 A/B/C/D (见 docs §4 决策矩阵)
2. 选项 B (路径 3+1 组合) 推荐, 跨 2 周 2 批派工
3. 选项 A (路径 3 单独) 次推, 1 周 1 批派工
4. 选项 D (暂不排期) 维持 W67 占位

---

## 1️⃣ 当前 D5 CI 现状快照 (W68 Route-B 调研基线)

- **Workflow**: `.github/workflows/qa-bench-ci.yml` 363 行
- **Timeout**: 120 min, 实测 25+ min (冷) / 5 min (warm + GHCR hit)
- **题库**: 1000 题 (780 base + D4 300 extra), rounds 3 majority consensus
- **LLM**: mimo cloud (`LLM_BACKEND=openai_compat` + `mimo-v2.5`)
- **Router 探针**: `/health` 200 + `/auth/login` 401/422 双探针 + 60s wait
- **Image**: GHCR pre-built (`ghcr.io/<OWNER>/microbubble-agent:app-test-latest`)
- **DB**: `pgvector/pgvector:pg16` (W67 第 49 步替换)
- **现状**: 12 次跑每次差 0.5-1% budget, 主指挥跳出循环接受占位

## 2️⃣ 启动阶段耗时分解

| 阶段 | 实测耗时 | 占总时长 |
|------|----------|----------|
| Checkout + Setup Python + Cache pip | 30-45 s | ~3% |
| Pull pre-built image (GHCR) | 30-90 s / 5-15 s | ~5% |
| Start pg-test | 5-15 s | ~1% |
| Start app-test container | 30 s | ~2% |
| **uvicorn app.main:app 启动** | **5-7 min (实测 1510 s / 25 min budget)** | **~25%** |
| /health 200 (lifespan yield) | 1-2 s | <1% |
| **router 真正 ready (login 401/422)** | **60 s wait + 2-30 s probe** | **~5%** |
| Init test DB schema + seed | 10-15 s | ~1% |
| Run 1000 题 × 3 rounds × mimo cloud | 40-60 min | ~50% |
| 合计 | **~50-75 min** | 100% |

## 3️⃣ router 时序问题 5 根因候选

### 候选 A: `_load_application_routers` 后台 task 与 lifespan yield 时序 (~40%)

`app/main.py:96-105` 后台 task + `app/main.py:118-131` `_start_router_loader` + `app/main.py:200` yield → /health 200 立即响应, 但 24 个 router 仍在后台 import.

### 候选 B: 24 个 router 文件 import chain 累计 (~30%)

W67 第 48 步 lazy 改造后冷启动 5 min. 单 router ~3.75s (chat 1.2s + meeting_recording 0.8s + voice 0.6s + voiceprint 2.5s + ...).

### 候选 C: mimo SDK 初始化 + connection pool (~15%)

mimo SDK 启动建立 HTTPS pool, TLS 握手 ~3-5s 启动阻塞.

### 候选 D: pgvector 扩展安装 (~5%, W67 第 41 步已解)

SKIP_DB_SETUP=1 短路 lifespan 内 create_extension.

### 候选 E: Whisper model lazy load (~10%, W67 第 48 步部分解)

faster-whisper large-v3 ~1.5 GB, 首次 load ~10-30s. 仅在 ASR 类题库触发, 当前 1000 题不直接触发.

## 4️⃣ 5 路径详细分析 (全部 0 production code 改动)

### 路径 1: GHCR cache hit 深度优化 (治标, ⭐⭐, 0.5 人天)

pycache 跨 run 共享 volume, 40-60% 改善. 风险低, 0 production code 改动.

### 路径 2: 改用 cimg/python:3.11 直接 pytest, 跳过 lifespan (治本但侵入, ⭐⭐⭐, 1-2 人天)

FastAPI TestClient 同步等 lifespan startup, 60-75% 改善. 风险中-高, 仍要 import 24 个 router 5 min.

### 路径 3 (推荐): 改 qa-bench runner 直接打 test DB 不通过 HTTP API (真治本, ⭐⭐⭐⭐, 2-3 人天)

新增 `tests/qa-bench/runner_in_process.py`, in-process 直调 chat engine + AsyncSession. **完全跳过 uvicorn + lifespan + router 注册**, 60-80% 改善. 工程价值高 (可复用作 benchmark 工具).

### 路径 4: 拆分 1000 题到 4 runner matrix 并行 (横向扩展, ⭐⭐, 0.5-1 人天)

4× GitHub minutes, uvicorn 启动 5 min × 4 = 20 min wall clock, 节省有限.

### 路径 5: act 本地跑 GitHub Actions 模拟 (开发工具, ⭐, 0.5 人天)

不解决 CI 时长, 仅开发工具. 任何路径 1-4 实施时辅助.

## 5️⃣ 主指挥拍板决策矩阵

| 选项 | 时间节省 | 派工 | 风险 | 工程价值 | 推荐度 |
|------|----------|------|------|----------|--------|
| A: 路径 3 单独 | 60-80% | 2-3 人天 | 中 | 高 | ⭐⭐⭐⭐ |
| **B: 路径 3+1 组合** | **70-90%** | **3-4 人天** | **中** | **很高** | **⭐⭐⭐⭐⭐** |
| C: 路径 1 单独 | 40-60% | 0.5 人天 | 低 | 中 | ⭐⭐⭐ |
| D: 暂不排期 | 0% | 0 | 0 | 0 | ⭐⭐ (维持 W67 占位) |

**拍板建议**: 选项 B (路径 3+1 组合), 跨 2 周 2 批派工. 资源受限时退回选项 A.

## 6️⃣ 5 条新铁律沉淀 (W68 Route-B 调研新增)

### 铁律 1: uvicorn 启动 router 时序是 GitHub runner 独有瓶颈

生产环境 server 一次启动后长期运行, 25 min 启动成本被摊销. CI 环境每次跑都重新启动, 25 min 启动成本完全无法摊销. 任何 CI 优化策略必须区分"uvicorn 启动耗时" vs "uvicorn 运行时行为". 路径 3 是唯一同时消除两个维度的方案.

### 铁律 2: GHCR pre-built image 已实现 layer 级 cache, 但 Python __pycache__ 是 layer 外资源

`docker build` 缓存 layer 不缓存 Python 模块初始化. 跨 run 持久化 `__pycache__` 需要 volume 共享, 不是 image layer. 路径 1 是 layer 外补充, 不替代 layer 内 cache.

### 铁律 3: FastAPI TestClient + in-process runner 与 HTTP runner 行为差异需量化对比

TestClient 触发 lifespan 同步阻塞, 但仍要 import 24 个 router. In-process runner 跳过 lifespan 但仍需 import app.main (拿到 chat engine). 二者都有 ~5 min 冷启动, 路径 3 真正节省的是 uvicorn + 中间件 + CORS + rate_limit.

### 铁律 4 (复用 W67 第 47 步): lifespan yield 早于 router 注册完成, /health 200 ≠ router ready

双探针 (/health + /auth/login 401/422) 仍是路径 1-2 唯一可行方案. 路径 3 完全绕开此问题. 主指挥拍板"接受 docs/CI 占位"是当前默认, 任何路径实施前需明确 override.

### 铁律 5 (复用 CLAUDE.md): 0 production code 改动铁律维持

5 路径全部不动 production code (app/ + web/ + alembic/versions/ 全部不动). 仅在 `.github/workflows/` + `docs/` + `memory/` + `tests/qa-bench/` 新增文件. 派工时严格审查 diff, 任何 `app/` 下改动立即拒绝.

## 7️⃣ 锚点范式第 30 次守恒

**W67 → W68 路径**:
- W67 (W66 27 → 28): qa-bench D5 gate 真治本失败接受 docs/CI 占位 + 8 批 42+ agent commits
- W68 第 1 批 (W67 28 → 29): Drive v2 PR8 收官 + Mobile UX 14+1 agents merged
- **W68 第 2 批路线 B (W68 29 → 30)**: 本次调研 — 5 路径技术决策文档, 0 production code, 锚点范式正向推进

**未来 PR 触发监控点**:
1. GitHub Actions minutes 用量 > 1500 min/月 → 触发路径 3 加速 (避免路径 4 横向消耗)
2. qa-bench D6 (2000 题) 启动后单 runner > 80 min → 触发路径 3 in-process (避免 uvicorn 启动瓶颈放大)
3. uvicorn 启动仍 > 5 min 在 warm cache 时 → 触发路径 1 pycache 复用 (layer 外补充)

## 8️⃣ 沉淀位置

- **核心调研文档**: `docs/qa-bench-d5-future-roots.md` (400 行, 5 路径详细分析 + 推荐 + 拍板指南 + 铁律)
- **本 memory**: 调研汇总 + 锚点范式第 30 守恒 + 5 新铁律
- **不写入**: CLAUDE.md (避免 50KB 核心膨胀) / MEMORY.md 索引 (5 路径分析太详细, 仅在索引加 1 行概要)
- **关联文档**: `docs/2026-07-22-future-pr-evaluation.md` (4 留未来 PR 评估范式) + `docs/2026-07-22-future-pr-roadmap-update.md` (季度排期)

---

**Anchor**: 锚点范式 W68 29 → **30** 单调上升, W68 第 2 批路线 B 调研汇总 0 production code 改动铁律完全守恒.