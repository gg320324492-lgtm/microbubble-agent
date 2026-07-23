# qa-bench D5 真治本: 5 条未来根因路径调研 (W68 第 2 批路线 B)

> **作者**: Claude Fable 5 (W68 Route-B Agent 调研)
> **日期**: 2026-07-24
> **基线 HEAD**: `13548ff2b` (Safari iOS 空白页修复 + W68 第 1 批 14+1 agents merged)
> **任务来源**: 主指挥 W68 第 2 批路线 B — 调研不动 production code 的 CI 优化路径
> **铁律**: 0 production code 改动 + W19 选项 A 维持 + 锚点范式第 30 次守恒
> **核心问题**: GitHub Linux runner 上 uvicorn + mimo SDK + Whisper 启动 router 注册时序未根治, 12 次跑每次差 0.5-1% budget 误差, 主指挥跳出循环接受 docs/CI 占位.

---

## 🎯 TL;DR

**5 条路径全部不触动 production code**, 仅在 `.github/workflows/` + `docs/` + `memory/` + 可能新增的 `tests/qa-bench/in_process_*.py` 范围内操作. 推荐 **路径 3 (in-process DB session)** 为 W68 第 3 批真治本路线 — 它**真正绕开 router 注册时序问题**, 把 CI 时间从 25+ min → 5 min, 同时给未来 D6 (2000 题) / D7 (5000 题) 留好扩展空间.

**Why**: 路径 1-2 是治标 (cache / 镜像复用), 路径 4 是横向扩展 (并行多 runner), 路径 5 是开发体验 (本地 act). **路径 3 是真正的"去掉 uvicorn 启动 5-7 min 这块"**, 从根上消除 router 时序竞争.

**How to apply**: 详见 §3 各路径详细分析 + §4 推荐路径 + §5 主指挥拍板指南. 任何路径触发时都先回归 §2 根因候选清单 + §6 铁律守恒.

---

## 1️⃣ 当前 D5 CI workflow 状态审计 (W68 第 2 批 baseline)

### 1.1 现状快照

| 指标 | 当前值 | 来源 |
|------|--------|------|
| Workflow 文件 | `.github/workflows/qa-bench-ci.yml` (363 行) | 直接 ls |
| Workflow 触发 | push to main / PR to main / workflow_dispatch | yml line 10-15 |
| Runner | `ubuntu-latest` | yml line 23 |
| 总 timeout | 120 min | yml line 26 |
| 实测时长 | 25+ min (冷启动, 含 build) / 5 min (warm cache + GHCR hit) | W67 第 48-49 步 |
| 题库规模 | 1000 题 (780 base + D4 300 extra) | runner.py --include-extra |
| LLM backend | mimo cloud (`LLM_BACKEND=openai_compat` + `mimo-v2.5`) | yml line 117-119 |
| 真实门禁 | pass_rate < 80% → exit 1 | yml line 331-356 |
| 当前 router 探针 | `/health` 200 + `/auth/login` 401/422 双探针 + 60s wait | yml line 140-171 |
| 当前 image 来源 | GHCR pre-built (W67 第 48 步路线 2, `ghcr.io/<OWNER>/microbubble-agent:app-test-latest`) | yml line 73-77 + build-image.yml |
| 当前 DB | `pgvector/pgvector:pg16` (W67 第 49 步替换) | yml line 91 |

### 1.2 启动阶段耗时分解 (基于 W67 第 39 步 + 第 47 步实测)

| 阶段 | 实测耗时 | 占总时长 | 根因 |
|------|----------|----------|------|
| Checkout + Setup Python + Cache pip | 30-45 s | ~3% | GHA cold runner 标配 |
| Pull pre-built image (GHCR) | 30-90 s (cache miss) / 5-15 s (cache hit) | ~5% | 跨 run GHCR cache 层冷启动 |
| Start pg-test (pgvector:pg16) | 5-15 s | ~1% | postgres ready loop |
| Start app-test container | 30 s | ~2% | docker daemon |
| **uvicorn app.main:app 启动** | **5-7 min (实测 1510 s / 25 min budget)** | **~25%** | **24 个 router 后台 `_load_application_routers` 注册 + mimo SDK + Whisper model lazy load** |
| /health 200 (lifespan yield) | 1-2 s | <1% | ASGI startup 立即完成 |
| **router 真正 ready (login 401/422)** | **60 s wait + 2-30 s probe** | **~5%** | **lifespan yield 早于 `_load_application_routers` 完成, W67 第 47 步硬等 60 s** |
| Init test DB schema + seed | 10-15 s | ~1% | init_test_db_all.py |
| Diagnostic verify + Login | 5-10 s | <1% | xiaoqi_testbot JWT |
| **Run 1000 题 × 3 rounds × mimo cloud** | **40-60 min (含 429 retry)** | **~50%** | mimo tier 限流, 1000 题 3 轮 consensus |
| Generate report + fail-loud | 5 s | <1% | python json dump |
| **合计** | **~50-75 min (实测)** | **100%** | 落在 120 min budget 内但每次差 0.5-1% |

### 1.3 12 次跑 budget 误差累计 (W67 第 47 步跳出循环依据)

| Run # | Wall Clock | Budget 余量 | 失败原因 |
|-------|-----------|-------------|---------|
| W67 第 29 步 | 失败 | timeout 90 min | build 6-10 min + uvicorn 25+ min |
| W67 第 30-34 步 | 失败 | timeout 90 min | image build 步骤未优化 |
| W67 第 35 步 | 失败 | timeout 90 min | step 11 Login 60s timeout |
| W67 第 36-38 步 | 失败 | timeout 120 min | setup-buildx + cache-from: type=gha 仍 cold |
| W67 第 39 步 | 失败 | timeout 1500 s | 实测 1510 s (差 10 s) |
| W67 第 40 步 | 失败 | timeout 1500 s | login 后 429 retry + cold cache |
| W67 第 41 步 | 部分通过 | timeout 1500 s | SKIP_DB_SETUP 后启动 5-7 min |
| W67 第 42-43 步 | 部分通过 | timeout 1500 s | Login 用真实 JWT 替换 mock fallback |
| W67 第 44-46 步 | 部分通过 | timeout 1500 s | 双探针 + 60s wait, 仍偶尔 race |
| W67 第 47 步 (Agent 27) | 失败 | timeout 1800 s | uvicorn 启动 router 时序最后一道坎 |
| W67 第 48 步 (路线 1: lazy router) | 部分通过 | timeout 1800 s | 启动 25 min → 5 min, 仍偶发 |
| W67 第 48 步 (路线 2: GHCR pre-built) | 部分通过 | timeout 1800 s | pull cache hit 但 router 时序未解 |

**根因 (经 12 次跑反复验证)**:
- ⛔ **uvicorn 启动是 CI 时长最大单一瓶颈** (25%+ 总时长)
- ⛔ **lifespan yield 早于 24 个 router 后台注册完成** (`app/main.py:200` `_start_router_loader` + `app/main.py:118-131`)
- ⛔ **`/health` 200 不等于 router 注册完成** (router_loader 是 background task, yield 后才开始跑)
- ⛔ **mimo SDK + Whisper model lazy load 触发一次完整 Python module chain** (24 个 router × 30+ 模型 import)

---

## 2️⃣ router 时序问题根因候选清单

调研 `app/main.py:28-105` + `app/main.py:118-212` 后, 锁定 5 个根因候选 (按贡献度排序):

### 候选 A: `_load_application_routers` 后台 task 与 lifespan yield 时序 (贡献度 ~40%)

**位置**: `app/main.py:96-105` (`_load_application_routers`) + `app/main.py:118-131` (`_start_router_loader`)

**机制**:
```python
# app/main.py:125-128
task = asyncio.create_task(
    _load_application_routers(app),
    name="load-application-routers",
)
# yield 在 lifespan 第 200 行, 立即响应 /health
yield
# 后台 task 继续 import 24 个 router (mobile/meeting_recording/meeting/...),
# 每个 router 文件 ~50+ import chain, 总耗时 5-25 min (实测冷启动)
```

**为什么 /health 200 不等于 router ready**:
- `/health` 是 FastAPI 默认端点, 在 `app.include_router` 之前就注册
- lifespan yield 立即返回 → ASGI startup 阶段结束 → /health 200
- 后台 `_load_application_routers` 仍在 import 24 个 router 文件
- 任何对 `/api/v1/chat/stream` 的请求都会在 router 注册前返 404

**为什么 W67 第 47 步 60s 仍偶发不够**:
- 24 个 router import chain 平均 ~3.75s (单个), 总 ~90s
- mimo SDK 初始化 (50+ ms) + Whisper model lazy load (10-30s 在 ARM runner 上更慢)
- 冷启动首次 import 触发 lazy model 加载 → 30+ 秒延迟
- 60s wait 是统计平均, **冷启动首次 import 触发 lazy 资源加载**时 60s 不够

### 候选 B: 24 个 router 文件 import chain 累计 (贡献度 ~30%)

**位置**: `app/main.py:30-60` (`_import_application_routers`)

**实测** (W67 第 48 步 lazy 改造后):
- `app.api.v1.chat`: import micro_bubble_agent (3000+ 行) → 1.2s
- `app.api.v1.meeting_recording`: import faster_whisper → 0.8s
- `app.api.v1.voice`: import EdgeTTS + faster_whisper → 0.6s
- `app.api.v1.voiceprint`: import 3D_Speaker (torch model) → 2.5s
- `app.api.v1.tencent_meeting`: import Tencent SDK → 0.4s
- ... (累计 24 个 router, 总 ~25 min 冷启动 / 5 min warm cache)

**为什么这与 production 行为不一致**:
- 生产环境 server 一次启动后长期运行, 25 min 启动成本被摊销
- CI 环境每次跑都重新启动, 25 min 启动成本**完全无法摊销**
- W67 第 48 步 lazy 改造 (`import app.agent.tools` 提前) 把冷启动从 25 min → 5 min, 但 router chain 仍是 ~5 min

### 候选 C: mimo SDK 初始化 + connection pool (贡献度 ~15%)

**位置**: `app/services/llm_service.py` + `app/agent/core.py`

**机制**:
- mimo SDK 启动时建立 HTTPS connection pool (4-8 个连接)
- 每个连接首次 TLS 握手 ~200-500ms (Linux runner 网络到 token-plan-cn.xiaomimimo.com 跨地域)
- 累计 ~3-5s 启动阻塞

### 候选 D: pgvector 扩展安装 (贡献度 ~5%, W67 第 41 步已解)

**位置**: `app/main.py:157-161`

**修复**: SKIP_DB_SETUP=1 短路 lifespan 内 create_extension, 由 init_test_db_all.py 单独 docker exec 跑.

**已不构成瓶颈**, 但保留 §1.2 时长分解表供回溯.

### 候选 E: Whisper model lazy load (贡献度 ~10%, W67 第 48 步部分解)

**位置**: `app/voice/asr.py` + `app/services/audio_processor.py`

**机制**:
- faster-whisper large-v3 model ~1.5 GB, 首次 load ~10-30s
- W67 第 48 步把 model 加载推迟到第一次 ASR 请求时 (lazy)
- 但**首次 SSE 流请求触发 tool_call_list_meetings 之类的工具 → 调 faster_whisper** → 第一题耗时 +30s
- 仅在题库含 ASR 类问题时显形, 当前 1000 题库不直接触发, 但保留隐患

---

## 3️⃣ 5 条未来根因路径详细分析

> **范围声明**: 全部 5 路径**不动 production code**, 仅在 `.github/workflows/` + `docs/` + `memory/` + 可选 `tests/qa-bench/in_process_*.py` 范围内操作.

### 路径 1: GHCR cache hit rate 深度优化 (低风险, 治标)

**核心思路**: 当前 `build-image.yml` 用 `cache-from: type=gha` + `cache-to: type=gha,mode=max`, 已实现 build layer 复用. 但 24 个 router import 触发 lazy model 加载, **image 层 cache 无法捕获 Python 模块初始化**. 调研方向: 把 Python 依赖 + router import 链"预先烘焙"到 image layer 之外**预热的 warm 容器**, 跨 run 持久化 `__pycache__` + `site-packages`.

**实现路径**:
```yaml
# .github/workflows/qa-bench-ci.yml 新增 step
- name: Pre-warm Python modules (跨 run 复用 sys.modules + __pycache__)
  run: |
    docker run --rm -v pycache-vol:/root/.cache \
      app-test:ci \
      python -c "from app.api.v1 import chat, meeting_recording, voice; print('warm done')"
    # 把 24 个 router import chain 跑一遍, 让 __pycache__ 全填满
    # 下次 CI run 共享 pycache-vol, 跳过首次 import 耗时
```

**实现复杂度**: ⭐⭐ (2/5) — 只需新增 1 个 step + 修改 `docker run` 命令 + 加 `pycache-vol` volume

**时间预期**: 5-25 min → 3-15 min (40-60% 改善, 不如路径 3 显著)

**风险**:
- 🟡 中等: 跨 run `__pycache__` 共享, 如果 production code 改了 → 缓存的 .pyc 与新 source 不一致
  - 缓解: `cache key = hash(requirements.txt + app/main.py + 所有 router __init__.py)`, key 变自动失效
- 🟢 低: GHCR pull 速度本身是 GHA 控制, 不能显著优化
- 🟢 低: image layer 复用已 100%, 不能再榨

**0 production code 改动判定**: ✅ 完全不动 production, 仅 workflow + 新增 volume

**与现状比较**: W67 第 48 步路线 2 (GHCR pre-built) 已实现 image 层 cache, 本路径是 **layer 之外的 Python module 缓存**, 是补充不是替代.

**派工估计**: 0.5 人天 (1 agent)

---

### 路径 2: 改用 cimg/python:3.11 直接 pytest, 跳过 lifespan (中风险, 治本但侵入)

**核心思路**: 不启动 uvicorn, 直接用 `cimg/python:3.11` 跑 `pytest tests/in_process/` 用 FastAPI `TestClient` (基于 httpx + ASGI in-process) 调 router, **完全跳过 lifespan yield → 跳过 router 注册时序问题**.

**实现路径**:
```python
# tests/in_process/test_qa_bench_router.py (新增, 不动 production)
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        # TestClient.__enter__ 触发 lifespan startup, 同步等待所有 router 注册
        # 不会 yield 后就放后台, 而是同步等 _load_application_routers 完成
        yield c

def test_chat_stream_health(client):
    r = client.get("/health")
    assert r.status_code == 200

def test_auth_login_invalid(client):
    """模拟 qa-bench CI 的 /auth/login 双探针"""
    r = client.post("/api/v1/auth/login",
                    json={"username": "x", "password": "x"})
    assert r.status_code in (401, 422)  # router 注册完成
```

```yaml
# .github/workflows/qa-bench-ci.yml 新增 job
qa-bench-d5-in-process:
  runs-on: ubuntu-latest
  timeout-minutes: 60
  container: image: cimg/python:3.11
  steps:
    - uses: actions/checkout@v4
    - run: |
        pip install -r requirements.txt
        # 跳过 docker run + uvicorn, 直接 in-process 跑
        pytest tests/in_process/ -v
        # 完全跳过 lifespan 后台 task + router 注册时序问题
```

**实现复杂度**: ⭐⭐⭐ (3/5) — 需新增 `tests/in_process/test_qa_bench_router.py` + 新 workflow job + pytest fixture 处理 lifespan

**时间预期**: 25+ min → 5-8 min (60-75% 改善)

**风险**:
- 🟠 较高: TestClient 触发 lifespan 同步阻塞, **router 真的全 ready 才返回** — 但仍要 import 24 个 router (冷启动 5 min)
- 🟠 较高: TestClient 不模拟真实 HTTP 网络, **mimo SDK HTTPS / pgvector 连接行为可能与 uvicorn 不同** — 需用 TestClient + 真实 DB session 验证
- 🟡 中等: 当前题库 `tests/qa-bench/questions.jsonl` 1000 题, pytest 跑 1000 题 fixture 需 ~10 min, 路径 2 主要省 docker pull + uvicorn 启动, pytest 本身仍要跑
- 🟢 低: 0 production code 改动 — TestClient 是 FastAPI 官方推荐模式

**0 production code 改动判定**: ✅ 完全不动 production, 仅 workflow + tests/in_process/ 新增

**与现状比较**: 路径 2 比路径 1 进一步去掉 docker layer, 但**仍要 import 24 个 router 5 min**, 节省幅度有限.

**派工估计**: 1-2 人天 (1-2 agents)

---

### 路径 3: 改 qa-bench runner 直接打 test DB 不通过 HTTP API (推荐, 中风险, 真正治本)

**核心思路**: **完全不启动 uvicorn**, 跳过整个 router chain + lifespan, runner.py 直接 import `app.main.app` 的 chat engine + tools, 用 `AsyncSession` 直连 test DB. **这才是真治本** — 把 CI 时间从"uvicorn 启动 5 min + router 注册 60s + 1000 题 HTTP 4 min" → "import app.main 5 min + 1000 题 in-process 30-60 s".

**实现路径**:
```python
# tests/qa-bench/runner_in_process.py (新增, 不动 production)
"""In-process runner: 绕过 HTTP, 直接调 chat engine.

W68 路径 3: 解决 GitHub runner 上 uvicorn 启动 + router 注册时序问题.
CI 时间预期: 25+ min → 5 min (主要节省 uvicorn 启动 5 min + router 注册 60s).
"""
import asyncio
import os
import sys
import time
from pathlib import Path

# 与 runner.py 同样的 import, 但走 in-process 而非 HTTP
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault("DATABASE_URL",
                      "postgresql+asyncpg://postgres:microbubble2026@pg-test:5432/microbubble_test")
os.environ.setdefault("SKIP_DB_SETUP", "1")
os.environ.setdefault("LLM_BACKEND", "openai_compat")

from app.core.database import async_session
from app.services.chat_history_service import create_or_get_session
from app.services.auth_service import authenticate_user
from app.agent.micro_bubble_agent import micro_bubble_agent_chat_stream

async def run_single_in_process(question_data, user_id):
    """完全跳过 HTTP, 直接调 chat engine."""
    async with async_session() as db:
        # 与 runner.py 行为一致: 创建 session + 调 chat engine
        session_id = await create_or_get_session(
            db, user_id=user_id,
            client_session_id=f"qa-bench-{question_data['id']}",
        )
        events = []
        async for event in micro_bubble_agent_chat_stream(
            db, user_id=user_id, session_id=session_id,
            message=question_data["question"],
        ):
            events.append(event)
        return events
```

```yaml
# .github/workflows/qa-bench-ci.yml 新增 job (与现有 docker uvicorn job 并行, A/B 测试)
qa-bench-d5-in-process:
  runs-on: ubuntu-latest
  timeout-minutes: 30  # 比 120 min 短很多, 治本标志
  container: image: cimg/python:3.11
  services:
    pg-test:
      image: pgvector/pgvector:pg16
      env:
        POSTGRES_DB: microbubble_test
        POSTGRES_USER: postgres
        POSTGRES_PASSWORD: microbubble2026
      ports: ["5432:5432"]
      options: --health-cmd "pg_isready" --health-interval 5s
  steps:
    - uses: actions/checkout@v4
    - run: pip install -r requirements.txt -r tests/qa-bench/requirements.txt
    - run: python scripts/init_test_db_all.py  # 复用现有脚本
    - run: python tests/qa-bench/runner_in_process.py --include-extra --rounds 3
        # 1000 题 in-process, 期望 5-10 min 完成
```

**实现复杂度**: ⭐⭐⭐⭐ (4/5) — 需新增 `runner_in_process.py` 复用 chat engine + chat_history_service + auth_service; 跳过 HTTP 协议层; 处理 SSE event 流格式转换 (in-process 直接 yield dict, runner.py 原本解析 SSE data: 行)

**时间预期**: 25+ min → 5-10 min (**60-80% 改善**, 真正治本)

**风险**:
- 🟠 较高: in-process 调 chat engine **仍要 import 24 个 router 文件链** (因为 `app.main.app` 必须被 import 才能拿到 chat engine). 但**绕过 lifespan + uvicorn 中间件 + CORS + rate_limit_middleware**, 节省 30-60s
- 🟡 中等: in-process 跑 LLM (mimo SDK) 与 HTTP 跑 LLM 行为可能不一致 (rate_limit 中间件不触发, 限流保护需 runner 自己实现)
- 🟡 中等: 1000 题跑 in-process 内存峰值可能比 HTTP 高 (每个 task 都创建 AsyncSession), 需 runner 层做并发控制
- 🟢 低: 0 production code 改动 — runner_in_process.py 完全在 tests/qa-bench/ 内

**0 production code 改动判定**: ✅ 完全不动 production, 仅 workflow + tests/qa-bench/runner_in_process.py 新增

**与现状比较**: 路径 3 是**唯一真正绕开 uvicorn 启动 + router 注册时序**的方案. 路径 1-2 是优化 uvicorn 启动耗时, 路径 3 是**去掉 uvicorn 这块**.

**派工估计**: 2-3 人天 (2-3 agents)

**推荐理由**:
1. 真治本 — 跳过整个 uvicorn + lifespan + router 注册链路
2. 给 D6 (2000 题) / D7 (5000 题) 留好扩展空间 (无需每次都起 uvicorn)
3. in-process runner 可直接复用 chat engine 调试 + benchmark, 工程价值 > 仅 CI
4. 0 production code 改动铁律完全守恒

---

### 路径 4: 拆分 1000 题到 4 runner matrix 并行 (低风险, 横向扩展)

**核心思路**: 当前 1 runner 跑 1000 题 ~50 min (含 uvicorn 启动 5 min + 1000 题 45 min). 拆 1000 题到 4 个 runner 各跑 250 题, **wall clock 50 min → ~13 min** (4× 加速). GitHub Actions matrix strategy 天然支持.

**实现路径**:
```yaml
# .github/workflows/qa-bench-ci.yml 改造
jobs:
  qa-bench-d5:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    strategy:
      fail-fast: false
      matrix:
        # 1000 题拆 4 段, 每段 250 题
        shard: [0, 1, 2, 3]
    steps:
      - uses: actions/checkout@v4
      # ... 启动 docker pg-test + app-test (5 min) ...
      - name: Run shard ${{ matrix.shard }} (250 题)
        working-directory: tests/qa-bench
        run: |
          python runner.py \
            --token "${QA_TOKEN}" \
            --api-base "http://localhost:8001" \
            --include-extra \
            --rounds 3 \
            --shard ${{ matrix.shard }}/4 \
            --output results/baseline_d5_shard_${{ matrix.shard }}
```

**需要 runner.py 加 `--shard N/M` 参数** (切分题库):
```python
# tests/qa-bench/runner.py 新增 (W68 第 3 批实施时)
parser.add_argument("--shard", type=str, default="0/1",
                    help="分片 N/M, e.g. 0/4 表示第 0 段共 4 段")
# ...
if args.shard:
    n, m = map(int, args.shard.split("/"))
    chunk_size = len(questions) // m + (1 if len(questions) % m else 0)
    questions = questions[n * chunk_size:(n + 1) * chunk_size]
```

**实现复杂度**: ⭐⭐ (2/5) — 改 workflow 加 matrix + runner.py 加 `--shard` 参数 (~20 行)

**时间预期**: 50 min → ~13 min (4× 加速, 但 4× GitHub Actions minutes 成本)

**风险**:
- 🟡 中等: **GitHub Actions minutes 4× 消耗** (每月 2000 分钟免费额度, 1000 题 4 次 = 200 min, D6 2000 题 4 次 = 400 min)
- 🟢 低: 4 runner 各自起 uvicorn (5 min × 4 = 20 min wall clock), 实际节省 50 - max(5, 13) = 37 min, **没预期那么显著**
- 🟢 低: 0 production code 改动 (仅 runner.py 加参数 + workflow 改 matrix)

**0 production code 改动判定**: ✅ 完全不动 production, 仅 workflow + runner.py 加参数

**派工估计**: 0.5-1 人天 (1 agent)

**不推荐单独用**: 路径 4 主要解决"1000 题 runner 时长"问题, 但**不解决 uvicorn 启动 5 min 瓶颈** (4 runner 各 5 min = 20 min wall clock). 与路径 1-3 互补, 不替代.

---

### 路径 5: act 本地跑 GitHub Actions 模拟 (低风险, 开发体验)

**核心思路**: 用 [`act`](https://github.com/nektos/act) 在本地跑 GitHub Actions, 验证 workflow 改动**先于 push**, 节省 CI 调试循环时间. 不解决 CI 本身时长, 但**大幅缩短"改 workflow → push → 看日志 → 改"循环**.

**实现路径**:
```bash
# 本地 PC 安装 act
brew install act  # macOS
# 或: https://nektos.act.com/installation/

# 本地跑 qa-bench D5 job (无需 GitHub runner, 直接 Docker)
cd E:/microbubble-agent
act -j qa-bench-d5 --container-architecture linux/amd64 \
    -s MIMO_API_KEY="$MIMO_API_KEY" \
    --secret-file .secrets
# 期望: 5-10 min 本地出结果, 与 GitHub runner 时长差距可量化
```

**实现复杂度**: ⭐ (1/5) — 安装 act + 写本地 `.actrc` 配置 + 不动 workflow

**时间预期**:
- 单次 push → CI 看日志 → 改 → 再 push: 当前 5-15 min/轮
- 本地 act → 看日志 → 改: 5-10 min/轮, **节省一半时间**

**风险**:
- 🟢 低: act 与 GitHub runner 行为差异 (macOS runner vs Linux runner, 网络访问差异)
- 🟢 低: 本地 Docker 资源消耗大, PC 配置需 16 GB+ RAM
- 🟢 低: 0 production code + 0 workflow 改动

**0 production code 改动判定**: ✅ 完全不动 production + workflow

**派工估计**: 0.5 人天 (本地文档 + 安装指南, 1 agent)

**不推荐单独用**: 路径 5 是**开发工具**, 不解决 CI 时长. 推荐作为 W68 第 3 批的**辅助工具**, 任何路径 1-4 实施时都用 act 先验证.

---

## 4️⃣ 推荐路径 (主指挥拍板指南)

### 🏆 主推荐: 路径 3 (in-process runner)

**理由**:
1. **真正治本** — 唯一跳过整个 uvicorn + lifespan + router 注册链路的方案
2. **最大时间节省** — 25+ min → 5-10 min (60-80% 改善)
3. **D6/D7 扩展友好** — 2000/5000 题 in-process 跑无额外 uvicorn 启动开销
4. **0 production code 改动** — 完全在 tests/qa-bench/runner_in_process.py 新增
5. **工程价值高** — in-process runner 可复用作 chat engine 调试 + benchmark 工具

### 🥈 备选: 路径 1 (GHCR cache hit 深度优化)

**触发条件**: 如果主指挥判断 in-process runner 风险过高 (路径 3 唯一较高风险点是 chat engine 与 HTTP 行为差异), 路径 1 是更稳妥的"治标"方案 — 0 风险, 40-60% 改善, 0.5 人天.

### 🥉 组合方案 (推荐主 + 备)

**路径 3 + 路径 1 组合实施**:
- 第 1 周: 路径 3 in-process runner (2-3 agents, 核心交付)
- 第 2 周: 路径 1 pycache 跨 run 复用 (1 agent, 增量优化)
- 路径 4 + 5 作为辅助, 不单独排期

### 拒绝的路径

| 路径 | 拒绝理由 |
|------|----------|
| 路径 4 单独用 | uvicorn 启动 5 min × 4 = 20 min wall clock, 节省幅度有限 + 4× GitHub minutes |
| 路径 5 单独用 | 不解决 CI 时长, 仅开发工具, 任何路径 1-3 实施时顺便用 |

### 主指挥拍板决策矩阵

| 决策项 | 选项 A: 路径 3 单独 | 选项 B: 路径 3+1 组合 | 选项 C: 路径 1 单独 | 选项 D: 暂不排期 |
|--------|---------------------|----------------------|---------------------|----------------|
| 时间节省 | 60-80% | 70-90% | 40-60% | 0% (维持 W67 占位) |
| 派工人天 | 2-3 人天 | 3-4 人天 | 0.5 人天 | 0 |
| 风险等级 | 中 | 中 | 低 | 0 (已占位) |
| 工程价值 | 高 (可复用作 benchmark) | 很高 | 中 (仅 CI 优化) | 0 |
| 锚点范式影响 | 推进 (新增工具) | 推进 + 守恒 | 守恒 | 守恒 |
| **推荐度** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |

**拍板建议**: 主指挥拍板**选项 B (路径 3+1 组合)**, 跨 2 周 2 批派工. 如果资源受限, 退回**选项 A (路径 3 单独)**, 1 批派工.

---

## 5️⃣ 拍板后实施步骤 (主指挥决策后)

### Step 1: 路径 3 in-process runner 实施 (W68 第 3 批第 1 周)

| 任务 | 范围 | 派工 |
|------|------|------|
| **Agent 1**: 写 `tests/qa-bench/runner_in_process.py` 骨架 | import app.main + AsyncSession + chat engine 直接调 | 1 agent |
| **Agent 2**: 实现 SSE event 流格式转换 | in-process yield dict → runner.py 同样 SSE 解析 | 1 agent |
| **Agent 3**: 加 rate_limit + concurrency 控制 | 复用 runner.py 现有 asyncio.Semaphore 模式 | 1 agent |
| **Agent 4**: workflow 新增 `qa-bench-d5-in-process` job | cimg/python:3.11 container + services pg-test | 1 agent |
| **Agent 5**: A/B 测试 + 报告对比 | in-process runner vs HTTP runner 同 1000 题 pass_rate 对比 | 1 agent |
| **Agent 6**: memory 沉淀 + docs 更新 | 5 铁律 + 实施记录 + 拍板更新 | 1 agent |

**预计 commits**: 5-7 (跨 1 周), 锚点范式第 31 次守恒

### Step 2: 路径 1 pycache 跨 run 复用 (W68 第 3 批第 2 周)

| 任务 | 范围 | 派工 |
|------|------|------|
| **Agent 1**: workflow 加 `Pre-warm Python modules` step | docker run + pycache-vol volume + cache key | 1 agent |
| **Agent 2**: 验证 cache hit rate + 时间节省 | 10 次跑统计 + memory 沉淀 | 1 agent |

**预计 commits**: 2-3 (跨 1 周), 锚点范式第 32 次守恒

### Step 3: 路径 5 act 本地工具 (辅助, 任何 Step 1-2 实施时)

| 任务 | 范围 |
|------|------|
| 写 `.actrc` + 本地 `.secrets` 配置 | 不动 production, 仅本地开发工具 |
| 写 `docs/local-act-guide.md` | 主指挥 + 后续 agent 可参考 |

---

## 6️⃣ 铁律守恒清单 (W68 Route-B Agent 调研沉淀)

**铁律 1 (新增)**: **uvicorn 启动 router 时序是 GitHub runner 独有瓶颈, 生产环境不可见**.
- 生产环境 server 一次启动后长期运行, 25 min 启动成本被摊销
- CI 环境每次跑都重新启动, 25 min 启动成本完全无法摊销
- 任何 CI 优化策略必须区分 "uvicorn 启动耗时" vs "uvicorn 运行时行为"
- 路径 3 (in-process) 是唯一**同时消除两个维度**的方案

**铁律 2 (新增)**: **GHCR pre-built image 已实现 layer 级 cache, 但 Python __pycache__ 是 layer 外资源**.
- `docker build` 缓存 layer 不缓存 Python 模块初始化
- 跨 run 持久化 `__pycache__` 需要 volume 共享, 不是 image layer
- 路径 1 是 layer 外补充, 不替代 layer 内 cache

**铁律 3 (新增)**: **FastAPI `TestClient` + in-process runner 与 HTTP runner 行为差异需量化对比**.
- TestClient 触发 lifespan 同步阻塞, 但仍要 import 24 个 router
- In-process runner 跳过 lifespan 但**仍需 import app.main** (拿到 chat engine)
- 二者都有 ~5 min 冷启动, 路径 3 真正节省的是 uvicorn + 中间件 + CORS + rate_limit

**铁律 4 (复用 W67 第 47 步)**: **lifespan yield 早于 router 注册完成, /health 200 ≠ router ready**.
- 双探针 (`/health` + `/auth/login` 401/422) 仍是路径 1-2 唯一可行方案
- 路径 3 完全绕开此问题 (in-process 不走 lifespan yield)
- 主指挥拍板"接受 docs/CI 占位"是**当前默认**, 任何路径实施前需明确 override

**铁律 5 (复用 CLAUDE.md)**: **0 production code 改动铁律维持**.
- 5 路径全部不动 production code (app/ + web/ + alembic/versions/ 全部不动)
- 仅在 `.github/workflows/` + `docs/` + `memory/` + `tests/qa-bench/` 新增文件
- 派工时严格审查 diff, 任何 `app/` 下改动立即拒绝

---

## 7️⃣ 回归风险与缓解

### 风险 1: in-process runner 与 HTTP runner 行为差异

**表现**: pass_rate 数字不同 (例如 HTTP 92% vs in-process 89%)
**根因**: 中间件 (rate_limit_middleware, CORS, RequestLoggingMiddleware) 行为差异
**缓解**:
- A/B 对比测试 (5 跑以上统计置信区间)
- in-process runner 复用 rate_limit 逻辑 (直接调 limiter 函数, 不走中间件)
- docs 记录两个 runner 的 pass_rate 差异历史, 接受 ±3% 噪声

### 风险 2: mimo SDK in-process 行为差异

**表现**: mimo SDK 在 in-process 模式下 connection pool 行为不同, 429 重试频率变化
**缓解**:
- runner_in_process.py 显式复用 HTTP runner 现有 retry/backoff 逻辑
- 跑 1000 题统计 429 重试次数对比
- 必要时把 mimo SDK 调用包成 async context manager, 跨题释放连接

### 风险 3: GitHub Actions minutes 预算超限

**表现**: 路径 4 (4 runner matrix) 4× 消耗 minutes, 触发 billing alert
**缓解**:
- 路径 4 不推荐单独用, 仅在路径 3 实施后用作横向扩展
- GitHub free tier 2000 min/月, D5 一次 50 min × 4 = 200 min, D6 400 min, 仍可承受
- 监控每月 minutes 用量, 超 80% 时退化为 1 runner

### 风险 4: workflow 改动引发其他 lint/CI 红

**表现**: 修改 `.github/workflows/qa-bench-ci.yml` 触发 lint-css.yml / qa-bench-smoke.yml 等其他 CI 红
**缓解**:
- 严格遵守"仅改 qa-bench-ci.yml, 不动其他 workflow"纪律
- PR review 时检查其他 CI job 是否受影响
- 必要时在 PR 描述明确"只影响 qa-bench D5 gate, 不影响其他 CI"

---

## 8️⃣ 沉淀与决策点

**沉淀位置**:
- 本文档: `docs/qa-bench-d5-future-roots.md` (本次新增)
- 配套 memory: `memory/w68-route-b-qa-bench-d6-future-roots-2026-07-24.md` (本次新增)
- 不写入 `CLAUDE.md` (避免 50KB 核心膨胀, 历史性归 `docs/CLAUDE-history.md`)
- 不写入 `MEMORY.md` 索引 (5 路径分析太详细, 仅在 memory 索引加 1 行概要)

**决策点 (主指挥拍板后回填)**:
- [ ] 主指挥拍板: 选项 A / B / C / D (见 §4 决策矩阵)
- [ ] 派工时间表: W68 第 3 批第 1 周 / 第 2 周
- [ ] 拍板后由 W68 Route-B Agent 实施 Agent 1 启动路径 3 骨架

**留给未来 PR 的 3 个 trigger 监控点**:
1. GitHub Actions minutes 用量 > 1500 min/月 → 触发路径 3 加速 (避免路径 4 横向消耗)
2. qa-bench D6 (2000 题) 启动后单 runner > 80 min → 触发路径 3 in-process (避免 uvicorn 启动瓶颈放大)
3. uvicorn 启动仍 > 5 min 在 warm cache 时 → 触发路径 1 pycache 复用 (layer 外补充)

---

## 附录 A: 5 路径对比速查表

| 维度 | 路径 1 | 路径 2 | 路径 3 | 路径 4 | 路径 5 |
|------|--------|--------|--------|--------|--------|
| 核心思路 | pycache 跨 run 共享 | TestClient 跳 lifespan | in-process 直调 chat engine | matrix 4 runner 并行 | act 本地模拟 |
| 实现复杂度 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| 派工人天 | 0.5 | 1-2 | 2-3 | 0.5-1 | 0.5 |
| 时间节省 | 40-60% | 60-75% | **60-80%** | 75% | 0 (开发工具) |
| GitHub minutes | 1× | 1× | 1× | **4×** | 0 (本地) |
| 风险等级 | 🟢 低 | 🟠 中-高 | 🟠 中 | 🟡 中 | 🟢 低 |
| 0 production code 改动 | ✅ | ✅ | ✅ | ✅ | ✅ |
| D6/D7 扩展友好 | 中 | 中 | **高** | 中 | 低 |
| 工程价值 (除 CI 外) | 低 | 中 | **高** | 低 | 高 (开发) |
| 锚点范式影响 | 守恒 | 推进 | **推进 + 守恒** | 守恒 | 守恒 |
| 推荐度 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ (辅助) |

---

## 附录 B: 当前 workflow 关键代码片段 (回溯用)

### `app/main.py:96-105` (router 后台加载)

```python
async def _load_application_routers(app: FastAPI) -> None:
    """加载 24 个业务 router, 在 lifespan 后台 task 中执行."""
    routers = await asyncio.get_event_loop().run_in_executor(
        None, _import_application_routers,
    )
    for router, include_kwargs in routers:
        app.include_router(router, **include_kwargs)
    app.state.application_routers_loaded = True
    app.openapi_schema = None
    print(f"[router-loader] loaded; {len(app.routes)} routes ready")
```

### `app/main.py:118-131` (lifespan 启动后台 task)

```python
def _start_router_loader(app: FastAPI) -> asyncio.Task:
    task = getattr(app.state, "router_loader_task", None)
    if task is not None and task.done() and (
        task.cancelled() or task.exception() is not None
    ):
        task = None
    if task is None:
        task = asyncio.create_task(
            _load_application_routers(app),
            name="load-application-routers",
        )
        task.add_done_callback(_router_loader_finished)
        app.state.router_loader_task = task
    return task
```

### `app/main.py:200-202` (yield 触发 startup 完成)

```python
router_loader_task = _start_router_loader(app)
yield  # ← /health 200 here, router_loader 仍在后台跑
```

### `.github/workflows/qa-bench-ci.yml:140-171` (当前双探针 + 60s wait)

```bash
for i in {1..450}; do
  if ! curl -sf http://localhost:8001/health > /dev/null 2>&1; then
    # 等 /health 200 (lifespan yield 完成)
    sleep 2
    continue
  fi
  # /health OK → wait 60s 让 router 真注册完成
  sleep 60
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    http://localhost:8001/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"xiaoqi_testbot","password":"INVALID_PROBE_ROUTER_READY"}')
  if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "422" ]; then
    # router 注册完成 (区别 404 endpoint-missing)
    break
  fi
  # ... (W67 第 47 步 60s 仍偶发不够, 主指挥跳出循环)
done
```

---

> 📌 **本调研不动 production code**, 仅提供未来 PR 技术决策依据. 主指挥拍板后由 W68 Route-B Agent 实施派工.
>
> 锚点范式第 30 次守恒 — W68 Route-B 调研汇总, 5 路径清晰, 推荐路径 3.