/**
 * tests/visual/desktop/rag-citation-highlight-2026-09-01.spec.mjs
 *
 * WP10 收口验证: knowledge_ref 卡片 citation 段落级高亮端到端
 *
 * 链路: 真实登录 → /chat 发知识库问题 → search_knowledge 工具 (RRF chunk 路 +
 * citation 提取, 2026-09-01 修复) → rich_block knowledge_ref →
 * KnowledgeRefBlock.vue 按 result.chunk_id 匹配 citation → mark.citation-mark 高亮
 *
 * 断言:
 *  1. .kb-ref.rich-card 出现 (search_knowledge 工具端到端跑通)
 *  2. mark.citation-mark 出现 (citation 高亮渲染)
 *  3. 相邻探针: assistant 答案文本非空 + 无 pageerror
 *
 * 前置: 生产后端已部署 2026-09-01 RAG 修复 (向量主路 + citation 链)。
 */
import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost'
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'

test.describe('rag-citation-highlight-2026-09-01', () => {
  test('search_knowledge → knowledge_ref 卡片 → citation 高亮', async ({ page }) => {
    test.setTimeout(360_000)

    const consoleErrors = []
    const pageErrors = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 200))
    })
    page.on('pageerror', (err) => pageErrors.push(String(err).slice(0, 200)))

    // 1. API 登录拿 token (跳过登录 UI)
    const tokenResp = await page.request.post(`${BASE_URL}/api/v1/auth/login`, {
      data: { username: USERNAME, password: PASSWORD },
    })
    expect(tokenResp.status()).toBe(200)
    const token = (await tokenResp.json()).access_token
    expect(token).toBeTruthy()

    // 2. 注入 token (cookie domain 与访问 host 一致; initScript 保证路由守卫前有 token)
    await page.context().addCookies([{ name: 'access_token', value: token, domain: 'localhost', path: '/' }])
    await page.addInitScript((t) => {
      localStorage.setItem('access_token', t)
    }, token)
    await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded' })

    // 3. 等聊天页就绪
    await page.waitForSelector('#thinking-mode-fast', { timeout: 30_000 })

    // 4. deep 模式发知识库问题 — 意图分类 few-shot 原例, explain_concept →
    // Phase 0 强制派工 search_knowledge (确定性触发, 不赌 LLM 工具自选)
    await page.click('#thinking-mode-deep')
    const textarea = page.locator('textarea').first()
    await textarea.fill('什么是微纳米气泡')
    await page.click('#chat-send-btn')

    // 5. 等 knowledge_ref 富卡片 (真实 LLM + 检索, 给足超时)
    let cardFound = false
    try {
      await page.waitForSelector('.kb-ref.rich-card', { timeout: 300_000, state: 'visible' })
      cardFound = true
    } catch {
      console.log('[rag-citation] knowledge_ref 卡片未出现 (工具未被调用或链路断)')
    }
    expect(cardFound, 'search_knowledge 应产生 knowledge_ref 富卡片').toBe(true)

    const refItems = await page.locator('.kb-ref.rich-card .ref-item').count()
    console.log(`[rag-citation] ref-item 数量: ${refItems}`)
    expect(refItems).toBeGreaterThan(0)

    // 6. citation 高亮锚点
    const markCount = await page.locator('.kb-ref.rich-card mark.citation-mark').count()
    console.log(`[rag-citation] mark.citation-mark 数量: ${markCount}`)
    expect(markCount, 'citation 段落高亮应渲染 (chunk_id ↔ citations 匹配)').toBeGreaterThan(0)

    // 7. 相邻探针: assistant 答案非空
    const answer = await page.evaluate(() => {
      const msgs = document.querySelectorAll('[data-role="assistant"], .chat-message.assistant, .message.assistant')
      return msgs.length > 0 ? msgs[msgs.length - 1].textContent : ''
    })
    console.log(`[rag-citation] answer len=${answer.length}`)
    expect(answer.length).toBeGreaterThan(0)

    // 8. 截图 (gitignored)
    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/rag-citation-highlight-2026-09-01.png',
      fullPage: true,
    })

    // 9. 无 JS 崩溃
    expect(pageErrors, `pageerror: ${pageErrors.join(' | ')}`).toHaveLength(0)
    console.log(`[rag-citation] console errors (非阻断记录): ${consoleErrors.length}`)
  })
})
