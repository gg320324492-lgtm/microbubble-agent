import { describe, it, expect, beforeEach } from 'vitest'
import { useSafeArea } from '../useSafeArea'

describe('useSafeArea', () => {
  beforeEach(() => {
    // Mock CSS variables
    const root = document.documentElement
    root.style.setProperty('--sat', '44px')
    root.style.setProperty('--sar', '0px')
    root.style.setProperty('--sab', '34px')
    root.style.setProperty('--sal', '44px')
  })

  it('读取 CSS 变量作为 inset 值', () => {
    const { top, right, bottom, left } = useSafeArea()
    expect(top.value).toBe('44px')
    expect(right.value).toBe('0px')
    expect(bottom.value).toBe('34px')
    expect(left.value).toBe('44px')
  })

  it('inset 输出完整简写字符串', () => {
    const { inset } = useSafeArea()
    expect(inset.value).toBe('44px 0px 34px 44px')
  })

  it('SSR 时返回 0px', () => {
    const originalDocument = global.document
    delete global.document
    const { top, right, bottom, left } = useSafeArea()
    expect(top.value).toBe('0px')
    expect(right.value).toBe('0px')
    expect(bottom.value).toBe('0px')
    expect(left.value).toBe('0px')
    global.document = originalDocument
  })
})