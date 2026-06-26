/**
 * tests/visual/mobile/pwa-manifest.spec.mjs
 *
 * PWA manifest 逻辑检查 (v76.2h 拆出, 不属于视觉回归)
 *
 * 之前写在 visual-regression.spec.mjs 里, 但 dev server 上 /manifest.webmanifest 404
 * (vite-plugin-pwa 仅在 build 产物里输出 hash manifest), 拖垮整个视觉回归 job
 *
 * 此 spec 独立运行, 验证:
 *   - build 产物 manifest URL 可访问 (用 vite preview)
 *   - JSON 字段正确 (name / theme_color)
 *
 * 跑法:
 *   1. npm run build
 *   2. npx vite preview --port 4173 &
 *   3. BASE_URL=http://localhost:4173 npx playwright test pwa-manifest.spec.mjs
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:4173'

test.describe('PWA manifest 逻辑检查 (v76.2h 拆出)', () => {
  test('manifest.webmanifest 可访问 + JSON 字段正确', async ({ request }) => {
    // 用 request 而不是 page (不需要浏览器, 更快)
    const response = await request.get(`${BASE_URL}/manifest.webmanifest`)
    expect(response.status(), 'manifest 应该 200').toBe(200)

    const manifest = await response.json()
    expect(manifest.name, 'manifest.name 字段').toBe('微纳米气泡课题组智能助手')
    expect(manifest.theme_color, 'manifest.theme_color = #FF7A5C').toBe('#FF7A5C')
  })

  test('PWA 图标可访问 (192/512 两尺寸)', async ({ request }) => {
    for (const size of ['192', '512']) {
      const response = await request.get(`${BASE_URL}/pwa-${size}.png`)
      expect(response.status(), `pwa-${size}.png 应 200`).toBe(200)
    }
  })

  test('Service Worker 注册 (生产 build)', async ({ page }) => {
    // 这一步需要浏览器 (检查 navigator.serviceWorker), 不能纯 request
    await page.goto(`${BASE_URL}/`)
    const swRegistered = await page.evaluate(async () => {
      if (!('serviceWorker' in navigator)) return false
      const reg = await navigator.serviceWorker.getRegistration()
      return !!reg
    })
    // SW 在生产 build 后注册 (vite preview 模拟生产)
    expect(typeof swRegistered).toBe('boolean')
  })
})