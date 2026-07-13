/**
 * tests/visual/desktop/chat-qa-comprehensive-2026-07-13.spec.mjs
 *
 * 全方位问答质量对比 (fast / balanced / deep):
 * 6 类问题 × 3 档 mode = 18 次, 验证:
 * 1. 闲聊类 (casual_chat): "你好"
 * 2. 数据查询 (data_query): "课题组的博士都有谁"
 * 3. 概念解释 (explain_concept): "什么是微纳米气泡"
 * 4. 对比分析 (compare): "对比一下微气泡和超声空化的区别"
 * 5. 工具调用 (tool_call): "帮我创建一个待办: 写会议纪要"
 * 6. 长答案 (long_answer): "详细解释羟基自由基怎么在水处理中生成"
 *
 * 前置: 同 chat-three-mode-2026-07-13.spec.mjs (vite dev + ollama + xiaoqi_testbot)
 *
 * 输出: console.log 每题答案, 便于人工判断质量差异
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3100'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

const QUESTIONS = [
  { id: 'q1-casual', label: '闲聊类', text: '你好' },
  { id: 'q2-data', label: '数据查询', text: '课题组的博士都有谁? 简单列举一下名字' },
  { id: 'q3-concept', label: '概念解释', text: '什么是微纳米气泡?请详细解释' },
  { id: 'q4-compare', label: '对比分析', text: '对比一下微气泡和超声空化的区别,从原理和应用两个角度' },
  { id: 'q5-tool', label: '工具调用', text: '帮我创建一个待办任务:写周会纪要' },
  { id: 'q6-deep', label: '长答案', text: '详细解释羟基自由基在水处理中怎么生成? 涉及什么反应? 实际效果如何?' },
]

const MODES = ['fast', 'balanced', 'deep']

async function setupPage(page) {
  // 2026-07-13: chat UI mount 阶段 fetchMessages 失败 + WS 重连卡住, 等任何 UI 元素都 timeout
  // 改: 只注入 token cookie + goto (vite 200 OK 即可), 实际 chat 用 page.evaluate fetch
  await page.context().addCookies([{
    name: 'access_token',
    value: TEST_TOKEN,
    domain: new URL(BASE_URL).hostname,
    path: '/',
  }])
  await page.addInitScript((token) => {
    localStorage.setItem('access_token', token)
  }, TEST_TOKEN)
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 15_000 }).catch(() => null)
}

async function chatOne(page, text, mode) {
  // 用 captureChatStream 直接走原生 fetch SSE (避免 chat UI mount 问题)
  return await page.evaluate(
    async ({ url, token, message, thinkingMode }) => {
      const ctrl = new AbortController()
      const t = setTimeout(() => ctrl.abort(), 240_000)
      const r = await fetch(`${url}/api/v1/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          message,
          session_id: `qa-${thinkingMode}-${Date.now()}`,
          thinking_mode: thinkingMode,
        }),
        signal: ctrl.signal,
      })
      clearTimeout(t)
      if (!r.ok || !r.body) return { error: `HTTP ${r.status}` }
      const reader = r.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let text = ''
      let done = null
      const t0 = Date.now()
      while (true) {
        const { value, done: rdone } = await reader.read()
        if (rdone) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n\n')
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].replace(/^data: /, '').trim()
          if (!line) continue
          try {
            const evt = JSON.parse(line)
            if (evt.type === 'text_delta') text += evt.delta || ''
            else if (evt.type === 'done') done = evt
          } catch (e) { /* ignore */ }
        }
        buf = lines[lines.length - 1]
      }
      return {
        elapsed: Date.now() - t0,
        text,
        badge: done ? `${done.mode} ${done.model} ${done.duration_ms}ms` : 'no-done',
      }
    },
    { url: BASE_URL, token: TEST_TOKEN, message: text, thinkingMode: mode }
  )
}

test.describe('chat-qa-comprehensive-2026-07-13: 6 题 × 3 mode 质量对比', () => {
  test('A: 全 18 次问答 + 打印每题答案', async ({ page }) => {
    test.setTimeout(1_500_000)  // 25 分钟总预算 (含 ollama 加载 + 6×3 次 chat)
    await setupPage(page)

    const results = {}

    for (const q of QUESTIONS) {
      results[q.id] = { label: q.label, text: q.text, modes: {} }
      for (const mode of MODES) {
        console.log(`\n========== [${q.id}] ${q.label} | ${mode} ==========`)
        console.log(`Q: ${q.text}`)
        const r = await chatOne(page, q.text, mode)
        results[q.id].modes[mode] = r
        console.log(`model/duration: ${r.badge}`)
        console.log(`elapsed: ${r.elapsed}ms`)
        console.log(`answer: ${r.text.slice(0, 500)}${r.text.length > 500 ? '...' : ''}`)
      }
    }

    // 汇总输出
    console.log('\n\n========== 汇总 ==========')
    for (const q of QUESTIONS) {
      console.log(`\n--- [${q.id}] ${q.label} ---`)
      for (const mode of MODES) {
        const r = results[q.id].modes[mode]
        console.log(`  ${mode.padEnd(8)}: ${r.elapsed}ms | text_len=${r.text.length} | badge=${r.badge?.slice(0, 50)}`)
      }
    }

    // 简单断言: 3 档 model 字段都正确
    expect(results['q3-concept'].modes.deep.badge).toContain('deepseek-r1')
    expect(results['q3-concept'].modes.balanced.badge).toContain('qwen3')
    expect(results['q3-concept'].modes.fast.badge).toContain('qwen3')
  })
})