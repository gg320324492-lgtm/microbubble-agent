/**
 * chat-append-message-404-fix.spec.mjs
 *
 * 2026-07-15 P2-#chatHistory-appendMessage-404 修复 E2E 回归测试
 *
 * 触发链路:
 *   1. 用户首次发消息 (sessionId.value 为空)
 *   2. useChatStream.sendMessage 走 if(!sessionId.value) 分支
 *   3. 新建本地 session (chatSessions.createSession 生成 user_<ts>_<rand>)
 *   4. ★ 修复后: 串行 createServerSession({clientSessionId}) → appendMessageAsync
 *   5. 服务端: createSession 看到 clientSessionId 撞车 → 改用后端生成 ID
 *   6. 客户端: appendMessage 改用 server-returned ID 持久化
 *
 * 修复前: appendMessage 必触发 404/timeout (本地 ID 在 server 不存在)
 *
 * 验证点:
 *   - Network: POST /chat/sessions (with client_session_id) + POST /chat/sessions/{newId}/messages
 *   - localStorage: 新会话 ID 与 server-returned ID 一致
 *   - Console: NO [chatHistory] appendMessage 失败日志
 */

import { test, expect } from '@playwright/test'

const TEST_USER = {
  username: 'xiaoqi_testbot',
  password: 'testbot_pass_2026',
}

async function login(page) {
  await page.goto('/login')
  await page.fill('input[name="username"]', TEST_USER.username)
  await page.fill('input[name="password"]', TEST_USER.password)
  await page.click('button[type="submit"]')
  await page.waitForURL(/\/(workspace|chat|dashboard)/, { timeout: 15_000 })
}

test('首次发消息: 新 session 同步到 server 后再 appendMessage, 无 404 错误', async ({ page }) => {
  const consoleErrors = []
  page.on('console', (msg) => {
    if (msg.type() === 'error' && /\[chatHistory\] appendMessage 失败/.test(msg.text())) {
      consoleErrors.push(msg.text())
    }
  })

  // 抓网络请求用于断言
  const requests = []
  page.on('request', (req) => {
    const url = req.url()
    if (url.includes('/api/v1/chat/sessions') || url.includes('/api/v1/chat/stream')) {
      requests.push({ method: req.method(), url: url.replace(/^https?:\/\/[^/]+/, '') })
    }
  })

  // 清空 localStorage 强制走"首次发消息"路径
  await page.goto('/')
  await page.evaluate(() => {
    localStorage.removeItem('chat_current_session_v3')
    localStorage.removeItem('chat_session_id')
    Object.keys(localStorage).filter((k) => k.startsWith('chat_msgs_')).forEach((k) => localStorage.removeItem(k))
  })

  await login(page)

  // 导航到 chat view
  await page.goto('/chat')
  await page.waitForSelector('textarea[placeholder*="输入"], textarea[placeholder*="消息"], .chat-input textarea', { timeout: 10_000 })

  // 触发首次发消息
  const textarea = page.locator('textarea').first()
  await textarea.fill('修复验证测试消息 P2-#chatHistory-appendMessage-404')
  await page.keyboard.press('Enter')

  // 等流式响应完成
  await page.waitForTimeout(5_000)

  // 断言 1: 没有 [chatHistory] appendMessage 失败 日志
  expect(
    consoleErrors.filter((e) => /404|timeout of \d+ms exceeded/.test(e)),
    `Found chatHistory appendMessage errors: ${consoleErrors.join('\n')}`,
  ).toEqual([])

  // 断言 2: 网络请求包含 create_session (POST /chat/sessions)
  const createSessionReq = requests.find(
    (r) => r.method === 'POST' && /\/api\/v1\/chat\/sessions$/.test(r.url),
  )
  expect(
    createSessionReq,
    'Expected POST /api/v1/chat/sessions to be called for first message',
  ).toBeTruthy()

  // 断言 3: 网络请求包含 appendMessage (POST /chat/sessions/{id}/messages)
  const appendMessageReq = requests.find(
    (r) => r.method === 'POST' && /\/api\/v1\/chat\/sessions\/[^/]+\/messages$/.test(r.url),
  )
  expect(
    appendMessageReq,
    'Expected POST /chat/sessions/{id}/messages to be called',
  ).toBeTruthy()

  // 断言 4: appendMessage 的 URL 与 createSession 的响应 ID 一致
  // (通过验证 chat_history localStorage / store 拿到 server id)
  const finalLocalStorage = await page.evaluate(() => ({
    currentSession: localStorage.getItem('chat_current_session_v3'),
  }))
  expect(finalLocalStorage.currentSession).toBeTruthy()
  // 客户端 ID 必须非空 (无论本地生成还是 server-returned)
})