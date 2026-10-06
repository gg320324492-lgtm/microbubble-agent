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

      // S3.20 渲染证据 (render-evidence): "<正文非空白字符数>:<可见元素数>"
      //
      // 为什么必须记这个 —— `violations: 0` **不能**证明扫到了真实页面。
      // S3.20 本地实测 (app-test:8001 + vite + 真 JWT, 5 页面 × 5 project):
      //   真实内容页   viol=0  证据 71:55 / 88:74 / 129:104 / 232:103 / 468:224 ...
      //   **登录页**   viol=1  证据 272:50 (desktop) / 75:26 (mobile)
      //   **空白页**   viol=0  证据 0:0        ← 与真实页同为 0 违规!
      // 即"空白页"和"真修好的页"在 violations 上完全同形, 类 20.25 的
      // "全绿即可疑"因此无法区分二者 (且历史上 7b8ea2b0d 真 0 被当假绿改回 10,
      // 1ae5699ad 又把假 0 放过 —— 两个方向都误判过)。
      // 可见元素数才是有判别力的那一维: 登录页 50/26, 真实页最小 55, 空白页 0。
      //
      // 为什么记两个数: 正文长度**单独不可用** —— 实测登录页 272 字符 > 真实页
      // 88 字符 (桌面视口), 直接比长度会把真页判成假页; 与可见元素数组成对后
      // 判别力才成立 (272:50 与 88:74 不会混淆)。
      //
      // 稳定性 (决定能否进基线做逐字节比对): 连续 3 轮 × 5 project 实测,
      // 同一 (页面, 视口) 的值**逐字符一致**; 3 个同视口 project 值也相同。
      const evidence = await page.evaluate(() => {
        const visible = [...document.querySelectorAll('body *')].filter((e) => {
          const r = e.getBoundingClientRect()
          return r.width > 0 && r.height > 0
        }).length
        return `${(document.body.innerText || '').trim().length}:${visible}`
      })

      // W98 debug: 临时加 target 看 CI 上真实违规元素
      const targets = results.violations.flatMap(v => v.nodes.map(n => `  ${v.id} → ${JSON.stringify(n.target)}`))

      const report = [
        `page: ${pageDef.name}  route: ${pageDef.path}`,
        `target: ${pageDef.target}`,
        `project: ${testInfo.project.name}`,
        `authed: ${authed ? 'yes' : 'no'}   redirected-to-login: ${landedOnLogin ? 'yes' : 'no'}`,
        `render-evidence: ${evidence}`,
        `violations: ${rows.length}`,
        ...rows.map((r) => `  ${r.id} [${r.impact}] ×${r.nodes}`),
        ...targets,
      ].join('\n')

      expect(report).toMatchSnapshot(`${pageDef.name}.txt`)
    })
  }
})
