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
  it('① Notebook 按钮 light mode hover/focus 加 color-mix 背景', () => {
    expect(source).toMatch(/\.header-context-toggle:hover[\s\S]*?color-mix\(in srgb, var\(--color-primary\)/)
    expect(source).toMatch(/\.header-context-toggle:focus-visible\s*\{/)
  })

  it('② Notebook 按钮 dark mode 覆盖 hover/focus', () => {
    expect(source).toMatch(/\[data-theme="dark"\]\s+\.header-context-toggle:hover/)
    expect(source).toMatch(/\[data-theme="dark"\]\s+\.header-context-toggle:focus-visible/)
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
    expect(source).toMatch(/\.user-bubble,\s*\.bot-bubble[\s\S]*?background:\s*#fff\s*!important/)
    expect(source).toMatch(/\.user-bubble::before,\s*\.bot-bubble::before,\s*\.bot-bubble::after\s*\{\s*display:\s*none\s*!important/)
    expect(source).toMatch(/\.msg-content-typing[\s\S]*?mask-image:\s*none\s*!important[\s\S]*?-webkit-mask-image:\s*none\s*!important/)
  })
})