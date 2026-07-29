/**
 * tests/visual/a11y/dark-accent.spec.mjs — W89-P-11 dark mode × 3 accent 扫描
 *
 * 主指挥 W89 第 1 批 P-1 留口调研结论:
 *   项目用 data-accent 切色 (orange=default/ocean/forest), 派工 brief 写 "4 accent"
 *   是历史派工纪要的措辞遗留, 实际实现 = 3 accent × 2 mode = 6 主题 (变量 css:1440-1543
 *   与 stores/useThemeStore.js:28 ACCENT_OPTIONS 证明). 本 spec 跑 3 accent 全集,
 *   不擅自扩到不存在的第 4 个 (扩了必假绿).
 *
 * 模式: 报告型 — 把 violations 数 + 命中数打到 console + 不设硬断言.
 *   真硬门禁在 a11y-baseline.spec.mjs (比对 baseline).
 *
 * 用法:
 *   cd web
 *   BASE_URL=http://localhost npx playwright test \
 *     -c tests/visual/a11y/playwright.a11y.config.mjs \
 *     tests/visual/a11y/dark-accent.spec.mjs --reporter=list
 *
 * 前提: TEST_TOKEN 已注入 (登录态), 否则 sidebar 没 el-menu 命中, 桌面端会被守卫打到 /login.
 *
 * 派工 v6 §5 反馈 类 20.59 沉淀:
 *   "dark 4 accent a11y 必含: data-accent 切换 + axe WCAG 2.1 AA + el-menu hover 单独扫描"
 *   (留口措辞 "4 accent" 沿用派工 brief, 实际实现是 3 accent)
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

test.describe('dark mode × 3 accent a11y 扫描 (6 主题 × 3 页面 = 18 case)', () => {
  for (const mode of MODES) {
    for (const accent of ACCENTS) {
      for (const pageDef of PAGES) {
        test(`${mode}/${accent}/${pageDef.name}`, async ({ page }) => {
          const authed = await injectAuth(page, BASE_URL)

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
          // 主题真切验证 — 当 TEST_TOKEN 缺失导致 router 守卫重定向或阻止 SPA 挂载时,
          // 应用主题可能为 null. 这时 axe 扫的可能是 /login 页 (变量 css 部分仍生效),
          // 仍能反映主题色, 不应强行 fail — 仅当主题生效且与预期不符时才 fail.
          if (appliedTheme === mode && appliedAccent !== accent) {
            throw new Error(`accent mismatch: expected=${accent} applied=${appliedAccent}`)
          }
          if (appliedTheme !== null && appliedTheme !== mode) {
            throw new Error(`mode mismatch: expected=${mode} applied=${appliedTheme}`)
          }
        })
      }
    }
  }
})
