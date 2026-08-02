/**
 * EventBadges 组件单测 — W100 +26
 *
 * 7 case 覆盖：
 * ① 空 msg → 整体不渲染 (data-testid 不存在)
 * ② synthesis_start 触发 → 显示 burst badge, 3s 后消失
 * ③ retry 触发 → 显示橙色 badge, 内容含 "第 N 次"
 * ④ critique 完成 → 显示绿色 badge, 含 score=N/10
 * ⑤ tool_compressed 触发 → 显示灰底 badge, 含 "N → M 条"
 * ⑥ 4 状态同时存在 → 4 个 badge 全部显示, 不冲突
 * ⑦ compact 模式 → 内边距/字号小
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import EventBadges from '../EventBadges.vue'

function makeMsg(over: Partial<{
  role: 'user' | 'assistant'
  state: 'streaming' | 'idle' | 'aborted'
  intent: any
  critique: any
  retryCount: number
  toolTrace: any[]
}> = {}) {
  return {
    role: 'assistant' as const,
    state: 'idle' as const,
    ...over,
  }
}

describe('EventBadges — W100 +26', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it('① 空 msg → 整体不渲染 (data-testid 不存在)', () => {
    const wrapper = mount(EventBadges, {
      props: { msg: makeMsg() },
    })
    expect(wrapper.find('[data-testid="event-badges"]').exists()).toBe(false)
  })

  it('② synthesis_start 触发 → 显示 burst badge, 3s 后消失', async () => {
    const msg = makeMsg({
      state: 'streaming',
      toolTrace: [{ type: 'thinking', label: '✨ 综合分析中...' }],
    })
    const wrapper = mount(EventBadges, {
      props: { msg },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').text()).toContain('正在组织回答')

    // 3s 后消失
    vi.advanceTimersByTime(3001)
    await nextTick()
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(false)
  })

  it('③ retry 触发 → 显示橙色 badge, 内容含 "第 N 次"', async () => {
    const msg = makeMsg({
      state: 'streaming',
      retryCount: 2,
    })
    const wrapper = mount(EventBadges, {
      props: { msg },
    })
    await nextTick()
    const badge = wrapper.find('[data-testid="event-badge-retry"]')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('第 2 次')
    expect(badge.classes()).toContain('event-badge-retry')
  })

  it('④ critique 完成 → 显示绿色 badge, 含 score=N/10', async () => {
    const msg = makeMsg({
      state: 'idle',
      critique: { score: 8, suggestion: 'good' },
    })
    const wrapper = mount(EventBadges, {
      props: { msg },
    })
    await nextTick()
    const badge = wrapper.find('[data-testid="event-badge-critique"]')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('8/10')
    expect(badge.classes()).toContain('event-badge-critique')
  })

  it('⑤ tool_compressed 触发 → 显示灰底 badge, 含 "N → M 条"', async () => {
    const msg = makeMsg({
      state: 'idle',
      toolTrace: [
        { type: 'tool', name: 'search_knowledge', compression: { original_count: 18, selected_count: 5, summary: '已精简' } },
      ],
    })
    const wrapper = mount(EventBadges, {
      props: { msg },
    })
    await nextTick()
    const badge = wrapper.find('[data-testid="event-badge-compressed"]')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('18')
    expect(badge.text()).toContain('5')
    expect(badge.text()).toContain('条')
    expect(badge.classes()).toContain('event-badge-compressed')
  })

  it('⑥ 4 状态同时存在 → 4 个 badge 全部显示, 不冲突', async () => {
    const msg = makeMsg({
      state: 'streaming',
      retryCount: 1,
      critique: { score: 9 },
      toolTrace: [
        { type: 'thinking', label: '✨ 综合分析中...' },
        { type: 'tool', name: 'search_knowledge', compression: { original_count: 12, selected_count: 4, summary: 's' } },
      ],
    })
    const wrapper = mount(EventBadges, {
      props: { msg },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="event-badges"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="event-badge-retry"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="event-badge-critique"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="event-badge-compressed"]').exists()).toBe(true)
  })

  it('⑦ compact 模式 → 内边距/字号小 (视觉验证 + class 校验)', async () => {
    const msg = makeMsg({
      state: 'idle',
      critique: { score: 7 },
    })
    const wrapper = mount(EventBadges, {
      props: { msg, compact: true },
    })
    await nextTick()
    const root = wrapper.find('[data-testid="event-badges"]')
    expect(root.classes()).toContain('compact')
    const badge = wrapper.find('[data-testid="event-badge-critique"]')
    expect(badge.classes()).toContain('compact')
  })
})
