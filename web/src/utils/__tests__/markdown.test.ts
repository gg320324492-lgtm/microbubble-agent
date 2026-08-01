/**
 * markdown.ts 渲染 + onerror 注入单测 — W99 +20 派工 v10
 * 5 case：空文本透传 / 普通文本渲染 / img 注入 onerror / 已有 onerror 跳过 / 非 img 标签不动
 */
import { describe, expect, it } from 'vitest'
import { renderMarkdown } from '../markdown'

describe('renderMarkdown — W99 +20 img onerror 注入', () => {
  it('① 空文本透传空字符串', () => {
    expect(renderMarkdown('')).toBe('')
  })

  it('② 普通 markdown 渲染', () => {
    const html = renderMarkdown('**bold** text')
    expect(html).toContain('<strong>bold</strong>')
  })

  it('③ img 标签注入 onerror + data-fallback-text', () => {
    const html = renderMarkdown('![alt text](https://example.com/x.png)')
    expect(html).toMatch(/<img[^>]*onerror=/)
    expect(html).toContain('data-fallback-text="alt text 加载失败"')
    expect(html).toContain('src="https://example.com/x.png"')
  })

  it('④ 已有 onerror 不重复注入（防重）', () => {
    // 用户在 markdown 写 raw HTML 带 onerror
    const html = renderMarkdown('<img src="/x.png" onerror="alert(1)" />')
    // 应只保留原 onerror，不重复注入
    const onerrorAttrs = html.match(/\sonerror\s*=\s*"/g) || []
    expect(onerrorAttrs.length).toBe(1)
  })

  it('⑤ 多 img 全部注入', () => {
    const html = renderMarkdown('![a](https://a/1.png) ![b](https://b/2.png)')
    const onerrorAttrs = html.match(/\sonerror\s*=\s*"/g) || []
    expect(onerrorAttrs.length).toBe(2)
  })
})
