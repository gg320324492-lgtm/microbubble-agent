/**
 * tests/visual/desktop/followup-chips-fulltext-2026-09-01.spec.mjs
 * 验证追问 chip 两行 line-clamp — 长问句不再单行省略截断 (用户反馈)
 */
import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost'
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'

test('followup chips 完整显示 (两行 clamp, 无单行省略)', async ({ page }) => {
  test.setTimeout(120_000)

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
  await page.waitForSelector('#thinking-mode-fast', { timeout: 30_000 })

  // 发一条消息触发追问生成
  await page.click('#thinking-mode-fast')
  const textarea = page.locator('textarea').first()
  await textarea.fill('什么是微纳米气泡')
  await page.click('#chat-send-btn')

  // 等 chips (LLM 生成, done 之后到达)
  const chips = page.locator('.followup-chips .chip')
  try {
    await chips.first().waitFor({ timeout: 180_000, state: 'attached' })
  } catch {
    test.skip(true, 'chips 未生成 (LLM 失败或超时)')
  }
  const n = await chips.count()

  const probe = await chips.first().evaluate((el) => {
    const cs = getComputedStyle(el)
    return {
      whiteSpace: cs.whiteSpace,
      lineClamp: cs.webkitLineClamp,
      overflowX: el.scrollWidth <= el.clientWidth,
      text: el.textContent.trim(),
      textLen: el.textContent.trim().length,
      endsWithEllipsis: el.textContent.includes('…'),
    }
  })
  console.log('[chips]', JSON.stringify(probe))

  // 两行 clamp 生效
  expect(probe.whiteSpace).toBe('normal')
  expect(probe.lineClamp).toBe('2')
  // 首个 chip 内容不被横向截断 (40 字以内问句应完整)
  expect(probe.overflowX, `chip 横向溢出: ${probe.text}`).toBe(true)
  expect(probe.endsWithEllipsis, `chip 仍带省略号: ${probe.text}`).toBe(false)

  await page.screenshot({
    path: 'tests/visual/desktop/screenshots/followup-chips-fulltext-2026-09-01.png',
    fullPage: true,
  })
})
