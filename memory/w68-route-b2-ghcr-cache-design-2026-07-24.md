---
name: w68-route-b2-ghcr-cache-design-2026-07-24
description: "W68 第 3 批路线 B-2 路径 1 (GHCR cache hit + pycache 跨 run 共享) 技术设计沉淀. 锚点范式第 34 次守恒. 0 production code 改动, 4 层叠加 cache + 风险分析 + 实施步骤."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-Route-B-2
  modified: 2026-07-24T00:00:00.000Z
---

# 2026-07-24 W68 第 3 批路线 B-2 — qa-bench GHCR cache hit 深度优化设计

## TL;DR

W68 Route-B 调研 (5 路径汇总) 推荐路径 3 (in-process runner), 主指挥决定配套实施**路径 1 (GHCR cache hit 深度优化)** — 4 层叠加 cache 架构, 在不动 production code 的前提下把 CI build 阶段从 8-12 min 砍到 2-3 min (warm cache). 设计文档 + workflow patch + memory 三件套全部沉淀, 主指挥拍板后由 W68 Route-B-2 Agent 派工实施.

## Why

W67 第 47 步主指挥跳出循环接受 docs/CI 占位后, W68 第 2 批路线 B 调研 5 路径 + 推荐路径 3 (主推). 主指挥决策"配套实施路径 1", 作为路径 3 的增量优化 (路径 3 in-process runner 实施后, 路径 1 是 layer 外补充, 不替代 layer 内 cache). 锚点范式要求"调研 → 设计 → 拍板 → 实施"四阶段逐步推进, 路线 B-2 是"设计"阶段, 输出可落地的技术方案 + workflow patch + 风险分析.

## How to apply

主指挥拍板后由 W68 Route-B-2 Agent 实施派工:
1. 拍板选项 A (路径 1 单独 0.5-1 人天) / B (路径 3+1 组合 3-4 人天, 推荐) / C (维持占位)
2. 拍板后由 Agent 1 改 build-image.yml (Layer 1) + Agent 2 改 cache step (Layer 2)
3. Agent 3 加 Pre-warm step (Layer 3) + Agent 4 加 pycache-vol mount (Layer 4)
4. Agent 5 A/B 测试 5 次跑统计 cache hit rate + 时间节省

---

## 1️⃣ 现状审计结论 (W68 Route-B-2 baseline)

### build-image.yml (54 行) 缺陷

| 配置项 | 当前值 | 缺陷 |
|--------|--------|------|
| `cache-from` | `type=gha` | ⚠️ 未加 `mode=max` |
| `cache-to` | `type=gha,mode=max` | ✅ 正确 |
| scope | 默认 | ❌ 未设 cache-scope, 跨 job 共享可能碰撞 |
| action 版本 | `docker/build-push-action@v5` | ⚠️ v5 偶发 mode=max 空指针, v6 已修 |
| provenance + sbom | 默认 on | ⚠️ push 慢 1-2 s |

### qa-bench-ci.yml (363 行) 缺陷

| 配置项 | 当前值 | 缺陷 |
|--------|--------|------|
| cache path | `~/.cache/pip` + `/tmp/.buildx-cache` + `/var/cache/apt/archives` | ❌ `/tmp/.buildx-cache` 是 dead path (buildx 写到 `~/.cache/buildx`) |
| 缓存路径覆盖 | 无 | ❌ 缺 `/root/.cache` (Python `__pycache__`) + `/root/.cache/torch` (Whisper/ERes2Net) + `/root/.cache/huggingface` |
| cache key | hash(requirements.txt + Dockerfile + app/requirements.txt) | ⚠️ 不含 24 个 router 源码, 改 router 后 stale cache |
| restore-keys | 单 prefix | ✅ 合理 |

## 2️⃣ 4 层叠加 cache 架构 (核心新增)

```
Layer 1: Docker Image Layer Cache (GHA cache backend)
  └─ cache-from: type=gha,scope=app-test-image-v1,mode=max (新)
  └─ cache-to: type=gha,scope=app-test-image-v1,mode=max (新)

Layer 2: GitHub Actions Cache (actions/cache@v4)
  └─ 修 /tmp/.buildx-cache → ~/.cache/buildx (新)
  └─ 加 /root/.cache + /root/.cache/torch + /root/.cache/huggingface (新)
  └─ cache key hash 增 router __init__.py + agent/tools/* (新)

Layer 3: 预热 lazy 模型 step (全新设计)
  └─ Pre-warm step: docker run app-test:ci 触发 24 router import + 3 lazy 模型
  └─ 冷启动 3-5 min, warm 5-15 s

Layer 4: pycache cross-run volume (全新设计)
  └─ docker volume create pycache-vol
  └─ app-test container mount -v pycache-vol:/root/.cache
  └─ actions/cache 持久化 /root/.cache 路径实现跨 run 复用
```

## 3️⃣ 预期收益 (W68 Route-B-2 baseline → 优化后)

| 阶段 | 当前 | 优化后 | 节省 |
|------|------|--------|------|
| docker pull image | 30-90 s (miss) / 5-15 s (hit) | **5-15 s (90%+ hit)** | 25-75 s |
| uvicorn 启动 + router import | **5-7 min** | **30-90 s (warm)** | **3-6 min** |
| /health + router 探针 | 60-90 s | **5-15 s (warm)** | **45-75 s** |
| **CI build 阶段合计** | **8-12 min** | **2-3 min (warm)** | **5-9 min (60-75%)** |
| **CI 总耗时 (含 1000 题)** | **50-75 min** | **42-63 min** | **8-12 min (15-20%)** |

**稳态 cache hit rate**: 5 次连续跑后 99%+, 跨 run 持久化 `__pycache__` + lazy 模型.

## 4️⃣ 风险矩阵

| 风险 | 等级 | 缓解 |
|------|------|------|
| GHCR quota 限制 (private repo 500 MB storage/月) | 🔴 高 | public repo 无限 + 退路 `mode=min` + 定期清理 |
| cache stale (`__pycache__` 与 source 不同步) | 🟡 中 | cache key hash 全部 router + Python mtime 自动 invalidate |
| docker volume 跨 run 不可复用 (新 runner 实例) | 🟡 中 | actions/cache@v4 持久化 /root/.cache 路径 |
| cache 失效导致 CI 反慢 (改 requirements.txt) | 🟢 低 | 预期内行为 + 依赖分组 cache |
| 0 production code 改动铁律 | ✅ 守恒 | 仅 docs/ + memory/, 不动 app/ web/ alembic/ |

## 5️⃣ 与 W68 Route-B 5 路径对照

| W68 Route-B 路径 | 关系 |
|------------------|------|
| **路径 1 (GHCR cache hit)** | **本次 B-2 完整技术设计** |
| 路径 3 (in-process runner) | 主推路径, 与路径 1 配套 (B-1 由其他 agent 实施) |
| 路径 4 (matrix 并行) | 横向扩展, 路径 1 实施后评估 |
| 路径 5 (act 本地) | 开发工具, 任何路径辅助 |
| 路径 2 (TestClient) | 不推荐, 留未来 |

## 6️⃣ 5 条新铁律沉淀 (W68 Route-B-2 设计新增)

### 铁律 1: Docker image layer cache 不缓存 Python 模块初始化

- `docker build` 缓存 layer 不缓存 Python `__pycache__` (容器启动后才生成)
- 跨 run 持久化 `__pycache__` 需要 volume 共享 + actions/cache 配合
- 路径 1 是 layer 外补充, 不替代 layer 内 cache

### 铁律 2: cache key 必须严格 hash 所有依赖源码

- 改 `app/api/v1/chat.py` 后 cache key 不变 → runner 拿 stale `.pyc` → 行为错乱
- 修法: key hash 24 个 router `__init__.py` + `agent/tools/*` + `requirements.txt` 全部进去
- Python mtime 自动校验是兜底, 但 cache key 是第一道防线

### 铁律 3: docker volume 在 GHA runner 上不可跨 job 复用

- 每个 CI job 是新 runner 实例, `docker volume create` 创建的 volume 在 job 结束时销毁
- 必须靠 `actions/cache@v4` 持久化 volume 内容到 GHA cache storage
- 简化: 直接 mount bind path (`$GITHUB_WORKSPACE/.pycache-backup`) 而非 docker volume

### 铁律 4: cache-scope 是 GHA cache namespace 隔离必备

- 默认 scope 是 `refs/heads/main`, 跨 PR/preview deployment 可能互相覆盖
- 显式 `scope=app-test-image-v1` 让 build / test / deploy 各自独立 namespace
- 监控 cache 用量, 超出 5 GB 时清理

### 铁律 5: 0 production code 改动铁律完全维持

- 4 层 cache 改动全在 `.github/workflows/` + `docs/` + `memory/`
- 不动 `app/` + `web/` + `alembic/versions/` 任何文件
- workflow patch 写到 `docs/qa-bench-ci-cache-patch.yml`, 不直接合并到真 workflow
- 主指挥拍板后才实施, 派工时严格审查 diff

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

## 8️⃣ 沉淀位置

- **核心设计文档**: `docs/qa-bench-ghcr-cache-design.md` (~400 行, 4 层 cache + 风险 + 实施步骤 + 附录)
- **workflow patch 文件**: `docs/qa-bench-ci-cache-patch.yml` (~150 行, 不直接生效, 待主指挥拍板)
- **本 memory**: 设计汇总 + 5 新铁律 + 锚点范式第 34 守恒 + 风险矩阵
- **关联文档**: `docs/qa-bench-d5-future-roots.md` (W68 Route-B 调研基线) + `memory/w68-grand-closure-2026-07-24.md` (第 30 守恒)
- **不写入**: CLAUDE.md (避免 50KB 核心膨胀) / MEMORY.md 索引 (设计文档太详细, 仅在索引加 1 行概要)

## 9️⃣ 派工估计 (主指挥拍板后)

| Agent | 范围 | 派工人天 |
|-------|------|----------|
| Agent 1 | 改 build-image.yml (Layer 1: cache-scope + v6) | 0.5 |
| Agent 2 | 改 qa-bench-ci.yml cache step (Layer 2: 路径修复 + router hash) | 0.5 |
| Agent 3 | 加 Pre-warm step (Layer 3: 24 router import + 3 lazy 模型) | 1 |
| Agent 4 | pycache-vol volume mount (Layer 4: docker run mount + cache 备份) | 1 |
| Agent 5 | A/B 测试 + memory 沉淀 (5 次跑统计 cache hit rate) | 0.5 |
| **合计** | **5 commits / 1 周** | **3.5 人天** |

**预计 commits**: 5-7, 锚点范式第 35 次守恒.

---

**Anchor**: 锚点范式 W68 33 → **34** 单调上升, W68 第 3 批路线 B-2 路径 1 技术设计 0 production code 改动铁律完全守恒.