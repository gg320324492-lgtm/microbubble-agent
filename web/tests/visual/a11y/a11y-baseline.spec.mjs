/**
 * tests/visual/a11y/a11y-baseline.spec.mjs — W87-G-1 a11y baseline 门禁
 *
 * baseline 模式 (派工纪律 2 "避免假绿"):
 *   首次 --update-snapshots 生成 __snapshots__/{name}-{project}.txt 记录当前 violations
 *   后续跑比对; 新增 violation = 漂移 = fail, 修好 violation 也 fail (提示更新 baseline)
 *
 * 5 页面 × 5 project = 25 case.
 *
 * baseline 内容用 toBaseline() 压成 `ruleId [impact] ×N` 行, 不存 node.html —
 * html 片段每次渲染都可能变 (时间戳/随机 id), 存进 baseline 必假红.
 */

import { test, expect } from '@playwright/test'
import { A11Y_PAGES, axeBuilder, injectAuth, toBaseline } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'

test.describe('a11y baseline 比对 (5 页面 × 5 project = 25 case)', () => {
  for (const pageDef of A11Y_PAGES) {
    test(`${pageDef.name} baseline`, async ({ page }, testInfo) => {
      const authed = await injectAuth(page, BASE_URL)

      await page.goto(`${BASE_URL}${pageDef.path}`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(1500)

      // W93: SPA 路由跳转 (→/dashboard) 可能与 axe 注入竞态 → retry
      let results
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          results = await axeBuilder(page).analyze()
          break
        } catch (err) {
          if (attempt === 3) throw err
          console.log(`[a11y] analyze retry ${attempt}/3 (${err.message?.slice(0, 60)})`)
          await page.waitForTimeout(1000)
        }
      }
      const rows = toBaseline(results)
      const landedOnLogin = /\/login/.test(new URL(page.url()).pathname)

      // W98 debug: 临时加 target 看 CI 上真实违规元素
      const targets = results.violations.flatMap(v => v.nodes.map(n => `  ${v.id} → ${JSON.stringify(n.target)}`))

      const report = [
        `page: ${pageDef.name}  route: ${pageDef.path}`,
        `target: ${pageDef.target}`,
        `project: ${testInfo.project.name}`,
        `authed: ${authed ? 'yes' : 'no'}   redirected-to-login: ${landedOnLogin ? 'yes' : 'no'}`,
        `violations: ${rows.length}`,
        ...rows.map((r) => `  ${r.id} [${r.impact}] ×${r.nodes}`),
        ...targets,
      ].join('\n')

      expect(report).toMatchSnapshot(`${pageDef.name}.txt`)
    })
  }
})
