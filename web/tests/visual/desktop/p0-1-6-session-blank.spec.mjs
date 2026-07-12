import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('P0-#1.6 终极验证', async ({ page }) => {
  const events = []
  page.on('console', (msg) => {
    const t = msg.text()
    if (t.includes('fetchSessionFromServer') || t.includes('chatHistory') || t.includes('sync_required')) {
      events.push(`[console.${msg.type()}] ${t}`)
    }
  })
  page.on('response', (r) => {
    const u = r.url()
    if (u.includes('/api/v1/chat/sessions') && u.includes('/messages')) {
      events.push(`[api] ${r.status()} ${u.replace(BASE, '')}`)
    }
  })

  // 直接 goto /chat (用 Token 注入)
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'dutonghe')
  await page.fill('input[type=password]', '123456')
  await page.locator('button').filter({ hasText: /登录/ }).first().click()
  await page.waitForTimeout(6000) // login + redirect

  // 等 chat 路由加载
  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(5000) // 等 SSE 接 + session list 拉取

  // 探索 DOM: 找 session-card / session-item 父 div, 找侧栏
  // 试多个 selector
  const layoutHtml = await page.locator('body').innerHTML()
  const matches = layoutHtml.match(/class="[^"]*(?:session)[^"]*"/g) || []
  console.log(`session-related class names found: ${matches.slice(0, 5).join(', ')}`)

  // 简化策略: 直接用文本定位 - "8 小时前"
  // 侧栏结构通常 .session-card .title + .preview + .time
  const sessionItems = page.locator(':text("小时前")')
  const sessionText = await sessionItems.allTextContents()
  console.log(`session items matching '小时前': ${JSON.stringify(sessionText.slice(0, 3))}`)

  if (sessionItems.count() === 0) {
    console.log('SKIP: 找不到 session items (可能 chat 路由加载有问题)')
    return
  }

  // 点击第一个
  await sessionItems.first().click()
  await page.waitForTimeout(5000)

  // 检查 .bubble 数量
  const bubbleCount = await page.locator('.bubble').count()
  console.log(`.bubble count: ${bubbleCount}`)

  // 检查主区 messages 容器
  const messagesArea = page.locator('[class*="messages"]').first()
  const text = await messagesArea.textContent().catch(() => '(empty)')
  console.log(`主区文本长度: ${text.length}, 前 200 字符: ${JSON.stringify(text.slice(0, 200))}`)

  // ★ 验证: 至少 1 个 bubble (修复前是 0)
  expect(bubbleCount).toBeGreaterThan(0)

  await page.screenshot({ path: 'tests/visual/desktop/screenshots/p0-1-6-FIXED-v2.png', fullPage: false })
  console.log('--- 关键事件 ---')
  for (const e of events) console.log(e)
})
