/**
 * @fileoverview ChatViewSSE W100 +61 polish 测试 (dark mode + 浏览器降级 + print)
 *
 * 派工前提 (类 20.13/20.108): 路径实测 + grep 必验证
 * 测试策略: 不 mount 整个 ChatViewSSE, 直接读源文件验证 CSS 含必要规则.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const viewPath = resolve(__dirname, '../ChatViewSSE.vue')
const source = readFileSync(viewPath, 'utf-8')

describe('ChatViewSSE W100 +61 polish (dark mode + 浏览器降级 + print)', () => {
  // 2026-10-01: ①/② 原盯 `.header-context-toggle` (Notebook 引用切换键), 该键已被
  // f1c3c2645「移除头部『引用』切换按钮」连同死样式一起删干净 (源文件 0 命中)。
  // 头部控制权已交给 #chat-header-search-toggle + .header-search-pill, 断言改钉现行契约:
  // hover/focus-visible 必须有高亮背景, 且 dark mode 必须逐条覆盖。
  it('① 头部控制键 light mode hover/focus-visible 加高亮背景', () => {
    expect(source).toMatch(
      /\.chat-immersive #chat-header-search-toggle:hover,\n\.chat-immersive #chat-header-search-toggle:focus-visible \{/
    )
    expect(source).toMatch(
      /\.chat-immersive #chat-header-search-toggle:hover,[\s\S]*?background: rgba\(14, 118, 110, 0\.06\);/
    )
    expect(source).toMatch(/\.chat-immersive \.header-search-pill:focus-within \{/)
  })

  it('② 头部控制键 dark mode 覆盖 hover/focus-visible', () => {
    expect(source).toMatch(/\[data-theme="dark"\] \.chat-immersive #chat-header-search-toggle:hover/)
    expect(source).toMatch(/\[data-theme="dark"\] \.chat-immersive #chat-header-search-toggle:focus-visible/)
    expect(source).toMatch(
      /\[data-theme="dark"\] \.chat-immersive #chat-header-search-toggle:hover,[\s\S]*?background: rgba\(53, 194, 164, 0\.08\);/
    )
    expect(source).toMatch(/\[data-theme="dark"\] \.chat-immersive \.header-search-pill:focus-within \{/)
  })

  it('③ 用户气泡 dark mode 加 box-shadow + color-mix 边框', () => {
    expect(source).toMatch(/\[data-theme="dark"\]\s+\.user-bubble\s*\{/)
    expect(source).toMatch(/\[data-theme="dark"\][\s\S]{0,300}\.user-bubble\s*\{[\s\S]{0,500}?box-shadow/)
    expect(source).toMatch(/\[data-theme="dark"\][\s\S]{0,300}\.user-bubble\s*\{[\s\S]{0,500}?color-mix\(in srgb, var\(--color-primary\)/)
  })

  it('④ 用户气泡小尾巴 dark mode 加 drop-shadow', () => {
    expect(source).toMatch(/\[data-theme="dark"\]\s+\.user-bubble::before[\s\S]*?drop-shadow/)
  })

  it('⑤ 助手气泡小尾巴 dark mode 加深 border + box-shadow', () => {
    expect(source).toMatch(/\[data-theme="dark"\]\s+\.bot-bubble::after[\s\S]*?border-(left|bottom)-color:\s*var\(--color-border-base\)/)
    expect(source).toMatch(/\[data-theme="dark"\][\s\S]{0,300}\.bot-bubble::after[\s\S]{0,300}?box-shadow/)
  })

  it('⑥ 打字机 mask 在 dark mode 用更亮过渡边界', () => {
    expect(source).toMatch(/\[data-theme="dark"\]\s+\.msg-content-typing\s*\{/)
    expect(source).toMatch(/\[data-theme="dark"\][\s\S]{0,400}\.msg-content-typing\s*\{[\s\S]{0,800}?--reveal-start/)
    expect(source).toMatch(/\[data-theme="dark"\][\s\S]{0,400}\.msg-content-typing\s*\{[\s\S]{0,800}?mask-image:\s*linear-gradient/)
  })

  it('⑦ 老浏览器 @supports (transition: --reveal) 退化路径', () => {
    expect(source).toMatch(/@supports\s+not\s+\(transition:\s+--reveal/)
    expect(source).toMatch(/\.msg-content-typing\s*\{\s*mask-image:\s*none/)
  })

  it('⑧ Safari 15-17.3 双重判定 (webkit mask 支持 + custom prop transition 不支持)', () => {
    expect(source).toMatch(/@supports\s+\(-webkit-mask-image:\s*linear-gradient\(black,\s*black\)\)\s+and\s+\(not\s+\(transition:\s+--reveal/)
  })

  it('⑨ @media print: 气泡纯黑白 + 隐藏装饰 ::before/::after + 强制 mask=none', () => {
    expect(source).toMatch(/@media\s+print\s*\{/)
    // 2026-10-02 S3.7-9: `#fff` 已收敛为等值 token `var(--raw-fff)`
    // (定义值 === #fff, 无主题覆盖, 渲染结果不变)。断言接受两种写法 ——
    // 盯的是「print 下强制白底」这个契约, 不是色值书写形式。
    expect(source).toMatch(
      /\.user-bubble,\s*\.bot-bubble[\s\S]*?background:\s*(?:#fff|var\(--raw-fff\))\s*!important/
    )
    expect(source).toMatch(/\.user-bubble::before,\s*\.bot-bubble::before,\s*\.bot-bubble::after\s*\{\s*display:\s*none\s*!important/)
    expect(source).toMatch(/\.msg-content-typing[\s\S]*?mask-image:\s*none\s*!important[\s\S]*?-webkit-mask-image:\s*none\s*!important/)
  })
})