// CU1/CU2 聊天体验 —— 纯逻辑 + 布局断言（全部离线）
//
// CU1：输入框常驻底部（布局层保证：grid-template-rows: auto 1fr auto）
// CU2：新消息/流式输出自动滚动跟随；用户上滚暂停、回底恢复
import { describe, expect, it } from 'vitest'
import {
  FOLLOW_THRESHOLD,
  bottomScrollTop,
  distanceFromBottom,
  followOnNewMessage,
  isAtBottom,
  nextFollowing
} from '@renderer/composables/useAutoFollow'

const m = (scrollTop: number, clientHeight = 600, scrollHeight = 2000): { scrollTop: number; clientHeight: number; scrollHeight: number } => ({
  scrollTop,
  clientHeight,
  scrollHeight
})

describe('CU2 自动滚动跟随（纯逻辑）', () => {
  it('★ 贴底判定：距底 ≤ 阈值算贴底；内容不足一屏也算贴底', () => {
    expect(distanceFromBottom(m(1400))).toBe(0) // 2000-1400-600 = 0
    expect(isAtBottom(m(1400))).toBe(true)
    expect(isAtBottom(m(1400 - FOLLOW_THRESHOLD))).toBe(true)
    expect(isAtBottom(m(1400 - FOLLOW_THRESHOLD - 1))).toBe(false)
    // 内容不足一屏：scrollHeight < clientHeight → 距离归一为 0（贴底）
    expect(distanceFromBottom(m(0, 600, 300))).toBe(0)
    expect(isAtBottom(m(0, 600, 300))).toBe(true)
  })

  it('★ 用户上滚 → 暂停跟随；手动回底 → 恢复跟随', () => {
    // 跟随中，用户上滚到远处 → 暂停
    expect(nextFollowing(m(200), true, false)).toBe(false)
    // 暂停中，用户继续上滚 → 仍暂停（不会因为「离底更远」而反转）
    expect(nextFollowing(m(100), false, false)).toBe(false)
    // 暂停中，用户滚回底部 → 恢复跟随
    expect(nextFollowing(m(1400), false, false)).toBe(true)
  })

  it('★ 程序性滚动不改变跟随意图（防自锁：自动滚动触发 scroll 事件不得把自己判定成用户上滚）', () => {
    // 跟随中，程序滚动（此刻 scrollTop 可能还没到最终位置）→ 仍保持跟随
    expect(nextFollowing(m(0), true, true)).toBe(true)
    // 暂停中，程序滚动 → 仍暂停
    expect(nextFollowing(m(1400), false, true)).toBe(false)
  })

  it('★ 新消息到达：仅在跟随时才拉到底（绝不打断用户回看历史）', () => {
    expect(followOnNewMessage(true)).toBe(true)
    expect(followOnNewMessage(false)).toBe(false)
    // 目标位置 = 内容底部
    expect(bottomScrollTop({ scrollHeight: 2000 })).toBe(2000)
  })

  it('边界：刚好在阈值上算贴底；超出 1px 即暂停', () => {
    const exact = 2000 - 600 - FOLLOW_THRESHOLD
    expect(isAtBottom(m(exact))).toBe(true)
    expect(isAtBottom(m(exact - 1))).toBe(false)
  })
})

describe('CU1 输入框常驻（布局层）', () => {
  it('★ ChatPanel 采用三行网格（头部/可滚主体/输入区），输入区不随内容滚走', async () => {
    const { readFileSync } = await import('node:fs')
    const src = readFileSync('src/renderer/src/components/chat/ChatPanel.vue', 'utf8')
    // 三行网格：auto（头） minmax(0,1fr)（主体，DL-5 可收缩） auto（输入）
    expect(src).toMatch(/\.chat\s*\{[^}]*display:\s*grid/s)
    expect(src).toMatch(/grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\)\s+auto/)
    // 只有主体可滚（输入区不参与滚动）
    expect(src).toMatch(/\.chat-body\s*\{[^}]*overflow-y:\s*auto/s)
  })

  it('★ 主体挂了滚动监听（CU2 的输入）', async () => {
    const { readFileSync } = await import('node:fs')
    const src = readFileSync('src/renderer/src/components/chat/ChatPanel.vue', 'utf8')
    expect(src).toContain('@scroll.passive="onBodyScroll"')
    expect(src).toContain('onBodyScroll')
    expect(src).toContain('useAutoFollow')
  })
})
