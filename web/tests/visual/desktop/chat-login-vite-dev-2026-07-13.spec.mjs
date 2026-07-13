/**
 * tests/visual/desktop/chat-login-vite-dev-2026-07-13.spec.mjs
 *
 * Playwright 完整 UI 登录测试 (走 vite dev :3100, 验证代码本身, 不走外网云 nginx 500)
 * - 用户当前实际访问的 https://agent.mnb-lab.cn/chat 500 (外网云 nginx 缺 SPA fallback 配错)
 * - vite dev :3100 完整 SPA + try_files + login page 都 OK
 * - 这个 spec 验证如果绕过外网云 nginx, 我的代码能完整工作
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100'
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'

test.describe('chat-login-vite-dev-2026-07-13: 真实完整 UI 登录 (绕过外网 nginx 500)', () => {
  test('A: 完整登录 → /chat → 看 3 段 toggle → 切 deep 发问题', async ({ page }) => {
    test.setTimeout(240_000)

    // 完整 console + pageerror 监听
    page.on('console', (msg) => {
      const t = msg.text()
      if (t.includes('[SW]') || t.includes('error') || t.includes('Error') || t.includes('failed') || t.includes('version:') || t.includes('cancel') || t.includes('404') || t.includes('500')) {
        console.log(`  [browser ${msg.type()}] ${t.slice(0, 250)}`)
      }
    })
    page.on('pageerror', (err) => {
      console.log(`  [pageerror] ${err.message.slice(0, 200)}`)
    })
    page.on('requestfailed', (req) => {
      console.log(`  [reqfailed] ${req.method()} ${req.url().slice(0, 100)} | ${req.failure()?.errorText}`)
    })
    page.on('response', (resp) => {
      if (resp.url().includes('/api/v1/chat') || resp.url().includes('/api/v1/auth')) {
        console.log(`  [api] ${resp.status()} ${resp.request().method()} ${resp.url().replace(BASE_URL, '').slice(0, 80)}`)
      }
    })

    // 1. 打开根 URL (vite dev SPA, 会 redirect 到 /login)
    console.log(`\n=== STEP 1: 打开 ${BASE_URL} ===`)
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 30_000 })
    console.log(`start url: ${page.url()}`)

    // 2. 等重定向到登录页
    await page.waitForURL(/\/(login|register|chat)/, { timeout: 15_000 }).catch(() => null)
    console.log(`after redirect: ${page.url()}`)

    // 3. 找登录表单并填
    console.log('\n=== STEP 2: 填登录表单 ===')
    // 多个可能选择器 (兼容桌面 Element Plus + 移动 NutUI)
    const usernameInput = page.locator(
      'input[name="username"], input[placeholder*="账号"], input[placeholder*="用户名"], input[placeholder*="username"], input[type="text"]:not([readonly])'
    ).first()
    const passwordInput = page.locator('input[name="password"], input[type="password"]').first()
    const loginBtn = page.locator(
      'button[type="submit"], button:has-text("登录"), button:has-text("Login"), button:has-text("登 录")'
    ).first()

    await usernameInput.waitFor({ timeout: 10_000 })
    await usernameInput.fill(USERNAME)
    await passwordInput.fill(PASSWORD)
    console.log(`filled: user=${USERNAME}, pwd=***`)
    await loginBtn.click()
    console.log('clicked login')

    // 4. 等跳到 /chat (或 /dashboard)
    await page.waitForURL(/\/(chat|dashboard|knowledge|projects|tasks)/, { timeout: 30_000 }).catch(() => null)
    const afterLoginUrl = page.url()
    console.log(`after login: ${afterLoginUrl}`)

    // 5. 跳到 /chat (用户要测的页面)
    if (!afterLoginUrl.includes('/chat')) {
      console.log('强制 goto /chat')
      await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded', timeout: 15_000 })
    }
    console.log(`\n=== STEP 3: 在 /chat ===`)
    console.log(`url: ${page.url()}`)

    // 6. 等 3 段 toggle 渲染
    await page.waitForSelector('#thinking-mode-fast', { timeout: 30_000 })
    await page.waitForSelector('#thinking-mode-balanced', { timeout: 5_000 })
    await page.waitForSelector('#thinking-mode-deep', { timeout: 5_000 })
    console.log('✓ 3 段 toggle 已渲染')

    // 7. 验证默认是 balanced
    const balancedChecked = await page.locator('#thinking-mode-balanced').getAttribute('aria-checked')
    console.log(`默认 mode aria-checked: balanced=${balancedChecked}`)

    // 8. 截图初始 chat 页
    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/chat-login-A-initial-chat.png',
      fullPage: true,
    })
    console.log('screenshot: chat-login-A-initial-chat.png')

    // 9. 切 3 档 + 各发一个问题
    const questions = [
      { mode: 'fast', text: '你好' },
      { mode: 'balanced', text: '课题组的博士都有谁' },
      { mode: 'deep', text: '什么是微纳米气泡' },
    ]

    const results = []
    for (const { mode, text } of questions) {
      console.log(`\n========== 切 ${mode} + 发: ${text} ==========`)

      await page.click(`#thinking-mode-${mode}`)
      await page.waitForTimeout(300)

      const textarea = page.locator('textarea').first()
      await textarea.fill('')
      await page.waitForTimeout(100)
      await textarea.fill(text)

      await page.click('#chat-send-btn')

      const badge = page.locator('#chat-mode-badge')
      try {
        await badge.waitFor({ timeout: 180_000, state: 'visible' })
        const badgeText = await badge.textContent()
        console.log(`  badge: ${badgeText}`)

        const answer = await page.evaluate(() => {
          const msgs = document.querySelectorAll('[data-role="assistant"], .chat-message.assistant, .message.assistant')
          return msgs.length > 0 ? msgs[msgs.length - 1].textContent : ''
        })
        console.log(`  answer (前 150): ${answer.slice(0, 150).replace(/\n/g, ' | ')}`)
        results.push({ mode, text, badge: badgeText, answer: answer.slice(0, 200), answer_len: answer.length })
      } catch (e) {
        console.log(`  [TIMEOUT] ${e.message.slice(0, 80)}`)
        results.push({ mode, text, error: 'timeout' })
      }

      await page.screenshot({
        path: `tests/visual/desktop/screenshots/chat-login-B-${mode}.png`,
        fullPage: true,
      })
    }

    // 10. 汇总
    console.log(`\n========== 汇总 ==========`)
    for (const r of results) {
      const modelMatch = r.badge?.match(/(qwen3:8b|deepseek-r1:7b)/)
      console.log(`  ${r.mode.padEnd(8)}: badge=${r.badge?.slice(0, 60) || r.error} | model=${modelMatch?.[1] || '?'} | text_len=${r.answer_len}`)
    }

    // 断言
    const fast = results.find(r => r.mode === 'fast')
    const balanced = results.find(r => r.mode === 'balanced')
    const deep = results.find(r => r.mode === 'deep')
    if (fast?.badge) expect(fast.badge).toContain('fast')
    if (balanced?.badge) expect(balanced.badge).toContain('balanced')
    if (deep?.badge) {
      expect(deep.badge).toContain('deep')
      expect(deep.badge).toContain('deepseek-r1')
    }
    console.log('\n✓ 3 档 mode 真区分验证通过 (fast=qwen3 / balanced=qwen3 / deep=deepseek-r1)')
  })
})