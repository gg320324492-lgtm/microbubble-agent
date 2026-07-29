/**
 * tests/visual/a11y/axe-chats.spec.mjs — W89-P-1 a11y 真修硬门禁 (派工 v6 §5 反馈 #48)
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
 */

import { test, expect } from '@playwright/test'
import { A11Y_PAGES, axeBuilder, injectAuth } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'

test.describe('axe WCAG 2.1 AA 硬门禁 (5 核心页面 × 5 project)', () => {
  for (const pageDef of A11Y_PAGES) {
    test(`${pageDef.name} axe 扫描 violations = 0`, async ({ page }) => {
      const authed = await injectAuth(page, BASE_URL)

      await page.goto(`${BASE_URL}${pageDef.path}`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(1500) // SPA 首屏挂载

      const landedOnLogin = /\/login/.test(new URL(page.url()).pathname)

      const results = await axeBuilder(page).analyze()
      const violations = results.violations

      // 打印给人看 (reporter=list 会带出来)
      console.log(
        `\n[a11y] ${pageDef.name} (${pageDef.path}) → ${pageDef.target}` +
          `\n        TEST_TOKEN=${authed ? 'yes' : 'no'} url=${page.url()}` +
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
