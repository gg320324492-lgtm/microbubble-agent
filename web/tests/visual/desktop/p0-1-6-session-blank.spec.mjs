import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('P0-#1.6 调试版', async ({ page }) => {
  const logs = []
  page.on('console', (msg) => logs.push(`[console.${msg.type()}] ${msg.text()}`))
  page.on('requestfailed', (req) => logs.push(`[req-fail] ${req.method()} ${req.url()}`))
  page.on('response', (res) => {
    if (res.url().includes('/api/v1/chat/')) {
      logs.push(`[api] ${res.status()} ${res.url().replace(BASE, '')}`)
    }
  })

  await page.goto(`${BASE}/login`)
  await page.evaluate(async () => {
    localStorage.clear()
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations()
      for (const r of regs) await r.unregister()
    }
  })
  await page.reload()
  await page.waitForLoadState('networkidle')

  await page.fill('input[placeholder*="用户名"], input[placeholder*="username"], input[name="username"]', 'dutonghe').catch(() => {})
  await page.fill('input[type=password]', '123456')
  const btn = page.locator('button').filter({ hasText: /登录|login/i }).first()
  if (await btn.count()) await btn.click()
  await page.waitForTimeout(5000)

  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000) // 等 server session list 拉取

  // 列出会话列表项 (任何包含 '小时前' 时间的)
  const items = page.locator('text=/小时前|刚刚/').all()
  const allItems = await items
  console.log(`session item count: ${allItems.length}`)
  logs.push(`session item count: ${allItems.length}`)

  // 找一个 session item 的容器, 点进去
  // 通常 session 是 .session-item 或包含 session-id 的 div
  const sessionCard = page.locator('.session-card, [class*="session-card"], [class*="session-item"]').filter({ hasText: /小时前/ }).first()
  const cardCount = await page.locator('.session-card, [class*="session-card"], [class*="session-item"]').count()
  console.log(`session card count: ${cardCount}`)

  // 兜底: 找侧栏最顶的会话
  if (await sessionCard.count() === 0) {
    // 尝试点侧栏第一个 session
    const firstSession = page.locator('[class*="session"]').first()
    if (await firstSession.count()) {
      await firstSession.click()
      console.log('clicked first .session element')
    }
  } else {
    await sessionCard.click()
    console.log('clicked session card')
  }
  await page.waitForTimeout(5000) // server fetch + render

  // 多种 selector 兜底
  const selectors = ['.msg-row', '[class*="msg-row"]', '.bubble', '[class*="bubble"]', '.messages > *', '[class*="messages"] > *']
  for (const sel of selectors) {
    const c = await page.locator(sel).count()
    console.log(`  selector '${sel}' count: ${c}`)
  }

  // 整体文本检查
  const bodyText = await page.locator('body').textContent()
  console.log(`body text length: ${bodyText.length}`)
  const firstChars = bodyText.slice(0, 200)
  console.log(`body text first 200: ${JSON.stringify(firstChars)}`)

  await page.screenshot({ path: 'tests/visual/desktop/screenshots/p0-1-6-debug.png', fullPage: true })
  console.log('--- CONSOLE LOGS ---')
  for (const l of logs) console.log(l)
})
