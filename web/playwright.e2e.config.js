import { defineConfig, devices } from '@playwright/test'

/**
 * playwright.e2e.config.js — tests/e2e 专用极简 config
 *
 * 主 playwright.config.js 的 testDir 锁在 ./tests/visual (v76.2f), 扫不到 tests/e2e.
 * 本 config 供 tests/e2e/ 下的 functional spec 用:
 *   npx playwright test --config playwright.e2e.config.js
 *
 * 前置: npm run dev (web-dev, :3000) — mock spec 仍需 vite dev server 提供前端页面,
 * 但不需要后端 (page.route 全拦截).
 */
export default defineConfig({
  testDir: './tests/e2e',
  // tests/e2e 下混有历史 vitest-style spec (thinking-mode-breadcrumb 等) 与
  // describe 内 test.use 的老写法 — Playwright 跑不了. 本 config 只认 mock 基线 spec.
  //
  // ⚠️ 别把 mobile_dark_v33.spec.js 加进来 (2026-09-30 踩过): 它是
  // **vitest + @vue/test-utils** 用例 (文件头自述, 第 29-30 行 import vitest/mount),
  // 不是 Playwright spec —— 放进本 testMatch 会在 worker 里加载失败。而本 config
  // 本身也无人引用 (package.json 与所有 workflow 都没用它), 加了等于彻底不跑。
  testMatch: /mobile-baseline\.spec\.js/,
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  timeout: 30_000,
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    ...devices['Desktop Chrome'],
  },
})
