/**
 * tests/visual/a11y/axe-chats.spec.mjs — W87-G-1 axe WCAG 2.1 AA 扫描 (报告型) + W89-P-2 限流修复
 *
 * 本 spec 只做"扫描 + 打印 violations", 不设硬断言:
 *   派工 brief 原写 expect(builder.analyze()).resolves.toHaveNoViolations(),
 *   但 toHaveNoViolations 是 jest-axe 的 matcher, @playwright/test 1.61.1 不带
 *   (已实测 grep node_modules/@playwright + playwright-core = 0 命中).
 *   且 brief 同时要求"不真修 a11y 漂移" — 用 toHaveNoViolations 会让有漂移的页面
 *   直接 fail, 与"记录漂移留 W88+"矛盾. 故硬门禁交给 a11y-baseline.spec.mjs 的
 *   baseline 比对, 本文件负责人读的清单.
 *
 * 用法: 见 playwright.a11y.config.mjs 顶部
 *
 * W89-P-2 限流修复:
 *   5 case 各自调 login 触发 5 次/分/IP 限流 → 改 beforeAll 拿一次 token + beforeEach 注入.
 *   派工 v6 §5 反馈 类 20.49 沉淀: 'Playwright 多 case 必 beforeAll 共享 token, 避免限流'
 */

import { test, expect } from '@playwright/test'
import { A11Y_PAGES, axeBuilder, injectAuth, getAuthToken } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

test.describe('axe WCAG 2.1 AA 扫描 (5 核心页面) — shared token', () => {
  // W89-P-2: beforeAll 拿一次 token, 避免 5 case 各自触发 5 次/分/IP 限流
  let sharedAuth
  test.beforeAll(async ({ request }) => {
    sharedAuth = await getAuthToken(request, { baseUrl: API_BASE_URL })
  })

  test.beforeEach(async ({ page }) => {
    // 注入 cookie + localStorage (沿用 injectAuth 形态, 仅 token 来源改为 sharedAuth)
    await page.context().addCookies([
      { name: 'access_token', value: sharedAuth.token, domain: new URL(BASE_URL).hostname, path: '/' },
    ])
    await page.addInitScript((tk) => {
      localStorage.setItem('access_token', tk)
    }, sharedAuth.token)
  })

  for (const pageDef of A11Y_PAGES) {
    test(`${pageDef.name} axe 扫描`, async ({ page }) => {
      await page.goto(`${BASE_URL}${pageDef.path}`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(1500) // SPA 首屏挂载

      const landedOnLogin = /\/login/.test(new URL(page.url()).pathname)

      const results = await axeBuilder(page).analyze()
      const violations = results.violations

      // 打印给人看 (reporter=list 会带出来)
      console.log(
        `\n[a11y] ${pageDef.name} (${pageDef.path}) → ${pageDef.target}` +
          `\n        TEST_TOKEN=${sharedAuth ? 'yes' : 'no'} url=${page.url()}` +
          (landedOnLogin ? '\n        ⚠️  被 router 守卫重定向到 /login — 扫到的是登录页不是目标页' : '') +
          `\n        violations=${violations.length}` +
          violations
            .map((v) => `\n          - ${v.id} [${v.impact}] ×${v.nodes.length}`)
            .join(''),
      )

      // axe 至少要能注入并跑完 (这是本 spec 的真断言)
      expect(Array.isArray(violations)).toBe(true)
      expect(results.testEngine?.name).toBe('axe-core')
    })
  }
})
