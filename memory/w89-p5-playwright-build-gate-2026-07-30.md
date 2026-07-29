# W89-P-5 Playwright build 后 a11y 健康检查 (派工 v6 §5 反馈 类 20.52 沉淀)

> **派工批次**: W89 第 1 批 P-5 路线 (主指挥协调范式第 N 次派工)
> **任务类型**: docs/memory/tests 范畴 (W89-P-3 接 CI 后, P-5 接本地 build 后健康检查)
> **base ref**: 5ace8015e (W87 第 1 批 grand closure, 锚点 337)
> **commit**: (pending) — 锚点 337 → 338 预期 (+1 实际据实)
> **worktree**: E:/agent-w89-p5-playwright-build (claude/w89-p5-playwright-build-gate)

## 1. 任务定位

W89-P-3 (Playwright CI 接入) + W89-P-5 (本地 build 后健康检查) 双轨:
- **W89-P-3**: CI 跑 Playwright (GitHub Actions)
- **W89-P-5**: 本地 developer 跑 `npm run build:a11y` (本任务)

本任务是 developer 自检工具, 不替代 CI; 但作为 build 后前置门禁, 比 CI 早发现 a11y regression。

## 2. 设计要点

### 2.1 npm scripts 设计

| Script | 命令 | 用途 |
|---|---|---|
| `prebuild` | `echo 'Pre-build hook placeholder (W89-P-5 build:a11y 链入口)'` | 占位 hook, 非 destructive |
| `build` | (保留原样) | CLAUDE.md 永久纪律: 唯一合法 build |
| `build:a11y` | `npm run build && npm run test:playwright:a11y -- --grep='health-check'` | build + a11y health-check 链 |
| `test:playwright:a11y` | `playwright test -c tests/visual/a11y/playwright.a11y.config.mjs` | 单跑 a11y (复用 W87-G-1 config) |

**派工 brief 字面 vs 实战修正**:
- 派工 brief 原 `prebuild` 用 `echo 'Pre-build hook placeholder'`
- 实战补 "(W89-P-5 build:a11y 链入口)" 注释, 让未来 grep `build:a11y` 能定位到 prebuild hook 出处
- 派工 brief `build:a11y` 引 `test:playwright:a11y` 但**未定义**该 script → 实战补 `test:playwright:a11y` 入口 (复用 W87-G-1 playwright.a11y.config.mjs)

### 2.2 health-check spec 设计

`web/tests/visual/a11y/health-check.spec.mjs` (新文件):

- **3 case**: `/login`, `/chat`, `/drive` (高曝光入口, 不重 W87-G-1 baseline 25 case)
- **硬断言**: `expect(criticalOrSerious).toEqual([])` (类 20.52 核心)
- **WARN**: moderate+minor violations 在 testInfo.annotations 列, 不 block
- **dev server 容错**: goto 失败不立即 fail, 让 axe.analyze() 暴露 dev server 假启动
- **额外 case**: 'dev server reachable at BASE_URL' 单独测连通性, 避免假绿
- **BASE_URL 默认**: `http://localhost:5173` (派工 brief 字面); 实测本仓库 dev 是 3000, 用 `process.env.BASE_URL` 兼容

### 2.3 prebuild hook 安全设计

e2e 守恒 (派工 v6 §1.2 实战):
- 必非 destructive (no `rm -rf` / `mv` / `del`)
- 必含 `echo` (placeholder 标识, 不静默执行)
- npm 生命周期: `prebuild` 自动在 `npm run build` 前跑, 但因仅 echo, 不破坏现有 build 流程

**实战边界**: vite-plugin-pwa / workbox 内部有 `prebuild` 钩子, npm 允许用户**追加**同 lifecycle script (后跑), 不会冲突。

### 2.4 e2e 设计

`tests/build_a11y/test_scripts.py` (新):

| Test | 守恒 |
|---|---|
| `test_build_a11y_script_exists` | scripts.build:a11y + test:playwright:a11y 必存在 + 链完整 |
| `test_health_check_spec_exists` | spec 文件必存在 + critical+serious 硬断言代码可见 |
| `test_prebuild_hook_safe` | prebuild 非 destructive + 含 echo |
| `test_existing_build_script_unchanged` | 已有 build script 必未被误改 (回归守恒) |

## 3. 派工 v6 §5 反馈 类 20.52 沉淀

> **类 20.52**: build 后必跑 a11y health-check, critical+serious 硬断言 = 0; moderate+minor 由主指挥拍板 (WARN, 不 block)

不入 doc string, 留主指挥后续 PR 补 CLAUDE.md 永久纪律章节。

**类 20.52 与既有类 20 关系**:
- 类 20.25 (W87-G-1): a11y 测试必先 baseline, 全绿是可疑信号 → baseline 派
- 类 20.52 (W89-P-5): build 后必跑 a11y health-check, critical+serious=0 → 健康检查派
- 双锚定: baseline 比对漂移 + health-check 硬断言 = 0, 互补不重叠

## 4. 留口 (W89+ 真跑派工)

| 留口 | 说明 |
|---|---|
| **真跑 health-check** | 本任务仅写 spec, 不真跑 (需 dev server + playwright npx install). 留 W89-P-6 真跑派工 |
| **CI 接入** | build:a11y 链 入 GitHub Actions, 失败 block merge. 留 W89-P-7 |
| **axe rule 文档** | 50+ axe rule 修复 SOP 沉淀 docs/axe-rules.md. 留 W89-P-8 |
| **moderate 调研** | 主指挥拍板 moderate violations 是否逐项修 vs 永久 WARN. 留 W89+ |
| **a11y 0 violation 终极目标** | critical+serious=0 是底线, moderate+minor 仍可能存在. 长期目标=0 |

## 5. 边界守恒 (本任务未动)

- `web/src/` — 0 改动
- `alembic/versions/` — 0 改动
- `nginx/` — 0 改动
- `docker/` — 0 改动
- `web/dist/` — 0 改动
- `commercial/` — 0 改动
- `web/package.json` 其它段 (deps / devDeps / 现有 scripts) — 0 改动
- `web/tests/visual/` 中其它文件 — 0 改动
- 已有 memory — 0 改动

**允许改 (5 项)**:
- `web/package.json` scripts 段 (+4 行: prebuild + build:a11y + test:playwright:a11y + reorder)
- `web/tests/visual/a11y/health-check.spec.mjs` (新)
- `tests/build_a11y/test_scripts.py` (新)
- `tests/build_a11y/__init__.py` (新)
- `docs/build-a11y-gate.md` (新)
- `memory/w89-p5-playwright-build-gate-2026-07-30.md` (本文件)

## 6. commit 预期

```
feat(w89): Playwright build 后 a11y 健康检查 (build:a11y + prebuild + health-check.spec) (W89-P-5)

CLAUDE.md 永久纪律 'npm run build 唯一合法' 强化:
- npm run build:a11y: build + a11y health-check 链
- prebuild hook 非 destructive (e2e 守恒)
- health-check.spec.mjs critical+serious=0 硬断言

派工 v6 §5 反馈 类 20.52 沉淀

锚点 +1 守恒 (337 → 338)
```

## 7. 派工前提铁律实战 5

1. **独立 worktree** (派工 v6 §1.1) — claude/w89-p5-playwright-build-gate, base 5ace8015e
2. **派工 brief 字面 vs 实战偏差据实上报** (类 20.13 实战) — `test:playwright:a11y` 入口补强
3. **派工 v6 §1.2 必真验证** — pytest 4 PASS 跑过
4. **派工 v6 §5 反馈** — 类 20.52 沉淀本任务
5. **0 production code 改动铁律** — 5 项改动 (scripts 段 + spec + tests + docs + memory), 0 production code (派工 brief 边界 100% 守恒)