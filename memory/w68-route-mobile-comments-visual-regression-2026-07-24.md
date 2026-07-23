# W68 路线 F-3 Mobile 评论 UI Playwright 视觉回归 (2026-07-24)

**锚点范式第 51 守恒** — W68 第 4 批 跨主题 grand closure 收口

## 背景

W68 第 3 批 F-3 留"完整 Playwright 视觉回归留给后续 PR", W68 第 4 批接力交付。

**前置 commit**: W68 第 1 批 main HEAD `13548ff2b` (Drive v2 PR8 + Mobile UX v3.0 + Safari iOS 修复)
**前置 commit**: W68 第 3 批 main HEAD `26c7c5620` (Mobile UX v3.1 文档 + F-3 mobile_drive_comments.spec.js)

## 任务交付 (3 文件, 0 production code 改动)

### 1. 新建 `web/tests/visual/mobile/mobile_drive_comments.spec.mjs` (283 行)

**结构**:
- 28 截图点 (7 viewport × 4 页面)
- 7 viewport 矩阵:
  - iPhone SE (375×667)
  - iPhone 12 (390×844)
  - iPhone 14 Pro Max (430×932)
  - iPad (768×1024)
  - Galaxy S20 (412×915)
  - Pixel 5 (393×851)
  - OnePlus 8 (412×869)
- 4 页面:
  - 01-list: 评论列表 (header + tabs + 列表 + 输入栏)
  - 02-top: 单条顶层评论展开
  - 03-thread: 嵌套回复 (thread_depth=1)
  - 04-input: 评论输入框聚焦 (键盘弹出)

**额外场景** (28 + 2 = 30 截图):
- dark mode: `iphone-12-01-list-dark.png` (W68 第 4 批铁律 13 验证 dark CSS 变量)
- 长按菜单: `iphone-12-05-longpress-menu.png` (W68 第 4 批铁律 13 vibrate 验证)

**核心实现**:
```js
const SCREENSHOT_OPTIONS = {
  fullPage: true,
  animations: 'disabled',
  maxDiffPixelRatio: 0.002,  // 0.2% 像素差 (跟 v76.2g 视觉基线一致)
  threshold: 0.1,            // 0-255 颜色差
}

async function injectAuth(page) {
  // 双注入 (cookie + localStorage) — v77 P2.6-C 教训
  // 仅 cookie 注入会导致 router 守卫拦截重定向 /login
}

async function waitForCommentsUI(page) {
  // 等待 .mfcc-list / .mfcc-empty / .mfcc-loading 至少一个出现
  await page.waitForSelector('.mfcc-list, .mfcc-empty, .mfcc-loading', { timeout: 5000 })
}
```

### 2. 修改 `web/playwright.config.js` (1 project 新增)

**新增 project** `mobile-comments`:
```js
{
  name: 'mobile-comments',
  use: {
    ...devices['Desktop Chrome'],  // 借用 chromium engine (本地没装 webkit)
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
    userAgent: '...iPhone OS 17_0...',
  },
  testMatch: /mobile\/mobile_drive_comments\.spec\.mjs$/,
}
```

**testMatch 锚定**: 只匹配 `mobile_drive_comments.spec.mjs`, 不污染 mobile-iphone14 / desktop-chrome / harmonyos-arkweb 3 个已有 project。

### 3. 新建 `memory/w68-route-mobile-comments-visual-regression-2026-07-24.md` (本文件)

## 设计权衡

### 为什么用 chromium engine 而不是 webkit?

`devices['iPhone 14']` 默认 webkit, **本地没装** (项目历史踩坑, v76.2f 修复)。复用 `...devices['Desktop Chrome']` 只借用 chromium 默认配置, 然后**手工覆盖** viewport / deviceScaleFactor / isMobile / hasTouch / userAgent。

**代价**: 渲染可能与真实 Safari 有差异 (Webkit 字体 hinting / emoji 颜色)
**收益**: 本地能跑, CI 能跑, 不需要 webkit binary

### 为什么双注入登录态?

v77 P2.6-C 教训: 仅 cookie 注入 → 浏览器发请求带 cookie, 但 Vue router 守卫读 `localStorage.getItem('access_token')` 校验 → 守卫拦截 → 重定向 `/login` → baseline 拍到登录页 (3 张旧 baseline 字节数完全相同 = 登录页)。

**正解**: cookie + localStorage 双注入:
```js
await page.context().addCookies([{ name: 'access_token', value: token, domain: host, path: '/' }])
await page.addInitScript((tk) => { localStorage.setItem('access_token', tk) }, token)
```

### 为什么 7 viewport 而不是 5?

CLAUDE.md "视觉回归 5 viewport × 13 核心页面" 是 v76.2 baseline 范围。本任务 W68 第 4 批扩到 7 viewport:
- 已有 5: iPhone SE / iPhone 14 / iPad / Galaxy S20 / Pixel 5
- 新增 2: iPhone 12 (390×844, 与 W68 第 3 批 F-3 mobile_drive_comments.spec.js 一致) + iPhone 14 Pro Max (430×932, 2026 最新机) + OnePlus 8 (412×869, 国内常见机)

### 为什么 dark mode 单独测?

W68 第 4 批铁律 13 (CLAUDE.md 沉淀): "mobile long-press 必带 `navigator.vibrate(10)` 触觉反馈 + dark mode 跨组件必须非 scoped 块"。dark mode 是 mobile 评论 UI 必测场景 (用户实际使用高频)。

### 为什么 long-press 菜单单独测?

`vibrate(10)` 是触觉反馈 (CLAUDE.md 2026-06-27 教训), 但视觉回归看的是菜单弹出后页面布局变化:
- Teleport to body → DOM 结构变化 → fullPage 截图会包含菜单
- 但菜单弹出后页面**其他部分**不变 → 改用 `fullPage: false` 只截可视区
- 验证 `.mobile-context-menu` 元素确实渲染 (避免空 baseline)

## 纪律

1. **0 production code 改动铁律维持** — 仅 e2e test (mobile_drive_comments.spec.mjs) + playwright config (mobile-comments project) + memory
2. **复用 v77 P2.6-C 视觉回归模式** — 双注入 + baseline 对比 + testMatch 锚定
3. **commit 末尾 Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**
4. **分支 `test/mobile-comments-visual-regression-2026-07-24`** — 不 merge, 主指挥 merge
5. **push 到 origin** — webhook 自动部署
6. **基线截图首次会失败** — 无 baseline, 主指挥部署后第一次跑生成 baseline, 后续跑做对比 (跟 v76.2f 一样)

## 复用要点 (后续 PR 抄作业)

- **7 viewport 矩阵**: W68 第 4 批定义, 后续视觉回归 spec 直接 `import VIEWPORTS from './mobile_drive_comments.spec.mjs'` 复用
- **双注入 login helper**: `injectAuth(page)` 函数独立可复用
- **`waitForCommentsUI(page)`**: 等待 mfcc-list / mfcc-empty / mfcc-loading, 通用 mobile 评论 UI 等待模式
- **SCREENSHOT_OPTIONS**: 全局常量, 28+ 截图统一配置

## 与现有视觉回归 spec 的关系

```
web/tests/visual/
├── desktop/                       # v77 废弃 (workflow bug 长期未修)
├── local-only/
│   └── pwa-manifest.spec.mjs     # 独立 PWA manifest 测试
├── mobile/
│   ├── visual-regression.spec.mjs         # v77 P2.6-C 9 路由 baseline
│   ├── mobile-ux-v3-dark-2026-07-24.spec.mjs   # W68 第 1 批 dark mode
│   ├── mobile-ux-v3-idb-2026-07-24.spec.mjs    # W68 第 1 批 IndexedDB
│   ├── drive-mobile-feed-2026-07-22.spec.mjs  # W68 Drive feed
│   ├── drive-mobile-routing-2026-07-22.spec.mjs  # W68 Drive routing
│   ├── drive-v2-integration-2026-07-22.spec.mjs   # W68 Drive v2
│   └── mobile_drive_comments.spec.mjs   # ⭐ W68 第 4 批 F-3 视觉回归 (本任务)
└── pwa/
```

**互不冲突**: 每个 spec 独立 project + 独立 testMatch + 独立 baseline 目录 (`*-snapshots/`)。

## 4 截图文件命名约定

- `{viewport}-{page}.png`: 例 `iphone-se-01-list.png`, `ipad-04-input.png`
- `{viewport}-01-list-dark.png`: 例 `iphone-12-01-list-dark.png` (dark mode 单测)
- `{viewport}-05-longpress-menu.png`: 例 `iphone-12-05-longpress-menu.png` (长按菜单单测)

**与 Playwright snapshot 目录约定**: 默认存 `tests/visual/mobile/mobile_drive_comments.spec.mjs-snapshots/` (Playwright 自动创建, 跟 git 仓库, `git add -f` 强制提交)。

## 下次 PR 待办

- [ ] 主指挥部署后第一次跑视觉回归 → 生成 30 张 baseline
- [ ] 后续每次跑 → 像素差 > 0.2% 报错 (W68 第 4 批铁律 14: 视觉回归必须严格)
- [ ] **dev mode vs prod build** — 当前 spec 假设 BASE_URL 跑部署环境, 本地 `npm run dev` 也能跑但需 `BASE_URL=http://localhost:3000`
- [ ] **webkit binary** — 长期目标是从 chromium 切到 webkit (Playwright 支持, 但本地需 `npx playwright install webkit`), 减少渲染差异
- [ ] **视觉回归 CI** — v76.2g CI 已禁用 visual-regression job (40% 失败率), 后续可重新评估价值 (W68 跨主题 dark + 长按 + 嵌套回复 三维度 = 高价值)

## 锚点范式守恒记录

- W66: 27 守恒
- W67: 28 守恒 (qa-bench D5 docs/CI)
- W68 第 1 批: 30 守恒 (Drive v2 PR8 + Mobile UX v3.0 + Safari)
- W68 第 2 批: 跨主题派工
- W68 第 3 批: F-3 mobile_drive_comments.spec.js 端到端测试 (vitest)
- **W68 第 4 批: 51 守恒** — Mobile 评论 UI Playwright 视觉回归 (本任务)

**单调上升**: W7 12 → W66 27 → W67 28 → W68 30 → **W68 51** (本批跨多个阶段累计)

## 参考

- W68 第 1 批 grand closure: `memory/w68-grand-closure-2026-07-24.md`
- W68 第 3 批 F-3 端到端测试: `web/tests/e2e/mobile_drive_comments.spec.js`
- v77 P2.6-C 视觉回归模式: `web/tests/visual/mobile/visual-regression.spec.mjs`
- v76.2g 视觉基线配置: `web/playwright.config.js` line 38-50 (maxDiffPixelRatio 0.002)
- W68 第 4 批铁律 13 (dark + vibrate): CLAUDE.md "2026-06-29 #043 账号持久化聊天历史" 阶段铁律段