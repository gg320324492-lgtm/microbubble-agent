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

    // 1. API 登录拿 token (跳过登录 UI; auth 限流 5 次/分, 带退避重试)
    let token = null
    for (let i = 0; i < 4; i++) {
      const tokenResp = await page.request.post(`${BASE_URL}/api/v1/auth/login`, {
        data: { username: USERNAME, password: PASSWORD },
      })
      if (tokenResp.status() === 200) {
        token = (await tokenResp.json()).access_token
        break
      }
      console.log(`[rag-citation] login status=${tokenResp.status()} (attempt ${i + 1}), wait 20s`)
      await page.waitForTimeout(20_000)
    }
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
      // collapsed_by_default 可能由 LLM 设 true (v-show 隐藏) — 用 attached 断言存在性
      await page.waitForSelector('.kb-ref.rich-card', { timeout: 300_000, state: 'attached' })
      cardFound = true
    } catch {
      console.log('[rag-citation] knowledge_ref 卡片未出现 (工具未被调用或链路断)')
      // DOM 诊断转储: rich 容器/消息/最近 assistant HTML
      const diag = await page.evaluate(() => {
        const wrap = document.querySelectorAll('.rich-content-wrapper')
        const assistant = document.querySelectorAll('[data-role="assistant"], .chat-message.assistant, .message.assistant')
        const last = assistant.length ? assistant[assistant.length - 1] : null
        return {
          richWrappers: wrap.length,
          richTypes: [...wrap].map((w) => w.className),
          assistantCount: assistant.length,
          lastHtmlSlice: last ? last.innerHTML.slice(-1500) : '',
        }
      })
      console.log('[rag-citation][diag]', JSON.stringify(diag, null, 2).slice(0, 2200))
    }
    expect(cardFound, 'search_knowledge 应产生 knowledge_ref 富卡片').toBe(true)

    // 可见性探测: collapsed 时 v-show display:none (存在但不可见是合法状态)
    const kbCard = page.locator('.kb-ref.rich-card').first()
    const cardVisible = await kbCard.isVisible()
    console.log(`[rag-citation] kb-ref visible=${cardVisible}`)

    const refItems = await page.locator('.kb-ref.rich-card .ref-item').count()
    console.log(`[rag-citation] ref-item 数量: ${refItems}`)
    expect(refItems).toBeGreaterThan(0)

    // 6. citation 高亮锚点
    const markCount = await page.locator('.kb-ref.rich-card mark.citation-mark').count()
    console.log(`[rag-citation] mark.citation-mark 数量: ${markCount}`)
    expect(markCount, 'citation 段落高亮应渲染 (chunk_id ↔ citations 匹配)').toBeGreaterThan(0)

    // 7. 相邻探针: 引用卡片自身内容非空 (组件契约: aria-label + ref-item 文本)
    const firstRefText = await kbCard.locator('.ref-item').first().textContent()
    console.log(`[rag-citation] first ref-item: ${(firstRefText || '').slice(0, 60)}`)
    expect((firstRefText || '').trim().length).toBeGreaterThan(0)
    const ariaLabel = await kbCard.getAttribute('aria-label')
    expect(ariaLabel).toContain('知识库引用')

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
