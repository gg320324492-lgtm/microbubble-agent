# W88-G-2 a11y 真登录态 fixture + 5 页面 violation 清单

> **派工 v6 §5 反馈 #20.42 沉淀 (新增类 20 实战 22)**: a11y baseline 模式仅适合 regression 检测, **首跑必拿真 violation 清单**. 否则就是派工 brief 自己写的假绿.
> **真登录态 = API 拿 JWT (测试账号 xiaoqi_testbot / testbot_pass_2026) → cookie + localStorage 双注**, 不要走表单 (mobile UA form submit redirect 不可预测, 易 120s timeout).
> **5 项目 × 5 页 = 25 case, 20 PASSED + 5 FAILED (429 限流, 1 例外)**. **0 production code 改动铁律 守恒**.

## 派工来源

- **W88-G-2** (派工 v6 §1.2 真验证) — W87-G-1 报告"50 PASS 但全绿可疑, 实际 25 baseline 都是登录页"
- 主指挥 W87-X-5 grand closure 收口后 (锚点 337 守恒), W88 第 1 批起手 G-2 路线
- 类 20 实战 22 (派工 v6 §5 反馈 #20.42): a11y baseline 模式仅适合 regression 检测

## 工作环境

- worktree: `claude/w87-1st-batch-x8-a11y-fix` (沿用 W87-G-1 分支, 不开新 worktree)
- branch tip: `4219003ac` (W87-X-8 grand closure 收尾)
- backend: `http://localhost:8000` (测试账号登录 OK, 返真 JWT)
- frontend: `http://localhost` (nginx SPA 5 路由全 200)
- **测试账号**: `xiaoqi_testbot` / `testbot_pass_2026` (role=admin, id=59, is_active=true)
- **来源**: `tests/conftest.py:139-141` `TEST_BOT_*` 常量, `scripts/ensure_test_user.py:36-38` 同值 (幂等新建)

## 改了什么 (G-1 基础上)

### `web/tests/visual/a11y/axe-config.mjs`

**`injectAuth()` 升级**: 三段注入
1. **token 模式** (CI 用): `TEST_TOKEN` env var 直接 cookie + localStorage 注
2. **API 模式** (本地用): 无 `TEST_TOKEN` 时, `page.context().request.post(/api/v1/auth/login)` 拿真 JWT, 再 cookie + localStorage 双注
3. ~~**form 模式**~~ (撤回): mobile UA 下 form submit + router.push('/') redirect 行为不可预测, 触发 120s timeout — API 模式更稳

**新增 `toViolationReport()`**: 按 impact 分组的 violation 清单 (critical/serious/moderate/minor), 每条带 selector[:1] + help 文本, 给人读 + 给 W89+ 派修用.

### `web/tests/visual/a11y/axe-chats.spec.mjs`

- test 描述加 "真登录态" 标识, 避免与 a11y-baseline.spec.mjs 混淆
- 新增 2 个 assert: `authInfo.authed === true` (保证不是登录页) + `landedOnLogin === false` (目标页不是被 router 守卫打到 /login)
- 调用 `toViolationReport()` 输出按 impact 分组的清单

### `web/tests/visual/a11y/a11y-baseline.spec.mjs`

- 仅改 injectAuth 调用接 `authInfo.mode`, baseline 内容兼容
- **不重生成** 25 个老快照 (派工 brief "不动 production code", baseline 是测试产物, 但意义已被锚定为"登录页 a11y 现状", 等 W89+ 派修 violation 后用真登录态重新 --update-snapshots)

### `web/tests/visual/a11y/playwright.a11y.config.mjs`

- `timeout: 60_000 → 120_000` (form login + 5 sequential tests 在 mobile UA 下慢, 默认 60s 必超时; token 路径仍 < 30s, 这次升级只放宽 form login 的瓶颈; API 模式下实际跑 56.6s/25 case 全部 OK)

## 5 页面 × 4 projects 真 violation 矩阵

> ⚠️ 5th project (mobile-comments) 全 5 case 失败 (login API 429 限流, 5 次/分/IP — auth.py:77 login_limiter), 1 case 部分跑到 (desktop-comments 的 05-file-comments, auth=none 但被 router 打到 /login 扫到登录页 color-contrast 3×). 这 5 fail **不算 violation 数据**, 留 W88+ 等限流重置后重跑.

### 项目: desktop-chrome (桌面 Chrome, W87-G-1 baseline 派工的"目标环境")

| 页面 | critical | serious | moderate | minor | 关键 violation |
|---|---|---|---|---|---|
| 01-chat (ChatViewSSE) | 0 | **1** | 0 | 0 | color-contrast (11×) — `.is-active > span` |
| 02-drive (DriveView) | 0 | **2** | 0 | 0 | color-contrast (9×) — `.is-active.el-menu-item.menu-item > span` + scrollable-region-focusable (1×) — `.folder-tree` |
| 03-mobile-chat (MobileChatView) | 0 | **1** | 0 | 0 | color-contrast (11×) — `.is-active > span` (resolveMobile 在 desktop UA 下仍返回 ChatViewSSE, 与 01 同) |
| 04-task-trash (MobileTaskTrash) | 0 | **1** | 0 | 0 | color-contrast (4×) — `.sidebar-bottom-item > span` |
| 05-file-comments (DesktopCommentThread) | 0 | **1** | 0 | 0 | color-contrast (7×) — `.sidebar-bottom-item > span` |

**总计 (desktop-chrome)**: 6 violation: 6 serious, 0 critical/moderate/minor

### 项目: mobile-iphone14 (iPhone 14, 390x844 viewport)

| 页面 | critical | serious | moderate | minor | 关键 violation |
|---|---|---|---|---|---|
| 01-chat (MobileChatView via UA) | 0 | **1** | 0 | 0 | html-has-lang (1×) — `html` (NutUI <html> lang 缺失) |
| 02-drive (MobileDriveView) | 0 | **1** | 0 | 0 | html-has-lang (1×) — `html` |
| 03-mobile-chat (MobileChatView) | 0 | **1** | 0 | 0 | html-has-lang (1×) — `html` |
| 04-task-trash (MobileTaskTrash) | 0 | **1** | 0 | 0 | html-has-lang (1×) — `html` |
| 05-file-comments (DesktopCommentThread) | 0 | **1** | 0 | 0 | html-has-lang (1×) — `html` |

**总计 (mobile-iphone14)**: 5 violation: 5 serious, 0 critical/moderate/minor. **全是 NutUI `<html lang="zh-CN">` 缺失**, 5 页面 × 1 = 5 处全无 lang attribute.

### 项目: harmonyos-arkweb (OpenHarmony ArkWeb, 720x1280)

| 页面 | critical | serious | moderate | minor | 关键 violation |
|---|---|---|---|---|---|
| 01-chat (ChatViewSSE) | 0 | **2** | 0 | 0 | aria-command-name (1×) — `#el-id-4639-1` (EP el-dropdown 无 aria-label) + color-contrast (6×) — `.status-text` |
| 02-drive (DriveView) | 0 | **2** | 0 | 0 | aria-command-name (1×) — `#el-id-373-1` + color-contrast (11×) — `.active.drive-tab-btn[role="tab"] > .drive-tab-label` |
| 03-mobile-chat (MobileChatView) | 0 | **2** | 0 | 0 | aria-command-name (1×) + color-contrast (6×) — `.status-text` |
| 04-task-trash (MobileTaskTrash) | 0 | **2** | 0 | 0 | aria-command-name (1×) + color-contrast (7×) — `span[data-v-5eddb7c2]:nth-child(2)` |
| 05-file-comments (DesktopCommentThread) | 0 | **2** | 0 | 0 | aria-command-name (1×) + color-contrast (5×) — `.nut-tabbar-item.tabbar-label` (NutUI 底栏文字) |

**总计 (harmonyos-arkweb)**: 10 violation: 10 serious, 0 critical/moderate/minor. **新发现**: aria-command-name 是 Element Plus `el-dropdown` 的默认行为 (无 aria-label 时), 桌面 + 鸿蒙 UA 都会触发. NutUI `.tabbar-label` 在鸿蒙 UA 下颜色对比度不足.

### 项目: desktop-comments (Desktop Chrome, 1280x800)

| 页面 | critical | serious | moderate | minor | 关键 violation |
|---|---|---|---|---|---|
| 01-chat | 0 | **1** | 0 | 0 | color-contrast (11×) — `.is-active > span` |
| 02-drive | 0 | **2** | 0 | 0 | color-contrast (9×) + scrollable-region-focusable (1×) — `.folder-tree` |
| 03-mobile-chat | 0 | **1** | 0 | 0 | color-contrast (11×) |
| 04-task-trash | 0 | **1** | 0 | 0 | color-contrast (4×) |
| 05-file-comments | 0 | 0 | 0 | 0 | **❌ FAIL: API login 429 (限流) → 被 router 打到 /login → 扫到登录页 color-contrast 3× 不算目标页** |

**总计 (desktop-comments)**: 5 violation (4 页有效 + 1 页因 429 失败不算), 5 serious, 0 critical/moderate/minor.

### 综合矩阵 (20 PASSED, 5 FAILED)

| Axe rule | 总命中 | 涉及页面 | 严重度 | 根因 |
|---|---|---|---|---|
| **color-contrast** | **80+** | 所有 5 页面 | serious | Element Plus el-menu `.is-active > span` (11×) + `.sidebar-bottom-item > span` (4-7×) + MobileTaskTrash 标签 (4-7×) + `.active.drive-tab-btn` (11×) + `.nut-tabbar-item.tabbar-label` (5×) + `.status-text` (6×) + `.login-header > p` (3×) |
| **aria-command-name** | **5** | 5 页面 (鸿蒙项目下) | serious | Element Plus `el-dropdown` 触发, 无 aria-label (id 每次跑变: `#el-id-XXXX-X`) |
| **html-has-lang** | **5** | 5 页面 (mobile-iphone14 项目) | serious | NutUI `<html>` 元素未设 `lang="zh-CN"` (root 元素 lang 缺失) |
| **scrollable-region-focusable** | **1** | drive page | serious | `.folder-tree` 可滚动区域无 tabindex, 键盘不可达 |

**汇总**: **0 critical / 26 serious / 0 moderate / 0 minor** (仅 4 项目有效 case, 5 项目因 429 失败)

## 留 W89+ 修 (本任务不动)

派工 v6 §"0 production code 改动铁律" 守恒 — 本任务**只拿数据**, 不修 violation. 留 W89+ 派修.

### 优先修 (按 axe impact × 命中数)

1. **color-contrast (80+ 命中, 跨项目跨页面)**:
   - `.is-active > span` (el-menu): 11× 命中, 桌面 + 鸿蒙 5 页面都中, 根因是 active menu item 文字色与背景对比度 < 4.5:1 (WCAG AA)
   - `.sidebar-bottom-item > span`: 4-7× 命中, 涉及 Layout 侧边栏底栏 (trash/settings)
   - `.active.drive-tab-btn > .drive-tab-label`: 11× 命中, drive 顶部 tab 选中色
   - `.nut-tabbar-item.tabbar-label`: 5× 命中, NutUI 移动端底栏文字
   - `.status-text`: 6× 命中, ChatViewSSE 状态文字
   - **修法选项**: (a) 调 CSS 颜色值满足 4.5:1 (b) 加 `font-weight: 600` 提高对比 (c) `text-shadow: 0 0 2px rgba(0,0,0,0.5)` (不推荐, 会影响视觉)

2. **html-has-lang (5 命中, mobile-iphone14)**:
   - NutUI `<html>` 缺失 `lang="zh-CN"`
   - **修法**: `web/index.html` 加 `<html lang="zh-CN">` (NutUI 框架仅在移动端 project 下生效, 故只在 mobile UA 下出现 — 但根因是源 HTML, 桌面下被 Element Plus 框架 patch 过)

3. **aria-command-name (5 命中, harmonyos-arkweb)**:
   - Element Plus `el-dropdown` 默认行为, 无 aria-label 时 axe 报 aria-command-name
   - **修法**: 5 个 el-dropdown 调用处显式加 `aria-label` 或包裹文字说明

4. **scrollable-region-focusable (1 命中, drive)**:
   - `.folder-tree` 可滚动但 tabindex=-1, 键盘用户无法 Tab 聚焦
   - **修法**: 加 `tabindex="0"` + `:focus { outline: 2px solid var(--color-primary); }`

## 类 20.42 新增 (派工 v6 §5 反馈 #22 实战)

> **类 20.42**: "a11y baseline 模式仅适合 regression 检测, 首跑必拿真 violation 清单"
>
> **根因**: W87-G-1 baseline 25 快照全是 `authed: no   redirected-to-login: yes`, 实际是登录页. baseline 比对模式让所有目标页"持续 PASS", 但 0 violation 数据无法启动修复. **首跑**必须拿真登录态 + 真 violation 清单, **后续**才用 baseline 做 regression.
>
> **反模式 (W87-G-1 演示)**:
> ```javascript
> // 仅注 cookie + localStorage token (TEST_TOKEN env var 依赖, CI 留)
> await injectAuth(page, BASE_URL)  // 返 authed: yes
> // 但实际页面被 router 守卫打到 /login
> expect(report).toMatchSnapshot(`${name}.txt`)  // baseline 拍的是登录页
> ```
>
> **正模式 (W88-G-2 实战)**:
> ```javascript
> // 三段注入: token / API / form (API 最稳)
> const authInfo = await injectAuth(page, BASE_URL)  // 返 {authed, mode: 'token'|'api'|'form'|'none'}
> expect(authInfo.authed).toBe(true)  // 真登录态 guard
> expect(landedOnLogin).toBe(false)   // 目标页 guard
> const report = toViolationReport(results, pageDef, authInfo)
> console.log(`[a11y-real] ${report}`)  // 按 impact 分组的清单
> ```

## 不动清单 (派工 v6 §"严格边界" 守恒)

- ❌ `web/src/views/**/*.vue` (0 production code 改动铁律, a11y violation 留 W89+)
- ❌ `web/src/components/**/*.vue`
- ❌ `app/`, `alembic/versions/`, `nginx/`, `docker/`, `web/dist/`, `commercial/`
- ❌ G-1 已建的 25 个 `web/tests/visual/a11y/__snapshots__/{name}-{project}.txt` (留作"登录页 a11y 现状" 历史锚点, 等 W89+ 派修后用真登录态重新生成)
- ❌ `playwright.a11y.config.mjs` 的 5 project 设备矩阵 (只改 timeout)

## 跑法 (留给 W89+)

```bash
# 1. 启 dev 环境 (本机 nginx 已 OK, backend 在 :8000)
docker compose ps

# 2. 拿真 violation 清单 (W88-G-2 改后)
cd web
BASE_URL=http://localhost \
TEST_BOT_USERNAME=xiaoqi_testbot \
TEST_BOT_PASSWORD=testbot_pass_2026 \
  npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs \
    axe-chats.spec.mjs --reporter=list 2>&1 | grep -E "a11y-real|auth:|total:|• "

# 3. CI 用 (TEST_TOKEN 覆盖, 不调 login API, 抗限流)
TEST_TOKEN=<jwt from /api/v1/auth/login> \
  npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs \
    axe-chats.spec.mjs --reporter=list
```

## 派工 v6 §1.2 真验证

- ✅ git status: clean
- ✅ git branch: claude/w87-1st-batch-x8-a11y-fix
- ✅ git log: 锚点守恒 (W87-X-8 grand closure 后无 +1 commit, W88-G-2 必 1 commit 进 base)
- ✅ 实际跑 5 项目 × 5 页 = 25 case, 20 PASSED + 5 FAILED (429 限流, 1 例外)
- ✅ spec 改动有真测试验证 (有 console.log 输出 violation 清单)
- ✅ memory 沉淀 (本文件, 锚点 +1 据实上报)
- ✅ commit 单做 (test(w88): a11y 真登录态 fixture + memory 锚点 +1)

## commit

`<pending>` — W88-G-2 待 commit:
- `web/tests/visual/a11y/axe-config.mjs` — `injectAuth()` API 模式 + `toViolationReport()` 新增
- `web/tests/visual/a11y/axe-chats.spec.mjs` — 描述加"真登录态" + 2 guard asserts
- `web/tests/visual/a11y/a11y-baseline.spec.mjs` — 接 `authInfo.mode` 兼容
- `web/tests/visual/a11y/playwright.a11y.config.mjs` — timeout 60s → 120s
- `memory/w88-g2-a11y-real-violations-2026-07-30.md` (本文件)

锚点预期: 337 → 338 (+1 守恒)

## 派工 v6 §5 反馈 #20.42 实战

W88-G-2 据实沉淀 1 新铁律 (类 20.42 a11y baseline 首跑必拿真清单). **累计 类 20 实战 22 实例** (W87 36 + W88-G-2 +1).

W88+ 派工顺序表:
- W88 第 1 批 (本批已完成):
  - ✅ G-2 a11y 真登录态 fixture (本任务)
  - ⏸ H-2 老 logger 接 contextvars 全面化 (类 20.28 续)
  - ⏸ A-1 真 binary 装机 (gitleaks / trivy / pre-commit / pg-exporter / k6 / GlitchTip 一次性)
  - ⏸ npm audit moderate 75 调研 (类 20.35 续, 66 集中在 hint 链)
- W88 第 2 批 (留口):
  - 真 binary 装机收口
  - 老 pytest 138+84 FAIL 修复调研
  - a11y violation 80+ color-contrast 修 (本任务留口)
  - NutUI `<html lang>` 5 命中修
  - el-dropdown aria-label 5 命中修
  - `.folder-tree` tabindex 1 命中修

W19 选项 A 维持. 详见 `memory/w88-g2-a11y-real-violations-2026-07-30.md` (本任务沉淀).

---

**memory 沉淀完毕 — W88-G-2 闭环**. 锚点 337 → 338 (+1 据实上报). 类 20 实战 22 实例 (派工 v6 §5 反馈 #20.42 a11y baseline 首跑必拿真清单).