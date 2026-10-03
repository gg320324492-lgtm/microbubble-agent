/**
 * tests/visual/playwright.visual.config.mjs — S3.10 (2026-10-03) 视觉回归专用 config
 *
 * 为什么需要独立 config:
 *   web/playwright.config.js 的 testMatch 是 `tests/visual/.*\.spec\.mjs`, 即把
 *   tests/visual/ 下 **所有** spec 一并收进"视觉回归"这道门禁。实测该目录下
 *   46 个 spec / 257 个用例中, 真正做像素比对 (toHaveScreenshot) 的只有
 *   5 个 spec / 13 处调用点 —— 其余 41 个是历史 LLM / 功能 E2E 残留
 *   (chat 系列、drive 系列、RAG、recording 等), 它们断言的是 DOM / computed style,
 *   与"像素"无关。
 *
 *   本 config 把门禁收回到它声称要守的范围: **只跑有 toHaveScreenshot 的 5 个 spec**。
 *   与 a11y 的 tests/visual/a11y/playwright.a11y.config.mjs 同一模式 (W87-G-1 先例),
 *   落在 tests/visual/ 内, 不改 web/playwright.config.js (那份保留给本地全量 dev 用)。
 *
 * 为什么收敛是安全的 (实测依据, run 37100057334):
 *   这 5 个 spec 全部**不依赖 LLM、不调 drive 上传** —— 逐个 grep 确认无
 *   `chat/stream` / `api/v1/chat`, 也无 `drive/files/upload`:
 *     desktop/chat-topbar-6-themes.spec.mjs   no-llm no-upload
 *     desktop/desktop_drive_comments.spec.mjs no-llm no-upload
 *     mobile/mobile_drive_comments.spec.mjs  no-llm no-upload
 *     mobile/secondary-routes.spec.mjs        no-llm no-upload  (全 mock)
 *     mobile/visual-regression.spec.mjs       no-llm no-upload  (双注入登录态)
 *   实测单例耗时 (同一 run 的 CI 实测, n=50):
 *     mean 4.10s / max 10.9s / 合计 205.2s
 *   对照被移出的部分: 17m02s 只跑到 100/257, 单例最高打满
 *   test.setTimeout(240_000) 且 CI retries: 1 再翻一倍。
 *   ⇒ 收敛后必然能在 job 预算内跑完 (估 ~9 分钟 / 127 用例), 不再有 cancelled。
 *
 * ⚠️ 收敛后本门禁**预期是 failure**, 原因是**缺基线**, 不是代码回归:
 *   这 5 个 spec 的 **-snapshots/ 基线在 git 里全都不存在**
 *   (f9495f13b 废弃 v76 视觉回归时删, 4c97ae562 删 baseline png,
 *    81423c4a2 又把 PNG 加进 .gitignore)。实测 Playwright 在缺基线时
 *   (updateSnapshots 默认 "missing") 判 1 failed 并报
 *   `A snapshot doesn't exist at ...`, **不会自动写盘**。
 *   ⇒ 看到这个红, 不要误判成"UI 回归了"; 它的含义是"还没有基线可比"。
 *   录基线的前置条件是 ChatViewSSE 的 CSS 抽取完成 (像素比对是验收 CSS 的唯一手段),
 *   顺序不可颠倒: CSS 抽取 → 视觉回归转硬门 → 才谈录基线。
 *
 * 用法:
 *   本地全量 dev (含 LLM/功能 E2E, 需要真后端 + LLM key):
 *     npx playwright test
 *   本门禁真正守的 5 个 spec (与 CI 一致):
 *     npx playwright test -c tests/visual/playwright.visual.config.mjs
 */

import { defineConfig, devices } from '@playwright/test'

// 只认这 5 个**真正含 toHaveScreenshot** 的 spec。
// ⚠️ 别把 grade-tag-extension / task-action-buttons 加进来: 它们 grep 命中
// toHaveScreenshot 只是**注释里说明自己刻意不用**它 (改用 evaluate() 取
// computed style 精确断言), 本身不是像素比对。
//
// ⚠️ testMatch 放在**顶层**会让它与各 project 自己的 testMatch **相乘** —— 顶层
// 命中 5 个 spec, 而 4 个 project 若不各自收窄就会各跑一遍, 实测 "Total: 300"
// (127 × 4 的量级)。必须让每个 project 各自只认自己那份 spec。
const VISUAL_MATCH =
  /(chat-topbar-6-themes|desktop_drive_comments|mobile_drive_comments|secondary-routes|visual-regression)\.spec\.mjs$/

// 各 spec 的归属 project —— **严格复刻 web/playwright.config.js 原有口径**, 一处不多一处不少。
// 实测原 config 对这 5 个 spec 的 project 分布 (n=127):
//   desktop-chrome    28 = chat-topbar-6-themes 6 + desktop_drive_comments 22
//   desktop-comments  22 = desktop_drive_comments 22
//   mobile-comments   30 = mobile_drive_comments 30
//   mobile-iphone14   47 = mobile_drive_comments 30 + secondary-routes 8 + visual-regression 9
// ⚠️ 注意两个评论 spec 在原 config 里各跑**两个** project (如 desktop_drive_comments
// 同时属 desktop-chrome 与 desktop-comments), 因为原 project 的 testMatch 是
// `/desktop\/.*\.spec\.mjs/` 这类目录通配, 而 mobile-comments/mobile-iphone14 的
// testMatch 是**具体文件名**, 但 mobile-iphone14 的 `/mobile\/.*\.spec\.mjs/`
// 又把 mobile_drive_comments 也捞进来了。基线文件名带 projectName, 少一个 project
// 就会让既有基线对不上, 故这里逐条复刻而非"优化"。
const iphone14 = {
  ...devices['Desktop Chrome'], // 只借 chromium engine (本机没装 webkit, 与既有 config 同口径)
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
  userAgent:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
}

export default defineConfig({
  testDir: '.',
  // 顶层只做"目录收窄"(限 tests/visual/), 具体 spec 由各 project 的 testMatch 决定。
  // ⚠️ 不能在这里放 VISUAL_MATCH: 顶层 testMatch 会与各 project 的 testMatch 相乘 ——
  // 实测那样得到 "Total: 300"(每个 project 各跑全部 5 个 spec)。
  testMatch: /.*\.spec\.mjs$/,
  fullyParallel: false,
  // 像素严格对比, 单 worker 避免竞态 (与 web/playwright.config.js 同口径)
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  forbidOnly: !!process.env.CI,

  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.002, // 允许 0.2% 像素差 (anti-aliasing / 字体 sub-pixel 抖动)
      threshold: 0.1,
      fullPage: true,
      animations: 'disabled',
    },
    timeout: 10_000,
  },

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    viewport: { width: 1280, height: 720 },
  },

  // 保留与 web/playwright.config.js 同名的 project, 使 -snapshots/ 文件名带
  // projectName, 与既有基线口径一致。
  projects: [
    {
      name: 'mobile-iphone14',
      use: iphone14,
      // 原 config 的 /mobile\/.*\.spec\.mjs/ 会同时捞到 mobile_drive_comments
      testMatch: /(mobile_drive_comments|secondary-routes|visual-regression)\.spec\.mjs$/,
    },
    {
      name: 'desktop-chrome',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /(chat-topbar-6-themes|desktop_drive_comments)\.spec\.mjs$/,
    },
    {
      name: 'mobile-comments',
      use: iphone14,
      testMatch: /mobile_drive_comments\.spec\.mjs$/,
    },
    {
      name: 'desktop-comments',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 800 },
        deviceScaleFactor: 1,
        isMobile: false,
        hasTouch: false,
        userAgent:
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      },
      testMatch: /desktop_drive_comments\.spec\.mjs$/,
    },
  ],
})