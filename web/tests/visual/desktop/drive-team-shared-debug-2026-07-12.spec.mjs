/**
 * Final verify v2: 手动 fetch + 赋值 + 展开 组会PPT 节点
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

test('final-v2: 手动 fetch + 展开组会PPT', async ({ page }) => {
  // Login
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('input.el-input__inner', { timeout: 10_000 })
  await page.locator('input.el-input__inner').nth(0).fill('xiaoqi_testbot')
  await page.locator('input.el-input__inner').nth(1).fill('testbot_pass_2026')
  await page.click('button.login-button')
  await page.waitForURL((url) => url.pathname !== '/login', { timeout: 15_000 }).catch(() => {})
  await page.waitForTimeout(1500)

  await page.goto(`${BASE_URL}/drive`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.drive-sidebar', { timeout: 15_000 })
  await page.waitForTimeout(3000)

  // Click 团队共享盘 (走原 click 路径)
  await page.evaluate(() => {
    document.querySelector('.drive-folder-tree-special-item.is-team')?.click()
  })
  await page.waitForTimeout(3000)

  // 手动 fetch + 赋值 store
  await page.evaluate(async () => {
    const app = document.querySelector('#app').__vue_app__
    const pinia = app.config.globalProperties.$pinia
    const store = pinia._s.get('folderTree')
    const token = localStorage.getItem('access_token')
    const r = await fetch('/api/v1/folders/tree?scope=team', {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    const data = await r.json()
    store.folderTree = data.tree || []
    // 也添加到 expanded set
    store.expandedFolderIds = new Set([data.tree[0].id])
  })
  await page.waitForTimeout(2000)

  // 截图 (未展开前)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/final-A-collapsed.png', fullPage: true })

  // 找到组会PPT 展开图标点击
  const expandClicked = await page.evaluate(() => {
    const node = document.querySelector('.folder-tree-node:has(.folder-tree-node-name)')
    // 找包含 组会PPT 的 row
    const rows = document.querySelectorAll('.folder-tree-node-row')
    for (const row of rows) {
      if (row.textContent.includes('组会PPT')) {
        const toggle = row.querySelector('.folder-tree-node-toggle')
        if (toggle) {
          toggle.click()
          return true
        }
      }
    }
    return false
  })
  console.log('\n[A] expand 组会PPT:', expandClicked)
  await page.waitForTimeout(2000)

  // 截图 (展开后)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/final-B-expanded.png', fullPage: true })

  // 检查 23 个成员是否可见
  const memberNames = [
    '余歆睿', '关小未', '冯懿鑫', '刘子毅', '吴孟铨',
    '宋洋', '张宏魁', '张懿', '李胜景', '李锐远',
    '杜同贺', '杨慈', '王书馨', '耿嘉栋', '胡小琪',
    '艾琳朔', '蒋芦笛', '贾琦', '赵航佳', '陈天祥',
    '陈金薪', '雒培媛', '韩重阳',
  ]
  const visible = []
  const missing = []
  for (const name of memberNames) {
    const count = await page.locator(`text=${name}`).count()
    if (count > 0) visible.push(name)
    else missing.push(name)
  }
  console.log('\n[B] After expanding 组会PPT:')
  console.log('  可见成员:', visible.length, '/ 23')
  visible.forEach((m) => console.log(`     ✓ ${m}`))
  if (missing.length) {
    console.log('  缺失:', missing.length)
    missing.forEach((m) => console.log(`     ✗ ${m}`))
  }
})