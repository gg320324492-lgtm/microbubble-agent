/**
 * tests/visual/mobile/visual-regression.spec.mjs
 *
 * Playwright 视觉回归 — v76.2 升级 baseline 对比模式
 *
 * 用法:
 *   npx playwright test                                    # 对比 baseline
 *   npx playwright test --update-snapshots                # 更新 baseline
 *   BASE_URL=https://staging npx playwright test          # 跑 staging 环境
 *   TEST_TOKEN=<jwt> npx playwright test                   # 注入登录态
 *
 * 前置:
 *   - dev server 跑起来 (npm run dev) 或用 BASE_URL 指向部署环境
 *   - 登录态: 通过 TEST_TOKEN 环境变量注入 access_token cookie
 *   - 第一次跑必须带 --update-snapshots 生成 baseline
 *
 * 关键纪律:
 *   - 视觉差异 > 0.2% 才 fail (配置在 playwright.config.js)
 *   - 不要手动改 baseline/*.png (用 --update-snapshots)
 *   - baseline 必须跟代码一起 commit (跟 dist 一样, git add -f)
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const VIEWPORT = { width: 390, height: 844 } // iPhone 14

// v76.2 收窄: 从 14 路由 → 3 核心页面 (避免 baseline 维护成本失控)
// 未来按需扩展
const CORE_ROUTES = [
  { path: '/dashboard', name: '01-dashboard' },
  { path: '/knowledge', name: '06-knowledge' },
  { path: '/chat', name: '03-chat' },
]

test.describe('Mobile 核心页面视觉回归 (v76.2 baseline 对比)', () => {
  test.use({ viewport: VIEWPORT })

  // 公共登录态注入 helper
  async function injectAuth(page) {
    await page.context().addCookies([{
      name: 'access_token',
      value: process.env.TEST_TOKEN || 'mock-token',
      domain: new URL(BASE_URL).hostname,
      path: '/',
    }])
  }

  for (const route of CORE_ROUTES) {
    test(`${route.name} 截图对比 baseline`, async ({ page }) => {
      await injectAuth(page)
      await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'networkidle' })

      // 等动画/异步数据加载完成
      await page.waitForTimeout(800)

      // v76.2: baseline 对比 (替换 v70 旧版 "覆盖截图" 模式)
      // 首次跑会自动生成 tests/visual/mobile/visual-regression.spec.mjs-snapshots/{name}-iphone14.png
      await expect(page).toHaveScreenshot(`${route.name}.png`, {
        fullPage: true,
        animations: 'disabled',
        maxDiffPixelRatio: 0.002,
      })

      // 验证页面真的渲染了内容 (避免空白页通过 baseline 对比)
      const bodyText = await page.textContent('body')
      expect(bodyText.length, `${route.name} 页面应渲染内容`).toBeGreaterThan(10)
    })
  }

  test('PWA manifest 可访问 (含视觉基线对比意义)', async ({ page }) => {
    const response = await page.goto(`${BASE_URL}/manifest.webmanifest`)
    expect(response.status()).toBe(200)
    const manifest = await response.json()
    expect(manifest.name).toBe('微纳米气泡课题组智能助手')
    expect(manifest.theme_color).toBe('#FF7A5C')
  })
})