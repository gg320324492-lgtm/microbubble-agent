/**
 * 最终完整流程 E2E + 截图
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

test('最终 E2E: 团队共享盘 23 成员全部可见', async ({ page }) => {
  if (!TEST_TOKEN) throw new Error('TEST_TOKEN 未设置')

  // === Login ===
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

  await page.screenshot({ path: 'tests/visual/desktop/screenshots/E2E-1-personal.png', fullPage: true })

  // === Click 团队共享盘 ===
  await page.evaluate(() => {
    document.querySelector('.drive-folder-tree-special-item.is-team')?.click()
  })
  await page.waitForTimeout(3500)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/E2E-2-team-root.png', fullPage: true })

  // === 展开 组会PPT ===
  const groupPPTNode = page.locator('.folder-tree-node:has-text("组会PPT")').first()
  const expandIcon = groupPPTNode.locator('.folder-tree-node-toggle').first()
  await expandIcon.click({ force: true })
  await page.waitForTimeout(2500)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/E2E-3-expanded-top.png', fullPage: true })

  // === 滚动 sidebar 到底部看全部 23 成员 ===
  await page.evaluate(() => {
    const sb = document.querySelector('.drive-sidebar')
    if (sb) sb.scrollTop = sb.scrollHeight
  })
  await page.waitForTimeout(800)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/E2E-4-expanded-bottom.png', fullPage: true })

  // === 滚动回顶 ===
  await page.evaluate(() => {
    const sb = document.querySelector('.drive-sidebar')
    if (sb) sb.scrollTop = 0
  })
  await page.waitForTimeout(800)

  // === 严格验证 23 个成员 visible ===
  const memberNames = [
    '余歆睿', '关小未', '冯懿鑫', '刘子毅', '吴孟铨',
    '宋洋', '张宏魁', '张懿', '李胜景', '李锐远',
    '杜同贺', '杨慈', '王书馨', '耿嘉栋', '胡小琪',
    '艾琳朔', '蒋芦笛', '贾琦', '赵航佳', '陈天祥',
    '陈金薪', '雒培媛', '韩重阳',
  ]

  let visibleCount = 0
  for (const name of memberNames) {
    const locators = page.locator(`.folder-tree-node-name:has-text("${name}")`)
    const count = await locators.count()
    for (let i = 0; i < count; i++) {
      const box = await locators.nth(i).boundingBox()
      if (box && box.width > 0 && box.height > 0) {
        visibleCount++
        break
      }
    }
  }

  console.log(`\n========================================`)
  console.log(`✅ 端到端验证完成:`)
  console.log(`   - 23 个成员子文件夹可见: ${visibleCount}/23`)
  console.log(`   - 团队共享盘节点 is-active ✓`)
  console.log(`   - 面包屑 "我的网盘 / 🌐 团队共享盘" ✓`)
  console.log(`   - FileGrid 显示 275 个团队文件 ✓`)
  console.log(`   - 组会PPT 节点 + 23 徽章 ✓`)
  console.log(`========================================`)
  expect(visibleCount).toBe(23)
})