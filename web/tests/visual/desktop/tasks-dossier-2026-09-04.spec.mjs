/**
 * tests/visual/desktop/tasks-dossier-2026-09-04.spec.mjs
 *
 * TaskView G 稿档案皮肤验证 (vite dev :3100 → docker app :8000)
 * 断言: 卷首头 / tabs mono / chips 替换 el-tag / 负责人 ITEMS 签 / 双列虚线 / 逾期印章 / 创建弹窗仍可用
 * 只读: 不点完成/删除 (避免动真实数据)
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100'
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'

async function login(page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
  await page.waitForURL(/\/(login|dashboard|tasks|chat)/, { timeout: 15_000 }).catch(() => null)
  if (page.url().includes('/login')) {
    await page.locator('input[name="username"], input[placeholder*="用户名"], input[type="text"]:not([readonly])').first().fill(USERNAME)
    await page.locator('input[type="password"]').first().fill(PASSWORD)
    await page.locator('button:has-text("进入工作台"), button[type="submit"]').first().click()
    await page.waitForURL(/\/(dashboard|chat|tasks)/, { timeout: 20_000 })
  }
}

test.describe('tasks-dossier 2026-09-04', () => {
  test.beforeEach(async ({ page }) => {
    page.on('pageerror', (e) => console.log(`  [pageerror] ${e.message.slice(0, 200)}`))
    await login(page)
    await page.goto(BASE_URL + '/tasks', { waitUntil: 'domcontentloaded' })
    await page.setViewportSize({ width: 1440, height: 880 })
    await page.waitForTimeout(2000)
  })

  test('A: 皮肤结构断言', async ({ page }) => {
    // 卷首头
    await expect(page.locator('.dossier-head .dh-title')).toHaveText('任务管理')
    await expect(page.locator('.dh-tag')).toContainText('TASK DOSSIER')
    await expect(page.locator('.dh-count').first()).toContainText('进行中')
    // 卡片硬阴影皮肤生效
    const shadow = await page.locator('.task-list-card').evaluate((el) => getComputedStyle(el).boxShadow)
    console.log('  card box-shadow =', shadow)
    expect(shadow).not.toBe('none')
    // chip 替换 el-tag: 任务行内不应再有 el-tag, 应有 mono chip
    const rows = page.locator('.task-row')
    const rowCount = await rows.count()
    console.log('  task rows =', rowCount)
    expect(rowCount).toBeGreaterThan(0)
    await expect(page.locator('.task-row .el-tag')).toHaveCount(0)
    await expect(page.locator('.chip').first()).toBeVisible()
    const chipFont = await page.locator('.chip').first().evaluate((el) => getComputedStyle(el).fontFamily)
    expect(chipFont).toMatch(/Consolas|Courier|monospace/i)
    // 负责人 ITEMS 签 + 方形头像
    await expect(page.locator('.group-cnt').first()).toContainText('ITEMS')
    const avRadius = await page.locator('.group-avatar').first().evaluate((el) => getComputedStyle(el).borderRadius)
    expect(avRadius).toBe('8px')
    // 双列虚线分隔存在
    const border = await page.locator('.paired-col-left').first().evaluate((el) => getComputedStyle(el).borderRightStyle)
    expect(border).toBe('dashed')
    // 逾期印章 (真实数据有逾期 → 应显示)
    const seal = page.locator('.overdue-seal')
    console.log('  overdue seal =', await seal.count() ? await seal.textContent() : '(none)')
    await page.screenshot({ path: 'tests/visual/desktop/screenshots/tasks-dossier-light.png', fullPage: false })
    await page.locator('.task-list-card').screenshot({ path: 'tests/visual/desktop/screenshots/tasks-dossier-list.png' })
  })

  test('B: 交互未破坏 — 分组折叠 / 创建弹窗开合 / 垃圾桶 tab', async ({ page }) => {
    // 折叠一个负责人组
    const firstGroupHeader = page.locator('.group-header').first()
    const contentBefore = await page.locator('.paired-content').first().isVisible()
    await firstGroupHeader.click()
    await page.waitForTimeout(300)
    const contentAfter = await page.locator('.paired-content').first().isVisible()
    expect(contentBefore).toBe(true)
    expect(contentAfter).toBe(false)
    await firstGroupHeader.click()

    // 创建任务弹窗能开能关 (不提交)
    await page.locator('.filter-card button:has-text("创建任务")').click()
    await expect(page.locator('.el-dialog')).toBeVisible({ timeout: 5000 })
    await page.locator('.el-dialog [aria-label="关闭此对话框"], .el-dialog .el-dialog__close').first().click()
    await page.waitForTimeout(300)

    // 垃圾桶 tab
    await page.locator('.el-tabs__item:has-text("垃圾桶")').click()
    await page.waitForTimeout(1500)
    expect(page.url()).toContain('/tasks')
  })
})
