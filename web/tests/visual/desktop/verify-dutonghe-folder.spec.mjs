/**
 * 验证 杜同贺 sub-folder 修复后行为
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

test('杜同贺 sub-folder 完整验证', async ({ page }) => {
  if (!TEST_TOKEN) throw new Error('TEST_TOKEN 未设置')

  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('input.el-input__inner', { timeout: 10_000 })
  await page.locator('input.el-input__inner').nth(0).fill('xiaoqi_testbot')
  await page.locator('input.el-input__inner').nth(1).fill('testbot_pass_2026')
  await page.click('button.login-button')
  await page.waitForURL((url) => url.pathname !== '/login', { timeout: 15_000 }).catch(() => {})
  await page.waitForTimeout(1500)

  await page.goto(`${BASE_URL}/drive`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.drive-sidebar', { timeout: 15_000 })
  await page.waitForTimeout(2500)

  // 进入团队共享盘
  await page.evaluate(() => {
    document.querySelector('.drive-folder-tree-special-item.is-team')?.click()
  })
  await page.waitForTimeout(3500)

  // 展开组会PPT
  const groupPPTNode = page.locator('.folder-tree-node:has-text("组会PPT")').first()
  const expandIcon = groupPPTNode.locator('.folder-tree-node-toggle').first()
  await expandIcon.click({ force: true })
  await page.waitForTimeout(2000)

  // click 杜同贺
  await page.evaluate(() => {
    const dutonghe = Array.from(document.querySelectorAll('.folder-tree-node-name')).find(n => n.textContent === '杜同贺')
    if (dutonghe) dutonghe.closest('.folder-tree-node-row').click()
  })
  await page.waitForTimeout(3500)

  await page.screenshot({
    path: 'tests/visual/desktop/screenshots/dutonghe-FINAL.png',
    fullPage: true,
  })

  const breadcrumb = await page.locator('.drive-breadcrumb').textContent()
  const fileCount = await page.locator('.drive-filter-stat-num').textContent()
  const teamActive = await page.locator('.drive-folder-tree-special-item.is-team.is-active').count()

  // 列出 FileGrid 中可见的 PPT 名
  const fileNames = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.file-grid-item .file-name, .drive-file-item-name, [class*="file"]:not([class*="folder"]) [class*="name"]'))
      .map(el => el.textContent?.trim())
      .filter(Boolean)
      .slice(0, 10)
  })

  console.log('\n========================================')
  console.log('✅ 杜同贺 sub-folder 验证:')
  console.log(`   面包屑: "${breadcrumb?.trim().replace(/\s+/g, ' ')}"`)
  console.log(`   FileGrid 文件数: ${fileCount}`)
  console.log(`   团队共享盘 active: ${teamActive === 1 ? '✓' : '✗'}`)
  console.log(`   PPT 列表 (前 ${fileNames.length}):`)
  fileNames.forEach((n) => console.log(`     - ${n}`))
  console.log('========================================')

  expect(parseInt(fileCount || '0', 10)).toBeGreaterThanOrEqual(6)
  expect(teamActive).toBe(1)
})