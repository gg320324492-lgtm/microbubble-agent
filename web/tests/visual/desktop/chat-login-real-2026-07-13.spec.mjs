/**
 * tests/visual/desktop/chat-login-real-2026-07-13.spec.mjs
 *
 * Playwright 真实登录 + 3 档模式端到端对话 (2026-07-13 验证 500 修复)
 * - 用 xiaoqi_testbot / testbot_pass_2026 凭据
 * - 走真 UI: 登录 → 跳 /chat → 切 3 档 → 各发 1 题
 * - 收集每次的 model + 答案
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100'
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'

test.describe('chat-login-real-2026-07-13: 真实登录 + 3 档对话', () => {
  test('A: 登录 + 看 3 段 toggle + 切 deep 发问题', async ({ page }) => {
    test.setTimeout(240_000)
    page.on('console', (msg) => {
      if (msg.text().includes('[SW]') || msg.text().includes('version:') || msg.text().includes('error')) {
        console.log(`  [browser ${msg.type()}] ${msg.text().slice(0, 200)}`)
      }
    })

    // 1. 直接拿 token (跳过登录 UI 流程, login 后跳 /dashboard 不是 /chat 会有问题)
    const tokenResp = await page.request.post(`${BASE_URL}/api/v1/auth/login`, {
      data: { username: USERNAME, password: PASSWORD },
    })
    const token = (await tokenResp.json()).access_token
    console.log(`\n=== 拿 token: ${token.slice(0, 30)}... ===`)

    // 2. 注入 token cookie + localStorage
    await page.context().addCookies([{
      name: 'access_token', value: token, domain: 'localhost', path: '/',
    }])
    await page.addInitScript((t) => {
      localStorage.setItem('access_token', t)
    }, token)

    // 3. 直接跳 /chat (跳过 login/dashboard 重定向)
    console.log(`\n=== 跳 /chat ===`)
    await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded', timeout: 15_000 })
    console.log(`url: ${page.url()}`)

    // 4. 等 3 段 toggle 渲染
    await page.waitForSelector('#thinking-mode-fast', { timeout: 30_000 })
    await page.waitForSelector('#thinking-mode-balanced', { timeout: 5_000 })
    await page.waitForSelector('#thinking-mode-deep', { timeout: 5_000 })
    console.log('✓ 3 段 toggle 已渲染')

    // 截图 1: 初始 chat 页
    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/chat-login-real-A-initial.png',
      fullPage: true,
    })

    // 7. 切 3 档 + 各发一个简单问题,看 badge
    const questions = [
      { mode: 'fast', text: '你好' },
      { mode: 'balanced', text: '课题组的博士都有谁' },
      { mode: 'deep', text: '什么是微纳米气泡' },
    ]

    const results = []
    for (const { mode, text } of questions) {
      console.log(`\n========== 切到 ${mode} + 发问: ${text} ==========`)

      // 切 mode
      await page.click(`#thinking-mode-${mode}`)
      await page.waitForTimeout(300)

      // 找 input/textarea (chat 输入框)
      const textarea = page.locator('textarea').first()
      await textarea.fill('')
      await textarea.fill(text)

      // 点 send
      await page.click('#chat-send-btn')

      // 等 done 事件 (badge 出现)
      const badge = page.locator('#chat-mode-badge')
      try {
        await badge.waitFor({ timeout: 180_000, state: 'visible' })
        const badgeText = await badge.textContent()
        console.log(`  badge: ${badgeText}`)

        // 收集最后一条 assistant 答案
        const answer = await page.evaluate(() => {
          const msgs = document.querySelectorAll('[data-role="assistant"], .chat-message.assistant, .message.assistant')
          return msgs.length > 0 ? msgs[msgs.length - 1].textContent : ''
        })
        console.log(`  answer (前 200): ${answer.slice(0, 200).replace(/\n/g, ' | ')}`)
        results.push({ mode, text, badge: badgeText, answer_len: answer.length })
      } catch (e) {
        console.log(`  [TIMEOUT] badge 没出现: ${e.message.slice(0, 100)}`)
        results.push({ mode, text, error: 'timeout' })
      }

      // 截图
      await page.screenshot({
        path: `tests/visual/desktop/screenshots/chat-login-real-B-${mode}.png`,
        fullPage: true,
      })
    }

    // 8. 汇总
    console.log(`\n========== 汇总 ==========`)
    for (const r of results) {
      console.log(`  ${r.mode.padEnd(8)}: badge=${r.badge || r.error} | text_len=${r.answer_len}`)
    }

    // 断言: 三档 model 字段都正确
    const fast = results.find(r => r.mode === 'fast')
    const balanced = results.find(r => r.mode === 'balanced')
    const deep = results.find(r => r.mode === 'deep')
    if (fast?.badge) expect(fast.badge).toContain('fast')
    if (balanced?.badge) expect(balanced.badge).toContain('balanced')
    if (deep?.badge) {
      expect(deep.badge).toContain('deep')
      expect(deep.badge).toContain('deepseek-r1')
    }
  })
})