/**
 * useChatViewScroll 直接单测 (L-1 阶段 2 — 拆出模块的独立可测性证明)
 *
 * ChatViewSSE.behavior.test.js 从视图层兜底整体行为; 本文件直接驱动 composable
 * (纯 ref 注入, 无组件挂载), 覆盖行为测试在 jsdom 下难触达的滚动分支:
 * autoStick 贴底 / 用户上滚取消 / 跳到最新·最早按钮显隐门控。
 */
import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { useChatViewScroll } from '@/composables/chat/useChatViewScroll'
import type { ChatMessage } from '@/composables/chat/useChatStream'

const fakeContainer = (metrics: { scrollTop: number; scrollHeight: number; clientHeight: number }) => {
  // 真 DOM 元素 (useVirtualList 会 addEventListener) + 覆写布局度量 (jsdom 无布局)
  const el = document.createElement('div')
  let st = metrics.scrollTop
  Object.defineProperty(el, 'scrollTop', {
    get: () => st,
    set: (v: number) => { st = v },
    configurable: true,
  })
  Object.defineProperty(el, 'scrollHeight', { value: metrics.scrollHeight, configurable: true })
  Object.defineProperty(el, 'clientHeight', { value: metrics.clientHeight, configurable: true })
  return el
}

const setup = () => {
  const messages = ref<ChatMessage[]>([])
  const sessionId = ref('')
  const scroll = useChatViewScroll({ messages, sessionId })
  return { messages, sessionId, scroll }
}

describe('useChatViewScroll (L-1 拆出)', () => {
  it('scrollToBottom(force) 滚到底并恢复 autoStick、熄灭"跳到最新"', async () => {
    const { scroll } = setup()
    const el = fakeContainer({ scrollTop: 0, scrollHeight: 1000, clientHeight: 300 })
    scroll.messagesRef.value = el
    scroll.autoStick.value = false
    scroll.showJumpToBottom.value = true

    await scroll.scrollToBottom(true)
    expect(el.scrollTop).toBe(1000)
    expect(scroll.autoStick.value).toBe(true)
    expect(scroll.showJumpToBottom.value).toBe(false)
  })

  it('scrollToBottom 非 force 且 autoStick=false 时不滚动 (用户上滚守卫)', async () => {
    const { scroll } = setup()
    const el = fakeContainer({ scrollTop: 100, scrollHeight: 1000, clientHeight: 300 })
    scroll.messagesRef.value = el
    scroll.autoStick.value = false

    await scroll.scrollToBottom(false)
    expect(el.scrollTop).toBe(100)
  })

  it('中间区域滚动 → 两个跳转按钮都出现; autoStick 关闭', () => {
    const { scroll } = setup()
    // 距底 = 1000-500-300 = 200 > 80, 距顶 = 500 > 100 → 中间区域
    scroll.messagesRef.value = fakeContainer({ scrollTop: 500, scrollHeight: 1000, clientHeight: 300 })
    scroll.onMessagesScroll()
    expect(scroll.showJumpToBottom.value).toBe(true)
    expect(scroll.showJumpToTop.value).toBe(true)
    expect(scroll.autoStick.value).toBe(false)
  })

  it('接近底部 → 恢复 autoStick, 熄灭"跳到最新"', () => {
    const { scroll } = setup()
    // scrollTop=680: 距底 = 1000-680-300 = 20 (距底 < 80)
    scroll.messagesRef.value = fakeContainer({ scrollTop: 680, scrollHeight: 1000, clientHeight: 300 })
    scroll.onMessagesScroll()
    expect(scroll.autoStick.value).toBe(true)
    expect(scroll.showJumpToBottom.value).toBe(false)
    expect(scroll.showJumpToTop.value).toBe(true)  // 距顶 680 > 100
  })

  it('接近顶部 → 关闭 autoStick + 熄灭"跳到最早"', () => {
    const { scroll } = setup()
    // scrollTop=50 (< 100), 距底 = 1000-50-300 = 650 (> 80)
    scroll.messagesRef.value = fakeContainer({ scrollTop: 50, scrollHeight: 1000, clientHeight: 300 })
    scroll.onMessagesScroll()
    expect(scroll.autoStick.value).toBe(false)
    expect(scroll.showJumpToTop.value).toBe(false)
    expect(scroll.showJumpToBottom.value).toBe(true)  // 溢出 700 > 80 且距底 650 > 80
  })

  it('jumpToTop/jumpToBottom 归零/贴底并复位按钮', async () => {
    const { scroll } = setup()
    const el = fakeContainer({ scrollTop: 500, scrollHeight: 1000, clientHeight: 300 })
    scroll.messagesRef.value = el

    scroll.jumpToTop()
    expect(el.scrollTop).toBe(0)
    expect(scroll.showJumpToTop.value).toBe(false)
    expect(scroll.showJumpToBottom.value).toBe(true)

    scroll.jumpToBottom()
    expect(el.scrollTop).toBe(1000)
    expect(scroll.autoStick.value).toBe(true)
    expect(scroll.showJumpToBottom.value).toBe(false)
  })

  it('messages 增长触发贴底滚动 (deep watcher, autoStick 守卫)', async () => {
    const { messages, scroll } = setup()
    const el = fakeContainer({ scrollTop: 0, scrollHeight: 500, clientHeight: 300 })
    scroll.messagesRef.value = el

    messages.value.push({ id: 'm1', role: 'user', content: 'hi' } as ChatMessage)
    await new Promise((r) => setTimeout(r, 0))  // flush: 'post'
    expect(el.scrollTop).toBe(500)
    expect(scroll.autoStick.value).toBe(true)
  })
})
