# W89-P-13 Playwright 集成真验证 (2026-07-30)

> **锚点**: base `3a1ab24b3` (338) → tip +1 = **339 守恒**
> **分支**: `claude/w89-p13-integration`
> **worktree**: `E:\agent-w89-p13-integration` (独立, 派工纪律守恒)
> **0 production code**: ✅ 守恒 (仅 `tests/integration/` 新增 1 + `memory/` 新增 1)

---

## 0. 一句话结论

W89-P-3 + W89-P-5 的 3 件套**真跑了**, 不是只验证文件存在:

| 项 | 真跑结果 |
|---|---|
| `pre-commit run --all-files` | ✅ 真跑, 3 PASS + 2 FAIL (均 pre-existing) |
| a11y health-check (20 case) | ✅ 真跑, **14 PASS + 6 FAIL** (真 color-contrast 违规) |
| `npm run build` (build:a11y 前半) | ❌ **Rolldown panic**, 但 **pre-existing on main**, 与 P-5 无关 |
| 3 件套联动 | ⚠️ **2/3 在 main**, npm scripts 待 P-3/P-5 merge |

**据实上报 2 处派工 brief 错配** (类 20.13) + **1 处 pre-existing 阻塞** (留主指挥拍板)。

---

## 1. 派工 brief 错配据实上报 (类 20.13 实战)

### 1.1 错配 A — 3 件套只有 2/3 在 main

派工 brief 步骤 1 假设 `build:a11y` 已落地 main, 实测 main tip `3a1ab24b3`:

```
build:a11y = NOT EXISTS
test:playwright:a11y = NOT EXISTS
```

跨分支实测:

| 分支 | `test:playwright:a11y` | `build:a11y` |
|---|---|---|
| `main` (3a1ab24b3) | ❌ | ❌ |
| `claude/w89-p3-playwright-ci` (a765adf2f) | ✅ | ❌ |
| `claude/w89-p5-playwright-build-gate` (356740c44) | ✅ | ✅ |

**根因**: W89-P-3 / W89-P-5 **均未 merge 进 main** (`git branch --merged main` 无二者)。
派工 brief 说"W89-P-3 + W89-P-5 写了 workflow + npm scripts" — 写了是真的, 但写在**未合并的分支上**。

**处理**: 不擅自 merge (超出边界), 不伪造 PASS。e2e 用 `skipif` 守卫 —
main 合入 P-3/P-5 后**自动转 PASS**, 无需改测试。已用负向对照验证 (见 §4.2)。

### 1.2 错配 B — health-check 是 3 case 不是 50

派工 brief 步骤 3 写 "a11y health-check 跑通(50 case)"。
实测 `health-check.spec.mjs` 只定义 **3 页面** (01-login / 02-chat / 03-drive) + 1 个
`dev server reachable` 冒烟 = 4 test × 5 project = **20 case**。

50 case 应是把 `a11y-baseline.spec.mjs` (W87-G-1, 25 case) 混算了。
本任务按**实测 20 case** 报告, 不凑 50。

### 1.3 错配 C — dev server 端口是 3000 不是 5173

派工 brief 步骤 2 写 `curl http://localhost:5173`。实测 `web/vite.config.js:313` `port: 3000`。
P-5 的 spec 已注释此偏差并留 `BASE_URL` 环境变量兼容。
真跑用 `BASE_URL=http://localhost:3000` 通过。

---

## 2. `pre-commit run --all-files` 真跑结果

环境: `pre-commit 4.6.1` (已装, `/c/Users/pc/AppData/Local/Programs/Python/Python312/Scripts/pre-commit`)

```
Secret scan (gitleaks, W86-A-1)....................................Failed
Dockerfile base image must be pinned (no :latest)..................Failed
Alembic single chain discipline (CLAUDE.md §2.3)...................Passed
Python typing import check (CLAUDE.md 641 行纪律)..................Passed
web/dist must use hashed manifest (CLAUDE.md 永久纪律).............Passed
```

**3 PASS + 2 FAIL, 与派工 brief 预期 (3 PASS + 2 已知) 完全一致。**

2 个 FAIL 均 **pre-existing on main**, 非本任务引入:

1. **gitleaks-scan** (exit 2) — `[ERR ] gitleaks 未安装`。
   hook 本身工作正常 (正确检测缺 binary 并 fail loud, 非静默跳过)。
   装机留 **W87 第 2 批 A-1 真 binary 装机** (CLAUDE.md 已排期)。

2. **dockerfile-pinning** (exit 1) — 2 处 floating image:
   - `docker-compose.dev.yml:53` — `image: minio/minio` (无 tag)
   - `docker-compose.test.yml:61` — `image: minio/minio` (无 tag)
   属 `docker/` 边界, 本任务禁改 → 留主指挥拍板。

**类 20.21 实战守恒**: hook 测的是**合规**不是 hook 自身 —
gitleaks 缺 binary 时 fail loud 而非假绿, 正是 W86-D-1 的设计意图。

---

## 3. a11y health-check 真跑结果 (14 PASS + 6 FAIL)

### 3.1 环境准备

- backend: `microbubble-agent-app-1` Up (healthy), `curl localhost:8000/health` → **200** `{"status":"healthy"}`
- vite dev: `npx vite --port 3000` → **200** (VITE v8.1.5 ready in 390ms)
- playwright chromium: `chromium-1228` 已装
- P-5 worktree `npm ci`: 1140 packages, 27s

### 3.2 真跑

```bash
BASE_URL=http://localhost:3000 npx playwright test \
  -c tests/visual/a11y/playwright.a11y.config.mjs --grep='health-check' --reporter=list
```

结果: **20 tests, 14 passed, 6 failed (34.2s)**

| project | 01-login | 02-chat | 03-drive | dev-reachable |
|---|---|---|---|---|
| mobile-iphone14 | ✅ | ✅ | ✅ | ✅ |
| desktop-chrome | ❌ | ❌ | ❌ | ✅ |
| harmonyos-arkweb | ✅ | ✅ | ✅ | ✅ |
| mobile-comments | ✅ | ✅ | ✅ | ✅ |
| desktop-comments | ❌ | ❌ | ❌ | ✅ |

### 3.3 6 FAIL 归因

**全部 = `color-contrast` (impact: serious)**, 24 处实例 / 42 条 serious 记录, **0 条 critical**。

```
"id": "color-contrast"   × 24
"impact": "serious"      × 42   (critical = 0)
```

关键观察 (**类 20.25 "全绿是可疑信号" 反向实战**):
- **只有 desktop 两个 project 红, 3 个移动端 project 全绿** → 不是 spec 写错, 是桌面视口
  真实存在对比度不足。移动端 NutUI 栈配色不同故未触发。
- health-check 的 `critical+serious == 0` **硬门禁按设计生效了** —— 这正是 P-5 类 20.52 的意图,
  门禁红说明它**在干活**, 不是假绿。

**处理**: 属 `web/src/` 边界 (需改配色 token), 本任务禁改 → 留 W89-P-1 / W89-P-11
(`claude/w89-p1-a11y-violation-fix` + `claude/w89-p11-dark-accent` 已在派工中)。

---

## 4. `npm run build:a11y` 真跑 — Rolldown panic (pre-existing)

### 4.1 真跑

```bash
BASE_URL=http://localhost:3000 npm run build:a11y   # EXIT=1
```

前半 `npm run build` 即挂:

```
✓ 3488 modules transformed.
Rolldown panicked. This is a bug in Rolldown, not your code.
thread 'rolldown-worker' panicked at
  crates\rolldown\src\stages\generate_stage\compute_cross_chunk_links.rs:584:13:
Symbol "easeInOutCubic" in ".../element-plus/es/utils/easings.mjs" should belong to a chunk
✗ Build failed in 1.94s
```

### 4.2 归因: pre-existing, 与 P-5 无关 (3 条独立证据)

1. **P-5 commit 未碰构建链** — `git show --stat 356740c44` 只改 6 文件:
   `docs/build-a11y-gate.md` / `memory/...` / `tests/build_a11y/*` /
   `web/package.json` (**仅 scripts 段 +3 行**) / `web/tests/visual/a11y/health-check.spec.mjs`。
   **0 处** `vite.config.js` / `package-lock.json` / 依赖版本改动。

2. **纯 main 上直接复现** —
   ```bash
   cd /e/microbubble-agent/web && npx vite build   # EXIT=1, 同一 panic
   ```
   不经过 P-5 任何代码, panic 一模一样。

3. **已有独立分支在修** — `chore/w89-rag-rolldown-hotfix` commit `3bfe0cfc5`:
   "vite 8.x 降级到 7.3.6 解 rolldown 1.1.5 panic (easeInOutCubic + defaults_default +
   多个 element-plus symbol)"。当前 main 装的是 **vite 8.1.5**。

**结论**: `build:a11y` 的**后半 (a11y health-check) 已真跑通** (§3),
前半 (`npm run build`) 被**独立的 vite 8 / rolldown 缺陷**阻塞。
按派工纪律第 4 条 — **报告并暂停, 留主指挥拍板**, 不擅自降级 vite
(改 `package.json` deps + lock 超出本任务边界, 且 `3bfe0cfc5` 已在做)。

---

## 5. 3 件套联动验证

| 件 | 来源 | main 状态 | 真跑状态 |
|---|---|---|---|
| `.pre-commit-config.yaml` (5 hook) | W86-D-1 | ✅ 在 main | ✅ 真跑 3 PASS + 2 pre-existing FAIL |
| `web/tests/visual/a11y/playwright.a11y.config.mjs` | W87-G-1 / W89-P-3 | ✅ 在 main | ✅ 真跑 14 PASS + 6 真违规 FAIL |
| `web/package.json` `build:a11y` | W89-P-5 | ❌ 未 merge | ⚠️ 在 P-5 worktree 真跑, build 半程被 rolldown 阻塞 |

**联动链路真实性**: `build:a11y` → `npm run build` → `test:playwright:a11y` →
`playwright.a11y.config.mjs` → `health-check.spec.mjs`。
链路每一环都实测存在且可执行, 唯一断点是 rolldown panic (外部缺陷)。

---

## 6. e2e 加固: `tests/integration/test_build_a11y.py` (7 case)

设计要点:

- **`import json` 补齐** — 派工 brief 示例代码用了 `json.loads` 但漏 `import json`, 照抄必 `NameError`
  (**类 20.22 "不照抄建议版本" 实战**)。
- **`encoding="utf-8"` 显式** — Windows 默认 gbk 读 `package.json` 会炸。
- **`skipif` 守卫而非硬 FAIL** — 未 merge 的 npm script 用 skip 据实上报,
  合入后自动转 PASS, 无需回头改测试。
- **`test_integration_3_artefacts_status` 防"读取失败冒充缺失"** —
  先断言 `package.json` 可达且 `scripts` 段非空, 再 skip。避免路径写错时假装"3 件套不全"。
- **`test_build_a11y_chains_npm_run_build`** — 断言 `build:a11y` 走 `npm run build` 而非
  `vite build` 直跑 (CLAUDE.md 永久纪律 `5d2bcdfd` PWA 410 教训)。

跑测 (需 `SKIP_DB_SETUP=1`, DB 容器未映射 5432 到宿主):

```bash
SKIP_DB_SETUP=1 pytest tests/integration/test_build_a11y.py -v
# main ref:  3 passed, 4 skipped
# P-5 ref:   7 passed          ← 负向对照
```

**负向对照实测 (类 20.23)**: 把同一文件复制进 P-5 worktree 跑 → **7/7 PASS**。
证明 4 个 skip 是**真的因为 main 缺 script**, 而不是 skipif 条件写错导致的"永久跳过"。
探针文件已删除, 未污染 P-5 分支。

---

## 7. 派工 v6 §5 反馈 — 类 20.61 沉淀

> **类 20.61**: "Playwright 集成必含: 真跑 build:a11y + pre-commit + 3 件套联动"

展开 5 条子纪律 (本任务实战):

1. **集成验证必须真跑三方, 不能只 `assert path.exists()`** —
   文件存在 ≠ 能跑。本任务真跑才发现 build 挂在 rolldown、a11y 挂在 desktop 对比度。
2. **集成前必须实测每件套所在 ref** — 派工 brief 说"已写"可能是"写在未合并分支"。
   `git branch --merged main` + 跨分支 `git show <ref>:file` 是必查项 (类 20.32 延伸)。
3. **未 merge 的依赖用 skipif 守卫 + 负向对照, 不用硬 FAIL 也不用无条件 skip** —
   硬 FAIL 卡死收尾; 无条件 skip 是假绿。skipif + 在目标 ref 上验证能翻绿 = 两头都占。
4. **构建失败必先归因 pre-existing vs 本次引入** — 三证据法:
   ① 涉事 commit `--stat` 是否碰构建链 ② 纯 base ref 能否复现 ③ 是否已有独立修复分支。
   本任务三证齐全才敢判 pre-existing。
5. **a11y 门禁"部分红"比"全绿"更可信 (类 20.25 反向实战)** —
   5 project 里 3 绿 2 红, 且红的全集中在 desktop `color-contrast`, 说明 axe 真在扫真实 DOM。
   若 20/20 全绿, 反而要怀疑 spec 没真访问到页面。

---

## 8. 留 W89+ (主指挥拍板)

| # | 项 | 归属边界 | 建议 |
|---|---|---|---|
| 1 | **rolldown panic 阻塞 `npm run build`** | `web/package.json` deps + lock | merge `chore/w89-rag-rolldown-hotfix` (`3bfe0cfc5`, vite 8.1.5 → 7.3.6)。**优先级最高** — 挡住全部 build 链 |
| 2 | W89-P-3 / W89-P-5 未 merge | 主指挥合并流程 | merge 后本任务 e2e 自动 3P+4S → 7P |
| 3 | desktop `color-contrast` 24 处 serious | `web/src/` 配色 token | 已有 `claude/w89-p1-a11y-violation-fix` + `claude/w89-p11-dark-accent` 在派工中 |
| 4 | gitleaks binary 未装 | 装机 | W87 第 2 批 A-1 (已排期) |
| 5 | 2 处 floating `minio/minio` image | `docker-compose.{dev,test}.yml` | 钉死 tag (如 `RELEASE.2024-xx`), 小修 |

---

## 9. 边界复检

```
tests/integration/test_build_a11y.py            (新)
memory/w89-p13-integration-2026-07-30.md        (新)
```

**未动** (派工禁改清单全守恒):
`.pre-commit-config.yaml` / `web/package.json` / `web/tests/visual/a11y/playwright.a11y.config.mjs` /
`app/` / `web/src/` / `alembic/versions/` / `nginx/` / `docker/` / `web/dist/` / `commercial/`

**0 production code 铁律**: ✅ 守恒 (0 例外)
