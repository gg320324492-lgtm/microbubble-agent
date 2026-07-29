/**
 * tests/visual/a11y/auth-shared-token.spec.mjs — W89-P-2 a11y 限流门禁 (shared token) + W89-P-6 硬门禁
 *
 * W88-G-2 报告: mobile-comments 5 case 因 login API 429 限流失败.
 *   根因: 5 case 各自调 /api/v1/auth/login → 5 次/分/IP 限流 (app/api/v1/auth.py:77 + 91-92 record).
 *
 * W89-P-2 修法:
 *   beforeAll 共享 token (本 spec 一次 login 拿 1 个 JWT, 5 case 复用)
 *   beforeEach 注入 cookie + localStorage (沿用 injectAuth 形态)
 *   硬门禁: 必须通过限流 (token 注入后, 不被 router 守卫重定向到 /login)
 *
 * W89-P-6 升级 (P-1 cherry-pick + 重建 dist 后):
 *   critical/serious violations 必须为 [] (硬断言)
 *   派工 v6 §5 反馈 类 20.50 沉淀: 'a11y baseline 重 sync 必 cherry-pick 修复 commit +
 *   --update-snapshots + 硬断言 = 0'
 *   注: 仅锁 critical/serious, 留 minor 余地 (region / landmark 等 axe 误报常见)
 *
 * 派工 v6 §5 反馈 类 20.49 沉淀: 'Playwright 多 case 必 beforeAll 共享 token, 避免触发后端限流'
 *
 * 跑法:
 *   cd web
 *   API_BASE_URL=http://localhost:8000 \
 *     npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs \
 *     --project=mobile-comments tests/visual/a11y/auth-shared-token.spec.mjs
 *
 * 预期 (W89-P-6 范围): 5 case PASS (mobile-comments 项目下 5 路由 × shared token,
 *   全不被路由守卫打回 /login + critical/serious violations = []).
 */

import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { getAuthToken } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

const PAGES = ['/chat', '/drive', '/tasks', '/meetings', '/knowledge']

test.describe('mobile-comments a11y - shared token (W89-P-2 限流修复)', () => {
  // W89-P-2: 整个 describe 共享 1 个 token, 不触发 5 次/分/IP 限流
  let sharedToken

  test.beforeAll(async ({ request }) => {
    const auth = await getAuthToken(request, { baseUrl: API_BASE_URL })
    sharedToken = auth.token
    expect(sharedToken).toBeTruthy()
    expect(sharedToken.length).toBeGreaterThan(20) // JWT 必 > 20 字符
  })

  for (const route of PAGES) {
    test(`mobile-comments ${route} a11y (shared token)`, async ({ page }) => {
      // 1. 先到 /login 让 origin 一致 (cookie 才能写到正确 domain)
      await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })

      // 2. 注入共享 token (cookie + localStorage 双注入)
      await page.context().addCookies([
        {
          name: 'access_token',
          value: sharedToken,
          domain: new URL(BASE_URL).hostname,
          path: '/',
        },
      ])
      await page.addInitScript((tk) => {
        localStorage.setItem('access_token', tk)
      }, sharedToken)

      // 3. 跳目标页
      await page.goto(`${BASE_URL}${route}`, { waitUntil: 'domcontentloaded' })
      await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
      await page.waitForTimeout(1500) // SPA 路由级组件挂载

      // 4. 跑 axe (WCAG 2.1 AA, 排除 EP 噪声)
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .exclude('.el-popper')
        .exclude('.el-overlay')
        .exclude('[aria-hidden="true"]')
        .analyze()

      // 报告型 (硬门禁交给 W89-P-1 cherry-pick 后)
      const criticalOrSerious = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious',
      )

      // 5. 限流门禁: 必须通过限流 (token 注入生效, 不重定向 /login) — W89-P-2 唯一目标
      const landedOnLogin = /\/login/.test(new URL(page.url()).pathname)

      console.log(
        `\n[a11y-shared] ${route}` +
          `\n        url=${page.url()}` +
          (landedOnLogin ? '\n        ❌ 重定向到 /login (token 未生效)' : '') +
          `\n        total violations=${results.violations.length}` +
          `\n        critical/serious=${criticalOrSerious.length}` +
          criticalOrSerious.map((v) => `\n          - ${v.id} [${v.impact}] ×${v.nodes.length}`).join(''),
      )

      // W89-P-2 硬门禁: 通过限流 + 路由守卫, **不要** 锁 a11y violations
      //   W89-P-2 范围 = 修 "5 次/分/IP login 限流" (1 个根因)
      //   真实 critical/serious violations (aria-command-name / color-contrast / nested-interactive)
      //   已经在 base 5ace8015e 上存在, 属 W89-P-1 mobile-comments a11y 修复范围 (派工依赖).
      //   本 spec 把 violations 写入 console 报告, 留给 W89-P-1 cherry-pick 后转硬断言.
      expect(landedOnLogin).toBe(false)

      // W89-P-6 硬门禁: P-1 cherry-pick + 重建 dist 后, critical/serious violations 必须为 0.
      //   派工 v6 §5 反馈 类 20.50 沉淀: 'a11y baseline 重 sync 必 cherry-pick 修复 commit +
      //   --update-snapshots + 硬断言 = 0'. 注意: 不锁 total violations, 只锁 critical/serious,
      //   避免 axe minor 误报 (e.g. region, landmark) 把 case 拖红.
      expect(criticalOrSerious).toEqual([])

      // 报告型断言: 收集已知 violation 留给下游 (基线 + 修复对比)
      const reportRow = {
        route,
        url: page.url(),
        total: results.violations.length,
        criticalOrSerious: criticalOrSerious.length,
        byRule: criticalOrSerious.map((v) => `${v.id}:${v.nodes.length}`),
      }
      if (!globalThis.__W89_P2_A11Y_REPORT__) globalThis.__W89_P2_A11Y_REPORT__ = []
      globalThis.__W89_P2_A11Y_REPORT__.push(reportRow)
    })
  }
})
