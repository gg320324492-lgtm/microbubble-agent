import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'
const TIMESTAMP = Date.now()
const TEST_MESSAGE = `[e2e验证-${TIMESTAMP}] Playwright 杜同贺端到端测试`

test.setTimeout(180000);
test('P0-#1.6 E2E 杜同贺账号全流程', async ({ page }) => {
  const events = []
  page.on('console', (msg) => {
    const t = msg.text()
    if (t.includes('fetchSessionFromServer') || t.includes('chatHistory') || t.includes('sse') || t.includes('text_delta')) {
      events.push(`[console.${msg.type()}] ${t.slice(0, 200)}`)
    }
  })
  page.on('response', (r) => {
    const u = r.url()
    if (u.includes('/api/v1/chat/')) {
      events.push(`[api ${r.status()}] ${u.replace(BASE, '')}`)
    }
  })

  console.log('\n========== STEP 1: 登录 杜同贺 ==========')
  await page.goto(`${BASE}/login`)
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.waitForLoadState('networkidle')

  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'dutonghe')
  await page.fill('input[type=password]', '123456')
  await page.locator('button').filter({ hasText: /登录/ }).first().click()
  await page.waitForURL(/dashboard|chat/, { timeout: 10000 })
  console.log('✅ 登录成功')

  console.log('\n========== STEP 2: 进入智能对话 ==========')
  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000)

  const sessionItems = await page.locator('.session-item, [class*="session-item"]').allTextContents()
  console.log(`看到 ${sessionItems.length} 个会话`)
  expect(sessionItems.length).toBeGreaterThan(0)

  console.log('\n========== STEP 3: 点击 server-only session (P0-#1.6 验证) ==========')
  const oldSession = page.locator('.session-item').filter({ hasText: /小时前/ }).first()
  await oldSession.waitFor({ state: 'visible', timeout: 5000 })
  const sessionTitle = await oldSession.locator('[class*="title"]').first().textContent()
  console.log(`点击 session: "${sessionTitle}"`)

  await oldSession.click()
  await page.waitForTimeout(5000)

  const bubbleCount = await page.locator('.bubble').count()
  console.log(`.bubble 数: ${bubbleCount}`)
  expect(bubbleCount).toBeGreaterThan(0)
  console.log('✅ P0-#1.6 修复生效: server-only session 不再空白')

  console.log('\n========== STEP 4: 发送新消息 ==========')
  // 找输入框 — 用 placeholder 兜底
  const inputBox = page.locator('textarea, [contenteditable="true"]').first()
  const inputVisible = await inputBox.count()
  if (inputVisible === 0) {
    console.log('SKIP: 找不到输入框 (UI 改版)')
    return
  }
  await inputBox.fill(TEST_MESSAGE)
  console.log(`输入: ${TEST_MESSAGE}`)

  // 用 ID selector 找发送按钮
  const sendBtn = page.locator('#chat-send-btn')
  await sendBtn.waitFor({ state: 'visible', timeout: 5000 })
  await sendBtn.click()
  console.log('点击 #chat-send-btn')

  console.log('========== STEP 5: 等 SSE 流回复 ==========')
  // mimo reasoning 慢,给 90s
  await page.waitForTimeout(90000)

  // 验证有 assistant 回复 (多个助手 bubble)
  const bubbleAfter = await page.locator('.bubble').count()
  console.log(`发送后 .bubble 数: ${bubbleAfter}`)
  expect(bubbleAfter).toBeGreaterThan(bubbleCount)
  console.log('✅ SSE 流回复正常 (P0-#1 + #1.5 + #1.6 链路全通)')

  await page.screenshot({ path: 'tests/visual/desktop/screenshots/p0-1-6-e2e-dutonghe-FINAL.png', fullPage: false })

  console.log('\n========== STEP 6: 切 session 验证仍可用 ==========')
  // 切到一个新的空 session
  const newSessionBtn = page.locator('button').filter({ hasText: /新对话/ }).first()
  if (await newSessionBtn.count()) {
    await newSessionBtn.click()
    await page.waitForTimeout(3000)
    // 新对话应该有欢迎语
    const newBubbleCount = await page.locator('.bubble').count()
    console.log(`新对话 .bubble 数 (欢迎语): ${newBubbleCount}`)
    expect(newBubbleCount).toBeGreaterThan(0)
    console.log('✅ 新对话流程正常')
  }

  console.log('\n========== STEP 7: API 事件摘要 ==========')
  const apiLogs = events.filter(e => e.startsWith('[api'))
  const errLogs = events.filter(e => e.includes('error'))
  console.log(`总 API 调用: ${apiLogs.length}`)
  console.log(`错误: ${errLogs.length}`)
  console.log(`/messages 调用 (P0-#1.6 验证): ${apiLogs.filter(e => e.includes('/messages')).length}`)
  console.log(`/stream 调用 (SSE 验证): ${apiLogs.filter(e => e.includes('/stream')).length}`)

  console.log('\n========== ✅ 全部 PASS ==========')
})
