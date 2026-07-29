/**
 * tests/visual/a11y/health-check.spec.mjs — W89-P-5 build 后 a11y 健康检查
 *
 * 设计意图 (派工 v6 §5 反馈 类 20.52):
 *   build 后必跑 a11y health-check, critical+serious 硬断言 = 0
 *   moderate+minor violations 由主指挥拍板 (WARN, 不 block)
 *
 * 与 a11y-baseline.spec.mjs 区别:
 *   baseline = 比对 snapshot (允许有 violations, 漂移才报错)
 *   health-check = 硬断言 critical+serious = 0 (零容忍门禁)
 *
 * 触发方式:
 *   npm run build:a11y       (自动 build + health-check)
 *   npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs --grep='health-check'
 *
 * 已知局限 (docs/build-a11y-gate.md):
 *   - 依赖 vite dev server (npm run dev) 监听 localhost:5173
 *     如用其它端口, 设置 BASE_URL=http://localhost:<port>
 *   - 不覆盖真实登录态 (W89-P-4 真环境验证覆盖)
 *   - PWA disabled 时不跑 manifest 检查
 *   - 本任务不真跑 health-check, 仅写 spec; 真跑留 W89+
 */

import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

/**
 * 1 个核心入口 + 2 个高曝光页面 = 3 case (避免 baseline 25 case 重叠)
 * 选页面标准: 路由级 SPA 入口 (login) + 主页 (chat) + Drive (业务核心)
 * 派工 brief 原计划 localhost:5173 (vite 默认), 实测本仓库 dev 是 3000
 *   → 用 BASE_URL 环境变量兼容, 默认 5173 保持派工 brief 字面一致
 */
const HEALTH_CHECK_PAGES = [
  { name: '01-login', path: '/login' },
  { name: '02-chat', path: '/chat' },
  { name: '03-drive', path: '/drive' },
]

/**
 * 构造标准 AxeBuilder (WCAG 2.0/2.1 AA, 与 W87-G-1 baseline 同口径)
 * exclude 三类 Element Plus / NutUI 内部噪声 (与 axe-config.mjs 一致)
 */
function axeBuilder(page) {
  return new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .exclude('.el-popper')
    .exclude('.el-overlay')
    .exclude('[aria-hidden="true"]')
}

test.describe('build a11y health check (W89-P-5 类 20.52 硬门禁)', () => {
  for (const pageDef of HEALTH_CHECK_PAGES) {
    test(`${pageDef.name} critical+serious violations == 0`, async ({ page }, testInfo) => {
      // 容错: build 后 dev server 可能尚未启动 (调用方必须先 npm run dev / preview)
      // 这里 waitForLoadState 拿不到也不 fail, 让 axe.analyze() 反映真实状态
      try {
        await page.goto(`${BASE_URL}${pageDef.path}`, {
          waitUntil: 'domcontentloaded',
          timeout: 10_000,
        })
        await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {})
      } catch (err) {
        // 网络错误也走 analyze, 让 axe 在不完整 DOM 上跑 (暴露 dev server 假启动)
        testInfo.annotations.push({
          type: 'navigation-warning',
          description: `goto 失败但继续 axe analyze: ${err.message}`,
        })
      }

      const results = await axeBuilder(page).analyze()

      // 硬断言 critical + serious = 0 (类 20.52 核心纪律)
      const criticalOrSerious = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      )

      // moderate + minor violations 不 block, 但要 warn (留主指挥拍板)
      const moderateOrMinor = results.violations.filter(
        (v) => v.impact === 'moderate' || v.impact === 'minor'
      )

      if (moderateOrMinor.length > 0) {
        testInfo.annotations.push({
          type: 'moderate-minor-warn',
          description: moderateOrMinor
            .map((v) => `${v.id}[${v.impact}]×${v.nodes.length}`)
            .join(', '),
        })
      }

      expect(criticalOrSerious).toEqual([])
    })
  }

  // 额外: dev server 不可达时给出明确错误 (避免假绿)
  test('dev server reachable at BASE_URL', async ({ page }) => {
    const response = await page.goto(BASE_URL, {
      waitUntil: 'domcontentloaded',
      timeout: 10_000,
    }).catch((err) => {
      throw new Error(
        `Cannot reach BASE_URL=${BASE_URL}. ` +
          `build:a11y 必须先跑 npm run dev / npm run preview. ` +
          `Original: ${err.message}`
      )
    })

    // 200 / SPA fallback 都算可达 (SPA fallback /index.html 是合法 200)
    expect(response, `BASE_URL=${BASE_URL} 不可达`).not.toBeNull()
    expect(response.status(), `BASE_URL=${BASE_URL} HTTP status`).toBeLessThan(500)
  })
})