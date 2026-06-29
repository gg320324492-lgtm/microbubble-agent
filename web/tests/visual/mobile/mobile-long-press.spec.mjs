/**
 * tests/visual/mobile/mobile-long-press.spec.mjs
 *
 * v77 P2.6-G.1: 移动端会议模板卡片 long-press 操作菜单集成测试
 *
 * 用法:
 *   npx playwright test mobile-long-press.spec.mjs --project=mobile-iphone14
 *
 * 前置:
 *   - dev server 跑起来 (npm run dev) 或用 BASE_URL 指向部署环境
 *   - 登录态: TEST_TOKEN env (双注入 cookie + localStorage)
 *
 * 注意: 这是功能性集成测试, **不依赖 baseline 截图**, 只验证 long-press 交互流程
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

// 等待 dialog/动画完成
async function waitForLoaded(page) {
  await page.waitForTimeout(800)
}

test.describe('v77 P2.6-G.1 移动端 long-press 操作菜单', () => {

  test('M-13 mobile 模板卡 long-press → ActionSheet 弹出 → 含 builtin actions', async ({ page }) => {
    test.setTimeout(30000)
    // 模拟移动端 viewport (iPhone 14)
    await page.setViewportSize({ width: 390, height: 844 })

    await injectAuth(page)
    await page.goto(`${BASE_URL}/meetings`)
    await waitForLoaded(page)

    // 点"手动创建"打开 MeetingCreateDialog
    await page.getByRole('button', { name: /手动创建/ }).click()
    await waitForLoaded(page)

    // 第一个 builtin 卡片 (mobile 模式下卡片用 LongPressWrapper 包裹)
    const firstBuiltin = page.locator('.template-card.builtin').first()
    await expect(firstBuiltin, '第一个 builtin 卡片应可见').toBeVisible()

    // 模拟 long-press (Playwright 在 mobile viewport 下 mouse.down + 700ms + mouse.up 模拟触摸)
    const box = await firstBuiltin.boundingBox()
    if (!box) {
      test.skip(true, 'long-press 模拟需要 boundingBox')
    }
    const centerX = box.x + box.width / 2
    const centerY = box.y + box.height / 2

    await page.mouse.move(centerX, centerY)
    await page.mouse.down()
    await page.waitForTimeout(700)  // LongPressWrapper 600ms 触发 + 100ms 容差
    await page.mouse.up()
    await waitForLoaded(page)

    // MobileActionSheet 弹出 (检查 sheet 可见)
    const sheet = page.locator('.mobile-action-sheet')
    await expect(sheet, 'MobileActionSheet 应弹出').toBeVisible({ timeout: 3000 })

    // 验证 builtin 卡片菜单含 复制 + 禁用 (is_active=true)
    await expect(sheet).toContainText('复制为自定义模板')
    await expect(sheet).toContainText('禁用模板')

    // 关闭 sheet
    await page.getByRole('button', { name: /取消/ }).click()
    await page.waitForTimeout(500)
  })

  test('M-14 mobile builtin(启用) 菜单: 复制 + 禁用 (is_active=true)', async ({ page }) => {
    test.setTimeout(30000)
    await page.setViewportSize({ width: 390, height: 844 })

    await injectAuth(page)
    await page.goto(`${BASE_URL}/meetings`)
    await waitForLoaded(page)
    await page.getByRole('button', { name: /手动创建/ }).click()
    await waitForLoaded(page)

    const firstBuiltin = page.locator('.template-card.builtin').first()
    const box = await firstBuiltin.boundingBox()
    const centerX = box.x + box.width / 2
    const centerY = box.y + box.height / 2

    await page.mouse.move(centerX, centerY)
    await page.mouse.down()
    await page.waitForTimeout(700)
    await page.mouse.up()
    await waitForLoaded(page)

    const sheet = page.locator('.mobile-action-sheet')
    await expect(sheet).toBeVisible({ timeout: 3000 })

    // builtin (启用) 菜单: 复制 + 禁用 (is_active=true → 显示禁用按钮)
    const actionButtons = sheet.locator('.mobile-action-item')
    const actionTexts = await actionButtons.allTextContents()
    expect(actionTexts.length, 'builtin(启用) 菜单应有 2 项').toBe(2)
    expect(actionTexts[0]).toContain('复制')
    expect(actionTexts[1]).toContain('禁用')

    await page.getByRole('button', { name: /取消/ }).click()
  })

  test('M-15 mobile builtin(禁用) 菜单: 复制 + 启用 (is_active=false)', async ({ page }) => {
    test.setTimeout(30000)
    await page.setViewportSize({ width: 390, height: 844 })

    await injectAuth(page)
    await page.goto(`${BASE_URL}/meetings`)
    await waitForLoaded(page)
    await page.getByRole('button', { name: /手动创建/ }).click()
    await waitForLoaded(page)

    // 找第一个 is_active=false 的 builtin (如果有的话)
    // 如果没有, 跳过此测试 (依赖初始数据状态)
    const disabledBuiltins = page.locator('.template-card.builtin.disabled')
    const disabledCount = await disabledBuiltins.count()
    test.skip(disabledCount === 0, 'M-15 跳过: 无 builtin(禁用) 测试数据 (依赖初始 is_active=false 模板)')

    const firstDisabled = disabledBuiltins.first()
    const box = await firstDisabled.boundingBox()
    const centerX = box.x + box.width / 2
    const centerY = box.y + box.height / 2

    await page.mouse.move(centerX, centerY)
    await page.mouse.down()
    await page.waitForTimeout(700)
    await page.mouse.up()
    await waitForLoaded(page)

    const sheet = page.locator('.mobile-action-sheet')
    await expect(sheet).toBeVisible({ timeout: 3000 })

    // builtin (禁用) 菜单: 复制 + 启用
    const actionButtons = sheet.locator('.mobile-action-item')
    const actionTexts = await actionButtons.allTextContents()
    expect(actionTexts[1]).toContain('启用')

    await page.getByRole('button', { name: /取消/ }).click()
  })

  test('M-16 mobile custom 菜单: 编辑 + 复制 + 删除 (需先有 custom 模板)', async ({ page }) => {
    test.setTimeout(30000)
    await page.setViewportSize({ width: 390, height: 844 })

    await injectAuth(page)
    await page.goto(`${BASE_URL}/meetings`)
    await waitForLoaded(page)
    await page.getByRole('button', { name: /手动创建/ }).click()
    await waitForLoaded(page)

    const customCount = await page.locator('.template-card.custom').count()
    test.skip(customCount === 0, 'M-16 跳过: 无 custom 模板测试数据')

    const firstCustom = page.locator('.template-card.custom').first()
    const box = await firstCustom.boundingBox()
    const centerX = box.x + box.width / 2
    const centerY = box.y + box.height / 2

    await page.mouse.move(centerX, centerY)
    await page.mouse.down()
    await page.waitForTimeout(700)
    await page.mouse.up()
    await waitForLoaded(page)

    const sheet = page.locator('.mobile-action-sheet')
    await expect(sheet).toBeVisible({ timeout: 3000 })

    // custom 菜单: 编辑 + 复制 + 删除 (3 个)
    const actionButtons = sheet.locator('.mobile-action-item')
    const actionTexts = await actionButtons.allTextContents()
    expect(actionTexts.length, 'custom 菜单应有 3 项').toBe(3)
    expect(actionTexts[0]).toContain('编辑')
    expect(actionTexts[1]).toContain('复制')
    expect(actionTexts[2]).toContain('删除')

    await page.getByRole('button', { name: /取消/ }).click()
  })
})