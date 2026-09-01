/**
 * tests/visual/desktop/chat-overlap-fix-2026-09-01.spec.mjs
 * 验证长对话消息不再重叠 (虚拟定位阈值 50→1000, 常态走 inline 流式布局)
 *
 * 断言:
 *  1. 消息行为 inline 模式 (非 virtual absolute 定位)
 *  2. 相邻消息包围盒不重叠 (next.top >= prev.bottom - 2px 容差)
 *  3. 消息数报告 (>= 50 时即复现用户场景)
 */
import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost'
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'

test('长对话消息行 inline 流式布局且互不重叠', async ({ page }) => {
  test.setTimeout(600_000)

  let token = null
  for (let i = 0; i < 4; i++) {
    const r = await page.request.post(`${BASE_URL}/api/v1/auth/login`, {
      data: { username: USERNAME, password: PASSWORD },
    })
    if (r.status() === 200) { token = (await r.json()).access_token; break }
    await page.waitForTimeout(20_000)
  }
  expect(token).toBeTruthy()

  await page.context().addCookies([{ name: 'access_token', value: token, domain: 'localhost', path: '/' }])
  await page.addInitScript((t) => localStorage.setItem('access_token', t), token)
  await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.chat-message-row', { timeout: 30_000 })
  await page.waitForTimeout(1500) // 历史渲染 + 图片/富块稳定

  const rows = page.locator('.chat-message-row')

  // 灌到 >50 条消息, 精确复现用户场景 (旧阈值 50 即触发虚拟定位重叠)
  const have = await rows.count()
  if (have < 60) {
    const sessionsResp = await page.request.get(`${BASE_URL}/api/v1/chat/sessions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const sessionsJson = await sessionsResp.json()
    const sessions = Array.isArray(sessionsJson) ? sessionsJson : (sessionsJson.items || [])
    const target = sessions.length ? sessions[0] : null
    const sessionId = target?.id
    if (sessionId) {
      const need = 60 - have
      for (let i = 0; i < need; i++) {
        // write 限流 30/min → 2.2s 间隔 + 429 退避
        for (let attempt = 0; attempt < 3; attempt++) {
          const r = await page.request.post(`${BASE_URL}/api/v1/chat/sessions/${sessionId}/messages`, {
            headers: { Authorization: `Bearer ${token}` },
            data: {
              role: i % 2 === 0 ? 'user' : 'assistant',
              content: i % 2 === 0
                ? `测试问题 ${i}: 微纳米气泡在水质处理中的应用机制是什么？包括溶解氧供给、接触面积、促进微生物活性与抑制有害生物四个方面。`
                : `测试回答 ${i}: 微纳米气泡通过形成大量细小气泡提供溶解氧, 增大气液接触面积, 促进微生物代谢活性, 并在一定条件下抑制有害病原菌, 从而改善水质。\n\n1. 溶解氧供给: 气泡提供充足氧气。\n2. 接触面积: 界面接触显著增大。\n3. 微生物活性: 代谢速率提升。\n4. 抑制有害生物: 减少病原菌数量。`,
              client_msg_id: `overlap-seed-${Date.now()}-${i}`,
            },
          })
          if (r.status() === 201) break
          if (r.status() === 429) {
            console.log(`[overlap] seed 429, wait 30s (i=${i})`)
            await page.waitForTimeout(30_000)
            continue
          }
          break
        }
        await page.waitForTimeout(2200)
      }
    }
    // 重载会话历史
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForSelector('.chat-message-row', { timeout: 30_000 })
    await page.waitForTimeout(2500)
  }
  const rowCount = await rows.count()
  console.log(`[overlap] 灌入后消息行数: ${rowCount}`)

  const count = rowCount
  console.log(`[overlap] 消息行数: ${count}`)
  expect(count).toBeGreaterThan(0)

  // 1. 全部 inline 模式 (阈值 1000 生效, 常态不再进入 virtual absolute 定位)
  const virtualCount = await page.locator('.chat-message-row.virtual').count()
  console.log(`[overlap] virtual 模式行数: ${virtualCount}`)
  expect(virtualCount, '消息不应进入 virtual absolute 定位 (重叠根源)').toBe(0)

  // 2. 相邻消息包围盒不重叠 (跳过 display:none)
  const overlaps = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.chat-message-row')]
    const boxes = rows
      .map((el) => el.getBoundingClientRect())
      .filter((r) => r.height > 0)
    const bad = []
    for (let i = 1; i < boxes.length; i++) {
      const prev = boxes[i - 1]
      const cur = boxes[i]
      if (cur.top < prev.bottom - 2) {
        bad.push({ i, overlapPx: Math.round(prev.bottom - cur.top) })
      }
    }
    return { pairs: boxes.length - 1, bad }
  })
  console.log(`[overlap] 相邻对: ${overlaps.pairs}, 重叠: ${JSON.stringify(overlaps.bad.slice(0, 5))}`)
  expect(overlaps.bad, `发现 ${overlaps.bad.length} 处消息重叠`).toHaveLength(0)

  await page.screenshot({
    path: 'tests/visual/desktop/screenshots/chat-overlap-fix-2026-09-01.png',
    fullPage: true,
  })
})
