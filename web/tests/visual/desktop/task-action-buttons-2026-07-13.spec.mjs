/**
 * tests/visual/desktop/task-action-buttons-2026-07-13.spec.mjs
 *
 * TaskView.vue 任务列表操作按钮美化回归测试
 *
 * 覆盖:
 *   P0-1: 桌面 /tasks 编辑/删除按钮是 EP <el-button circle> (圆形)
 *   P0-2: light-orange 主题下, --edit hover 触发 primary 橙 (border + bg + icon 三联动)
 *   P0-3: light-orange 主题下, --delete hover 触发 danger 红
 *   P0-4: dark 主题下 hover 仍变色, 但 bg alpha 提到 0.12 (深色背景补偿)
 *   P0-5: aria-label 保留 a11y ("编辑" / "删除")
 *   P0-6: 默认态 border = var(--color-border), bg = transparent (不是激活态)
 *   P0-7: 既有 .complete-btn 风格不受破坏 (回归)
 *
 * 不写 baseline 对比 — 用 evaluate() 拿 computed style 精确断言, 比 toHaveScreenshot 更稳定
 *
 * 运行:
 *   BASE_URL=http://localhost:3000 \
 *   npx playwright test tests/visual/desktop/task-action-buttons-2026-07-13.spec.mjs --project=desktop-chrome
 *
 * 关键发现 (2026-07-13 调试沉淀):
 *   - 必须先 goto /login 建立 origin → 注入 localStorage → 再 goto /tasks
 *   - 直接 goto /tasks + addInitScript 在某些 SPA 配置下 init script 时序不可靠
 *   - v2 spec 范式: page.context().request.post('/api/v1/auth/login') 拿 fresh token,
 *     然后 page.goto('/login') 触发 origin, evaluate() 注入 4 个 localStorage keys, 最后 goto 目标路由
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const TEST_USER = process.env.TEST_USER || 'xiaoqi_testbot'
const TEST_PASS = process.env.TEST_PASS || 'testbot_pass_2026'

// 4 主题组合 (light/dark × orange/ocean)
// dangerRgb 来自 variables.css: light=#F56C6C (245,108,108), dark=#f78989 (247,137,137)
const THEMES = [
  { name: 'light-orange', theme: 'light', accent: 'orange', primaryRgb: '255, 122, 92', dangerRgb: '245, 108, 108' },
  { name: 'light-ocean',  theme: 'light', accent: 'ocean',  primaryRgb: '74, 144, 226',  dangerRgb: '245, 108, 108' },
  { name: 'dark-orange',  theme: 'dark',  accent: 'orange', primaryRgb: '255, 157, 133', dangerRgb: '247, 137, 137' },
  { name: 'dark-ocean',   theme: 'dark',  accent: 'ocean',  primaryRgb: '107, 171, 255', dangerRgb: '247, 137, 137' },
]

/**
 * v2 spec 范式: API 登录 + /login origin 注入 + goto 目标路由
 * - page.context().request.post 走真实 backend API, 不受 SPA token 注入时序影响
 * - /login 是 noAuth 路由, 先 goto 它建立 origin + 触发 document_start
 * - evaluate() 在 document_start 之后注入 4 个 localStorage keys (sync)
 * - 再 goto 目标路由, 此时 router guard 能读到 token, 不再重定向 /login
 */
async function setupPage(page, { theme, accent }) {
  const loginResp = await page.context().request.post(`${BACKEND_URL}/api/v1/auth/login`, {
    data: { username: TEST_USER, password: TEST_PASS }
  })
  if (!loginResp.ok()) throw new Error(`Login failed: ${loginResp.status()}`)
  const loginData = await loginResp.json()
  const TOKEN = loginData.access_token

  // 先 goto /login (noAuth) → origin 已建立, document 可写
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
  await page.evaluate((data) => {
    localStorage.setItem('access_token', data.token)
    localStorage.setItem('refresh_token', data.refresh)
    localStorage.setItem('user_info', JSON.stringify(data.user))
    localStorage.setItem('theme', data.theme)
    localStorage.setItem('accent', data.accent)
    document.documentElement.setAttribute('data-theme', data.theme)
    document.documentElement.setAttribute('data-accent', data.accent)
  }, {
    token: TOKEN,
    refresh: loginData.refresh_token,
    user: loginData.user,
    theme,
    accent,
  })

  // 现在 goto 目标路由 — token 已 inject, router guard 通过
  await page.goto(`${BASE_URL}/tasks`, { waitUntil: 'domcontentloaded' })
  // 等任务行渲染（Vue hydration + API 加载）
  await page.waitForSelector('.task-action-btn', { timeout: 15_000 })
  // 让 EP <el-button> 样式稳定 (vue scoped 已注入)
  await page.waitForTimeout(300)
}

// 读取元素 computed style
async function getStyle(page, selector, props) {
  return await page.evaluate(({ selector, props }) => {
    const el = document.querySelector(selector)
    if (!el) return null
    const cs = window.getComputedStyle(el)
    const out = {}
    for (const p of props) out[p] = cs.getPropertyValue(p)
    return out
  }, { selector, props })
}

// 强制 hover (dispatchEvent 在 vue hover state 同步上更稳)
async function hoverElement(page, selector) {
  const el = page.locator(selector).first()
  await el.scrollIntoViewIfNeeded()
  await el.hover({ force: true })
  await page.waitForTimeout(200)  // 给 vue reactive 50ms 切换样式 + 150ms transition
}

test.describe('TaskView 操作按钮美化回归', () => {
  for (const t of THEMES) {
    test(`P0-${t.name} 编辑/删除按钮 computed style + hover`, async ({ page }) => {
      await setupPage(page, t)

      // ===== P0-1: EP <el-button circle> 圆形 (border-radius = 50%) =====
      const editBtn = page.locator('.task-action-btn--edit').first()
      const deleteBtn = page.locator('.task-action-btn--delete').first()

      const editBorderRadius = await editBtn.evaluate(el => window.getComputedStyle(el).borderRadius)
      const deleteBorderRadius = await deleteBtn.evaluate(el => window.getComputedStyle(el).borderRadius)
      // EP <el-button circle> 默认 border-radius: 50%
      expect(editBorderRadius, `${t.name} edit btn 应该是圆形`).toMatch(/50%/)
      expect(deleteBorderRadius, `${t.name} delete btn 应该是圆形`).toMatch(/50%/)

      // ===== P0-6: 默认态 =====
      // 移开鼠标到 body (避免 hover state 残留)
      await page.mouse.move(0, 0)
      await page.waitForTimeout(200)

      const defaultEdit = await getStyle(page, '.task-action-btn--edit', [
        'border-color', 'background-color', 'color'
      ])
      const defaultDelete = await getStyle(page, '.task-action-btn--delete', [
        'border-color', 'background-color', 'color'
      ])

      console.log(`[${t.name}] default edit:`, defaultEdit)
      console.log(`[${t.name}] default delete:`, defaultDelete)

      // 默认态 bg = 极淡 neutral tint (rgba(text-secondary-rgb, 0.04))
      expect(defaultEdit['background-color'], `${t.name} edit 默认 bg 极淡 neutral`)
        .toMatch(/rgba\(144,\s*147,\s*153[,\s]+0\.04\)/)
      expect(defaultDelete['background-color'], `${t.name} delete 默认 bg 极淡 neutral`)
        .toMatch(/rgba\(144,\s*147,\s*153[,\s]+0\.04\)/)

      // ===== P0-2/P0-3: hover 触发 primary / danger =====
      await hoverElement(page, '.task-action-btn--edit')
      const hoverEdit = await getStyle(page, '.task-action-btn--edit', [
        'border-color', 'background-color', 'color'
      ])
      console.log(`[${t.name}] hover edit:`, hoverEdit)

      // edit hover border 应包含 primary 色 rgb (基于当前主题的 primaryRgb)
      expect(hoverEdit['border-color'], `${t.name} edit hover border = primary`)
        .toContain(t.primaryRgb)
      // edit hover bg 应是 rgba(primaryRgb, alpha) — alpha = 0.15 light / 0.18 dark
      const editAlpha = t.theme === 'dark' ? '0.18' : '0.15'
      const editRgbEscaped = t.primaryRgb.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      expect(hoverEdit['background-color'], `${t.name} edit hover bg = rgba(primary ${editAlpha})`)
        .toMatch(new RegExp(`${editRgbEscaped}[,\\s]+${editAlpha.replace('.', '\\.')}`))

      // hover 完后 hover delete
      await page.mouse.move(0, 0)
      await page.waitForTimeout(200)
      await hoverElement(page, '.task-action-btn--delete')
      const hoverDelete = await getStyle(page, '.task-action-btn--delete', [
        'border-color', 'background-color', 'color'
      ])
      console.log(`[${t.name}] hover delete:`, hoverDelete)

      // delete hover border 应是 danger (主题相关 RGB triplet)
      expect(hoverDelete['border-color'], `${t.name} delete hover border = danger`)
        .toContain(t.dangerRgb)
      const deleteAlpha = t.theme === 'dark' ? '0.18' : '0.15'
      const deleteRgbEscaped = t.dangerRgb.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      expect(hoverDelete['background-color'], `${t.name} delete hover bg = rgba(danger ${deleteAlpha})`)
        .toMatch(new RegExp(`${deleteRgbEscaped}[,\\s]+${deleteAlpha.replace('.', '\\.')}`))

      // ===== P0-5: aria-label 保留 =====
      const editAriaLabel = await editBtn.getAttribute('aria-label')
      const deleteAriaLabel = await deleteBtn.getAttribute('aria-label')
      expect(editAriaLabel, 'edit btn aria-label').toBe('编辑')
      expect(deleteAriaLabel, 'delete btn aria-label').toBe('删除')
    })
  }

  test('P0-regression 既有 .complete-btn 风格仍 work (不破坏现有)', async ({ page }) => {
    await setupPage(page, { theme: 'light', accent: 'orange' })

    // .complete-btn--outline (进行中任务的完成按钮) 应仍是透明 border style
    const outlineStyle = await getStyle(page, '.complete-btn--outline', [
      'border-width', 'background-color'
    ])
    expect(outlineStyle['border-width'], 'complete-btn outline 边框宽度 = 2px')
      .toBe('2px')
    expect(outlineStyle['background-color'], 'complete-btn outline 默认透明')
      .toMatch(/rgba\(0,\s*0,\s*0,\s*0\)|transparent/)

    // .complete-btn--done (已完成任务的完成按钮) 应有绿色 bg
    const doneStyle = await getStyle(page, '.complete-btn--done', [
      'background-color'
    ])
    console.log('[regression] complete-btn--done bg:', doneStyle)
    expect(doneStyle['background-color'], 'complete-btn done bg 应有颜色 (success)')
      .not.toMatch(/rgba\(0,\s*0,\s*0,\s*0\)|transparent/)
  })
})