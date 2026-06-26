import { defineConfig, devices } from '@playwright/test'

/**
 * playwright.config.js — v76.2 视觉回归基线对比配置
 *
 * 用法:
 *   npx playwright test                    # 跑所有视觉回归 (对比 baseline)
 *   npx playwright test --update-snapshots # 更新 baseline (确认视觉变更是预期的)
 *   npx playwright test --grep dashboard   # 只跑某个 case
 *
 * 前置条件:
 *   1. npm run dev (或 BASE_URL 环境变量指向部署环境)
 *   2. 已登录态 (用 TEST_TOKEN 环境变量注入 access_token cookie)
 *
 * 视觉回归原理:
 *   第一次跑: 生成 tests/visual/mobile/screenshots/{name}-{viewport}.png 作 baseline
 *   后续跑:  重新截图, 像素 diff 超过 maxDiffPixelRatio (默认 0.2 = 20%) 报错
 *   故意改:  --update-snapshots 更新 baseline 并 git commit
 */
export default defineConfig({
  testDir: './tests/visual',
  // v76.2f: 限定 testMatch 到 tests/visual 下, 避免扫到 vitest 测试文件
  // (playwright 默认 testMatch 是 **/*.@(spec|test).?(c|m)[jt]s?(x), 会扫全项目所有 .test.js)
  testMatch: /tests\/visual\/.*\.spec\.mjs/,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // 视觉回归对像素严格, 单 worker 避免竞态
  reporter: process.env.CI ? 'github' : 'list',

  // baseline 对比核心配置
  expect: {
    toHaveScreenshot: {
      // 允许 0.2% 像素差异 (anti-aliasing / 字体 sub-pixel 渲染抖动)
      maxDiffPixelRatio: 0.002,
      // 允许 0.1 颜色差异阈值 (0-255)
      threshold: 0.1,
      // 完整页面截图
      fullPage: true,
      // 关闭动画避免 baseline 不稳定
      animations: 'disabled',
    },
    timeout: 10_000,
  },

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    // 桌面端 viewport 默认
    viewport: { width: 1280, height: 720 },
  },

  projects: [
    {
      name: 'mobile-iphone14',
      // v76.2f: 显式用 chromium engine (devices['iPhone 14'] 默认 webkit, 本地没装)
      use: {
        ...devices['Desktop Chrome'], // 只借用默认 chromium 配置
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 3,
        isMobile: true,
        hasTouch: true,
        userAgent:
          'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
      },
      testMatch: /mobile\/.*\.spec\.mjs/,
    },
    {
      name: 'desktop-chrome',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /desktop\/.*\.spec\.mjs/,
    },
  ],
})