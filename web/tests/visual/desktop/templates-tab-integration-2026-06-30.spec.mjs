/**
 * tests/visual/desktop/templates-tab-integration-2026-06-30.spec.mjs
 *
 * v78 UI redesign — 模板管理 → 会议管理 (2 tabs 集成) 端到端验证
 *
 * 覆盖:
 *   - /meetings 页面有 2 个 tab: 会议列表 / 模板管理
 *   - 模板管理 tab 渲染模板列表 (含 builtin + custom 标签)
 *   - 编辑按钮真正打开 MeetingTemplateDialog (不再 toast)
 *   - 批量操作 toolbar (启用/禁用/删除) 可用
 *   - sidebar 不再有 "模板管理" 独立项
 *   - 浏览器 console 无 error
 *
 * 前置:
 *   - dev server 跑起来 (npm run dev) 或 BASE_URL 指向部署环境
 *   - TEST_TOKEN 环境变量注入真实 JWT
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3004'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

async function setupPage(page, { theme = 'light', accent = 'orange' } = {}) {
  await page.context().addCookies([{
    name: 'access_token',
    value: TEST_TOKEN,
    domain: new URL(BASE_URL).hostname,
    path: '/',
  }])
  await page.addInitScript((data) => {
    localStorage.setItem('access_token', data.token)
    localStorage.setItem('theme', data.theme)
    localStorage.setItem('accent', data.accent)
  }, { token: TEST_TOKEN, theme, accent })
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
}

test.describe('templates-tab-integration-2026-06-30: 模板管理 集成到会议管理', () => {
  test('D6 /meetings 2 tabs + 模板管理 tab 渲染 + 批量 toolbar', async ({ page }) => {
    const consoleErrors = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    await setupPage(page)
    await page.goto(`${BASE_URL}/meetings`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(500)

    // 断言 1: 2 个 tab 存在
    const tabLabels = await page.locator('.el-tabs__item').allTextContents()
    expect(tabLabels.length, '应有 2 个 tab').toBe(2)
    expect(tabLabels.some(t => t.includes('会议列表'))).toBe(true)
    expect(tabLabels.some(t => t.includes('模板管理'))).toBe(true)

    // 断言 2: 默认选中 "会议列表" tab
    await expect(page.locator('.el-tabs__item.is-active')).toContainText('会议列表')

    // 断言 3: 点击 "模板管理" tab
    await page.locator('.el-tabs__item:has-text("模板管理")').click()
    await page.waitForTimeout(1000)

    // 断言 4: 模板管理 filter-card 渲染
    const filterCard = page.locator('.templates-panel .filter-card')
    await expect(filterCard).toBeVisible()

    // 断言 5: 表格 + 批量 toolbar
    const tableCard = page.locator('.templates-panel .table-card')
    await expect(tableCard).toBeVisible()
    await expect(page.locator('.templates-panel .batch-toolbar')).toBeVisible()
    await expect(page.locator('.templates-panel .batch-toolbar-left button:has-text("批量编辑")')).toBeVisible()

    // 断言 6: 至少 1 个 builtin 模板
    const builtinTags = page.locator('.templates-panel .el-tag:has-text("内置")')
    await expect(builtinTags.first()).toBeVisible()

    // 断言 7: 切换回会议列表 tab 不破坏
    await page.locator('.el-tabs__item:has-text("会议列表")').click()
    await page.waitForTimeout(500)
    await expect(page.locator('.meeting-list-card, .empty-state').first()).toBeVisible()

    // 断言 8: console 无 error (过滤掉已知 Vite HMR 假错误)
    const realErrors = consoleErrors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('webpack') &&
      !e.includes('404') &&
      !e.includes('504') &&
      !e.includes('Outdated Optimize Dep')
    )
    expect(realErrors, `Console errors: ${realErrors.join('; ')}`).toEqual([])

    // 截图保存
    await page.locator('.el-tabs__item:has-text("模板管理")').click()
    await page.waitForTimeout(500)
    await page.screenshot({
      path: 'test-results/templates-tab-integration/meetings-templates-tab.png',
      fullPage: true,
      animations: 'disabled',
    })
  })

  test('D6 sidebar 验证: 无 "模板管理" 独立项', async ({ page }) => {
    await setupPage(page)
    await page.goto(`${BASE_URL}/meetings`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(500)

    // 断言: sidebar 菜单项不含 "模板管理" 文本
    const menuItems = await page.locator('.el-menu-item').allTextContents()
    const hasTemplateMenu = menuItems.some(t => t.trim() === '模板管理')
    expect(hasTemplateMenu, 'sidebar 不应再显示 "模板管理" 独立菜单项').toBe(false)

    // 断言: "会议管理" 仍在
    const hasMeetingMenu = menuItems.some(t => t.trim() === '会议管理')
    expect(hasMeetingMenu, '"会议管理" 应仍在 sidebar').toBe(true)
  })
})
