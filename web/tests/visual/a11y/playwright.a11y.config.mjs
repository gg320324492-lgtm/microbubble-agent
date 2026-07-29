/**
 * tests/visual/a11y/playwright.a11y.config.mjs — W87-G-1 a11y 专用 config
 *
 * 为什么需要独立 config (派工 brief 未预料):
 *   web/playwright.config.js 的 5 个 project 每个都有自己的 testMatch
 *   (mobile/*.spec.mjs / desktop/*.spec.mjs / desktop/recording-*.spec.mjs /
 *    mobile_drive_comments / desktop_drive_comments), 没有一个能匹配
 *   tests/visual/a11y/*.spec.mjs → `npx playwright test tests/visual/a11y/`
 *   实测 "Total: 0 tests in 0 files". 而 brief 明确禁止改 playwright.config.js.
 *   故新增本 config (落在允许的 a11y 目录内), 复刻同一 5 project 设备矩阵.
 *
 * 用法:
 *   cd web
 *   npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs --update-snapshots
 *   npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs
 *
 * 前置: BASE_URL 指向已部署前端 (本机 nginx = http://localhost)
 *       TEST_TOKEN=<jwt> 注入登录态, 否则全部页面被 router 守卫打到 /login
 */

import { defineConfig, devices } from '@playwright/test'

const A11Y_MATCH = /a11y\/.*\.spec\.mjs$/

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
  testMatch: A11Y_MATCH,
  // baseline 落在 tests/visual/a11y/__snapshots__/ (派工 brief 指定位置)
  snapshotPathTemplate: '{testDir}/__snapshots__/{arg}-{projectName}{ext}',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: process.env.CI ? 'github' : 'list',
  timeout: 60_000,
  expect: { timeout: 15_000 },

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost',
    trace: 'retain-on-failure',
  },

  // 复刻 web/playwright.config.js 的 5 project 设备矩阵 (W86 已配, 本任务不重配那边)
  projects: [
    { name: 'mobile-iphone14', use: iphone14 },
    { name: 'desktop-chrome', use: { ...devices['Desktop Chrome'] } },
    {
      name: 'harmonyos-arkweb',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 720, height: 1280 },
        deviceScaleFactor: 2.625,
        isMobile: true,
        hasTouch: true,
        userAgent:
          'Mozilla/5.0 (Phone; OpenHarmony 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 ArkWeb/6.0.0.46SP3 Mobile',
      },
    },
    { name: 'mobile-comments', use: iphone14 },
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
    },
  ],
})
