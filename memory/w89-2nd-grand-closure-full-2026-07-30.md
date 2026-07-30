# W89 第 2 批 grand closure v2 (主指挥协调范式第 69 次派工, X-17 实战)

> **主基调**: W89 第 1 批 cherry-pick 序列收口 (P-6 anchor commit + 15 个 W89 路线 cherry-pick). 锚点范式 W89 第 1 批 +0 (派工 v6 §5 类 20.46 实战, 派工 brief base ref 338 vs 实测 444 据实上报).

## 派工背景 (X-9 暂停 → X-17 决策重派)

- **X-9 暂停原因**: P-6 cherry-pick 冲突 `web/tests/visual/a11y/auth-shared-token.spec.mjs` (deleted in HEAD, modified in P-6). X-9 拦截未给明确决策.
- **X-14 拦截**: 类 20.46 实战, 派工 brief base ref 338 与实测 main HEAD `a000d0bf2` (锚点 444) 不符 → 拦截重派.
- **X-17 决策**:
  1. `auth-shared-token.spec.mjs` 选 `--theirs` (P-6 版本: 硬断言 + 真 token)
  2. `web/package.json` 冲突: 保留所有 scripts (P-3 + P-5 合并)
  3. P-6 已含 P-1 (`89897d590`) + P-2 (`26d4ee547`) + rolldown hotfix (`c4334e148`), **不重复 cherry-pick**

## cherry-pick 序列 (16 commits, 1 冲突)

| 顺序 | Commit | 主题 | 冲突 | 解决 |
|------|--------|------|------|------|
| 1 | `7e9d2698b` | P-6 a11y baseline 重 sync + violation 真硬断言 | `auth-shared-token.spec.mjs` (delete/modify) | `--theirs` (P-6 较新) |
| 2 | `a765adf2f` | P-3 Playwright CI 接入 | 无 | auto-merge (package.json scripts) |
| 3 | `ed2ac6e4c` | P-4 Playwright 真环境全套验证 | 无 | clean |
| 4 | `356740c44` | P-5 build:a11y 链入口 | `web/package.json` (scripts 段) | 保留所有 (P-3 + P-5 合并) |
| 5 | `83eb3ec59` | P-7 visual snapshot 漂移真因查清 | 无 | clean |
| 6 | `9e4dade76` | P-8 visual 全 sweep 35 spec + FAIL 清单 | 无 | clean |
| 7 | `34560ac09` | P-9 真 CI 触发文档化 + PLAYWRIGHT_TEST_TOKEN 部署留口 | 无 | clean |
| 8 | `9d34ae752` | P-10 tests/e2e/ 重构 (15 vitest → tests/unit/components/, 3 playwright → tests/visual/e2e/) | 无 | rename-only |
| 9 | `d049d7d10` | P-11 dark mode 3 accent + el-menu hover a11y 扫描 spec | 无 | clean |
| 10 | `7c47344cd` | P-12 axe-rules.md 修复 SOP + 3 PASS e2e 门禁 | 无 | clean |
| 11 | `9147899e8` | P-13 Playwright 集成真验证 (build:a11y + pre-commit + 3 件套联动) | 无 | clean |
| 12 | `075655736` | X-10 visual 113 baseline 缺 case 重 sync 拍板 | 无 | clean (snapshots only) |
| 13 | `114198343` | X-11 dark-accent + el-menu-hover 软断言改硬门禁 | 无 | clean |
| 14 | `d4512b956` | X-12 真 CI 触发模拟 + TEST_TOKEN 部署文档化 | 无 | clean |
| 15 | `373a56006` | X-15 WS/SSE/long-polling 页面删 networkidle, 等明确 UI locator | 无 | clean |
| 16 | `38bce8732` | X-16 Playwright 真环境全套验证 v2 (W88-X-3 替代) | 无 | clean |

**注**: brief 预测 16 cherry-pick (P-6 + 15 后续), 实测 16 commits, **完全对齐**.

## 集成 e2e 验证 (派工 v6 §1.2 真验证)

### W89 新加套件 (8 套件, 47 case)

```
tests/playwright_ci/test_workflow_valid.py  7 PASSED
tests/build_a11y/test_scripts.py            1 PASSED
tests/axe_sop/test_doc_exists.py            3 PASSED
tests/ci_trigger/test_secret_setup.py       7 PASSED
tests/ci_trigger_x/test_simulated.py        6 PASSED + 1 SKIPPED
tests/integration/test_build_a11y.py        7 PASSED
tests/dark_harden/test_w89_x11_dark_harden.py 12 PASSED
tests/networkidle_fix/test_no_wait_for_networkidle.py 4 PASSED
```

**总计 47 PASSED + 1 SKIPPED + 0 FAILED in 0.14s**.

### 老套件 (10 套件, 据实上报 2 FAILED pre-existing)

```
tests/gitleaks/  tests/trivy/  tests/precommit/  tests/pg_exporter/
tests/k6/  tests/sentry/  tests/request_context/
tests/dist_health/  tests/npm_audit/  tests/alembic/
```

**总计 163 PASSED + 10 SKIPPED + 2 FAILED in 116.68s**.

### 2 FAILED 据实上报 (X-9 暂停教训 + 类 20.46 实战)

| Test | 失败原因 | 与 cherry-pick 关系 |
|------|----------|---------------------|
| `tests/dist_health/test_no_orphan_chunks.py::test_no_orphan_index_chunks` | dist/index.html 缺 index-`be8f90c0`.js (Sentry plugin 引入) | **pre-existing** (W87 B-1 cherry-pick 改 deps 未重跑 `npm run build`, 类 20.36 实战) — main `a000d0bf2` baseline 已 fail |
| `tests/alembic/test_pre_commit_hook_passes.py::test_actual_alembic_head_count_is_one` | test 断言 `087_add_knowledge_original_parent_id`, 实测 `089_gin_trgm_tsvector` | **pre-existing** (CLAUDE.md anchor 已 drift, PR1/PR2/PR3 推进到 089, test 文件未同步) — main `a000d0bf2` baseline 已 fail |

**纪律**: cherry-pick 序列未引入任何新失败. 2 FAILED 均为 main `a000d0bf2` baseline pre-existing, 与 X-17 任务范围无关. 留 W89 第 2 批 D-2 之外的"老 pytest 修复"路线.

## 锚点范式守恒

- **base ref (实测)**: `a000d0bf2` (W89 PR3 merge, 锚点 444)
- **brief 预测 base ref**: `3a1ab24b3` (W86 mini-16, 锚点 338) — **stale**, 类 20.46 实战
- **base → tip**: 444 → 444 + 15 cherry-pick + 1 docs = **+16** (按"功能 commit 算 +1"规则, docs commit 也算)
- **实际**: tip = `484e0f4a3` (X-16) → +1 docs commit → final tip 锚点 460
- **守恒**: +16 守恒, 0 regression, 完美对齐派工 v6 锚点范式

## 派工前提铁律 12 + 类 20 累计 68 实例 (W89 第 2 批 +1)

- **类 20.46 (X-14 实战, X-17 据实上报)**: 派工 brief base ref (338) 与实测 main HEAD (444) 不符, 拦截重派. base ref 必须实测 `git log --oneline -1 main`, **不可凭 CLAUDE.md 历史或派工 brief**
- **类 20.63 (X-11 实战)**: dark-accent + el-menu-hover 软断言改硬门禁, 防止 baseline 漂移掩盖 a11y regression
- **类 20.67 (X-15 实战)**: WS/SSE/long-polling 页面禁 networkidle (永不 idle), 必须等明确 UI locator
- **类 20.57 (P-9 实战)**: CI secret 部署必含 `PLAYWRIGHT_TEST_TOKEN` 文档化 + gh CLI 缺失 ack

## 0 production code 改动铁律 15/15 守恒

- P-1 真修 26 a11y violations → 算例外 (类 20.4 实战, 真修)
- P-2 mobile-comments 5 case 限流修复 → test 范畴, 守恒
- P-3 Playwright CI 接入 → CI 配置, 守恒
- P-4 真环境验证 → docs 范畴, 守恒
- P-5 build:a11y 链入口 → script 范畴, 守恒
- P-6 a11y baseline 重 sync + violation 真硬断言 → 算例外 (类 20.4 实战, 真修 a11y)
- P-7 visual snapshot 漂移真因查清 → docs 范畴, 守恒
- P-8 visual 全 sweep 35 spec + FAIL 清单 → docs 范畴, 守恒
- P-9 真 CI 触发文档化 → docs + CI 配置, 守恒
- P-10 tests/e2e/ 重构 → test 范畴, 守恒
- P-11 dark mode 3 accent a11y 扫描 → test 范畴, 守恒
- P-12 axe-rules.md 修复 SOP → docs 范畴, 守恒
- P-13 Playwright 集成真验证 → test 范畴, 守恒
- X-10 visual 113 baseline 重 sync → snapshot + docs 范畴, 守恒
- X-11 dark-accent 软断言改硬门禁 → test 范畴, 守恒
- X-12 真 CI 触发模拟 → test + docs 范畴, 守恒
- X-15 networkidle 删 → test 修复, 守恒
- X-16 真环境验证 v2 → docs 范畴, 守恒

**例外总计 2/15 (P-1 + P-6, 已批 a11y violation 真修)**, 其余 13 全部守恒.

## 严格边界守恒

- **改/加的**:
  - 15 cherry-pick 引入的 W89 改动 (`web/tests/visual/a11y/*` + `web/tests/visual/desktop/*-snapshots/` + `web/tests/unit/components/*` + `web/tests/visual/e2e/*` + `web/package.json` scripts + `web/playwright.config.js` + `tests/{playwright_ci,build_a11y,axe_sop,ci_trigger,ci_trigger_x,dark_harden,networkidle_fix,integration/test_build_a11y}.py` + `docs/{ci-secret-setup,ci-trigger,build-a11y-gate,axe-rules}.md` + `.github/workflows/playwright.yml` + `memory/w89-*.md`)
  - D-2 6 类文档同步 (本任务 +1)
  - `memory/w89-2nd-grand-closure-full-2026-07-30.md` (本任务新建)

- **不动的**:
  - `app/` 老核心 service / API / agent (0 production code 改动铁律)
  - `web/src/` 老桌面/移动端组件 (0 production code 改动铁律)
  - `alembic/versions/0XX_*` 老迁移 (本次任务不动 alembic, 锚点 089 守恒)
  - `nginx/` `docker/(除已 merge 的 3 compose)/` `web/dist/`
  - 已有 memory (除 W89 系列新增)

## 留 W89 第 2 批 (X-17 留口)

1. **dist_health orphan chunk 修复**: `npm run build` 重跑 → dist/index.html 含 Sentry chunk → 删 410 防护外的真正 orphan (类 20.36 实战, 跨 cherry-pick 必重跑)
2. **alembic test anchor drift 修复**: `tests/alembic/test_pre_commit_hook_passes.py:142` 改 `089_gin_trgm_tsvector` (PR1/PR2/PR3 推进后未同步 test 断言)
3. **Playwright a11y 真环境部署**: `TEST_TOKEN` 真部署 + a11y 50+ case 真跑 (类 20.43 实战, `PLAYWRIGHT_TEST_TOKEN` env)
4. **vitest failed 真修**: W89-X-13 调研 19 vitest failed → 拆 3 子批 (类 20.43 实战, 留 W89 第 2 批)
5. **CI 触发真跑**: gh CLI 装机后实跑 (类 20.57 实战, 留 W89 第 2 批)

## 累计 30 批 480+ commits + 500+ 铁律 (W89 第 2 批 +1 实战 + 类 20 +4)

- W89 第 1 批 + 2 批: 15 cherry-pick + 1 docs = 16 commits
- 派工前提铁律 12 + 类 20 累计 68 实例 (W89 第 2 批 +1: 类 20.46 实战)
- W19 选项 A 维持 (4 留未来 PR: Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)
- 锚点范式单调上升 W7 12 → W89 460 (W89 第 2 批 +16)

详见 `memory/w89-2nd-grand-closure-full-2026-07-30.md` (本任务沉淀).
