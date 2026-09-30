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
  // describe 内 test.use 的老写法 — Playwright 跑不了. 本 config 只认能跑的 spec.
  //
  // 2026-09-30 S3.4: 补 mobile_dark_v33.spec.js。它此前**任何 runner 都不跑**
  // (本 config 的 testMatch 只认 mobile-baseline, 主 config 只认 tests/visual),
  // 只在 vitest 里整体崩。它断言的"移动端 dark 模式 6 view 不应有硬编码 hex"并未被
  // stylelint 覆盖 —— stylelint 配置里 "color-no-hex": null 是**主动禁用**该规则,
  // 故本 spec 是这条约束的唯一执行者, 属真盲区。
  testMatch: /(mobile-baseline|mobile_dark_v33)\.spec\.js/,
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
