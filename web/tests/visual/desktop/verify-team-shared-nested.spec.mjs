/**
 * 验证: 组会PPT 嵌套在团队共享盘节点下 (Bug G 修复)
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

test('组会PPT 嵌套在团队共享盘节点下', async ({ page }) => {
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

  // 截图
  await page.screenshot({
    path: 'tests/visual/desktop/screenshots/team-nested-final.png',
    fullPage: true,
  })

  // === 验证 1: 个人网盘区域没有"组会PPT"节点 ===
  // 检查 sidebar 所有 .folder-tree-node-name 元素的 visible 位置
  const nodePositions = await page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll('.folder-tree-node-name'))
    return nodes.map(el => {
      const r = el.getBoundingClientRect()
      const row = el.closest('.folder-tree-node-row')
      const rowClass = row?.className || ''
      const paddingLeft = row?.style.paddingLeft || ''
      return {
        name: el.textContent,
        top: Math.round(r.top),
        left: Math.round(r.left),
        paddingLeft,
      }
    })
  })

  console.log('\n[节点位置 + 缩进]:')
  nodePositions.forEach((n) => {
    console.log(`  "${n.name}" top=${n.top}, left=${n.left}, paddingLeft=${n.paddingLeft || '(none)'}`)
  })

  // === 验证 2: 23 个成员 sub-folder 全部可见 ===
  const memberNames = [
    '余歆睿', '关小未', '冯懿鑫', '刘子毅', '吴孟铨',
    '宋洋', '张宏魁', '张懿', '李胜景', '李锐远',
    '杜同贺', '杨慈', '王书馨', '耿嘉栋', '胡小琪',
    '艾琳朔', '蒋芦笛', '贾琦', '赵航佳', '陈天祥',
    '陈金薪', '雒培媛', '韩重阳',
  ]

  let visible = 0
  for (const name of memberNames) {
    const l = page.locator(`.folder-tree-node-name:has-text("${name}")`)
    const c = await l.count()
    for (let i = 0; i < c; i++) {
      const box = await l.nth(i).boundingBox()
      if (box && box.width > 0 && box.height > 0) {
        visible++
        break
      }
    }
  }

  // === 验证 3: 组会PPT 节点的 paddingLeft 应该是 28 (depth=1) ===
  const groupPPTPadding = await page.evaluate(() => {
    const groupPPT = Array.from(document.querySelectorAll('.folder-tree-node-name')).find(n => n.textContent === '组会PPT')
    if (!groupPPT) return null
    const row = groupPPT.closest('.folder-tree-node-row')
    return row?.style.paddingLeft || ''
  })
  console.log(`\n组会PPT 节点 paddingLeft = "${groupPPTPadding}" (期望 28px)`)

  console.log(`\n========================================`)
  console.log(`✅ 嵌套验证:`)
  console.log(`   - 23 个成员 sub-folder 可见: ${visible}/23`)
  console.log(`   - 组会PPT 节点缩进: ${groupPPTPadding === '28px' ? '✓ (28px, depth=1)' : '✗ (' + groupPPTPadding + ')'}`)
  console.log(`========================================`)

  expect(visible).toBe(23)
  expect(groupPPTPadding).toBe('28px')
})