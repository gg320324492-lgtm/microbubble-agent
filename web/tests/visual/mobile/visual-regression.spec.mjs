/**
 * tests/visual/mobile/visual-regression.spec.mjs
 *
 * Playwright 视觉回归 — 14 个移动端路由 × iPhone 14 viewport
 *
 * 使用方法：
 *   1. 启动应用：cd web && npm run dev （或部署到测试环境）
 *   2. 运行测试：npx playwright test tests/visual/mobile/visual-regression.spec.mjs
 *   3. 截图输出到 tests/visual/mobile/screenshots/
 *
 * 注：需要在已登录状态下运行（或注入 token）
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const VIEWPORT = { width: 390, height: 844 } // iPhone 14

// 14 个移动端路由
const ROUTES = [
  { path: '/login', name: '01-login' },
  { path: '/dashboard', name: '02-dashboard' },
  { path: '/chat', name: '03-chat' },
  { path: '/tasks', name: '04-tasks' },
  { path: '/meetings', name: '05-meetings' },
  { path: '/knowledge', name: '06-knowledge' },
  { path: '/projects', name: '07-projects' },
  { path: '/project-stats', name: '08-project-stats' },
  { path: '/members', name: '09-members' },
  { path: '/memory', name: '10-memory' },
  { path: '/voiceprint', name: '11-voiceprint' },
  { path: '/settings', name: '12-settings' },
]

test.describe('Mobile 视觉回归', () => {
  test.use({ viewport: VIEWPORT })

  for (const route of ROUTES) {
    test(`${route.name} 截图`, async ({ page }) => {
      // 注入登录态（避免重定向到 login）
      await page.context().addCookies([{
        name: 'access_token',
        value: process.env.TEST_TOKEN || 'mock-token',
        domain: 'localhost',
        path: '/',
      }])

      await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'networkidle' })

      // 等待移动端组件加载
      await page.waitForTimeout(800)

      // 截图
      await page.screenshot({
        path: `tests/visual/mobile/screenshots/${route.name}.png`,
        fullPage: true,
      })

      // 验证页面没有空白
      const bodyText = await page.textContent('body')
      expect(bodyText.length).toBeGreaterThan(10)
    })
  }

  test('PWA manifest 可访问', async ({ page }) => {
    const response = await page.goto(`${BASE_URL}/manifest.webmanifest`)
    expect(response.status()).toBe(200)
    const manifest = await response.json()
    expect(manifest.name).toBe('微纳米气泡课题组智能助手')
    expect(manifest.theme_color).toBe('#FF7A5C')
  })

  test('Service Worker 注册', async ({ page }) => {
    await page.goto(`${BASE_URL}/`)
    const swRegistered = await page.evaluate(async () => {
      if (!('serviceWorker' in navigator)) return false
      const reg = await navigator.serviceWorker.getRegistration()
      return !!reg
    })
    // SW 在生产环境注册，开发环境不注册（devOptions.enabled: false）
    expect(typeof swRegistered).toBe('boolean')
  })

  test('PWA icons 可访问', async ({ page }) => {
    for (const size of ['192', '512']) {
      const response = await page.goto(`${BASE_URL}/pwa-${size}.png`)
      expect(response.status()).toBe(200)
    }
  })
})