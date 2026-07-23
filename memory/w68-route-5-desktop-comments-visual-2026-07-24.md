# W68 路线 5 #1 Desktop 评论 UI Playwright 视觉回归 (2026-07-24)

**锚点范式第 58 守恒** — W68 第 5 批 跨主题 grand closure 收口

## 背景

W68 第 4 批桌面端评论 UI agent (commit `5abab881c`) 留"不引入 Playwright 真实浏览器测试 (留给后续 PR)"。W68 第 5 批 #1 接力交付。

**前置 commit**: W68 第 4 批 main HEAD `243937b7f` (DesktopFileCommentsView F-4 + DesktopFileVersionsView + Drive v2 PR9 全套)
**前置 commit**: W68 第 4 批 mobile_drive_comments.spec.mjs (锚点范式第 51 守恒) — 本任务直接复用其结构

## 任务交付 (2 文件修改/新建, 0 production code 改动)

### 1. 新建 `web/tests/visual/desktop/desktop_drive_comments.spec.mjs` (~250 行)

**结构**:
- 20 截图点 (5 viewport × 4 页面)
- 5 viewport 矩阵 (桌面端核心分辨率):
  - desktop-1280 (1280×800) — 笔记本基线
  - desktop-1440 (1440×900) — 常见笔记本
  - desktop-1680 (1680×1050) — 高端笔记本
  - desktop-1920 (1920×1080) — 主流台式机
  - desktop-2560 (2560×1440) — 4K 宽屏 (新增覆盖)
- 4 页面:
  - 01-list: 评论列表 (header + tabs + 列表 + sticky 输入栏)
  - 02-top: 单条顶层评论展开 (DesktopCommentThread depth=0)
  - 03-thread: 嵌套回复 (DesktopCommentThread depth=1 缩进展开)
  - 04-input: 评论输入框聚焦 (DesktopCommentInput focus 视觉态)

**额外场景** (20 + 2 = 22 截图):
- dark mode: `desktop-1920-01-list-dark.png` (W68 第 4 批铁律 13 验证 dark CSS 变量, 复用 1920×1080)
- sticky 输入栏: `desktop-1440-05-sticky-input.png` (验证 .dfcv-compose position: sticky bottom: 0 滚动后仍可见)

**核心实现**:
```js
const SCREENSHOT_OPTIONS = {
  fullPage: true,
  animations: 'disabled',
  maxDiffPixelRatio: 0.002,  // 0.2% 像素差 (跟 v76.2g + 移动端评论视觉基线一致)
  threshold: 0.1,            // 0-255 颜色差
}

async function injectAuth(page) {
  // 双注入 (cookie + localStorage) — v77 P2.6-C 教训
  // 仅 cookie 注入会导致 router 守卫拦截重定向 /login
}

async function waitForDesktopCommentsUI(page) {
  // 等待 .dfcv-list / .dfcv-empty / .dfcv-loading 至少一个出现
  await page.waitForSelector('.dfcv-list, .dfcv-empty, .dfcv-loading', { timeout: 5000 })
}
```

### 2. 修改 `web/playwright.config.js` (1 project 新增)

**新增 project** `desktop-comments`:
```js
{
  name: 'desktop-comments',
  use: {
    ...devices['Desktop Chrome'],  // 借用 chromium engine (本地没装 webkit)
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: false,
    userAgent: '...Windows NT 10.0; Win64; x64 Chrome/120.0.0.0...',
  },
  testMatch: /desktop\/desktop_drive_comments\.spec\.mjs$/,
}
```

**testMatch 锚定**: 只匹配 `desktop_drive_comments.spec.mjs`, 不污染 mobile-iphone14 / desktop-chrome / harmonyos-arkweb / mobile-comments 4 个已有 project。

### 3. 新建 `memory/w68-route-5-desktop-comments-visual-2026-07-24.md` (本文件)

## 设计权衡

### 为什么 desktop viewport 矩阵是 5 个 (含 2560 wide)?

CLAUDE.md "视觉回归 5 viewport × 13 核心页面" 是 v76.2 baseline 范围。本任务 W68 第 5 批桌面端评论 UI 同样用 5 viewport:
- 已有 4: 1280 / 1440 / 1680 / 1920 (笔记本 + 台式机主流)
- 新增 1: 2560 (4K 宽屏, 2026 主流显示器 + 笔记本外接扩展)

**为什么 2560 重要**: 桌面端 max-width 880px 容器居中 (跟移动端对等), 2560 宽屏左右大量留白 → 验证 max-width 容器在 4K 屏下不撑爆 + 留白比例符合设计意图。

### 为什么 testMatch 锚定而不是放 desktop-chrome project?

`desktop-chrome` project 用 `testMatch: /desktop\/.*\.spec\.mjs/` 通配符, 会**全部**匹配 desktop/ 下 21 个 spec (含 v77 废弃 + 各种诊断 spec)。本任务新增 `desktop-comments` project 单独锚定 `/desktop\/desktop_drive_comments\.spec\.mjs$/`, 避免视觉回归跑全套 21 个 spec (耗时 + 干扰 baseline)。

### 为什么跟 mobile-comments project 复用 mobile_drive_comments.spec.mjs 的 7 viewport 而扩到 5 desktop viewport?

移动端碎片化严重 (iPhone SE 375 → iPhone 14 Pro Max 430 → iPad 768), 7 viewport 覆盖合理。
桌面端分辨率集中在 1280-1920, 5 viewport 足够覆盖; 2560 wide 替代 2 个桌面变种 (如 1366×768 / 1600×900) — 桌面端不像移动端那样按设备型号碎片化, 按分辨率阶梯覆盖。

### 为什么 dark mode 单独测?

W68 第 4 批铁律 13 (CLAUDE.md 沉淀): "dark mode 跨组件必须非 scoped 块"。DesktopFileCommentsView 第 484-495 行用 `<style>` 非 scoped 块守 dark mode 跨组件覆盖。本任务验证 dark mode 评论列表实际渲染。

### 为什么 sticky 输入栏单独测?

DesktopFileCommentsView 第 464-473 行 `.dfcv-compose { position: sticky; bottom: 0; }` — sticky 是 desktop 评论 UI 关键 UX 体验 (用户滚动翻历史时始终可见输入栏)。1440×900 viewport 滚动到底后, 验证：
1. `.dfcv-compose` 仍在 viewport 下方
2. 不被 `.dfcv-body` 滚动覆盖
3. z-index: 10 层级正确

**fullPage: false** vs fullPage: true: 滚动后 sticky 输入栏**仍在可视区底部** (不在 fullPage scroll 范围内), 所以用 `fullPage: false` 只截可视区。

### 为什么用 chromium engine 而不是 webkit?

复用 mobile-comments project 经验: `devices['Desktop Chrome']` 默认 chromium, 本地安装简单; webkit 本地需 `npx playwright install webkit` (CI 部署成本高)。

**代价**: 渲染可能与真实 Safari 有差异 (Webkit 字体 hinting / emoji 颜色)
**收益**: 本地能跑, CI 能跑, 不需要 webkit binary

### 为什么双注入登录态?

v77 P2.6-C 教训: 仅 cookie 注入 → 浏览器发请求带 cookie, 但 Vue router 守卫读 `localStorage.getItem('access_token')` 校验 → 守卫拦截 → 重定向 `/login` → baseline 拍到登录页 (3 张旧 baseline 字节数完全相同 = 登录页)。

**正解**: cookie + localStorage 双注入:
```js
await page.context().addCookies([{ name: 'access_token', value: token, domain: host, path: '/' }])
await page.addInitScript((tk) => { localStorage.setItem('access_token', tk) }, token)
```

## 纪律

1. **0 production code 改动铁律维持** — 仅 e2e test (desktop_drive_comments.spec.mjs) + playwright config (desktop-comments project) + memory
2. **复用 v77 P2.6-C 视觉回归模式** — 双注入 + baseline 对比 + testMatch 锚定
3. **复用 mobile-comments (W68 第 4 批) 经验** — 5 viewport 桌面端 + 20 截图 + 2 额外场景
4. **commit 末尾 Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**
5. **分支 `test/desktop-comments-visual-regression-2026-07-24`** — 不 merge, 主指挥 merge
6. **push 到 origin** — webhook 自动部署
7. **基线截图首次会失败** — 无 baseline, 主指挥部署后第一次跑生成 baseline, 后续跑做对比 (跟 v76.2f 一样)

## 复用要点 (后续 PR 抄作业)

- **5 viewport 矩阵**: W68 第 5 批定义, 后续桌面端视觉回归 spec 直接 `import VIEWPORTS from './desktop_drive_comments.spec.mjs'` 复用
- **双注入 login helper**: `injectAuth(page)` 函数独立可复用
- **`waitForDesktopCommentsUI(page)`**: 等待 dfcv-list / dfcv-empty / dfcv-loading, 通用桌面端评论 UI 等待模式
- **SCREENSHOT_OPTIONS**: 全局常量, 20+ 截图统一配置
- **dark mode + sticky 输入栏 2 额外场景**: 复用模式, 改 component class 即可套用任意桌面端页面

## 与现有视觉回归 spec 的关系

```
web/tests/visual/
├── desktop/                       # 含 W68 第 5 批 desktop-comments
│   ├── (20+ e2e spec)            # v77 废弃 + W68 各种诊断 spec
│   ├── desktop_drive_comments.spec.mjs   # ⭐ W68 第 5 批 F-4 视觉回归 (本任务)
│   └── ...
├── local-only/
│   └── pwa-manifest.spec.mjs     # 独立 PWA manifest 测试
├── mobile/
│   ├── visual-regression.spec.mjs         # v77 P2.6-C 9 路由 baseline
│   ├── mobile-ux-v3-dark-2026-07-24.spec.mjs   # W68 第 1 批 dark mode
│   ├── mobile-ux-v3-idb-2026-07-24.spec.mjs    # W68 第 1 批 IndexedDB
│   ├── drive-mobile-feed-2026-07-22.spec.mjs  # W68 Drive feed
│   ├── drive-mobile-routing-2026-07-22.spec.mjs  # W68 Drive routing
│   ├── drive-v2-integration-2026-07-22.spec.mjs   # W68 Drive v2
│   └── mobile_drive_comments.spec.mjs   # W68 第 4 批 F-3 视觉回归 (28 截图)
└── pwa/
```

**互不冲突**: 每个 spec 独立 project + 独立 testMatch + 独立 baseline 目录 (`*-snapshots/`)。

## 7 截图文件命名约定

- `{viewport}-{page}.png`: 例 `desktop-1280-01-list.png`, `desktop-1920-04-input.png`
- `{viewport}-01-list-dark.png`: 例 `desktop-1920-01-list-dark.png` (dark mode 单测)
- `{viewport}-05-sticky-input.png`: 例 `desktop-1440-05-sticky-input.png` (sticky 输入栏单测)

**与 Playwright snapshot 目录约定**: 默认存 `tests/visual/desktop/desktop_drive_comments.spec.mjs-snapshots/` (Playwright 自动创建, 跟 git 仓库, `git add -f` 强制提交)。

## 下次 PR 待办

- [ ] 主指挥部署后第一次跑视觉回归 → 生成 22 张 baseline
- [ ] 后续每次跑 → 像素差 > 0.2% 报错 (W68 第 5 批铁律 14: 视觉回归必须严格)
- [ ] **dev mode vs prod build** — 当前 spec 假设 BASE_URL 跑部署环境, 本地 `npm run dev` 也能跑但需 `BASE_URL=http://localhost:3000`
- [ ] **webkit binary** — 长期目标是从 chromium 切到 webkit (Playwright 支持, 但本地需 `npx playwright install webkit`), 减少渲染差异
- [ ] **视觉回归 CI** — v76.2g CI 已禁用 visual-regression job (40% 失败率), 后续可重新评估价值 (W68 跨主题 dark + sticky + 嵌套回复 三维度 = 高价值)
- [ ] **DesktopCommentThread depth=2+ 嵌套** — 当前 03-thread 只测 depth=1, 深度嵌套覆盖待补
- [ ] **mention @ autocomplete 视觉** — DesktopCommentInput mention 下拉菜单未覆盖 (等 W68 mention 集成 PR 收官后补)

## 锚点范式守恒记录

- W66: 27 守恒
- W67: 28 守恒 (qa-bench D5 docs/CI)
- W68 第 1 批: 30 守恒 (Drive v2 PR8 + Mobile UX v3.0 + Safari)
- W68 第 2 批: 跨主题派工
- W68 第 3 批: 42 守恒 (F-3 mobile_drive_comments.spec.js 端到端)
- W68 第 4 批: 51 守恒 (Mobile 评论 UI Playwright 视觉回归 28 截图)
- **W68 第 5 批: 58 守恒** — Desktop 评论 UI Playwright 视觉回归 (本任务 22 截图)

**单调上升**: W7 12 → W66 27 → W67 28 → W68 30 → W68 42 → W68 51 → **W68 58** (本批)

## 参考

- W68 第 4 批 grand closure: `memory/w68-grand-closure-2026-07-24.md`
- W68 第 4 批 mobile-comments 视觉回归: `memory/w68-route-mobile-comments-visual-regression-2026-07-24.md`
- W68 第 4 批 F-4 桌面端评论 UI 组件: `web/src/views/desktop/DesktopFileCommentsView.vue`
- W68 第 4 批 F-4 桌面端评论 UI 组件 thread: `web/src/components/desktop/DesktopCommentThread.vue`
- W68 第 4 批 F-4 桌面端评论 UI 输入栏: `web/src/components/desktop/DesktopCommentInput.vue`
- v77 P2.6-C 视觉回归模式: `web/tests/visual/mobile/visual-regression.spec.mjs`
- v76.2g 视觉基线配置: `web/playwright.config.js` line 38-50 (maxDiffPixelRatio 0.002)
- W68 第 4 批铁律 13 (dark + vibrate): CLAUDE.md "2026-06-29 #043 账号持久化聊天历史" 阶段铁律段
- W68 第 4 批 F-4 DesktopFileCommentsView: commit `5abab881c` (desktop-drive-comments-ui)
