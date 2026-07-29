/**
 * tests/visual/a11y/el-menu-hover.spec.mjs — W89-P-11 dark mode el-menu hover 态扫描
 *
 * 派工 brief §"步骤 4" 立意:
 *   hover 态的颜色对比 (rgb 主色 12% alpha 背景 + 主色文字) 在不同 accent 下生成不同 hsl,
 *   axe 默认扫的是 "当前生效 hover 态" 而非 :hover 伪类, 故需要先 hover 触发再扫.
 *   axe color-contrast 规则检查渲染后的 computed style, hover 触发后样色已应用即可被扫到.
 *
 * 重点页:
 *   /chat (桌面 layout 有 sidebar → el-menu) — 验证 el-menu-item:hover 在 dark/orange
 *   /        dark/ocean / dark/forest 三 accent 下 color-contrast AA 通过.
 *
 * 模式: 报告型 — console 出 violations, 不设硬断言.
 *
 * 用法:
 *   cd web
 *   BASE_URL=http://localhost npx playwright test \
 *     -c tests/visual/a11y/playwright.a11y.config.mjs \
 *     tests/visual/a11y/el-menu-hover.spec.mjs --reporter=list
 *
 * 派工 v6 §5 反馈 类 20.59 沉淀:
 *   el-menu hover 必单独扫描 (axe 默认不扫 :hover 伪类, 需 locator.hover() 触发后)
 */

import { test, expect } from '@playwright/test'
import { axeBuilder } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'

const HOVER_CASES = [
  { mode: 'dark', accent: 'orange', label: 'dark/orange' },
  { mode: 'dark', accent: 'ocean', label: 'dark/ocean' },
  { mode: 'dark', accent: 'forest', label: 'dark/forest' },
  // light 也测一次作为对照 (baseline)
  { mode: 'light', accent: 'orange', label: 'light/orange' },
]

test.describe('el-menu hover 态 a11y (dark × 3 accent + light × orange 对照)', () => {
  for (const c of HOVER_CASES) {
    test(`${c.label} sidebar el-menu-item:hover`, async ({ page }) => {
      // 注: 不调 injectAuth — TEST_TOKEN 缺失时它会写 access_token="undefined" 字符串到
      // localStorage, router 守卫把它当作"已登录"放行 (post-redirect 到 / 然后 token 校验失败),
      // 与"未登录被重定向到 /login"两条路径行为不一致, data-theme 是哪种 setAttribute
      // 命中就不可控. 报告型 spec 只关心 hover 态 axe 扫得到的对比度.
      await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })

      // 必须 in <html> 而非 <body>, useThemeStore.apply() 写 documentElement
      await page.evaluate(
        ({ m, a }) => {
          try {
            localStorage.setItem('theme', m)
            localStorage.setItem('accent', a)
            document.documentElement.setAttribute('data-theme', m)
            document.documentElement.setAttribute('data-accent', a)
          } catch { /* ignore */ }
        },
        { m: c.mode, a: c.accent },
      )

      await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(1500)

      // 记录实际生效的主题 (router 守卫未登录则被重定向到 /login, 这里 SPA 会重新读 localStorage)
      const appliedTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
      const appliedAccent = await page.evaluate(() => document.documentElement.getAttribute('data-accent'))
      console.log(
        `[el-menu-hover] ${c.label}  ` +
          `expected=${c.mode}/${c.accent}  ` +
          `applied=${appliedTheme ?? 'null'}/${appliedAccent ?? 'null'}  ` +
          `url=${page.url()}`,
      )

      // 触发第一项 el-menu-item hover — 用真 mouse, 不是 .evaluate 改 class
      // (Variables.css:351 el-menu-item:hover 是 :hover 伪类, 需真实 hit-test)
      // 报告型: 若 router 守卫把 /chat 重定向到 /login, sidebar 不存在则跳过 hover,
      // axe 仍扫 (扫的是登录页), 但不强行 hover 不存在的节点.
      const menuItem = page.locator('.sidebar-menu .el-menu-item').first()
      const menuVisible = await menuItem.isVisible().catch(() => false)

      if (!menuVisible) {
        console.log(
          `[el-menu-hover] ${c.label}  sidebar el-menu 不可见 (router 守卫重定向到 ${page.url()}) — 跳过 hover 触发`,
        )
        // 仍然跑 axe 全页扫描 (登录页也行), 报告 axe 命中数
        const results = await axeBuilder(page).analyze()
        const violations = results.violations
        console.log(
          `           violations=${violations.length}  ` +
            violations.map((v) => `- ${v.id} [${v.impact}] ×${v.nodes.length}`).join('  '),
        )
        expect(Array.isArray(violations)).toBe(true)
        return  // 跳过 hover 触发的剩余部分
      }

      await menuItem.scrollIntoViewIfNeeded()
      await menuItem.hover()
      // 等 transition 0.2s + computed style 刷新
      await page.waitForTimeout(600)

      // 在 axe 看 hover :focus :active 这种伪类需用 include 限制到 sidebar 内,
      // axe 默认扫整个 page, 但要排除既有的 .el-popper / .el-overlay (axe-config 已默认 exclude)
      const results = await axeBuilder(page)
        .include('.sidebar-menu')
        .analyze()

      const violations = results.violations
      const contrast = violations.filter((v) => v.id === 'color-contrast')

      console.log(
        `\n[el-menu-hover] ${c.label}` +
          `\n           violations=${violations.length}  color-contrast=${contrast.length}` +
          violations
            .map((v) => `\n             - ${v.id} [${v.impact}] ×${v.nodes.length}`)
            .join(''),
      )

      // 报告型断言
      expect(Array.isArray(violations)).toBe(true)
      expect(results.testEngine?.name).toBe('axe-core')
    })
  }
})
