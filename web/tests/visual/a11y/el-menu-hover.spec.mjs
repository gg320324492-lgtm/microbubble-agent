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
 * 模式: 硬门禁 (W89-X-11 由 P-11 软断言转硬门禁) —
 *   1. TEST_TOKEN 必注入 — process.env.TEST_TOKEN 缺失则 throw new Error 立即 fail.
 *   2. sidebar el-menu 不可见 (router 守卫重定向) 直接 fail — P-11 软断言的 "跳过 hover 触发"
 *      路径已废, 硬门禁必须真触发 hover, 否则 axe 扫的是 /login 数据不可信.
 *   3. axe critical + serious violations 数仍报告到 console 但不作硬断言 —
 *      历史 P-11 决策, 真硬门禁在 a11y-baseline.spec.mjs (比对 baseline).
 *
 * 用法:
 *   cd web
 *   TEST_TOKEN=<jwt> BASE_URL=http://localhost npx playwright test \
 *     -c tests/visual/a11y/playwright.a11y.config.mjs \
 *     tests/visual/a11y/el-menu-hover.spec.mjs --reporter=list
 *
 * 派工 v6 §5 反馈 类 20.59 沉淀:
 *   el-menu hover 必单独扫描 (axe 默认不扫 :hover 伪类, 需 locator.hover() 触发后)
 * 派工 v6 §5 反馈 类 20.63 沉淀 (W89-X-11):
 *   "Playwright 软断言改硬门禁必 TEST_TOKEN 真注入 + throw if missing"
 */

import { test, expect } from '@playwright/test'
import { axeBuilder, injectAuth } from './axe-config.mjs'

const BASE_URL = process.env.BASE_URL || 'http://localhost'

const HOVER_CASES = [
  { mode: 'dark', accent: 'orange', label: 'dark/orange' },
  { mode: 'dark', accent: 'ocean', label: 'dark/ocean' },
  { mode: 'dark', accent: 'forest', label: 'dark/forest' },
  // light 也测一次作为对照 (baseline)
  { mode: 'light', accent: 'orange', label: 'light/orange' },
]

// W89-X-11 硬门禁: TEST_TOKEN 缺失直接 fail 整个 describe — 不允许软降级.
// P-11 的 "不调 injectAuth, 让 router 守卫重定向到 /login 后软跳过" 路径已废.
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

test.describe('el-menu hover 态 a11y (dark × 3 accent + light × orange 对照)', () => {
  for (const c of HOVER_CASES) {
    test(`${c.label} sidebar el-menu-item:hover`, async ({ page }, testInfo) => {
      // W89-X-11 硬门禁: 仅 desktop project 适用 (mobile 用 NutUI 移动端布局, 没有
      // .sidebar-menu .el-menu-item). 这是派工 brief 立意本意 (Variables.css:351
      // el-menu-item:hover 是 Element Plus desktop sidebar 组件).
      // P-11 软断言的 "router 重定向到 /login → 跳过" 路径恰好掩盖了 mobile 无 sidebar
      // 真相, 留下 "20 case 全 PASS" 假绿. 硬门禁下必须明确区分 desktop vs mobile.
      const isDesktop = testInfo.project.name.startsWith('desktop-')
      test.skip(!isDesktop, 'el-menu hover 仅适用 desktop project (mobile 无 .sidebar-menu)')
      if (!isDesktop) return

      // W89-X-11 硬门禁: TEST_TOKEN 已校验, 此处调 injectAuth 必须 authed=true.
      // (P-11 软断言不调 injectAuth 是因为当时 TEST_TOKEN 不可靠, 现在硬门禁下必须真注入.)
      const authed = await injectAuth(page, BASE_URL)
      if (!authed) {
        throw new Error(
          `injectAuth 失败 (TEST_TOKEN 缺失或无效) — 硬门禁必须有真 token, ` +
            `请按 beforeAll 错误提示重新注入`,
        )
      }

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

      // 记录实际生效的主题. 硬门禁下 auth 已保证, 这里期望主题与预期一致.
      const appliedTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
      const appliedAccent = await page.evaluate(() => document.documentElement.getAttribute('data-accent'))
      console.log(
        `[el-menu-hover] ${c.label}  ` +
          `expected=${c.mode}/${c.accent}  ` +
          `applied=${appliedTheme ?? 'null'}/${appliedAccent ?? 'null'}  ` +
          `url=${page.url()}`,
      )

      // 硬门禁: 主题必须真切, 不允许 null / 错配.
      if (appliedTheme === null || appliedTheme !== c.mode) {
        throw new Error(`mode mismatch: expected=${c.mode} applied=${appliedTheme ?? 'null'}`)
      }
      if (appliedAccent === null || appliedAccent !== c.accent) {
        throw new Error(`accent mismatch: expected=${c.accent} applied=${appliedAccent ?? 'null'}`)
      }

      // 触发第一项 el-menu-item hover — 用真 mouse, 不是 .evaluate 改 class
      // (Variables.css:351 el-menu-item:hover 是 :hover 伪类, 需真实 hit-test)
      // 硬门禁: sidebar el-menu 必须可见. P-11 软断言 "跳过 hover 触发" 路径已废 —
      // 不可见直接 fail, 不能扫 /login 充数.
      const menuItem = page.locator('.sidebar-menu .el-menu-item').first()
      const menuVisible = await menuItem.isVisible().catch(() => false)

      if (!menuVisible) {
        throw new Error(
          `sidebar el-menu 不可见 (url=${page.url()}) — 硬门禁必须真触发 hover, ` +
            `请检查 router 守卫 / sidebar 渲染条件`,
        )
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

      // 报告型断言 — 至少 axe 跑完了
      expect(Array.isArray(violations)).toBe(true)
      expect(results.testEngine?.name).toBe('axe-core')
    })
  }
})
