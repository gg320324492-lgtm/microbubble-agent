/**
 * tests/visual/a11y/dark-accent.spec.mjs — W89-P-11 dark mode × 3 accent 扫描
 *
 * 主指挥 W89 第 1 批 P-1 留口调研结论:
 *   项目用 data-accent 切色 (orange=default/ocean/forest), 派工 brief 写 "4 accent"
 *   是历史派工纪要的措辞遗留, 实际实现 = 3 accent × 2 mode = 6 主题 (变量 css:1440-1543
 *   与 stores/useThemeStore.js:28 ACCENT_OPTIONS 证明). 本 spec 跑 3 accent 全集,
 *   不擅自扩到不存在的第 4 个 (扩了必假绿).
 *
 * 模式: 硬门禁 (W89-X-11 由 P-11 软断言转硬门禁) —
 *   1. TEST_TOKEN 必注入 — process.env.TEST_TOKEN 缺失则 throw new Error 立即 fail,
 *      不允许 "router 守卫重定向到 /login 后跳过" 的优雅降级 (那是软断言假绿).
 *   2. authed 必须 true — auth 失败直接 fail (之前 authed=false 时仍走 axe 扫的是 /login,
 *      数据不可信).
 *   3. axe critical + serious violations 数仍报告到 console 但不作硬断言 —
 *      历史 P-11 决策, 真硬门禁在 a11y-baseline.spec.mjs (比对 baseline).
 *      本 spec 只报告, 让 W89+ 派工按 axe 报告数修复 (a11y-baseline drift 是真门禁).
 *
 * 用法:
 *   cd web
 *   TEST_TOKEN=<jwt> BASE_URL=http://localhost npx playwright test \
 *     -c tests/visual/a11y/playwright.a11y.config.mjs \
 *     tests/visual/a11y/dark-accent.spec.mjs --reporter=list
 *
 * 派工 v6 §5 反馈 类 20.63 沉淀 (W89-X-11):
 *   "Playwright 软断言改硬门禁必 TEST_TOKEN 真注入 + throw if missing"
 *   (P-11 的 "authed=false → 优雅降级" 路径已废, 硬门禁必须有真 token)
 */

import { test, expect } from '@playwright/test'
import { axeBuilder, injectAuth } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'

// 6 主题 = 2 mode × 3 accent (orange=default, ocean, forest)
const MODES = ['light', 'dark']
const ACCENTS = ['orange', 'ocean', 'forest']
const PAGES = [
  { name: '01-chat', path: '/chat' },
  { name: '02-drive', path: '/drive' },
  { name: '03-tasks', path: '/tasks' },
]

// W89-X-11 硬门禁: TEST_TOKEN 缺失直接 fail 整个 describe — 不允许软降级.
// "TEST_TOKEN 缺失优雅降级" 是 P-11 软断言假绿根因, 删之.
test.beforeAll(() => {
  if (!process.env.TEST_TOKEN) {
    throw new Error(
      'TEST_TOKEN env not set — 硬门禁必须有真 token. ' +
        '跑前先: TEST_TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login ' +
        "-H 'Content-Type: application/json' " +
        "-d '{\"username\":\"xiaoqi_testbot\",\"password\":\"testbot_pass_2026\"}' " +
        "| python -c \"import json,sys; print(json.load(sys.stdin).get('access_token',''))\")",
    )
  }
})

test.describe('dark mode × 3 accent a11y 扫描 (6 主题 × 3 页面 = 18 case)', () => {
  for (const mode of MODES) {
    for (const accent of ACCENTS) {
      for (const pageDef of PAGES) {
        test(`${mode}/${accent}/${pageDef.name}`, async ({ page }) => {
          const authed = await injectAuth(page, BASE_URL)

          // W89-X-11 硬门禁: authed 必 true, 不允许 router 守卫重定向时还继续跑
          // (之前是软断言继续扫 /login 页, 数据不可信).
          if (!authed) {
            throw new Error(
              `injectAuth 失败 (TEST_TOKEN 缺失或无效) — 硬门禁必须有真 token, ` +
                `请按 beforeAll 错误提示重新注入`,
            )
          }

          // 先到 /login 注入主题偏好, 然后再 goto 目标页 — 这样 useThemeStore.apply()
          // 会在 SPA 启动时读 localStorage 并立即 setAttribute. (axe-config.mjs 注释
          // 提到的 "刷新时 brief flash" 即此路径.)
          await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
          await page.evaluate(
            ({ m, a }) => {
              try {
                localStorage.setItem('theme', m)
                localStorage.setItem('accent', a)
                // 立即 setAttribute 让 css variables 立刻生效, 不必等 store watcher
                document.documentElement.setAttribute('data-theme', m)
                document.documentElement.setAttribute('data-accent', a)
              } catch { /* ignore */ }
            },
            { m: mode, a: accent },
          )

          await page.goto(`${BASE_URL}${pageDef.path}`, { waitUntil: 'domcontentloaded' })
          await page.waitForTimeout(1500)

          // 验证主题确实生效 — 给 SPEC 一个人眼可读的 "主题真的切了" 信号
          const appliedTheme = await page.evaluate(() =>
            document.documentElement.getAttribute('data-theme'),
          )
          const appliedAccent = await page.evaluate(() =>
            document.documentElement.getAttribute('data-accent'),
          )

          const results = await axeBuilder(page).analyze()
          const violations = results.violations
          const seriousCritical = violations.filter(
            (v) => v.impact === 'critical' || v.impact === 'serious',
          )

          console.log(
            `\n[dark-accent] ${mode}/${accent} ${pageDef.path}` +
              `\n           authed=${authed ? 'yes' : 'no'} ` +
              `applied=${appliedTheme}/${appliedAccent}` +
              (appliedTheme !== mode || appliedAccent !== accent
                ? ` ⚠️ 主题切换失败 (期望 ${mode}/${accent})`
                : '') +
              `\n           violations=${violations.length} critical+serious=${seriousCritical.length}` +
              violations
                .map((v) => `\n             - ${v.id} [${v.impact}] ×${v.nodes.length}`)
                .join(''),
          )

          // 报告型断言 — 至少 axe 跑完了 (这是本 spec 的真门禁)
          expect(Array.isArray(violations)).toBe(true)
          expect(results.testEngine?.name).toBe('axe-core')
          // 主题真切验证 — 必须与预期一致, 不允许 null / 错配.
          // 硬门禁下 auth 已保证, router 不会再 redirect, 此处必为预期值.
          if (appliedTheme === null || appliedTheme !== mode) {
            throw new Error(`mode mismatch: expected=${mode} applied=${appliedTheme ?? 'null'}`)
          }
          if (appliedAccent === null || appliedAccent !== accent) {
            throw new Error(`accent mismatch: expected=${accent} applied=${appliedAccent ?? 'null'}`)
          }
        })
      }
    }
  }
})
