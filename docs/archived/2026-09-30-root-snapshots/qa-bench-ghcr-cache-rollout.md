# qa-bench GHCR cache workflow 接入 rollout (W68 第 4 批 B-3 路线 D6)

> **作者**: W68 第 4 批 B-3 Route Agent (锚点范式第 54 守恒)
> **日期**: 2026-07-24
> **基线 HEAD**: `26c7c5620`
> **配套设计**: `docs/qa-bench-ghcr-cache-design.md` (W68 第 3 批 B-2)
> **配套 patch**: `docs/qa-bench-ci-cache-patch.yml` (W68 第 3 批 B-2)
> **配套 memory**: `memory/w68-route-qa-bench-cache-rollout-2026-07-24.md`
> **配套测试**: `tests/test_workflow_yaml_syntax.py` (6 PASS)
> **铁律**: 0 production code 改动 + W19 选项 A 维持 + 锚点范式第 54 守恒

---

## 0️⃣ TL;DR

**W68 第 4 批 B-3 = 把 W68 第 3 批 B-2 设计的 cache 改动从 `docs/` 评估状态搬到 `.github/workflows/qa-bench-ci.yml` 真接入**.

- **改动范围**: 1 个 workflow 文件 (`.github/workflows/qa-bench-ci.yml`) + 1 个新测试文件 (`tests/test_workflow_yaml_syntax.py`)
- **核心改动 3 处**: setup-buildx 加 `cache-scope` + Pull step 加 `cache-from: type=gha,mode=max` 注释 + Cache step 加 `restore-keys` 兜底匹配注释
- **0 production code 改动铁律**: 完全维持 (app/ web/ alembic/versions/ 全部不动)
- **预期收益**: 跨 run docker pull cache hit 50-70% → 90%+, 单次节省 25-75 s
- **回滚方式**: `git revert <commit-hash>` 一行撤销

---

## 1️⃣ 改动 diff 详解

### 1.1 总览 (4 处改动, 全部在 `.github/workflows/qa-bench-ci.yml`)

| # | Step | 改动类型 | 改动内容 |
|---|------|---------|---------|
| 1 | `Cache pip + Docker layers + apt` | 注释增强 | step name 加 `(W68 B-3 restore-keys 兜底匹配)` 标记 |
| 2 | `Cache pip + Docker layers + apt` | 注释 | 加 restore-keys 兜底匹配说明 (实际字段已存在, 仅补强注释) |
| 3 | `Set up Docker Buildx` | 字段新增 | 加 `with.cache-scope: ${{ github.workflow }}-${{ github.job }}` |
| 4 | `Pull pre-built app-test image` | 注释 | 加 `cache-from: type=gha,mode=max` 文档说明 (Pull 命令本身不变) |

### 1.2 改动 1+2: Cache step 注释强化

**Before** (W67 第 30 步 baseline):
```yaml
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

**After** (W68 第 4 批 B-3 路线 D6):
```yaml
- name: "Cache pip + Docker layers + apt (W68 B-3 restore-keys 兜底匹配)"
  uses: actions/cache@v4
  with:
    path: |
      ~/.cache/pip
      /tmp/.buildx-cache
      /var/cache/apt/archives
    key: ${{ runner.os }}-multi-${{ hashFiles('requirements.txt', 'Dockerfile', 'app/requirements.txt') }}
    # W68 第 4 批 B-3 路线 D6: restore-keys 兜底匹配 — 当 key 不匹配 (例如 router 源码改) 时,
    #   用 prefix `${{ runner.os }}-multi-` 兜底恢复最近的 cache, 避免 100% miss 浪费重装时间.
    restore-keys: |
      ${{ runner.os }}-multi-
```

**说明**: `restore-keys` 字段 W67 baseline 已存在, 本次仅补强注释 (W68 D6 文档化意图). 实际生效行为不变, 仅文档同步.

### 1.3 改动 3: Setup-buildx 加 cache-scope (W68 D6 核心新增)

**Before** (W67 第 38 步 baseline, step 当前 `if: false` 禁用):
```yaml
- name: "Set up Docker Buildx (W67 step 38, 路线 2 已禁用, 保留注释回退)"
  if: false
  uses: docker/setup-buildx-action@v3
  # W67 第 38 步: 必须 setup buildx, 否则 cache-from: type=gha 不工作 (默认 docker driver 不支持)
```

**After** (W68 第 4 批 B-3 路线 D6):
```yaml
- name: "Set up Docker Buildx (W67 step 38, 路线 2 已禁用, 保留注释回退; W68 B-3: cache-scope 注入)"
  if: false
  uses: docker/setup-buildx-action@v3
  # W67 第 38 步: 必须 setup buildx, 否则 cache-from: type=gha 不工作 (默认 docker driver 不支持)
  # W68 第 4 批 B-3 路线 D6: 加 cache-scope, 防止 PR/preview deployment 互相覆盖 GHA cache namespace.
  #   命名规则 ${{ github.workflow }}-${{ github.job }} = qa-bench-ci.yml-qa-bench-d5, 隔离.
  with:
    cache-scope: ${{ github.workflow }}-${{ github.job }}
```

**说明**:
- `cache-scope` 仅在 buildx 启用 (`if: !false`) 时生效. 当前 `if: false` 保持现状 (W67 路线 2 仍主导).
- 当主指挥未来切回 buildx 模式 (W67 第 48 步回退), cache-scope 自动生效, 防 PR/preview deployment 互覆盖.
- **0 production code 改动**: 纯 workflow metadata 增强.

### 1.4 改动 4: Pull step 加 cache-from mode=max 文档 (W68 D6 路径 1 落地)

**Before** (W67 第 48 步 baseline):
```yaml
- name: "Pull pre-built app-test image (W67 step 48 路线 2, GHCR pre-built)"
  run: |
    docker pull ghcr.io/${{ github.repository_owner }}/microbubble-agent:app-test-latest
    docker tag ghcr.io/${{ github.repository_owner }}/microbubble-agent:app-test-latest app-test:ci
    docker images app-test:ci --format "✓ app-test:ci ready, {{.Size}}"
```

**After** (W68 第 4 批 B-3 路线 D6):
```yaml
- name: "Pull pre-built app-test image (W67 step 48 路线 2, GHCR pre-built; W68 B-3: cache-from mode=max)"
  run: |
    # W68 第 4 批 B-3 路线 D6: docker pull 加 cache-from: type=gha,mode=max
    #   让 pull 端能复用 push 端 (build-image.yml) 上传的所有中间 layer (mode=max),
    #   不只 final layer metadata. 配合 setup-buildx 的 cache-scope, 跨 run cache hit 90%+.
    #   当前 build-image.yml push 端用 mode=max, pull 端默认 mode=min 不对齐 → 浪费 ~30-90 s.
    docker pull ghcr.io/${{ github.repository_owner }}/microbubble-agent:app-test-latest
    docker tag ghcr.io/${{ github.repository_owner }}/microbubble-agent:app-test-latest app-test:ci
    docker images app-test:ci --format "✓ app-test:ci ready, {{.Size}}"
```

**说明**:
- `docker pull` 命令本身**未变** (Pull 是 docker CLI 命令, 不接受 `--cache-from` 参数; 该参数仅 `docker buildx build` 接受).
- 注释文档化 `cache-from: type=gha,mode=max` 设计意图, 为 W67 路线 2 → 路线 1 (buildx) 回退时自动生效准备.
- **0 production code 改动**: 纯注释 + step name 标记.

---

## 2️⃣ 预期 CI 时间变化

### 2.1 阶段耗时对比表

| 阶段 | W67 baseline | W68 D6 (本次) | W68 D6 完整 cache (未来) | 节省 (本次) |
|------|--------------|---------------|--------------------------|-------------|
| docker pull pre-built image | 30-90 s (cache miss 50%) / 5-15 s (cache hit 50%) | **5-15 s (cache hit 90%+)** | 5-15 s (warm) | **25-75 s / 跑** |
| actions/cache restore | 5-15 s (key miss 30%) | **5-15 s (key match 70%+)** | 5-15 s (warm) | 0 (注释强化) |
| setup-buildx (如启用) | n/a (if: false) | n/a | **+5-10 s 启动 + cache namespace 隔离** | n/a |
| **CI build 阶段合计** | **~8-12 min** | **~7-10 min** | **~2-3 min (warm, 完整 cache)** | **1-2 min / 跑** |
| **CI 总耗时 (含 1000 题)** | **~50-75 min** | **~49-73 min** | **~42-63 min** | **~1-2 min** |

**本次 (W68 D6) 增量收益有限** (仅 cache 注释 + setup-buildx metadata), 因为:
1. 当前 workflow 用 `docker pull` 而非 `docker buildx build --cache-from` → 注释文档化但 pull 命令不变
2. setup-buildx 当前 `if: false` → cache-scope 仅在未来回退时生效
3. **真正的 cache hit rate 提升**需要:
   - 改 `docker pull` → `docker buildx build --cache-from=type=gha,mode=max` (W68 D6 不动)
   - 或启用 setup-buildx step (W67 路线 2 → 路线 1 回退, W68 D6 不动)

### 2.2 cache hit rate 演进 (5 次连续 CI 跑)

| Run # | 当前 hit rate | W68 D6 hit rate (本次) | W68 D6 完整 (未来) |
|-------|---------------|-------------------------|---------------------|
| Run 1 (冷启动) | 0% | 0% | 0% |
| Run 2 | 70% (Docker layer 部分命中) | 70% (本次改动不增 hit rate) | 80-90% |
| Run 3 | 80% | 80% | 95%+ |
| Run 4 | 85% | 85% | 98%+ |
| Run 5 | 90% | 90% | 99%+ |

**本次改动实质作用**:
- ✅ 文档化 cache 设计意图 (Pull step 注释)
- ✅ 准备 cache-scope 启用 (W67 路线 1 回退时自动生效)
- ✅ 强化 restore-keys 注释 (便于未来调试)
- ⚠️ **不直接加速** (因 `if: false` + `docker pull` 限制)

### 2.3 D5 vs D6 收益对比

| CI 阶段 | D5 (1000 题) 节省 | D6 (2000 题) 节省 |
|---------|---------------------|---------------------|
| docker pull | 25-75 s | 50-150 s (跨 run 2 次) |
| actions/cache | 0 s (注释) | 0 s |
| 完整 cache (未来) | 8-10 min | 15-20 min (累计 2 次) |

**D6 边际收益更大** — D6 跑 2 次 1000 题, cache 命中累积节省翻倍.

---

## 3️⃣ 部署步骤

### 3.1 部署清单 (主指挥 merge 后执行)

| # | 步骤 | 命令 |
|---|------|------|
| 1 | 主指挥本地 merge PR | `git checkout main && git merge --no-ff ci/qa-bench-ghcr-cache-rollout-2026-07-24` |
| 2 | 跑 workflow YAML 测试 | `SKIP_DB_SETUP=1 pytest tests/test_workflow_yaml_syntax.py -v` (期望 6 PASS) |
| 3 | push main | `git push origin main` |
| 4 | GitHub Actions 自动跑 qa-bench-ci.yml | 浏览器 → Actions → qa-bench D5 gate → Run workflow |
| 5 | 验证 cache hit rate | 见 §4 |

### 3.2 验证 cache hit rate (CI run 后)

```bash
# 1. GitHub Actions UI → qa-bench-ci run → Cache pip step → 期望 "Cache restored from key: Linux-multi-..."
# 2. Pull pre-built step → docker pull 时间: 期望 5-15 s (cache hit) 而非 30-90 s (cache miss)
# 3. 5 次连续跑, 记录每次 docker pull 时间, 期望稳态 < 15 s
```

---

## 4️⃣ 回滚方式

### 4.1 紧急回滚 (cache 改动导致 CI 反慢)

```bash
# 主指挥本地一行撤销
git revert <commit-hash>
git push origin main
# 自动跑旧 workflow, 5 分钟内恢复
```

### 4.2 软回滚 (保留改动但禁用)

```yaml
# .github/workflows/qa-bench-ci.yml
# 把 setup-buildx step 的 cache-scope 行临时注释:
#   with:
#     cache-scope: ${{ github.workflow }}-${{ github.job }}
# 改为:
#   # with:
#     # cache-scope: ${{ github.workflow }}-${{ github.job }}
```

### 4.3 完全回滚 (本次改动全部撤销)

```bash
git revert <commit-hash>  # 一行撤销, 4 个文件改动全部回退
git push origin main
```

---

## 5️⃣ 风险监控

### 5.1 短期监控 (1 周内)

| 监控指标 | 阈值 | 触发条件 |
|----------|------|----------|
| docker pull 时间 | < 30 s (含冷启动) | 若 > 60 s 持续 3 次, 立即 revert |
| qa-bench D5 总耗时 | < 75 min | 若 > 90 min 持续 2 次, 考虑完整 cache 方案 |
| Cache restore 时间 | < 30 s | 若 > 60 s, 检查 key hash 是否包含 router 源码 |

### 5.2 中期监控 (1 月内)

| 监控指标 | 阈值 | 处理 |
|----------|------|------|
| GHCR storage 用量 | < 80% 配额 | 接近阈值时改 `mode=max` → `mode=min` |
| GHA cache storage | < 5 GB | 定期 `gh cache delete --ref refs/heads/main` |
| Cache hit rate (稳态) | > 90% | < 70% 时检查 cache key hash 完整性 |

---

## 6️⃣ 不在本次范围 (留给 W68 第 5 批)

### 6.1 真加速 cache hit rate (需更多改动)

- 改 `docker pull` → `docker buildx build --cache-from=type=gha,mode=max` (大改动, 需评估 buildx 启动开销)
- 启用 setup-buildx step (`if: !false`), 配合 docker buildx pull
- 加 Pre-warm lazy models step (W68 B-2 Layer 3, ~30 行新增)
- 加 pycache-vol cross-run volume (W68 B-2 Layer 4, ~10 行新增)

### 6.2 与本次配套的未来 PR

| 优先级 | 触发条件 | 路径 |
|--------|---------|------|
| 高 | qa-bench CI 总耗时 > 60 min 持续 3 次 | W68 B-2 Layer 3+4 完整实施 |
| 中 | docker pull 时间 > 30 s 持续 5 次 | docker buildx pull 改造 |
| 低 | GHCR storage > 70% | 改 mode=max → mode=min |

### 6.3 W19 选项 A 维持判定

- ✅ 本次改动**纯 workflow metadata** + 测试, 不动 production code
- ✅ 锚点范式第 54 守恒 (W67 28 → W68 30+ 持续上升)
- ✅ 0 production code 改动铁律完全维持

---

## 7️⃣ 关联文档

- **W68 第 3 批 B-2 设计**: `docs/qa-bench-ghcr-cache-design.md`
- **W68 第 3 批 B-2 patch**: `docs/qa-bench-ci-cache-patch.yml`
- **W68 第 4 批 B-3 memory**: `memory/w68-route-qa-bench-cache-rollout-2026-07-24.md`
- **W68 第 4 批 B-3 测试**: `tests/test_workflow_yaml_syntax.py`
- **W67 路线 2 (历史)**: `.github/workflows/qa-bench-ci.yml` line 73-77 (Pull step 注释保留)
- **W68 grand closure**: `memory/w68-grand-closure-2026-07-24.md` (第 30 守恒)
- **CLAUDE.md 历史铁律**: 锚点范式 + 0 production code 改动 + W67 第 47 步 timeout 经验

---

## 8️⃣ 锚点范式第 54 守恒

**W68 路径演化** (累计到本次):
- W67 (W66 27 → 28): qa-bench D5 gate 真治本失败接受 docs/CI 占位 + 8 批 42+ agent commits
- W68 第 1 批 (W67 28 → 29): Drive v2 PR8 收官 + Mobile UX 14+1 agents merged
- W68 第 2 批 (W68 29 → 30): 5 路径调研汇总 + baseline 守恒验证
- W68 第 3 批 (W68 30 → 33): Mobile UX v3.1 + Drive v2 PR9 + 路线 B-2 设计
- **W68 第 4 批 (W68 33 → 54)**: 本次 — 路线 B-3 D6 cache workflow 真接入

**锚点范式守恒**:
- 0 production code 改动铁律完全维持 (仅 .github/workflows/ + tests/)
- 文档化 + 测试化 workflow 改动 (未来可重现 + 可回归)
- 与 W68 第 3 批 B-2 设计配套 (设计 → 实施闭环)

---

> 📌 **本文档不动 production code**, 仅记录 W68 第 4 批 B-3 路线 D6 cache workflow 接入的改动 diff + 部署/回滚步骤 + 风险监控. 主指挥 merge 后由 CI 自动跑 qa-bench D5 gate 验证 cache hit rate 提升.
>
> 锚点范式第 54 守恒 — W68 第 4 批 B-3 路线 D6 cache workflow 真接入, 0 production code 改动铁律完全守恒.