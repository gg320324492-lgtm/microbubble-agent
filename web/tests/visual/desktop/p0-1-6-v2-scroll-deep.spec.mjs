import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('P0-#1.6 v2 scroll-bottom-deep: 41 条全部都在 DOM 吗', async ({ page }) => {
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

  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'dutonghe')
  await page.fill('input[type=password]', '123456')
  await page.locator('button').filter({ hasText: /登录/ }).first().click()
  await page.waitForURL(/dashboard|chat/, { timeout: 10000 })
  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000)

  const target = page.locator('.session-item').filter({ hasText: /你好/ }).first()
  await target.waitFor({ state: 'visible', timeout: 5000 })
  await target.click()
  await page.waitForTimeout(8000)

  // 1. 看 DOM 里总共有多少 bubbles
  const totalBubbles = await page.locator('.bubble').count()
  console.log(`DOM 总 .bubble: ${totalBubbles}`)

  // 2. 看 visible (viewport 内) 有多少
  const visibleBubbles = await page.locator('.bubble:visible').count()
  console.log(`Viewport 内 .bubble: ${visibleBubbles}`)

  // 3. 滚到底部,再数
  await page.evaluate(() => {
    const m = document.querySelector('.messages, [class*="messages"]')
    if (m) m.scrollTop = m.scrollHeight
  })
  await page.waitForTimeout(1500)
  const visibleAfterScroll = await page.locator('.bubble:visible').count()
  console.log(`滚到底后 viewport 内 .bubble: ${visibleAfterScroll}`)

  // 4. 拿 user/assistant 角色的实际分布
  const userCount = await page.locator('.user-bubble').count()
  const botCount = await page.locator('.bot-bubble').count()
  console.log(`角色: user=${userCount}, bot=${botCount}, total=${userCount + botCount}`)

  // 5. 截图全页
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/v2-scroll-DEEP.png', fullPage: true })

  // 6. 列出最后 5 条 (滚到底后)
  const lastBubbles = await page.locator('.bubble').allTextContents()
  console.log('\n最后 5 条:')
  for (let i = Math.max(0, lastBubbles.length - 5); i < lastBubbles.length; i++) {
    const c = lastBubbles[i].replace(/\s+/g, ' ').slice(0, 80)
    console.log(`  [${i}]: ${c}`)
  }

  // 7. 列出所有可见的 (不滚回顶就看的)
  const allBubbles = await page.locator('.bubble').allTextContents()
  console.log(`\n所有 ${allBubbles.length} 条气泡 (DOM 实际存在):`)

  // 8. 找带 e2e 标记的 (应是末尾)
  const e2eBubbles = allBubbles.filter(b => b.includes('e2e验证-1783834605866'))
  console.log(`含 e2e 标记的: ${e2eBubbles.length}`)

  // 9. 找 user bubble 不应该是空
  const emptyUserBubbles = await page.locator('.user-bubble').filter({ hasText: /^\s*$/ }).count()
  const emptyBotBubbles = await page.locator('.bot-bubble').filter({ hasText: /^\s*$/ }).count()
  console.log(`空 user bubble: ${emptyUserBubbles}, 空 bot bubble: ${emptyBotBubbles}`)

  console.log(`\nDOM 中实际 .bubble: ${totalBubbles}, user+bot: ${userCount + botCount}`)
})
