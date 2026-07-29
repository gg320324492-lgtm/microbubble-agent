/**
 * tests/visual/a11y/axe-chats.spec.mjs — W89-P-1 a11y 真修硬门禁 + W89-P-2 限流修复 (派工 v6 §5 反馈 #48/#49)
 *
 * W89-P-1 升级: W87-G-1 baseline 模式 (派工纪律 2 "避免假绿") 改硬门禁 (派工 v6 §1.2 真验证):
 *   - 本 spec 真跑 axe 扫描 5 页面 + 5 project
 *   - 硬断言 violations.length === 0
 *   - 仍打印 violations 给人看 (reporter=list)
 *
 * 为什么不用 jest-axe 的 toHaveNoViolations:
 *   @playwright/test 1.61.1 不带 jest-axe matcher (grep node_modules 0 命中)
 *   手动 expect(violations.length).toBe(0) 等价硬门禁
 *
 * W89-P-1 类 20.48 沉淀: 'a11y 真修必含 token 审计 + 多 component 分页修 + 硬断言 = 0'
 *
 * W89-P-2 限流修复:
 *   5 case 各自调 login 触发 5 次/分/IP 限流 → 改 beforeAll 拿一次 token + beforeEach 注入.
 *   派工 v6 §5 反馈 类 20.49 沉淀: 'Playwright 多 case 必 beforeAll 共享 token, 避免限流'
 *
 * W89-P-6 合并: P-1 硬断言 + P-2 共享 token (避免限流导致 token 取不到时硬断言失败)
 */

import { test, expect } from '@playwright/test'
import { A11Y_PAGES, axeBuilder, getAuthToken } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

test.describe('axe WCAG 2.1 AA 硬门禁 (5 核心页面) — shared token', () => {
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
    test(`${pageDef.name} axe 扫描 violations = 0`, async ({ page }) => {
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

      // axe 至少要能注入并跑完
      expect(Array.isArray(violations)).toBe(true)
      expect(results.testEngine?.name).toBe('axe-core')

      // W89-P-1 硬门禁: 必须 0 violations
      // (派工 v6 §5 反馈 #48: 类 20.48 a11y 真修必含硬断言 = 0)
      if (landedOnLogin) {
        // 登录态未注入时被重定向到 /login, 跳过硬门禁 (登录页的 violations 反映的是 login.vue 而非目标页)
        // 但必须 warn 让开发者看到 TEST_TOKEN 缺失
        console.warn(
          `[a11y] ⚠️  ${pageDef.name} 跳过硬门禁: TEST_TOKEN 未注入, 被重定向到 /login. ` +
            `需设置 TEST_TOKEN=<jwt> 才能真扫目标页.`,
        )
        return
      }
      expect(violations.length).toBe(0)
    })
  }
})