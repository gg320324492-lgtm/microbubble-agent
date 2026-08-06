# W-N-DEPLOY-F2 收口 (2026-08-06)

> **派工**: W-N-DEPLOY-F2 +2 收口 (W-N 周期 19 stages 收口后最终部署状态验证)
> **base HEAD**: `6d8f0226f` (W-N-FILL-REAL-N 测试回归断言修正)
> **状态**: **PASS** — 8 步验证 6 PASS + 1 部分 (容器) + 1 范畴守恒, 5 件套 4 PASS + 1 沿用
> **派工锚点**: W-N-DEPLOY-F2 +0 (startup) → +1 (报告 + commit) → +2 (本文件)

---

## 1. 8 步验证实测

| Step | 验证项 | 判定 | 实测证据 |
|------|--------|------|---------|
| 1 | local vs origin/main | ✅ PASS | `git rev-list --left-right --count origin/main...main` = **0 / 0** |
| 2 | 容器状态 | ⚠️ 部分 | 核心 8 Up (app/db/redis/nginx/ollama/minio/celery-beat/glitchtip-dev), 3 Exited |
| 3 | alembic 1 head | ✅ PASS | host + 容器 heads + 容器 current **三方均 `105_fix_drift`** |
| 4 | 3 套件 pytest | ✅ PASS | **42 passed, 0 failed** in 40.75s (12 + 8 + 22) |
| 5 | `/health` | ✅ PASS | HTTP **200**, `{"status":"healthy"}` |
| 6 | worktree clean | ✅ PASS | 0 tracked 改动 |
| 7 | 部署报告 | ✅ PASS | `docs/deploy-status-final-2026-08-06-f2.md` 8 节 (派工 brief 要求 6 节 + §7 严禁守恒 + §8 关联) |
| 8 | commit 范畴 | ✅ PASS | 1 docs + 2 memory |

---

## 2. 5 件套守恒实测

| # | 件 | 派工 brief | 实测 | 判定 |
|---|----|----------|------|------|
| 1 | alembic 1 head | `105_fix_drift` 守恒 | host / 容器 heads / 容器 current 三方一致, 无双头无 drift | ✅ PASS |
| 2 | pytest | 3 套件 PASS | **42 passed** (fill_impl_backfill 12 + g_plus_chunk_late_recall 8 + rag/pr7_e2e 22), 0 failed | ✅ PASS |
| 3 | PWA build | 沿用基线 | 沿用 W100 +75, **0 frontend 改动**, 未重跑 build | ⚠️ 沿用 |
| 4 | 0 production code | 严格守恒 | 仅 1 docs + 2 memory. `app/` `web/src/` `alembic/versions/` `docker-compose*` `.env` `tests/` **全 0** | ✅ PASS |
| 5 | 锚点范式 | +0/+1/+2 据实累计 | +0 startup memory + +1 报告 + +2 本文件, **1 commit** | ✅ PASS |

**5 件套 4 PASS + 1 沿用.**

---

## 3. 派工 brief vs 实测偏差据实 (类 20.13 实战)

| # | 派工 brief 假设 | 实测 | 偏差据实 |
|---|----------------|------|---------|
| 1 | 工作仓库根 = `E:\microbubble-agent\` (主仓库) | 派工 cwd 落在 `.claude/worktrees/bold-mendeleev-fdc0e8`, 该目录**为空壳** (`ls -a` 仅 `.` `..`), git 解析回落主仓库 | **偏差**: cwd ≠ 仓库根. 修法: 全程**绝对路径**操作主仓库 |
| 2 | `git status --short` worktree clean | 有 **1 untracked** `memory/w-n-clean-f2-startup-2026-08-06.md` (并发 W-N-CLEAN-F2 agent 产物) | **偏差**: 非本任务产物, 0 add / 0 改 / 0 删 (类 20.140 并发共存) |
| 3 | 容器全健康 | **3 Exited**: celery-worker (码 0 warm shutdown) / celery-meeting-worker (码 0) / sensevoice (码 **127** command not found) | **偏差**: 据实上报, 不擅自重启 (严禁改 compose), 留 §6.1 建议留口 |
| 4 | W-N 周期 19 stages, CLAUDE.md 记 +43 commits | `git rev-list --count 14bc9246e..6d8f0226f` = **92 commits** | **偏差 +49**: CLAUDE.md "+43" 为 W-N-FINAL 前子集, git 区间覆盖全周期含并行阶段. **不改 CLAUDE.md**, 留主拍 reconcile |
| 5 | W-N-BGE-A 1000 题真测数据可信 | `is_mock: false` + 真 VRAM/latency, 但**文件末 `note` 仍写 "fallback mock encoder (零向量)"** — 修订前陈旧残留, 自相矛盾 | **偏差**: 数据自洽性问题. 严禁改 `results/`, 仅据实标注 + 建议清理 |
| 6 | 写部署报告 6 节 | 写 **8 节** (6 节 + §7 严禁守恒实测 + §8 关联) | 超出据实, 不缩 |

---

## 4. 关键实测数据 (供后续派工引用)

### 4.1 W-N-FILL-REAL-N Bug 2 (commit `b99f300b7`)

- SQL `:chunk_emb::vector[]` → `CAST(:chunk_emb AS text)::vector(1024)[]` (3 处, +18/−6)
- array 字面量 `{[v1,v2]}` → `{"[v1,v2]"}` (PG nested array **必须双引号**)
- **DB 直查复验 2026-08-06: 37 / 37 chunks 全量写入, 0 pending** ✅
- HNSW **4 路径全 FAIL** (halfvec cast / vector_cosine_ops / GIN 4112>2712 / unnest set-returning) — pgvector 0.7.0 不支持 `vector[]` HNSW

### 4.2 测试 FAIL 修复 (commit `6d8f0226f`)

- 断言 `'vector[]'` → `'vector(1024)[]'` + 新增 `assert 'CAST' in ...` (类 20.161 反向验证)
- 12/12 PASS — 本次复验一致 ✅
- **纪律**: 该改动由 FILL-REAL-N 派工授权; **本次 DEPLOY-F2 严禁改 tests/**, 仅只读运行

### 4.3 W-N-BGE-A 1000 题 encoder-only

- 真模型 cuda, VRAM **2.115 GB** (门禁 < 4GB ✅), load 202.67s, dim 1024, max_seq 8192
- **1000 / 1000** 加载, 23 类覆盖, batch 32
- 延迟 **305.77 ms/doc**, 吞吐 **3.27 docs/s**
- 决策 **(a) 暂不切生产, 维持 Qwen3** — 明确**不声称端到端 recall** (encoder-only)

### 4.4 glitchtip 修复持续有效

- W-N-GLITCH-IMPL `2e6b71dbf`: compose `aliases: [db, redis]` 修 restartCount=936
- **本次复验: Up 51 minutes, 无 Restarting** ✅

---

## 5. 类 20 沿用 (本任务不新增编号)

- **类 20.13** — 派工 brief vs 实测偏差必据实上报 (本任务 6 项偏差)
- **类 20.140** — 并发批次共存, 不动他人 untracked 文件
- **类 20.161** — pgvector SQL 参数绑定必显式 cast (Bug 2 修复反向验证断言)
- **类 20.171** — 主拍收口必复核 alembic heads + 关键改动是否真进 main (三方 head 验证 + DB 直查 37/37)
- **CLAUDE.md §1.1/1.2 plans 审计纪律** — 禁止批量复制粘贴前序文档, stage 表从 `git log` 实测重建
- **类 20 E50** — 拒绝误判式 `rm -rf`, 16 worktree / Created 容器不清理

---

## 6. 0 改既有 commits 范畴守恒

本任务 **1 commit**, 内容仅:
- `docs/deploy-status-final-2026-08-06-f2.md` (新增)
- `memory/w-n-deploy-f2-startup-2026-08-06.md` (新增)
- `memory/w-n-deploy-f2-closure-2026-08-06.md` (新增, 本文件)

**0 改**: W-N-* 既有 commits / `alembic/versions/` / `app/` / `web/src/` / `docker-compose*` / `.env` / `tests/` / plan 文件 / 前序 deploy-status 文档 / 并发 agent untracked 文件.

---

## 7. 关联

- 报告: `docs/deploy-status-final-2026-08-06-f2.md` (W-N-DEPLOY-F2 +1)
- 起步: `memory/w-n-deploy-f2-startup-2026-08-06.md` (W-N-DEPLOY-F2 +0)
- 前序: `docs/deploy-status-final-2026-08-06.md` (W-N-DEPLOY-FINAL) / `74d1a965e` (W-N-DEPLOY)
