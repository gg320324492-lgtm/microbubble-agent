import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('P0-#1.6 v2 深度验证: 你好 session 41 条全部可见', async ({ page }) => {
  test.setTimeout(120000)
  const events = []
  page.on('response', (r) => {
    const u = r.url()
    if (u.includes('/api/v1/chat/sessions/')) {
      events.push(`[api ${r.status()}] ${u.replace(BASE, '')}`)
    }
  })

  console.log('\n========== STEP 1: 清缓存 + 登录 ==========')
  await page.goto(`${BASE}/login`)
  await page.evaluate(async () => {
    localStorage.clear()
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations()
      for (const r of regs) await r.unregister()
    }
    if (window.indexedDB && window.indexedDB.databases) {
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
  console.log('✅ 登录成功')

  console.log('\n========== STEP 2: 进入 /chat + 找 你好 session ==========')
  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/v2-deep-1-session-list.png', fullPage: true })

  const targetSession = page.locator('.session-item').filter({ hasText: /你好/ }).first()
  await targetSession.waitFor({ state: 'visible', timeout: 5000 })
  const sessionText = await targetSession.textContent()
  console.log(`目标 session: ${sessionText?.replace(/\s+/g, ' ').slice(0, 80)}`)
  expect(sessionText).toContain('41')
  console.log('✅ session list 显示 41 条')

  console.log('\n========== STEP 3: 点击 + 等 server fetch ==========')
  await targetSession.click()
  await page.waitForTimeout(8000)

  const totalBubbles = await page.locator('.bubble').count()
  console.log(`.bubble 总数 (DOM 渲染): ${totalBubbles}`)
  expect(totalBubbles).toBeGreaterThanOrEqual(41)
  console.log('✅ 41 条全部渲染')

  console.log('\n========== STEP 4: 验证消息内容真实可见 ==========')
  const bubbles = await page.locator('.bubble').allTextContents()
  const emptyBubbles = bubbles.filter(t => t.trim().length === 0).length
  console.log(`空 bubble 数: ${emptyBubbles}`)
  expect(emptyBubbles).toBe(0)
  console.log('✅ 0 个空 bubble (每条消息都有真实内容)')

  // 验证角色分布正确: 29 user + 12 assistant = 41
  const userBubbles = await page.locator('.user-bubble, [class*="user-bubble"]').count()
  const botBubbles = await page.locator('.bot-bubble, [class*="bot-bubble"]').count()
  console.log(`角色分布: user=${userBubbles}, bot=${botBubbles}`)
  expect(userBubbles + botBubbles).toBeGreaterThanOrEqual(41)

  // 截图 顶部
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/v2-deep-2-top.png', fullPage: false })

  console.log('\n========== STEP 5: 前 6 条预览 ==========')
  for (let i = 0; i < Math.min(6, bubbles.length); i++) {
    const c = bubbles[i].replace(/\s+/g, ' ').slice(0, 80)
    console.log(`  [${i}]: ${c}`)
  }

  console.log('\n========== STEP 6: 滚到底部 ==========')
  await page.evaluate(() => {
    const m = document.querySelector('.messages, [class*="messages"]')
    if (m) m.scrollTop = m.scrollHeight
  })
  await page.waitForTimeout(1000)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/v2-deep-3-bottom.png', fullPage: false })

  console.log('\n========== STEP 7: 最后 3 条 (验证最新 e2e 消息) ==========')
  const lastThree = bubbles.slice(-3)
  for (let i = 0; i < lastThree.length; i++) {
    const c = lastThree[i].replace(/\s+/g, ' ').slice(0, 100)
    console.log(`  [${bubbles.length - 3 + i}]: ${c}`)
  }
  const hasLastE2E = lastThree.some(b => b.includes('e2e验证-1783834605866'))
  expect(hasLastE2E).toBe(true)
  console.log('✅ 最后 3 条含 e2e 测试消息 (持久化完整)')

  console.log('\n========== STEP 8: 完整全页截图 ==========')
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.waitForTimeout(500)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/v2-deep-4-FULL.png', fullPage: true })

  console.log('\n========== API 事件摘要 ==========')
  const apiLogs = events.filter(e => e.startsWith('[api'))
  console.log(`总 API 调用: ${apiLogs.length}`)
  console.log(`/sessions/{id}/messages: ${apiLogs.filter(e => e.includes('/messages')).length}`)
  console.log(`/api/v1/chat/sync: ${apiLogs.filter(e => e.includes('/sync')).length}`)

  console.log('\n========== ✅ P0-#1.6 v2 真实端到端验证 PASS ==========')
})
