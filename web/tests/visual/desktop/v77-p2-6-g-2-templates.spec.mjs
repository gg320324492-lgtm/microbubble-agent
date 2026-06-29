/**
 * tests/visual/desktop/v77-p2-6-g-2-templates.spec.mjs
 *
 * v77 P2.6-G.2: 模板批量管理页 /admin/templates 集成测试
 *
 * 用法:
 *   npx playwright test v77-p2-6-g-2-templates.spec.mjs --project=desktop-chrome
 *
 * 前置:
 *   - dev server 跑起来 (npm run dev) 或用 BASE_URL 指向部署环境
 *   - 登录态: TEST_TOKEN env (双注入 cookie + localStorage)
 *
 * 4 个测试:
 *   B-17: /admin/templates 路由可访问 + 表格加载
 *   B-18: 搜索框输入 "组会" + Enter -> 表格过滤
 *   B-19: 批量编辑模式 -> 选中 2 个 -> 批量启用
 *   B-20: 切换 dark mode -> 视觉一致
 */

const { test, expect } = require('@playwright/test')

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

// 双注入登录态 (cookie + localStorage, 与 visual-regression.spec.mjs 同模式)
async function injectAuth(page) {
  if (!TEST_TOKEN) return
  await page.context().addCookies([
    { name: 'access_token', value: TEST_TOKEN, url: BASE_URL },
  ])
  await page.addInitScript((tk) => {
    localStorage.setItem('access_token', tk)
  }, TEST_TOKEN)
}

async function waitForLoaded(page, ms = 800) {
  await page.waitForTimeout(ms)
}

test.describe('v77 P2.6-G.2 模板管理页', () => {

  test('B-17 /admin/templates 路由可访问 + 表格加载', async ({ page }) => {
    test.setTimeout(30000)
    await injectAuth(page)
    await page.goto(`${BASE_URL}/admin/templates`)
    await waitForLoaded(page)

    // 顶部 page-header 可见
    await expect(page.getByText('模板管理', { exact: true })).toBeVisible()

    // 表格加载 (等待至少 1 行数据)
    const rows = page.locator('.el-table__body tr')
    await expect(rows.first()).toBeVisible({ timeout: 5000 })
  })

  test('B-18 搜索框输入 "组会" + Enter -> 表格过滤', async ({ page }) => {
    test.setTimeout(30000)
    await injectAuth(page)
    await page.goto(`${BASE_URL}/admin/templates`)
    await waitForLoaded(page)

    // 输入搜索
    await page.getByPlaceholder('按名称模糊搜索').fill('组会')
    await page.getByPlaceholder('按名称模糊搜索').press('Enter')
    await waitForLoaded(page, 500)

    // 表格行只含 "组会"
    const rows = page.locator('.el-table__body tr')
    const count = await rows.count()
    expect(count, '搜索 "组会" 至少 1 行').toBeGreaterThanOrEqual(1)
    for (let i = 0; i < count; i++) {
      await expect(rows.nth(i)).toContainText('组会')
    }
  })

  test('B-19 批量编辑模式 -> 选中 2 个 -> 批量启用', async ({ page }) => {
    test.setTimeout(30000)
    await injectAuth(page)
    await page.goto(`${BASE_URL}/admin/templates`)
    await waitForLoaded(page)

    // 点"批量编辑"按钮
    await page.getByRole('button', { name: /批量编辑/ }).click()
    await waitForLoaded(page, 300)

    // 勾选前 2 个 custom 模板的 checkbox (builtin 不可选)
    const checkboxes = page.locator('.el-table__body tr .el-checkbox')
    const selectableCount = await checkboxes.count()
    if (selectableCount < 2) {
      test.skip(true, 'B-19 跳过: 无 custom 模板可批量启用 (需要至少 2 个 custom 模板)')
      return
    }
    await checkboxes.nth(0).click()
    await checkboxes.nth(1).click()
    await waitForLoaded(page, 300)

    // 点"批量启用"
    await page.getByRole('button', { name: /批量启用/ }).click()
    await waitForLoaded(page, 800)

    // 验证 toast "已批量启用 N 个模板"
    await expect(page.getByText(/已批量启用/)).toBeVisible({ timeout: 5000 })
  })

  test('B-20 切换 dark mode -> 视觉一致', async ({ page }) => {
    test.setTimeout(30000)
    await injectAuth(page)
    await page.goto(`${BASE_URL}/admin/templates`)
    await waitForLoaded(page)

    // 切 dark mode
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark')
      localStorage.setItem('mnb:ui:theme', 'dark')
    })
    await waitForLoaded(page, 500)

    // 验证 page-desc 颜色跟随 dark (computed style != 浅色)
    const pageDesc = page.locator('.page-desc').first()
    const color = await pageDesc.evaluate((el) => getComputedStyle(el).color)
    // 浅色 desc 是 #909399 (rgb(144,147,153)), dark 应该不同
    expect(color, 'dark 模式 page-desc 颜色应不等于浅色默认值').not.toBe('rgb(144, 147, 153)')
  })
})
