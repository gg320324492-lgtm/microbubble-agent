/**
 * @fileoverview ChatViewSSE skip-link + main landmark 静态模板测试 (W101 P3-A11Y +4)
 *
 * 派工前提 (类 20.139 实战): skip-link 必置于 template 第一个可聚焦元素,
 * hidden by default (transform: translateY(-200%)), focus-visible 时显示.
 * 主内容区必带 role=main + id=chat-main 让 skip-link href 能锚到.
 *
 * 测试策略: 不 mount 整个 ChatViewSSE (依赖 chat stream / store), 直接读源文件
 * 验证模板字符串含必要的 a11y 属性 + CSS 含 skip-link 隐藏规则.
 *
 * 2026-10-05 (CSS 抽出): <style scoped> 已搬到 chatview-scoped.css。
 * ①/② 仍读 .vue (模板未动); ③④⑤ 改读 chatview-scoped.css。
 * 正则逐字保留, 只改读取位置。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const viewPath = resolve(__dirname, '../ChatViewSSE.vue')
const source = readFileSync(viewPath, 'utf-8')
// 2026-10-05 (CSS 抽出): skip-link 样式随 <style scoped src> 迁出
const scopedCss = readFileSync(resolve(__dirname, '../chatview-scoped.css'), 'utf-8')

describe('ChatViewSSE a11y skip-link + main landmark (W101 +4)', () => {
  it('① template 含 skip-link 第一个可聚焦元素', () => {
    expect(source).toMatch(/<a\s+href="#chat-main"\s+class="skip-link"\s+data-testid="skip-link">/)
  })

  it('② 主内容区含 id="chat-main" + role="main" + aria-label', () => {
    expect(source).toMatch(/id="chat-main"[^>]*role="main"[^>]*aria-label="聊天对话主区域"/s)
  })

  it('③ skip-link CSS 含 transform: translateY(-200%) 隐藏', () => {
    expect(scopedCss).toMatch(/\.skip-link\s*\{/)
    expect(scopedCss).toMatch(/transform:\s*translateY\(-200%\)/)
  })

  it('④ skip-link :focus-visible 时 transform: translateY(0) 显示', () => {
    expect(scopedCss).toMatch(/\.skip-link:focus-visible\s*\{/)
    expect(scopedCss).toMatch(/transform:\s*translateY\(0\)/)
  })

  it('⑤ 复用全局 --focus-outline-* token (W101 +1 验证一致性)', () => {
    expect(scopedCss).toMatch(/var\(--focus-outline-width\)/)
    expect(scopedCss).toMatch(/var\(--focus-outline-offset\)/)
  })
})