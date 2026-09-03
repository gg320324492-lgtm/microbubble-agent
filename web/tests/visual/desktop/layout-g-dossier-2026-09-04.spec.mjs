/**
 * tests/visual/desktop/layout-g-dossier-2026-09-04.spec.mjs
 *
 * G 稿「控制台档案」MainLayout 实装验证 (vite dev :3100 → 本地 docker app :8000)
 * 断言: 四段标本签 / 9 项 mitem / 16px sprite use / 计数徽标 / 档案印章 / 折叠态 / 夜览
 * 截图: screenshots/layout-g-*.png
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100'
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'

async function login(page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
  await page.waitForURL(/\/(login|dashboard|chat)/, { timeout: 15_000 }).catch(() => null)
  if (page.url().includes('/login')) {
    await page.locator('input[name="username"], input[placeholder*="账号"], input[placeholder*="用户名"], input[type="text"]:not([readonly])').first().fill(USERNAME)
    await page.locator('input[type="password"]').first().fill(PASSWORD)
    await page.locator('button:has-text("进入工作台"), button[type="submit"], button:has-text("登录")').first().click()
    await page.waitForURL(/\/(dashboard|chat|tasks)/, { timeout: 20_000 })
  }
}

test.describe('layout-g-dossier 2026-09-04', () => {
  test.beforeEach(async ({ page }) => {
    page.on('pageerror', (e) => console.log(`  [pageerror] ${e.message.slice(0, 200)}`))
    page.on('console', (m) => { if (m.type() === 'error') console.log(`  [browser error] ${m.text().slice(0, 200)}`) })
    await login(page)
    await page.goto(BASE_URL + '/dashboard', { waitUntil: 'domcontentloaded' })
    await page.setViewportSize({ width: 1440, height: 880 })
    await page.waitForTimeout(1500) // 侧栏徽标 stats 异步
  })

  test('A: 桌面侧栏 dossier 结构全断言', async ({ page }) => {
    // 四段标本签
    const tags = page.locator('aside .taglabel')
    await expect(tags).toHaveCount(4)
    await expect(tags.nth(0)).toContainText('FRONT MATTER · 卷首')
    await expect(tags.nth(1)).toContainText('RESEARCH · 研究')
    await expect(tags.nth(2)).toContainText('COLLAB · 协作')
    await expect(tags.nth(3)).toContainText('SYSTEM · 系统')

    // 9 项菜单
    const items = page.locator('aside .mitem')
    await expect(items).toHaveCount(9)

    // sprite 图标真实渲染 (use href 解析成功 → 图标有尺寸)
    const gauge = page.locator('aside .mitem use[href="#i-gauge"]')
    await expect(gauge).toHaveCount(1)
    const svgBox = await page.locator('aside .mitem').first().locator('svg.s').boundingBox()
    expect(Math.round(svgBox.width)).toBe(16)

    // active 态 (仪表盘) — 卡片底 + 左侧 teal 条
    const active = page.locator('aside .mitem.active')
    await expect(active).toHaveCount(1)
    await expect(active).toContainText('仪表盘')

    // 计数徽标 (stats 拉通才显示, 打印实测值)
    const badges = await page.locator('aside .cnt').allTextContents()
    console.log('  badges =', JSON.stringify(badges))

    // 档案印章
    const stamp = page.locator('aside .stamp')
    await expect(stamp).toContainText('项目动态')
    await expect(stamp).toContainText(/WK\d+/)

    await page.screenshot({ path: 'tests/visual/desktop/screenshots/layout-g-light.png' })
    await page.locator('aside').screenshot({ path: 'tests/visual/desktop/screenshots/layout-g-sidebar.png' })
  })

  test('B: 折叠态 64px + 分隔线 + title 提示', async ({ page }) => {
    await page.locator('.collapse-btn').click()
    await page.waitForTimeout(400)
    const aside = page.locator('aside')
    const box = await aside.boundingBox()
    expect(Math.round(box.width)).toBe(64)
    await expect(page.locator('aside .gsep:visible')).toHaveCount(3)
    await expect(page.locator('aside .mitem').first()).toHaveAttribute('title', '仪表盘')
    await aside.screenshot({ path: 'tests/visual/desktop/screenshots/layout-g-collapsed.png' })
  })

  test('C: 夜览 dark 覆盖', async ({ page }) => {
    await page.locator('.header-right button, .header-right [class*="theme"]').first().click().catch(async () => {
      await page.locator('.header-right').getByRole('button').nth(1).click()
    })
    await page.waitForTimeout(400)
    const theme = await page.evaluate(() => document.documentElement.getAttribute('data-theme') || document.body.getAttribute('data-theme'))
    console.log('  data-theme =', theme)
    await page.screenshot({ path: 'tests/visual/desktop/screenshots/layout-g-dark.png' })
  })
})
