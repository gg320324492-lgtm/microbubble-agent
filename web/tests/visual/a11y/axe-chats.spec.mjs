/**
 * tests/visual/a11y/axe-chats.spec.mjs — W87-G-1 + W88-G-2 axe WCAG 2.1 AA 扫描
 *
 * 本 spec 只做"扫描 + 打印 violations", 不设硬断言:
 *   派工 brief 原写 expect(builder.analyze()).resolves.toHaveNoViolations(),
 *   但 toHaveNoViolations 是 jest-axe 的 matcher, @playwright/test 1.61.1 不带
 *   (已实测 grep node_modules/@playwright + playwright-core = 0 命中).
 *   且 brief 同时要求"不真修 a11y 漂移" — 用 toHaveNoViolations 会让有漂移的页面
 *   直接 fail, 与"记录漂移留 W88+"矛盾. 故硬门禁交给 a11y-baseline.spec.mjs 的
 *   baseline 比对, 本文件负责人读的清单.
 *
 * W88-G-2 升级 (派工 v6 §5 反馈 #20.42):
 *   - injectAuth 加 form login fallback (axe-config.mjs), 摆脱 TEST_TOKEN 依赖
 *   - 输出按 impact 分组的 violation 清单 (toViolationReport), 给 W89+ 派修用
 *   - 不删除老 baseline 快照, 但 report 明确标 auth=form 表示非 TEST_TOKEN 真值
 *
 * 用法: 见 playwright.a11y.config.mjs 顶部
 */

import { test, expect } from '@playwright/test'
import { A11Y_PAGES, axeBuilder, injectAuth, toViolationReport } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'

test.describe('axe WCAG 2.1 AA 扫描 (5 核心页面)', () => {
  for (const pageDef of A11Y_PAGES) {
    test(`${pageDef.name} 真登录态 axe 扫描`, async ({ page }) => {
      const authInfo = await injectAuth(page, BASE_URL)

      await page.goto(`${BASE_URL}${pageDef.path}`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(1500) // SPA 首屏挂载

      const landedOnLogin = /\/login/.test(new URL(page.url()).pathname)

      const results = await axeBuilder(page).analyze()

      // W88-G-2: 按 impact 分组的清单 (类 20.42)
      const report = toViolationReport(results, pageDef, authInfo)
      console.log(`\n[a11y-real] ${report}`)

      if (landedOnLogin) {
        console.log(
          `\n[a11y-real] ⚠️  ${pageDef.name} 仍被 router 守卫重定向到 /login — ` +
            `扫到的是登录页不是目标页 (auth=${authInfo.mode})`,
        )
      }

      // axe 至少要能注入并跑完 (这是本 spec 的真断言)
      expect(Array.isArray(results.violations)).toBe(true)
      expect(results.testEngine?.name).toBe('axe-core')
      // W88-G-2: 顺手 assert 拿到了真登录态, 否则报告无效
      expect(authInfo.authed, `未拿到真登录态 (mode=${authInfo.mode})`).toBe(true)
      expect(landedOnLogin, `${pageDef.name} 路由到 /login, axe 扫的是登录页`).toBe(false)
    })
  }
})