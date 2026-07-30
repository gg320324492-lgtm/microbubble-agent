# W91-X-19 真违规 axe rule 修 (2026-07-30)

> **一句话**: 真登录态 axe 实测 **72 处 color-contrast**(而非派工 brief 写的 6), **aria-command-name 实测 0 命中**(brief 写 ×1). 全部 72 处 light mode color-contrast 真修完, 注入验证 **72 → 0**. 锚点 +1 守恒.

- **分支**: `claude/w91-x19-axe-violation`
- **worktree**: `E:\agent-w91-x19-axe-violation`
- **base**: `f57206c7c` (main tip 实测, 类 20.32 双锚定)

---

## 0. 派工 brief 与实测的 4 处错配 (据实上报, 类 20.13)

派工 brief 说 "W90-X-14 据实: 真登录态跑出 7 violations(aria-command-name ×1 + color-contrast ×6)". 实测全部对不上:

| # | brief 说 | 实测 | 处置 |
|---|---|---|---|
| 1 | `aria-command-name ×1` | **0 命中** | 不修. W89-X-20 #4 (`9eac061cc`) 已给 `DesktopDriveView.vue` 3 个 icon-only toggle 补 `aria-label`, cherry-pick 后不复现. **不为凑 brief 数字造违规** |
| 2 | `color-contrast ×6` | **×72** | 全修 (见 §2) |
| 3 | brief 列 `FileCard.vue` / `TranslationPanel.vue` / `MeetingCreateDialog.vue` / `MeetingDetailView.vue` 共 7 处需加 `aria-label` | 这 4 个组件**均不在** 5 条被扫路由的渲染树里, axe 一处都没报 | 不动. 加 `aria-label` 属"看着该加"的推测式改动, 不是实测违规, 越 0-production-code 边界 |
| 4 | `W91-X-18` 分支 "含真登录态 + 暗 axe", 要求 cherry-pick | 该分支 tip **等于 main tip**, `main..` 0 commit | 跳过. 真登录态设施 (`injectAuth` + `TEST_TOKEN`) 已在 main 的 `axe-config.mjs:58` |

**brief 的 7 violations 从哪来**: 大概率读的是**匿名态** baseline. main 上 25 个 `__snapshots__/*.txt` 全部写着
`authed: no   redirected-to-login: yes` —— 扫的是 `/login` 登录页, 不是目标路由。这正是派工纪律 3 说的"假绿"。

---

## 1. 真跑基线 (真登录态, desktop-chrome, 5 路由)

`TEST_TOKEN` 走 `POST /api/v1/auth/login` (`xiaoqi_testbot`) 真取, 141 字符 JWT, 5 条路由全部 `TEST_TOKEN=yes` 且**未**被守卫打回 `/login`:

| 路由 | color-contrast | scrollable-region-focusable |
|---|---|---|
| `/chat` (01-chat) | ×26 | ×1 `.session-list` |
| `/drive` (02-drive) | ×9 | ×1 `.folder-tree` |
| `/chat` (03-mobile-chat) | ×26 | ×1 `.session-list` |
| `/tasks/trash` (04-task-trash) | ×4 | — |
| `/drive/file/1/comments` (05-file-comments) | ×7 | — |
| **合计** | **72** | **2** |

对照匿名态 baseline: 每页仅 `color-contrast ×3` —— **真登录态多出 69 处**。

`scrollable-region-focusable ×2` **源码已修好**(W89-X-20 #3 `28b69d3db` 给 `.session-list` 加 `role="list" tabindex="0"`、`.folder-tree` 加 `role="tree" tabindex="0"`, 已 cherry-pick 进本分支), 浏览器仍报是因为 nginx 里跑的是**旧 dist**(见 §4 build 阻断)。

---

## 2. 72 处 color-contrast 逐条修法

全部落在 **light mode** token。W89-X-20 只覆盖了 dark mode, light 是空白。

### 2.1 根因归类 (axe 实测色值 → 对比度)

| 实测组合 | 比值 | 命中处 |
|---|---|---|
| `#909399` on `#ffffff` | 3.08 | `.user-role` / `.drive-filter-bar-label` / `.drive-filter-stat` / `.drive-status-path` / `.drive-status-storage` |
| `#909399` on `#fef5f1` | 2.87 | `.sidebar-bottom-item > span` |
| `#909399` on `#fff8f5` | 2.93 | `.session-meta .time/.count` / `.session-preview` |
| `#909399` on `#fff0ed` | **2.78** (最差底) | 同上, 会话激活态 |
| `#909399` on `#f5f7fa` | 2.87 | `.empty-hint` |
| `#ff7a5c` on `#ffffff` | 2.56 | `#chat-jump-to-top` / `#thinking-mode-*` / 面包屑 `aria-current="page"` |
| `#ffffff` on `#ff7a5c` | 2.56 | `.is-active > span` / `.new-btn-text` |
| `#e6a23c` on `#fdf6ec` | **2.04** (全场最差) | task-trash 倒计时 |
| `#ff7a5c` on `#fff0ed` | 2.31 | `.dfcv-tab-btn.active` |
| `#c0c4cc` on `#ffffff` | 1.74 | `.dci-hint` |
| `#8e9097` on `#f5f7fa` | 2.97 | `.dfcv-empty .empty-hint` (`opacity:.75` **合成后**色) |

### 2.2 token 层修法 (`web/src/assets/variables.css`, `:root`)

| token | 原 → 新 | 最差场景比值 |
|---|---|---|
| `--color-text-secondary` | `#909399` → **`#6B6E76`** | on `#fff0ed` = **4.60** ✅ |
| `--color-primary-text` (新增) | — → **`#B84523`** | on `#fff0ed` = **4.84** ✅ |
| `--color-primary-strong` (新增) | — → **`#B84523`** | white on it = **5.37** ✅ |
| `--color-warning-text` (新增) | — → **`#8C5200`** | on `#fdf6ec` = **5.89** ✅ |

**关键设计**: **不动 `--color-primary` 本身**。`#FF7A5C` 是品牌主色, 作 bg/装饰完全合法, 只是当**文字**色永远 fail AA(白底 2.56)。新开 `--color-primary-text` / `--color-primary-strong` 两个语义变体, 视觉基调不变。

### 2.3 选择器层修法 (scoped style 治不了的)

有些违规来自组件 scoped style **直接写 `var(--color-primary)` 当文字色** —— 光提暗 token 无效, 必须非 scoped 全局覆盖(CLAUDE.md dark mode 跨组件纪律同款):

| 选择器 | 问题 | 修法 |
|---|---|---|
| `.mode-option.active` | `ThinkingModeSwitch.vue:112` scoped `color: var(--color-primary)` | → `--color-primary-text` |
| `.dfcv-tab-btn.active` | `DesktopFileCommentsView.vue:686` 同上 | → `--color-primary-text` |
| `.dci-hint` | `DesktopCommentInput.vue:311` 用 `--color-text-placeholder` (1.74) | → `--color-text-secondary` |
| `.dfcv-empty .empty-hint` | `opacity: 0.75` 把 `#6B6E76` **合成**成 `#8e9097` | `opacity: 1` + 实色 |
| `.trash-hint` / `.countdown-urgent` | `MobileTaskTrash.vue:283` 用 `--color-warning` | → `--color-warning-text` |
| `.el-menu-item.is-active` / `.new-btn-text` / `.el-button--primary` | 主色实底 + 白字 | bg → `--color-primary-strong` |

**`opacity` 陷阱**: axe 按**合成后**渲染色判对比度。`color` 过 AA 但父/自身带 `opacity` 仍会 fail —— 这次 `.dfcv-empty .empty-hint` 就是这么漏的(token 已改对, 第 1 轮验证仍红)。

---

## 3. 真跑验证 (派工 v6 §1.2)

因 build 阻断(§4), 用 `page.addStyleTag({ content: <W91-X-19 段> })` 注入到真登录态页面后重扫 —— 验证的是**同一段 CSS 源文本**:

| 路由 | 修前 color-contrast | 第 1 轮 | 第 2 轮(终态) |
|---|---|---|---|
| 01-chat | 26 | 1 | **0** |
| 02-drive | 9 | 0 | **0** |
| 03-mobile-chat | 26 | 1 | **0** |
| 04-task-trash | 4 | 0 | **0** |
| 05-file-comments | 7 | 3 | **0** |
| **合计** | **72** | 5 | **0** ✅ |

残余 `scrollable-region-focusable ×2` 是旧 dist 造成(源码已修, 见 §1)。

### e2e 门禁 `tests/axe_violation_x19/test_no_real_violation.py` — **17/17 PASS**

不依赖跑 playwright(dist 不可重建), 改为静态锁源码 + **自算 WCAG 对比度**(不信注释里的数字):
- 4 个 token 各自在**所有** axe 实测过的 6 种底色上重算 ≥ 4.5:1
- 10 个实测违规选择器逐个断言已被覆盖(参数化)
- 负向对照(类 20.23): 禁止 4 个已证明 fail 的色值回到 `color:` 值位
- dark 段完整性 + 层叠顺序(light 段在 dark 段后, 且不含 `[data-theme="dark"]`)

**负向对照实跑**: 把 `--color-text-secondary` 改回 `#909399` → 立即 `1 failed`; 恢复 → `17 passed`。门禁真能拦回退。

### 相邻套件

`tests/dark_harden/` + `tests/baseline_sync_x29/` **15 PASS**。
`tests/dark_x20/` **2 FAIL** —— **pre-existing**, 与本任务无关(把我的改动 `git stash` 掉后同样 2 failed): `subprocess` 找不到 `npx`(Windows `shell=False`) + gbk 解码中文输出崩。属 cherry-pick 带入的 X-20 测试自身 Windows 兼容缺陷, 据实上报不修。

---

## 4. build 阻断 (pre-existing, 据实上报)

`npm run build` 失败:
```
src/views/admin/RAGEvalPanel.vue (24:18):
  "Play" is not exported by "node_modules/@element-plus/icons-vue/dist/index.js"
```
- 引入者 `cb5c98498 [PR5 W91 +7] feat(pwa): RAGEvalPanel.vue ...`, **与本任务无关**
- 在**干净 main**(`E:/microbubble-agent`, 无我的改动)上跑 `npx vite build` **同样失败** —— 确认 pre-existing
- 影响: dist 无法重建 → nginx 里是旧资源 → 无法走"build + docker cp"完成端到端验证, 故改用 `addStyleTag` 注入
- **不修**: 越边界(`web/src/views/admin/` 不在本任务允许范围), 且属另一路线的 in-flight 工作

**建议主指挥另派**: `Play` icon 在当前 `@element-plus/icons-vue` 版本不存在, 应换 `VideoPlay` 或 `CaretRight`。这条**阻断所有** web dist 重建, 优先级高。

---

## 5. cherry-pick 收口

| commit | 来源 | 说明 |
|---|---|---|
| `fd2dd5812` | `7e9d2698b` W89-P-6 | baseline 重 sync + 硬断言. **1 冲突**: `auth-shared-token.spec.mjs` DU(main 无此文件, P-6 依赖未合并的 P-2) → 取 P-6 全量版 |
| `d7856a1b0` | `4c66c9644` W89-X-29 | 25 baseline .txt sync git |
| `e95fc0440` | `ce53379fa` W89-X-20 #6 | memory 沉淀 |
| `860227f35` | `1aae7859c` W89-P-11 | dark-accent + el-menu-hover spec |
| `ecad1772d` | `1f581e7c0` W89-X-11 | 软断言 → 硬门禁 |
| `30c81b081` | `81d8c84b2` X-20 #1 | dark color-contrast |
| `edb302cc1` | `afafb5f5b` X-20 #2 | CardList nested-interactive |
| `dfcd1d88c` | `28b69d3db` X-20 #3 | **scrollable-region-focusable** (本任务实测的 2 处) |
| `50738089a` | `9eac061cc` X-20 #4 | **aria-command-name** (本任务实测 0 命中的原因) |
| `d76a679d2` | `f01647cbf` X-20 #5 | dark-accent e2e |

派工 brief 只给了 X-20 的 tip `ce53379fa`(纯 memory doc), 真修在它**前面 5 个 commit** —— 只 pick tip 会一处代码都拿不到。

---

## 6. 派工 v6 §5 反馈 — 类 20 新增 4 条

### 类 20.100 "axe 真违规必修项目代码可修部分, 接受 EP 内部残余"
真登录态实测 72 处 color-contrast 全部是项目自有 token / scoped style, **可修率 100%**。`axe-config.mjs` 已 exclude `.el-popper` / `.el-overlay` / `[aria-hidden="true"]` 三类 EP 内部噪声(类 20.91), 剩下的没有"EP 内部不可修"这一类 —— 不要拿"EP 内部"当不修的借口, 先跑再分类。

### 类 20.101 "a11y baseline 必标 authed 字段, 匿名态 baseline 不可作为违规清单依据"
main 上 25 个 baseline 全是 `authed: no  redirected-to-login: yes`, 只扫到登录页 3 处。派工 brief 的 "7 violations" 即源于此。**baseline 文件必须把 `authed` / `redirected-to-login` 打进快照内容**(本仓库已做, 是好设计), 且**下游读 baseline 前必须先看这两个字段** —— 否则拿登录页的数字当全站结论。

### 类 20.102 "品牌主色不可直接当文字色, 应开 -text / -strong 语义变体"
`#FF7A5C` 白底 2.56, 任何 `color: var(--color-primary)` 都必 fail AA。正解不是改主色(整站视觉全变), 而是新增 `--color-primary-text`(深色, 给文字) + `--color-primary-strong`(深色实底, 给白字压)。**6 套主题都该配齐这两个变体**(本次只补了默认橙, 其余 5 套留口 W92+)。

### 类 20.103 "axe 按 opacity 合成后颜色判对比度"
`color` 声明过 AA, 但自身或祖先带 `opacity < 1` 时 axe 仍报 fail —— 它取的是**合成后**像素色。本次 `.dfcv-empty .empty-hint`(`opacity:.75`)在 token 已改对的情况下第 1 轮验证仍红。**修 color-contrast 必须同时 grep 相关选择器的 `opacity`**。

---

## 7. 边界复检

改动文件(cherry-pick 引入的 43 个不计):
- `web/src/assets/variables.css` — 只**追加** W91-X-19 段(1 处 token 值改 + 3 个新 token + 精准选择器), 未删改任何既有规则
- `tests/axe_violation_x19/test_no_real_violation.py` — 新增
- `memory/w91-x19-axe-violation-2026-07-30.md` — 新增(本文件)

未动: `app/` / `alembic/` / `nginx/` / `docker/` / `commercial/` / 其它业务代码。
`web/package-lock.json` 被 `npm install` 改动 → 已 `git checkout` 还原。

**锚点 +1 守恒** (491 → 492)。
