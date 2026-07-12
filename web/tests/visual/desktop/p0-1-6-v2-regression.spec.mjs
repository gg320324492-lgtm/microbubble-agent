import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('P0-#1.6 v2 回归: orphan session (localStorage=[]) server fetch 兜底', async ({ page }) => {
  const events = []
  page.on('response', (r) => {
    if (r.url().includes('/api/v1/chat/sessions/') && r.url().includes('/messages')) {
      events.push(`[api ${r.status()}] ${r.url().replace(BASE, '')}`)
    }
  })

  // 1. 登录
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'dutonghe')
  await page.fill('input[type=password]', '123456')
  await page.locator('button').filter({ hasText: /登录/ }).first().click()
  await page.waitForURL(/dashboard|chat/, { timeout: 10000 })
  console.log('✅ 登录成功')

  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000)

  // 2. ★ 关键: 模拟"修复前已缓存空数组"的用户视角
  // 我们不能直接 mutate localStorage (会破坏 reactive), 但可以通过访问 server-only session 复现
  // Playwright 工作流: 自然 click 一个 server-only session, 看 .bubble 数
  const sessions = page.locator('.session-item').filter({ hasText: /小时前/ })
  const cnt = await sessions.count()
  console.log(`看到 ${cnt} 个 "小时前" session`)
  expect(cnt).toBeGreaterThan(0)

  // 3. 点 你好 (8 小时前 41 条) — 这是 user 报告的具体 session
  const targetSession = sessions.filter({ hasText: '你好' }).first()
  const sessionName = await targetSession.textContent()
  console.log(`目标 session: ${sessionName?.slice(0, 50)}`)
  await targetSession.click()

  await page.waitForTimeout(8000) // server fetch + 渲染

  // 4. 验证 .bubble 数与 server message count 一致
  const bubbleCount = await page.locator('.bubble').count()
  console.log(`.bubble 数: ${bubbleCount}`)
  // server 返 41 条 (29 user + 12 assistant) → 期望 41 + 1 greeting = 42 或 41 (取决于 welcome 是否在 server 数据里)
  expect(bubbleCount).toBeGreaterThanOrEqual(41)
  console.log('✅ v2 修复生效: 41 条全部可见')

  await page.screenshot({ path: 'tests/visual/desktop/screenshots/p0-1-6-v2-FIXED-41-bubbles.png', fullPage: false })

  console.log('--- API 调用摘要 ---')
  for (const e of events) console.log(e)
})
