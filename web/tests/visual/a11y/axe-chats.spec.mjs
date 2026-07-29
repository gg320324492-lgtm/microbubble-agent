/**
 * tests/visual/a11y/axe-chats.spec.mjs — W87-G-1 axe WCAG 2.1 AA 扫描 (报告型)
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
 */

import { test, expect } from '@playwright/test'
import { A11Y_PAGES, axeBuilder, injectAuth } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'

test.describe('axe WCAG 2.1 AA 扫描 (5 核心页面)', () => {
  for (const pageDef of A11Y_PAGES) {
    test(`${pageDef.name} axe 扫描`, async ({ page }) => {
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

      // axe 至少要能注入并跑完 (这是本 spec 的真断言)
      expect(Array.isArray(violations)).toBe(true)
      expect(results.testEngine?.name).toBe('axe-core')
    })
  }
})
