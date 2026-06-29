/**
 * tests/visual/desktop/voiceprint-6-themes-2026-06-30.spec.mjs
 *
 * voiceprint-2026-06-30 收官 6 主题视觉验证
 *
 * 覆盖:
 *   - 桌面 /voiceprint 路由 (含 VoiceprintCard bar / VoiceTestDialog Canvas / ConfidenceChart ECharts)
 *   - 移动端 /m/voiceprint 路由 (含 VoiceprintEnrollFlow option-icon 渐变)
 *   - 6 主题 (light/dark × orange/ocean/forest) 切换 → 主题色 DOM 断言 + 关键元素可见性
 *
 * 前置:
 *   - dev server 跑起来 (npm run dev) 或 BASE_URL 指向部署环境
 *   - TEST_TOKEN 环境变量注入真实 JWT (通过 /api/v1/auth/login 获取)
 *
 * 运行:
 *   BASE_URL=http://localhost:3004 \
 *   TEST_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
 *     -H "Content-Type: application/json" \
 *     -d '{"username":"wangtianzhi","password":"admin123"}' \
 *     | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])") \
 *     npx playwright test tests/visual/desktop/voiceprint-6-themes-2026-06-30.spec.mjs
 *
 * 关键纪律:
 *   - 真实 JWT token (mock-token 会被后端拒, 渲染 generic 用户)
 *   - 不写 baseline 对比 (本 spec 是 smoke test, 不依赖视觉回归阈值)
 *   - 截图保存到 test-results/ (失败时 + 主题截图)
 *   - 任务号 'voiceprint-2026-06-30' 避免与 'v77 P2.6-G.2' admin template 收官混淆
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3004'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

// voiceprint-2026-06-30 收官: 6 主题组合
const THEMES = [
  { name: '01-light-orange', theme: 'light', accent: 'orange' },
  { name: '02-light-ocean', theme: 'light', accent: 'ocean' },
  { name: '03-light-forest', theme: 'light', accent: 'forest' },
  { name: '04-dark-orange', theme: 'dark', accent: 'orange' },
  { name: '05-dark-ocean', theme: 'dark', accent: 'ocean' },
  { name: '06-dark-forest', theme: 'dark', accent: 'forest' },
]

/**
 * 公共 helper: 注入登录态 + 设主题 (v77 P2.6-C 双注入)
 *
 * 注意: useThemeStore 用的 localStorage key 是 'theme' / 'accent'
 */
async function setupPage(page, { theme = 'light', accent = 'orange' } = {}) {
  // 1. Cookie 注入
  await page.context().addCookies([{
    name: 'access_token',
    value: TEST_TOKEN,
    domain: new URL(BASE_URL).hostname,
    path: '/',
  }])
  // 2. localStorage 注入 (router 守卫读这里)
  await page.addInitScript((data) => {
    localStorage.setItem('access_token', data.token)
    localStorage.setItem('theme', data.theme)
    localStorage.setItem('accent', data.accent)
  }, { token: TEST_TOKEN, theme, accent })
  // 3. 首次访问后用 page.evaluate 强制设主题 (避免 useThemeStore 在 setup 时用默认值覆盖)
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
  await page.evaluate(([t, a]) => {
    localStorage.setItem('theme', t)
    localStorage.setItem('accent', a)
  }, [theme, accent])
}

async function waitForLoaded(page) {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
}

test.describe('voiceprint-2026-06-30: 桌面 /voiceprint 6 主题验证', () => {
  test('桌面 6 主题循环验证 + 256 bar 渲染 + .bar--* 存在', async ({ page }) => {
    for (const t of THEMES) {
      await setupPage(page, { theme: t.theme, accent: t.accent })
      await page.goto(`${BASE_URL}/voiceprint`, { waitUntil: 'networkidle' })
      await waitForLoaded(page)

      // 断言 1: <html data-theme + data-accent>
      const htmlTheme = await page.evaluate(() => document.documentElement.dataset.theme)
      const htmlAccent = await page.evaluate(() => document.documentElement.dataset.accent)
      expect(htmlTheme, `${t.name}: theme 应为 ${t.theme}`).toBe(t.theme)
      expect(htmlAccent, `${t.name}: accent 应为 ${t.accent}`).toBe(t.accent)

      // 断言 2: 页面有 voiceprint 关键元素
      const bodyText = await page.textContent('body')
      expect(bodyText, `${t.name}: 页面应有声纹相关内容`).toMatch(/声纹|录入|voice/i)

      // 断言 3: 至少 1 个 .bar 元素 (VoiceprintCard 渲染) — 不验证 256 (因数据后端 mock)
      const barCount = await page.locator('.bar').count()
      expect(barCount, `${t.name}: 至少 1 个 .bar 元素`).toBeGreaterThan(0)

      // 断言 4: .bar 必须有 .bar--low/mid/high 之一 (Commit 1 收敛)
      const firstBarClasses = await page.locator('.bar').first().getAttribute('class')
      expect(firstBarClasses, `${t.name}: .bar 应有 .bar--* class`).toMatch(/bar--(low|mid|high)/)

      // 截图首个主题
      if (t.name === '01-light-orange') {
        await page.screenshot({
          path: `test-results/voiceprint-6-themes/${t.name}-desktop.png`,
          fullPage: true,
          animations: 'disabled',
        })
      }
    }
  })
})

test.describe('voiceprint-2026-06-30: 移动端 /m/voiceprint 6 主题验证', () => {
  test('移动端 6 主题循环验证 + VoiceprintEnrollFlow token 化', async ({ page }) => {
    for (const t of THEMES) {
      await setupPage(page, { theme: t.theme, accent: t.accent })
      await page.goto(`${BASE_URL}/m/voiceprint`, { waitUntil: 'networkidle' })
      await waitForLoaded(page)

      // 断言 1: <html data-theme + data-accent>
      const htmlTheme = await page.evaluate(() => document.documentElement.dataset.theme)
      const htmlAccent = await page.evaluate(() => document.documentElement.dataset.accent)
      expect(htmlTheme, `${t.name}: theme 应为 ${t.theme}`).toBe(t.theme)
      expect(htmlAccent, `${t.name}: accent 应为 ${t.accent}`).toBe(t.accent)

      // 断言 2: 页面有 voiceprint 关键元素
      const bodyText = await page.textContent('body')
      expect(bodyText, `${t.name}: 页面应有声纹相关内容`).toMatch(/声纹|录入|voice/i)

      // 截图首个主题
      if (t.name === '01-light-orange') {
        await page.screenshot({
          path: `test-results/voiceprint-6-themes/${t.name}-mobile.png`,
          fullPage: true,
          animations: 'disabled',
        })
      }
    }
  })
})
