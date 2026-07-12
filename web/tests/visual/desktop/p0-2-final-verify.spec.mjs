import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('FINAL P0-#2 端到端验证: 你好 session 41 条全可见 + ↑ 按钮可达', async ({ page }) => {
  test.setTimeout(120000)
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

  console.log('\n========== 1. 登录 杜同贺 ==========')
  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'dutonghe')
  await page.fill('input[type=password]', '123456')
  await page.locator('button').filter({ hasText: /登录/ }).first().click()
  await page.waitForURL(/dashboard|chat/, { timeout: 10000 })
  console.log('✅ 登录成功')

  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/final-1-session-list.png', fullPage: true })

  const target = page.locator('.session-item').filter({ hasText: /你好/ }).first()
  await target.waitFor({ state: 'visible', timeout: 5000 })
  const sessTxt = await target.textContent()
  console.log(`\n========== 2. 你好 session 内容: ${sessTxt?.replace(/\s+/g,' ').slice(0,60)} ==========`)

  await target.click()
  await page.waitForTimeout(8000)

  console.log('\n========== 3. 验证 P0-#1.6 v2 (41 条都在 DOM) ==========')
  const total = await page.locator('.bubble').count()
  console.log(`DOM .bubble 总数: ${total}`)
  expect(total).toBeGreaterThanOrEqual(41)
  const userC = await page.locator('.user-bubble').count()
  const botC = await page.locator('.bot-bubble').count()
  console.log(`角色分布: user=${userC}, bot=${botC}`)
  expect(userC).toBe(29)
  expect(botC).toBe(12)

  console.log('\n========== 4. 验证 P0-#2 (↑ 跳到最早按钮 + 点击滚到顶) ==========')
  const jumpTop = page.locator('#chat-jump-to-top')
  await jumpTop.waitFor({ state: 'visible', timeout: 5000 })
  console.log('✅ ↑ 跳到最早 按钮可见 (在底部时)')
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/final-2-before-jump.png', fullPage: false })

  await jumpTop.click()
  await page.waitForTimeout(1500)
  const scrollTop = await page.evaluate(() => document.querySelector('.messages, [class*="messages"]')?.scrollTop ?? -1)
  console.log(`点击 ↑ 后 scrollTop: ${scrollTop}`)
  expect(scrollTop).toBe(0)
  console.log('✅ 滚到顶部 (scrollTop=0)')

  const firstBubble = await page.locator('.bubble').first().textContent()
  console.log(`顶部第 1 条: ${firstBubble?.replace(/\s+/g,' ').slice(0, 60)}`)
  expect(firstBubble).toContain('2026-07-01')
  console.log('✅ 顶部可见历史第 1 条 (日期匹配 2026-07-01)')
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/final-3-at-top.png', fullPage: false })

  console.log('\n========== 5. 验证 P0-#2 (滚到底部然后 ↑ 按钮再次出现) ==========')
  await page.evaluate(() => {
    const m = document.querySelector('.messages, [class*="messages"]')
    if (m) m.scrollTop = m.scrollHeight
  })
  await page.waitForTimeout(1500)
  await jumpTop.waitFor({ state: 'visible', timeout: 5000 })
  console.log('✅ 滚到底 ↑ 按钮再次可见 (一站式完整 UX)')

  console.log('\n========== 6. 最终全页截图 ==========')
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/final-4-bottom-FULL.png', fullPage: true })

  console.log('\n========== ✅ P0-#1.6 v2 + P0-#2 完整链路 PASS ==========')
  console.log('总累计修复链:')
  console.log('  P0-#1:      LLM_BACKEND=ollama → openai_compat (修 Connection error)')
  console.log('  P0-#1.5:    wrapper shape (修 chat 流不对话)')
  console.log('  P0-#1.6 v1: server fetch fallback (修 server-only session 空白)')
  console.log('  P0-#1.6 v2: orphan cache 修复 (修 "41条仍然看不全" 数据层)')
  console.log('  P0-#2:      ↑ 跳到最早按钮 (修 "41条仍然看不全" UX 层)')
})
