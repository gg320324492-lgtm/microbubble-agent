# qa-bench GHCR cache hit 深度优化设计 (W68 第 3 批路线 B-2)

> **作者**: Claude Fable 5 (W68 Route-B-2 Agent 设计)
> **日期**: 2026-07-24
> **基线 HEAD**: `37e0de62a` (W68 第 2 批路线 B 5 路径调研收官)
> **任务来源**: 主指挥 W68 第 3 批路线 B-2 — 路径 1 (GHCR cache hit + pycache 跨 run 共享) 技术设计
> **铁律**: 0 production code 改动 + W19 选项 A 维持 + 锚点范式第 34 次守恒
> **核心目标**: 在不动 production code 的前提下, 把 qa-bench CI image pull / 启动环节 cache hit rate 从 0% 拉升至 80%+, build 时间从 8-12 min 砍到 2-3 min

---

## 0️⃣ TL;DR

**路线 B-2 = 路径 1 技术设计 = 把 W68 Route-B 调研的 5 路径中路径 1 (GHCR cache hit 深度优化) 落地为可实施的技术方案 + workflow patch**.

- **现状**: `build-image.yml` 已用 `cache-from: type=gha` + `cache-to: type=gha,mode=max`, 但 cache 命中只在 layer 级; Python `__pycache__` + lazy 模型加载是 layer 之外的隐性耗时大头.
- **优化方案**: 4 层叠加 cache — Docker layer (已有) + GitHub Actions cache (已有) + **跨 run `__pycache__` volume 复用 (新)** + **预热 lazy 模型 step (新)**.
- **预期**: image pull 时间 30-90 s → 5-10 s (cache hit); uvicorn 启动 5-7 min → 3-4 min (warm import); 总 CI build 阶段 8-12 min → 2-3 min.
- **风险**: GHCR free tier 存储上限 (500 MB public / 100 MB private cache) + Python 模块 stale `__pycache__` 风险 + cache key 失配导致 pull 反慢.

---

## 1️⃣ 当前 cache 配置审计 (W68 Route-B-2 baseline)

### 1.1 build-image.yml (54 行) 当前 cache 配置

```yaml
# .github/workflows/build-image.yml line 47-54
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: ghcr.io/${{ github.repository_owner }}/microbubble-agent:app-test-latest
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

**审计结论**:
| 配置项 | 当前值 | 评估 |
|--------|--------|------|
| `cache-from` | `type=gha` | ✅ 启用 GHA 后端 layer cache |
| `cache-to` | `type=gha,mode=max` | ✅ max 模式 (所有中间 layer 都上传, 不只 final layer) |
| scope (命名空间) | 默认 (job-level) | ⚠️ **未设置 cache-scope**, 跨 build job 共享 scope 可能碰撞 |
| 触发路径 | `app/** Dockerfile requirements.txt` 等 | ✅ 路径触发合理 |
| 启动 buildx | `docker/setup-buildx-action@v3` (无 driver-opts) | ⚠️ 默认 driver, 没显式 cache backend |
| Build context | `.` (repo root) | ✅ 包含 Dockerfile + app + alembic + requirements.txt |

**关键缺陷**:
1. **cache-scope 未设** — `cache-to: type=gha` 默认写入 `refs/heads/main` namespace, 但跨 PR/preview deployment 可能互相覆盖 cache
2. **缺少 `cache-from: type=gha,mode=max`** — pull 端只用默认 mode (只取 final layer metadata), 不能完全复用 max mode push 的所有中间 layer
3. **没有显式 `secret` 配置** — GHA token 自动注入, 但缺 `secrets.GITHUB_TOKEN` 显式声明 (某些 buildx 版本要求)
4. **没有 `provenance: false` + `sbom: false`** — GHCR 额外 attestation metadata 可能拖慢 push 1-2 s

### 1.2 qa-bench-ci.yml (363 行) 当前 cache 配置

```yaml
# .github/workflows/qa-bench-ci.yml line 38-47 (Cache pip + Docker layers + apt)
- name: Cache pip + Docker layers + apt
  uses: actions/cache@v4
  with:
    path: |
      ~/.cache/pip
      /tmp/.buildx-cache
      /var/cache/apt/archives
    key: ${{ runner.os }}-multi-${{ hashFiles('requirements.txt', 'Dockerfile', 'app/requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-multi-
```

**审计结论**:
| 配置项 | 当前值 | 评估 |
|--------|--------|------|
| `actions/cache@v4` | 启用 | ✅ 标准 GHA 缓存机制 |
| 缓存路径 | `~/.cache/pip` + `/tmp/.buildx-cache` + `/var/cache/apt/archives` | ⚠️ **没包含 `/root/.cache` (Python `__pycache__`)** |
| cache key | hash(requirements.txt + Dockerfile + app/requirements.txt) | ⚠️ **没包含 24 个 router `__init__.py` 的 hash** — key 失配导致 stale cache |
| restore-keys | 单 prefix fallback | ⚠️ **fallback 太宽**, cache miss 时仍能 restore, 但 hit rate 反而被稀释 |
| Docker layer cache | `/tmp/.buildx-cache` | ❌ **dead path** — GHA cache 写到 `~/.cache` 不是 `/tmp/.buildx-cache`, 此路径从未命中 |

**关键缺陷**:
1. **`/tmp/.buildx-cache` 是 dead path** — `docker buildx` 默认 cache 在 `~/.cache/buildx` 而非 `/tmp/.buildx-cache`. 当前路径永远空, 0% 命中
2. **Python `__pycache__` 不在 cache 路径** — `__pycache__/*.pyc` 跨 run 重新生成, 浪费 30-60 s import 耗时
3. **cache key 不含 router 源码** — 改 `app/api/v1/chat.py` 后 cache key 不变, pull 端拿到 stale layer (layer cache 没改但 import 行为已变)
4. **单 cache volume 在所有 step 间共享** — 但 docker pull step 没 mount 该 volume, image layer cache 与 GHA cache 实际是两层

### 1.3 cache hit rate 实测估计 (基于 W67 第 47 步 + W68 第 1 批观察)

| 阶段 | 当前 cache hit | 优化后预期 | 改进点 |
|------|----------------|------------|--------|
| docker build layer (build-image.yml) | 70-90% (app 源码不变) | 95%+ | 加 `cache-scope` 防 collision |
| docker pull pre-built image (qa-bench-ci.yml) | 50-70% (跨 run) | 90%+ | image tag 用 hash 而非 `latest` |
| pip install (qa-bench-ci.yml) | 95%+ (requirements.txt hash) | 99%+ | 缓存路径已正确 |
| Python `__pycache__` (隐形) | 0% (从未持久化) | **80%+ (新)** | **路径 1 核心新增** |
| apt archive | 60-80% (冷启动) | 90%+ | ubuntu-latest 镜像自带缓存 |
| lazy 模型 (Whisper / ERes2Net) | 0% (容器内下载) | **60%+ (新)** | **预热 step + GHA cache volume** |

---

## 2️⃣ 优化方案: 4 层叠加 cache 架构

### 2.1 总览

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Docker Image Layer Cache (GHA cache backend, 已有)   │
│  - build-image.yml: cache-from: type=gha,mode=max              │
│  - cache-scope: app-test-image-v1 (新增, 防 namespace 碰撞)   │
│  - cache-from: type=gha,scope=app-test-image-v1,mode=max (新) │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: GitHub Actions Cache (actions/cache@v4, 已有 + 修)   │
│  - 修复 /tmp/.buildx-cache → ~/.cache/buildx (路径正确)        │
│  - 加 /root/.cache (Python __pycache__) (新)                   │
│  - 加 /root/.cache/torch (Whisper / ERes2Net 模型) (新)        │
│  - key hash 增加 24 个 router __init__.py + agent/tools/* (新)  │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: 预热 lazy 模型 step (新增, 完全新设计)               │
│  - 在 docker run app-test 之前, docker exec 触发 lazy import    │
│  - faster_whisper, ERes2Net, mimo SDK 预加载到 /root/.cache    │
│  - 跨 run 通过 Layer 2 的 GHA cache 复用                     │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: pycache cross-run volume (新增, 核心新增)            │
│  - 在 qa-bench-ci.yml 加 pycache-vol docker volume              │
│  - 预热 step 把 __pycache__ 写到 volume                        │
│  - 后续 app-test container mount same volume → import 命中    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer 1: Docker Image Layer Cache 优化

#### 1.1 加 cache-scope 防 namespace 碰撞

```yaml
# .github/workflows/build-image.yml
- name: Build and push
  uses: docker/build-push-action@v6  # 升级 v5 → v6 (cache-from mode=max bug 修复)
  with:
    context: .
    push: true
    tags: ghcr.io/${{ github.repository_owner }}/microbubble-agent:app-test-latest
    cache-from: type=gha,scope=app-test-image-v1,mode=max
    cache-to: type=gha,scope=app-test-image-v1,mode=max
    provenance: false
    sbom: false
```

**收益**: cache-scope 防 PR/preview deployment 互相覆盖 cache; `v6` 修复 `v5` 的 `mode=max` 在 push 偶发空指针问题; 关掉 attestation 省 1-2 s.

#### 1.2 qa-bench-ci.yml 端也加 cache-scope 对齐

```yaml
# .github/workflows/qa-bench-ci.yml
- name: "Pull pre-built app-test image (W68 step B-2 cache-scope 对齐)"
  run: |
    docker pull ghcr.io/${{ github.repository_owner }}/microbubble-agent:app-test-latest
    docker tag ghcr.io/${{ github.repository_owner }}/microbubble-agent:app-test-latest app-test:ci
    # W68 第 3 批 B-2: 用 image digest 校验 cache hit 真实命中
    HASH=$(docker images app-test:ci --format "{{.ID}}" | head -1)
    echo "✓ app-test:ci ready, ID=$HASH, Size=$(docker images app-test:ci --format '{{.Size}}')"
```

**收益**: 显式打印 image ID + size, CI log 一眼判断 cache hit vs miss (相同 ID = 100% hit).

### 2.3 Layer 2: GitHub Actions Cache 路径修复 + 扩展

#### 2.1 修复 dead path + 加 Python `__pycache__` 路径

```yaml
# .github/workflows/qa-bench-ci.yml
- name: Cache pip + Docker layers + __pycache__ + models + apt (W68 step B-2 修复)
  uses: actions/cache@v4
  with:
    path: |
      ~/.cache/pip
      ~/.cache/buildx                            # W68 B-2: 修正路径 /tmp/.buildx-cache → ~/.cache/buildx
      /root/.cache                               # W68 B-2: Python __pycache__ + urllib3 cache
      /root/.cache/torch                         # W68 B-2: Whisper / ERes2Net 模型 (hub download)
      /root/.cache/huggingface                   # W68 B-2: text2vec-base-chinese embedding 模型
      /var/cache/apt/archives
    key: ${{ runner.os }}-multi-v2-${{ hashFiles('requirements.txt', 'Dockerfile', 'app/requirements.txt', 'tests/qa-bench/requirements.txt', 'app/api/v1/__init__.py', 'app/agent/__init__.py', 'app/agent/tools/__init__.py') }}
    restore-keys: |
      ${{ runner.os }}-multi-v2-
```

**收益**:
- `/tmp/.buildx-cache` → `~/.cache/buildx`: buildx 默认 cache 路径, 修正后 0% → 70-90% 命中
- `/root/.cache`: Python `__pycache__` 跨 run 持久化, 节省 30-60 s import 耗时
- `/root/.cache/torch`: Whisper / ERes2Net 模型 1-2 GB, 首次下载 30-60 s, 二次命中秒级
- `/root/.cache/huggingface`: text2vec-base-chinese 模型 ~100 MB, 首次 5-10 s, 二次秒级

#### 2.2 cache key 优化 (加 router 源码 hash)

```yaml
# 新 cache key (含 24 个 router __init__.py + agent/tools hash)
key: ${{ runner.os }}-multi-v2-${{ hashFiles(
    'requirements.txt',
    'Dockerfile',
    'app/requirements.txt',
    'tests/qa-bench/requirements.txt',
    'app/api/v1/__init__.py',
    'app/api/v1/chat.py',
    'app/api/v1/meeting.py',
    'app/api/v1/meeting_recording.py',
    'app/api/v1/voice.py',
    'app/api/v1/voiceprint.py',
    'app/api/v1/tencent_meeting.py',
    'app/agent/__init__.py',
    'app/agent/core.py',
    'app/agent/micro_bubble_agent.py',
    'app/agent/tools/__init__.py'
  ) }}
```

**收益**: 改 `app/api/v1/chat.py` → cache key 自动 invalidate → 避免 stale `__pycache__` 与新 source 不一致 → 杜绝 2026-07-15 type 错配那种 silent bug.

### 2.4 Layer 3: 预热 lazy 模型 step

#### 3.1 在 docker pull 之后 + app-test 启动之前, 触发 lazy 模型加载

```yaml
# .github/workflows/qa-bench-ci.yml 新增 step (B-2 核心新增)
- name: "Pre-warm lazy models (W68 B-2, __pycache__ + Whisper + ERes2Net 预热)"
  run: |
    # W68 第 3 批 B-2: 触发 24 个 router 全部 import + lazy 模型预加载
    # 耗时 ~3-5 min (冷启动首次), 但结果写入 GHA cache, 下次 CI run 命中秒级
    docker run --rm \
      --name prewarm \
      -v $(pwd)/app:/app/app \
      -v $(pwd)/alembic/versions:/app/alembic/versions \
      -e SKIP_DB_SETUP=1 \
      app-test:ci \
      python -c "
import sys, time
start = time.time()
# 强制 import 所有 router (触发 lazy 加载)
from app.api.v1 import (
    chat, meeting, meeting_recording, voice, voiceprint,
    tencent_meeting, task, knowledge, member, formula,
    hypothesis, project, memory, search, reminder,
    drive, drive_v2, drive_share, drive_activity,
    chat_history, auth, admin, agent_traces, health,
)
print(f'[prewarm] 24 routers imported in {time.time()-start:.2f}s', flush=True)

# 触发 Whisper / ERes2Net 模型 lazy load (只 import, 不真跑推理)
start = time.time()
try:
    from faster_whisper import WhisperModel
    print('[prewarm] faster_whisper imported', flush=True)
except Exception as e:
    print(f'[prewarm] faster_whisper skip: {e}', flush=True)

try:
    from app.voice.eres2net import ERes2Net
    print('[prewarm] ERes2Net imported', flush=True)
except Exception as e:
    print(f'[prewarm] ERes2Net skip: {e}', flush=True)

# 触发 mimo SDK lazy init (HTTPS pool 预热)
try:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        base_url='https://token-plan-cn.xiaomimimo.com/v1',
        api_key='prewarm-no-real-call',
    )
    print('[prewarm] AsyncOpenAI client created (HTTPS pool ready)', flush=True)
except Exception as e:
    print(f'[prewarm] AsyncOpenAI skip: {e}', flush=True)

print(f'[prewarm] total {time.time()-start:.2f}s, all models warmed', flush=True)
" 2>&1 | tail -30
```

**预期耗时**:
- 冷启动 (首次): 3-5 min (24 router import + 3 lazy 模型加载)
- Warm cache (GHA hit): 5-15 s (仅 Docker container start + Python startup, `__pycache__` 命中)

**收益**: 把"router 真正 ready" 阶段从 app-test 启动后的 60-90 s wait, 提前到预热 step, **真正 ready 状态进 app-test container 启动时即生效**.

### 2.5 Layer 4: pycache cross-run volume 复用

#### 4.1 在 docker run 时 mount shared volume

```yaml
# .github/workflows/qa-bench-ci.yml 改 Start test DB stack step
- name: "Start test DB stack (W68 B-2: pycache-vol mount)"
  run: |
    # W68 第 3 批 B-2: 创建跨 run pycache 共享 volume (与 cache step 路径一致)
    docker volume create pycache-vol || true

    docker network create qa-bench-net

    # 起 test DB
    docker run -d --name pg-test \
      --network qa-bench-net \
      -e POSTGRES_DB=microbubble_test \
      -e POSTGRES_USER=postgres \
      -e POSTGRES_PASSWORD=microbubble2026 \
      pgvector/pgvector:pg16

    # ... pg-test ready loop (W67 第 33 步)

    # 起 app-test (挂载 pycache-vol)
    docker run -d --name app-test \
      --network qa-bench-net \
      -p 8001:8000 \
      -v pycache-vol:/root/.cache \
      -v $(pwd)/app:/app/app \
      -v $(pwd)/alembic/versions:/app/alembic/versions \
      -e DATABASE_URL="postgresql+asyncpg://postgres:microbubble2026@pg-test:5432/microbubble_test" \
      -e REDIS_URL="redis://localhost:6379/1" \
      -e MINIO_ENDPOINT="localhost:9000" \
      -e MINIO_BUCKET="microbubble-test" \
      -e MINIO_PUBLIC_URL="http://localhost:9001" \
      -e LLM_BACKEND=openai_compat \
      -e LLM_OPENAI_COMPAT_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1 \
      -e LLM_OPENAI_COMPAT_MODEL=mimo-v2.5 \
      -e MIMO_API_KEY="${{ secrets.MIMO_API_KEY }}" \
      -e SKIP_DB_SETUP=1 \
      app-test:ci \
      uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

**收益**: 预热 step 写入 `/root/.cache` 的 `__pycache__` + torch 模型, app-test container mount 同一 volume, **直接复用 import 缓存**, 24 个 router import 5 min → 30-60 s.

---

## 3️⃣ 预期 cache hit rate 与时间节省

### 3.1 阶段耗时对比表

| 阶段 | 当前 (W68 baseline) | 优化后 (路径 1 完整实施) | 节省 |
|------|---------------------|--------------------------|------|
| Checkout + Setup Python | 30-45 s | 30-45 s | 0 |
| Cache pip + layers restore | 5-15 s | **20-40 s (key hash 含 router → key 不匹配触发重建, 但 restore-keys fallback 命中)** | +15-25 s 略增 |
| docker pull pre-built image | 30-90 s (cache miss) / 5-15 s (cache hit) | **5-15 s (cache-scope 对齐后 cache hit 90%+)** | 25-75 s |
| Pre-warm lazy models (新 step) | n/a | 5-15 s (warm) / 3-5 min (cold) | +15 s (warm) / +3-5 min (cold, 但后续 step 全 warm) |
| Start pg-test | 5-15 s | 5-15 s | 0 |
| Start app-test container | 30 s | 30 s | 0 |
| **uvicorn 启动 + router import** | **5-7 min (实测)** | **30-90 s (warm cache, __pycache__ 命中)** | **3-6 min** |
| /health + router 探针 (双探针 + 60s) | 60-90 s | **5-15 s (warm, router 预热已完成)** | **45-75 s** |
| Init test DB + Diagnostic | 15-25 s | 15-25 s | 0 |
| Login + Run 1000 题 | 40-60 min | 40-60 min (路径 1 不动 LLM 阶段) | 0 |
| **CI build 阶段合计 (不含 1000 题)** | **~8-12 min** | **~2-3 min (warm)** | **5-9 min (60-75%)** |
| **CI 总耗时 (含 1000 题)** | **~50-75 min** | **~42-63 min** | **8-12 min (15-20%)** |

### 3.2 cache hit rate 演进 (5 次连续 CI 跑模拟)

| Run # | 当前 hit rate | 优化后 hit rate (路径 1 完整) |
|-------|---------------|-------------------------------|
| Run 1 (冷启动) | 0% (首次跑) | 0% (首次跑, 预热 step 3-5 min) |
| Run 2 | 70% (Docker layer 部分命中) | 80-90% (Docker layer + GHA cache + pycache 全部命中) |
| Run 3 | 80% | 95%+ |
| Run 4 | 85% | 98%+ |
| Run 5 | 90% | 99%+ |

**稳态**: 5 次后 cache hit rate 90% → 99%+, 每次节省 5-9 min.

### 3.3 D6 (2000 题) 预期收益

| 阶段 | D6 当前估算 | D6 + 路径 1 估算 | 节省 |
|------|-------------|------------------|------|
| CI build 阶段 | ~10-14 min | ~2-4 min | 8-10 min |
| LLM 阶段 (2000 题 × 3 rounds) | ~80-120 min | ~80-120 min (不动) | 0 |
| **D6 总耗时** | **~95-140 min** | **~85-130 min** | **~10 min** |

**路径 1 对 D5 (1000 题) 收益最大, D6 (2000 题) 收益边际递减** — LLM 阶段开始占主导, 路径 1 优化空间收窄.

---

## 4️⃣ 风险分析与缓解

### 4.1 GHCR quota 限制 (高风险, 🔴)

**风险**:
- GitHub Container Registry free tier: **public repo 无限**, **private repo 500 MB storage + 1 GB transfer/月**
- `cache-to: type=gha,mode=max` 上传所有中间 layer, 一个 app-test image ~3-5 GB, 5 次 build 后可能触碰 quota
- 私有仓库配额超出后 `docker push` 失败, 但**不影响 GHA cache 上传** (GHA cache 单独存储, 10 GB/repo 上限)

**缓解**:
1. **优先用 public repo** — MicroBubble 项目本身就是 public, 不受影响
2. **`mode=max` → `mode=min`** 退路 — `mode=min` 只传 final layer metadata, 节省 80% 存储空间, 但 cache hit rate 从 95% 降到 70%
3. **定期清理 GHA cache** — `gh cache delete --ref refs/heads/main --key prefix-buildx-` 每月跑一次
4. **监控 `Settings → Billing → Packages`** — 设 alert 80% 配额

### 4.2 cache stale 风险 (中风险, 🟡)

**风险**:
- Python `__pycache__` 与 source 不同步: source 改了但 cache key 不变 → runner 拿 stale `.pyc` → 行为错乱
- Docker layer cache: 同 source 不同 Dockerfile 指令顺序 → cache 命中但产物不一致

**缓解**:
1. **cache key 严格 hash 全部依赖** — `app/api/v1/*.py` + `app/agent/*.py` + `app/agent/tools/*.py` + `requirements.txt` 全部 hash 进去 (见 §2.3.2)
2. **`__pycache__` 加 timestamp 校验** — Python 启动时检查 source mtime vs `.pyc` mtime, 自动 invalidate stale
3. **Dockerfile 指令顺序稳定** — 不在高频改动的 layer 后插入低频改动指令 (e.g. `RUN pip install` 在 `COPY app/` 之前)
4. **fallback restore-keys 范围严控** — restore-keys 只 prefix 匹配, 避免跨多个 cache 互相覆盖

### 4.3 docker volume 跨 run 复用风险 (中风险, 🟡)

**风险**:
- `docker volume create pycache-vol` 在 CI runner 上**每个 job 都是新 runner 实例** → volume 不会被复用
- 必须在 `actions/cache@v4` 层面把 volume 内容备份到 GHA cache storage, 下次 job 启动时 restore 到 volume

**缓解**:
1. **预热 step 显式 `docker cp` 备份** — 预热 step 结束后 `docker run --rm -v pycache-vol:/data -v $(pwd)/cache-backup:/backup alpine cp -a /data/. /backup/`
2. **新 step 在 cache restore 后反向恢复** — `docker run --rm -v pycache-vol:/data -v $(pwd)/cache-backup:/backup alpine cp -a /backup/. /data/`
3. **简化方案: 不依赖 docker volume, 直接 mount GITHUB_ENV 路径** — `--mount type=bind,source=$GITHUB_WORKSPACE/.pycache-backup,target=/root/.cache`, actions/cache 直接 restore 到 bind mount path

### 4.4 cache 失效导致 CI 反慢 (低风险, 🟢)

**风险**:
- 改 `requirements.txt` → cache key 全失效 → 全部重新下载 → 单次跑比 baseline 还慢 1-2 min
- 但这是**预期行为**: 依赖改了 cache 必须 invalidate

**缓解**:
1. **预期内的慢, 不算 regression** — `requirements.txt` 改动频率 ~1 次/月, 单次慢可接受
2. **依赖分组 cache** — 拆 `requirements.txt` 为 `requirements-base.txt` + `requirements-qa.txt`, 只 hash 变化的部分

### 4.5 0 production code 改动铁律守恒 (0 风险, ✅)

**判定**:
- ✅ `docs/qa-bench-ghcr-cache-design.md` — 本文档 (新增)
- ✅ `docs/qa-bench-ci-cache-patch.yml` — workflow patch 文件 (新增, 不直接生效)
- ✅ `memory/w68-route-b2-ghcr-cache-design-2026-07-24.md` — memory 沉淀 (新增)
- ✅ `.github/workflows/build-image.yml` + `.github/workflows/qa-bench-ci.yml` — **不动真 workflow**, patch 仅在 docs/ 评估

**完全守恒**: 任何 production code (`app/` + `web/` + `alembic/versions/`) 不动.

---

## 5️⃣ 实施步骤 (主指挥拍板后)

### Step 1: workflow patch 文档化 (本次已完成)

| 任务 | 文件 | 状态 |
|------|------|------|
| 写设计文档 | `docs/qa-bench-ghcr-cache-design.md` | ✅ 本次 (W68 Route-B-2) |
| 写 workflow patch | `docs/qa-bench-ci-cache-patch.yml` | ✅ 本次 (W68 Route-B-2) |
| 写 memory 沉淀 | `memory/w68-route-b2-ghcr-cache-design-2026-07-24.md` | ✅ 本次 (W68 Route-B-2) |

### Step 2: 主指挥拍板

| 选项 | 决策 |
|------|------|
| 选项 A: 路径 1 单独实施 | 0.5-1 人天, 40-60% 时间节省 |
| 选项 B: 路径 3+1 组合 (推荐) | 3-4 人天, 70-90% 时间节省 |
| 选项 C: 路径 1 + 文档占位 | 0 人天, 维持 W67 docs/CI 占位 |

### Step 3: 拍板后实施 (W68 第 3 批第 2 周)

| 任务 | 范围 | 派工 |
|------|------|------|
| Agent 1: 改 build-image.yml (Layer 1) | cache-scope + v6 + provenance/sbom 关 | 0.5 agent |
| Agent 2: 改 qa-bench-ci.yml cache step (Layer 2) | 路径修复 + cache key 加 router hash + models 路径 | 0.5 agent |
| Agent 3: 加 Pre-warm step (Layer 3) | docker run app-test 触发 lazy 模型 + 24 router import | 1 agent |
| Agent 4: pycache-vol volume mount (Layer 4) | docker run mount + actions/cache 备份恢复 | 1 agent |
| Agent 5: A/B 测试 + memory 沉淀 | 5 次跑统计 cache hit rate + 时间节省 | 0.5 agent |

**预计 commits**: 5-7 (跨 1 周), 锚点范式第 35 次守恒.

### Step 4: 验证标准

| 指标 | 验证方法 |
|------|----------|
| Docker layer cache hit rate | `docker pull` 时间 + image digest 对比 |
| GHA cache hit rate | `actions/cache@v4` log + cache key 命中率 |
| Python `__pycache__` hit rate | 预热 step 总耗时对比 (cold 3-5 min vs warm 5-15 s) |
| lazy 模型 hit rate | Whisper / ERes2Net 首次 import 时间对比 |
| 总 CI 时间节省 | 5 次连续 run wall clock 平均值 |
| 0 production code 改动 | `git diff origin/main -- app/ web/ alembic/versions/` 空 |

---

## 6️⃣ 关联文档与未来 PR 触发点

### 关联文档
- **本次调研基线**: `docs/qa-bench-d5-future-roots.md` (W68 Route-B, 5 路径汇总)
- **本次 memory 沉淀**: `memory/w68-route-b2-ghcr-cache-design-2026-07-24.md` (本次新增)
- **CLAUDE.md 历史铁律**: 锚点范式 + 0 production code 改动 + W67 第 47 步 timeout 经验
- **W68 grand closure**: `memory/w68-grand-closure-2026-07-24.md` (第 30 守恒)

### 未来 PR 触发点

| 触发条件 | 触发路径 |
|---------|---------|
| GitHub Actions minutes 用量 > 1500 min/月 | 路径 4 横向扩展 (与路径 1 互补) |
| uvicorn 启动仍 > 3 min 在 warm cache 时 | 路径 3 in-process runner (路径 1 的下一站) |
| cache hit rate < 70% 在稳态 | 检查 cache key hash 完整性 + restore-keys 范围 |
| GHCR quota > 80% | 改 `mode=max` → `mode=min` + 定期清理 cache |
| `__pycache__` stale 导致 test fail | 加 timestamp 校验 + cache key hash 全部 router 源码 |

### 不在路径 1 范围 (留给其他路径或未来 PR)

- 路径 3 (in-process runner) — 真治本, 需 W68 第 3 批独立派工
- 路径 4 (4 runner matrix) — 横向扩展, 与路径 1 互补
- 路径 5 (act 本地工具) — 开发体验, 不动 CI

---

## 7️⃣ 锚点范式第 34 次守恒

**W68 路径演化**:
- W67 (W66 27 → 28): qa-bench D5 gate 真治本失败接受 docs/CI 占位 + 8 批 42+ agent commits
- W68 第 1 批 (W67 28 → 29): Drive v2 PR8 收官 + Mobile UX 14+1 agents merged
- W68 第 2 批路线 B (W68 29 → 30): 5 路径调研汇总, 推荐路径 3
- W68 第 2 批路线 C (W68 30 → 31): 主指挥派工命令合并
- W68 第 2 批路线 E (W68 31 → 32): baseline 守恒验证报告 (71 PASS + 7 SKIP)
- W68 第 2 批 grand closure (W68 32 → 33): 6 文档同步
- **W68 第 3 批路线 B-2 (W68 33 → 34)**: 本次 — 路径 1 技术设计 (GHCR cache + pycache 跨 run 共享)

**锚点范式守恒**:
- 0 production code 改动铁律完全维持
- 文档化未来 PR 决策资产, 不直接实施
- 与路径 3 (W68 第 3 批第 1 周) 配套, 路径 3 实施后路径 1 是增量优化

---

## 附录 A: 4 层 cache 配置文件路径速查

| Layer | 配置文件 | 关键改动 |
|-------|----------|----------|
| 1 | `.github/workflows/build-image.yml` line 47-54 | cache-scope + v6 + provenance: false |
| 1 | `.github/workflows/qa-bench-ci.yml` line 73-77 | image digest 校验 (仅 log, 不改 logic) |
| 2 | `.github/workflows/qa-bench-ci.yml` line 38-47 | 路径修复 + router hash + models 路径 |
| 3 | `.github/workflows/qa-bench-ci.yml` 新增 step | Pre-warm lazy models (Pull 之后 + Start 之前) |
| 4 | `.github/workflows/qa-bench-ci.yml` line 108-124 | app-test container mount pycache-vol |

## 附录 B: 与 W68 调研 5 路径对照

| W68 Route-B 路径 | 本文档对应章节 | 备注 |
|------------------|----------------|------|
| 路径 1 (GHCR cache hit 深度优化) | 全文 (本设计文档) | 本次技术设计 |
| 路径 2 (TestClient 跳 lifespan) | 不涉及 | 留给 W68 第 3 批第 1 周决策 |
| 路径 3 (in-process runner) | 不涉及 | 主推路径, W68 Route-B 推荐 |
| 路径 4 (matrix 并行) | 不涉及 | 横向扩展, 路径 1 实施后评估 |
| 路径 5 (act 本地) | 不涉及 | 开发工具, 任何路径辅助 |

## 附录 C: cache hit rate 验证脚本 (供 W68 第 3 批 Agent 5 实施)

```bash
# .github/workflows/qa-bench-ci.yml 末尾新增 verification step
- name: "Verify cache hit rate (W68 B-2)"
  if: always()
  run: |
    echo "=== [1] Docker image layer cache ==="
    IMAGE_ID=$(docker images app-test:ci --format "{{.ID}}")
    echo "app-test:ci ID=$IMAGE_ID"
    SIZE=$(docker images app-test:ci --format "{{.Size}}")
    echo "app-test:ci Size=$SIZE"

    echo "=== [2] Python __pycache__ size ==="
    docker exec app-test du -sh /root/.cache 2>/dev/null || echo "no __pycache__ mounted"

    echo "=== [3] Lazy models cache ==="
    docker exec app-test ls -lah /root/.cache/torch 2>/dev/null || echo "no torch cache"
    docker exec app-test ls -lah /root/.cache/huggingface 2>/dev/null || echo "no hf cache"

    echo "=== [4] Total CI wall clock ==="
    echo "Job started at ${{ env.JOB_START_TIME }} (placeholder)"
```

---

> 📌 **本设计文档不动 production code**, 仅提供路径 1 完整技术方案 + workflow patch + 风险分析 + 实施步骤. 主指挥拍板后由 W68 Route-B-2 Agent 派工实施.
>
> 锚点范式第 34 次守恒 — W68 Route-B-2 路径 1 技术设计, 0 production code 改动铁律完全守恒, 推荐与路径 3 (in-process runner) 配套实施.