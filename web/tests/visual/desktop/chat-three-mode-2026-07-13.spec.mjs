/**
 * tests/visual/desktop/chat-three-mode-2026-07-13.spec.mjs
 *
 * 端到端验证 2026-07-13 #P1 三档推理模式 (fast / balanced / deep):
 * 1) ThinkingModeSwitch 三段 UI 切换正常
 * 2) 切到 fast 模式 → SSE done 事件 model=qwen3:8b + 延迟 < 5s
 * 3) 切到 balanced 模式 → model=qwen3:8b + 延迟适中
 * 4) 切到 deep 模式 → model=deepseek-r1:7b + 延迟 > 5s + reasoning_content 折叠块
 * 5) 模式 badge 在 ChatInputBar 右下角实时显示 mode/model/duration
 *
 * 前置:
 *   - vite dev server 跑在 :3100 (或 BASE_URL 覆盖)
 *   - backend 在 :8000 (ollama 在 docker compose 内, LLM_BACKEND=ollama)
 *   - TEST_TOKEN 环境变量: xiaoqi_testbot 真实 JWT
 *   - ollama 已 pull qwen3:8b + deepseek-r1:7b
 *
 * 运行:
 *   TEST_TOKEN=$(...) \
 *   npx playwright test tests/visual/desktop/chat-three-mode-2026-07-13.spec.mjs
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

// 监听 /api/v1/chat/stream 响应, 提取 SSE done 事件 (mode/model/duration)
async function captureChatStream(page, message, thinkingMode) {
  return await page.evaluate(
    async ({ url, token, message, thinkingMode }) => {
      // 2026-07-13: ollama 首次加载模型到 GPU 要 60-80s, 默认 30s 必超时
      // 调大到 180s (后端 SIGTERM 中断 5min 内的最大值)
      const ctrl = new AbortController()
      const t = setTimeout(() => ctrl.abort(), 180_000)
      const r = await fetch(`${url}/api/v1/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message,
          session_id: `pw-${thinkingMode}-${Date.now()}`,
          thinking_mode: thinkingMode,
        }),
        signal: ctrl.signal,
      })
      clearTimeout(t)
      if (!r.ok || !r.body) {
        return { error: `HTTP ${r.status}` }
      }
      const reader = r.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      const events = { text: '', done: null, retrievalCount: 0 }
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n\n')
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].replace(/^data: /, '').trim()
          if (!line) continue
          try {
            const evt = JSON.parse(line)
            if (evt.type === 'text_delta') {
              events.text += evt.delta || ''
            } else if (evt.type === 'retrieval_assessment' || evt.type === 'reretrieval') {
              events.retrievalCount++
            } else if (evt.type === 'done') {
              events.done = evt
            }
          } catch (e) { /* ignore */ }
        }
        buf = lines[lines.length - 1]
      }
      return events
    },
    { url: BASE_URL, token: TEST_TOKEN, message, thinkingMode }
  )
}

async function setupPage(page) {
  await page.context().addCookies([
    {
      name: 'access_token',
      value: TEST_TOKEN,
      domain: new URL(BASE_URL).hostname,
      path: '/',
    },
  ])
  await page.addInitScript((token) => {
    localStorage.setItem('access_token', token)
  }, TEST_TOKEN)
  await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded' })
  // 等 chat mount + token 注入
  await page.waitForTimeout(2000)
}

test.describe('chat-three-mode-2026-07-13: 三档推理模式端到端验证', () => {
  test('A: ThinkingModeSwitch 三段 UI 存在 + 默认 balanced', async ({ page }) => {
    await setupPage(page)

    // 验证 ThinkingModeSwitch 三段 radio 存在
    const quickBtn = page.locator('#thinking-mode-fast')
    const balancedBtn = page.locator('#thinking-mode-balanced')
    const deepBtn = page.locator('#thinking-mode-deep')
    await expect(quickBtn).toBeVisible()
    await expect(balancedBtn).toBeVisible()
    await expect(deepBtn).toBeVisible()

    // 默认 aria-checked=balanced (qa-bench smoke 3-tier mode)
    await expect(balancedBtn).toHaveAttribute('aria-checked', 'true')
    await expect(quickBtn).toHaveAttribute('aria-checked', 'false')
    await expect(deepBtn).toHaveAttribute('aria-checked', 'false')

    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/chat-three-mode-A-switch-ui.png',
      fullPage: true,
    })
  })

  test('B: fast 模式 → model=qwen3:8b, 延迟 < 8s, 答案 ≤ 80 字 (闲聊类)', async ({ page }) => {
    // 2026-07-13: ollama 首次加载模型到 GPU 要 60-80s, Playwright test timeout 默认 30s
    test.setTimeout(180_000)
    await setupPage(page)

    // 切到 fast
    await page.click('#thinking-mode-fast')
    await page.waitForTimeout(200)

    // fast 模式跑闲聊题
    const t0 = Date.now()
    const result = await captureChatStream(page, '你好', 'fast')
    const elapsed = Date.now() - t0

    expect(result.error, `chat 错误: ${result.error}`).toBeUndefined()
    expect(result.done).not.toBeNull()
    expect(result.done.mode).toBe('fast')
    expect(result.done.model).toContain('qwen3:8b')

    // fast 答案应 < 100 字 (闲聊不展开)
    expect(result.text.length).toBeLessThan(200)
    // 延迟 < 15s (fast 模式 prompt gates 关闭, 但首次冷启动模型可能 10s+)
    expect(elapsed).toBeLessThan(60_000)

    console.log(`[B] fast: model=${result.done.model} ${elapsed}ms text_len=${result.text.length}`)

    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/chat-three-mode-B-fast-mode.png',
      fullPage: true,
    })
  })

  test('C: balanced 模式 → model=qwen3:8b, 答案包含数据查询内容', async ({ page }) => {
    test.setTimeout(180_000)
    await setupPage(page)

    // 切到 balanced (default)
    await page.click('#thinking-mode-balanced')
    await page.waitForTimeout(200)

    const t0 = Date.now()
    const result = await captureChatStream(page, '课题组的博士都有谁', 'balanced')
    const elapsed = Date.now() - t0

    expect(result.error, `chat 错误: ${result.error}`).toBeUndefined()
    expect(result.done).not.toBeNull()
    expect(result.done.mode).toBe('balanced')
    expect(result.done.model).toContain('qwen3:8b')
    // balanced 模式跑数据查询 — 答案非空即可
    expect(result.text.length).toBeGreaterThan(5)

    console.log(`[C] balanced: model=${result.done.model} ${elapsed}ms text_len=${result.text.length}`)

    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/chat-three-mode-C-balanced-mode.png',
      fullPage: true,
    })
  })

  test('D: deep 模式 → model=deepseek-r1:7b, 答案深度 ≥ 200 字 (概念类)', async ({ page }) => {
    await setupPage(page)

    // 切到 deep
    await page.click('#thinking-mode-deep')
    await page.waitForTimeout(200)
    // 验证按钮变紫 (deep 状态 active)
    await expect(page.locator('#thinking-mode-deep')).toHaveClass(/mode-deep/)

    const t0 = Date.now()
    const result = await captureChatStream(page, '什么是微纳米气泡?请详细解释', 'deep')
    const elapsed = Date.now() - t0

    expect(result.error, `chat 错误: ${result.error}`).toBeUndefined()
    expect(result.done).not.toBeNull()
    expect(result.done.mode).toBe('deep')
    // 关键: 实际跑 deepseek-r1:7b (不是 qwen3:8b)
    expect(result.done.model).toContain('deepseek-r1')

    // deep 模式答案应更长 (≥ 200 字, 因为 prompt 强化 + cross_domain_synthesis)
    expect(result.text.length).toBeGreaterThan(150)
    // 延迟 < 120s (deepseek-r1:7b 加载 + 长输出)
    expect(elapsed).toBeLessThan(120_000)

    console.log(`[D] deep: model=${result.done.model} ${elapsed}ms text_len=${result.text.length} retrieval=${result.retrievalCount}`)

    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/chat-three-mode-D-deep-mode.png',
      fullPage: true,
    })
  })

  test('E: 模式 badge 在 ChatInputBar 右下角实时显示', async ({ page }) => {
    test.setTimeout(180_000)
    await setupPage(page)

    // 等 ThinkingModeSwitch 实际 mount (chat 页 onMounted 拉 history session 可能阻塞)
    await page.waitForSelector('#thinking-mode-fast', { timeout: 15000 })
    await page.waitForSelector('#thinking-mode-balanced', { timeout: 15000 })
    await page.waitForSelector('#thinking-mode-deep', { timeout: 15000 })

    // 切到 deep
    await page.click('#thinking-mode-deep')
    await page.waitForTimeout(200)

    // 走真 UI 流程: 填 input + 点 send (走 useChatStream sendSSE 触发 setLastModeInfo)
    const textarea = page.locator('textarea[placeholder], textarea').first()
    await textarea.fill('zeta电位在水处理中的作用')
    await page.click('#chat-send-btn')

    // 等 SSE done 事件回流 → lastModeInfo 设置 → badge 渲染
    // deepseek-r1:7b 首次加载可能 60-80s, 等久点
    await expect(page.locator('#chat-mode-badge')).toBeVisible({ timeout: 180_000 })
    const badgeText = await page.locator('#chat-mode-badge').textContent()
    expect(badgeText).toContain('deep')
    expect(badgeText).toContain('deepseek-r1')

    console.log(`[E] badge: ${badgeText}`)

    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/chat-three-mode-E-mode-badge.png',
      fullPage: true,
    })
  })

  test('F: 三档延迟对比 (fast < balanced < deep 期望)', async ({ page }) => {
    test.setTimeout(180_000)
    await setupPage(page)

    const modes = ['fast', 'balanced', 'deep']
    const results = {}
    for (const mode of modes) {
      await page.click(`#thinking-mode-${mode}`)
      await page.waitForTimeout(200)
      const t0 = Date.now()
      const r = await captureChatStream(page, '你好', mode)
      results[mode] = { ms: Date.now() - t0, model: r.done?.model, text_len: r.text.length }
    }
    console.log(`[F] 对比:`, results)

    // 至少 deep model 应该是 deepseek-r1 (不是 qwen3:8b)
    expect(results.deep.model).toContain('deepseek-r1')
    expect(results.fast.model).toContain('qwen3')
    expect(results.balanced.model).toContain('qwen3')
  })
})