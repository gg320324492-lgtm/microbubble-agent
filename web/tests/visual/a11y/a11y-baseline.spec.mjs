/**
 * tests/visual/a11y/a11y-baseline.spec.mjs — W87-G-1 a11y baseline 门禁
 *
 * baseline 模式 (派工纪律 2 "避免假绿"):
 *   首次 --update-snapshots 生成 __snapshots__/{name}-{project}.txt 记录当前 violations
 *   后续跑比对; 新增 violation = 漂移 = fail, 修好 violation 也 fail (提示更新 baseline)
 *
 * 5 页面 × 5 project = 25 case.
 *
 * W88-G-2 警告 (派工 v6 §5 反馈 #20.42):
 *   本 baseline 25 快照都是 "redirected-to-login: yes", 实际拍的是登录页, 不是目标页.
 *   W88-G-2 已切 axe-chats.spec.mjs 到真登录态, 拿真 violation 清单留 W89+ 修.
 *   本 baseline spec 暂保留作为 fallback, 但跑前**必须** 意识到快照意义已被锚定
 *   为"登录页 a11y 现状", 不是"目标页 a11y 现状". 要重生成有意义 baseline, 等 W89+
 *   派修 violation 之后, 用真登录态重新 --update-snapshots.
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
      const authInfo = await injectAuth(page, BASE_URL)

      await page.goto(`${BASE_URL}${pageDef.path}`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(1500)

      const results = await axeBuilder(page).analyze()
      const rows = toBaseline(results)
      const landedOnLogin = /\/login/.test(new URL(page.url()).pathname)

      const report = [
        `page: ${pageDef.name}  route: ${pageDef.path}`,
        `target: ${pageDef.target}`,
        `project: ${testInfo.project.name}`,
        `auth: ${authInfo.mode} (${authInfo.authed ? 'OK' : 'FAILED'})`,
        `authed: ${authInfo.authed ? 'yes' : 'no'}   redirected-to-login: ${landedOnLogin ? 'yes' : 'no'}`,
        `violations: ${rows.length}`,
        ...rows.map((r) => `  ${r.id} [${r.impact}] ×${r.nodes}`),
      ].join('\n')

      expect(report).toMatchSnapshot(`${pageDef.name}.txt`)
    })
  }
})