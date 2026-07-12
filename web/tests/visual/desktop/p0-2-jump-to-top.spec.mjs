import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('P0-#2 UX 修复: ↑ 跳到最早按钮可见 + 点击滚到顶', async ({ page }) => {
  test.setTimeout(90000)
  await page.goto(`${BASE}/login`)
  await page.evaluate(async () => {
    localStorage.clear()
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations()
      for (const r of regs) await r.unregister()
    }
    if (window.indexedDB?.databases) {
      const dbs = await window.indexedDB.databases()
      for (const db of dbs) if (db.name) window.indexedDB.deleteDatabase(db.name)
    }
  })
  await page.reload()
  await page.waitForLoadState('networkidle')

  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'dutonghe')
  await page.fill('input[type=password]', '123456')
  await page.locator('button').filter({ hasText: /登录/ }).first().click()
  await page.waitForURL(/dashboard|chat/, { timeout: 10000 })
  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000)

  // 点 你好 (41 条)
  const target = page.locator('.session-item').filter({ hasText: /你好/ }).first()
  await target.waitFor({ state: 'visible', timeout: 5000 })
  await target.click()
  await page.waitForTimeout(8000)

  // ★ 关键验证 1: ↑ 跳到最早按钮应可见 (autoStick 滚到底后离顶部 > 100px)
  const jumpToTopBtn = page.locator('#chat-jump-to-top')
  await jumpToTopBtn.waitFor({ state: 'visible', timeout: 5000 })
  console.log('✅ ↑ 跳到最早 按钮可见')
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/p0-2-jump-btn-visible.png', fullPage: false })

  // ★ 关键验证 2: 点击 ↑ 按钮 → 滚到顶部
  await jumpToTopBtn.click()
  await page.waitForTimeout(1500)

  // 验证 scrollTop = 0 (滚到顶部)
  const scrollTopAfter = await page.evaluate(() => {
    const m = document.querySelector('.messages, [class*="messages"]')
    return m?.scrollTop ?? -1
  })
  console.log(`点击 ↑ 后 scrollTop: ${scrollTopAfter}`)
  expect(scrollTopAfter).toBe(0)
  console.log('✅ 滚到顶部 (scrollTop=0)')

  // ★ 关键验证 3: 顶部应该看到 41 条的第 1 条 "[当前时间: 2026-07-01 22:36] 你好"
  const firstBubble = await page.locator('.bubble').first().textContent()
  console.log(`第 1 条 bubble 内容: ${firstBubble?.slice(0, 60)}`)
  expect(firstBubble).toContain('2026-07-01')
  console.log('✅ 顶部可见历史第 1 条 (2026-07-01)')

  // 截图: 滚到顶 + 看到早期历史
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/p0-2-after-click-top-btn.png', fullPage: false })

  console.log('\n========== ✅ P0-#2 UX 修复验证 PASS ==========')
})
