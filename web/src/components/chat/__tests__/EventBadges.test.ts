/**
 * EventBadges 组件单测 — W100 +26
 *
 * 11 case 覆盖：
 * ① 空 msg → 整体不渲染 (data-testid 不存在)
 * ② 流式中新到达 synthesis_start → 显示 burst badge, 3s 后消失
 * ③ retry 触发 → 显示橙色 badge, 内容含 "第 N 次"
 * ④ critique 完成 → 显示绿色 badge, 含 score=N/10
 * ⑤ tool_compressed 触发 → 显示灰底 badge, 含 "N → M 条"
 * ⑥ 4 状态同时存在 → 4 个 badge 全部显示, 不冲突
 * ⑦ compact 模式 → 内边距/字号小
 * ⑧⑨⑩ 2026-11-04 修复回归：一进会话就闪「正在组织回答」3s 自消
 *    (历史消息挂载即带 synthesis 块被误判成"新触发" —— watch 用 !before 判首次)
 *    ⚠️ 旧用例 ② 曾把这个 bug 写成断言, 现改为「先空后补」以模拟真实 SSE 时序。
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

  it('② 流式中新到达 synthesis_start → 显示 burst badge, 3s 后消失', async () => {
    // 必须「先空后补」来模拟 SSE 新事件到达：挂载时就带 toolTrace 属于
    // 「历史消息加载」，不是新触发（旧用例正是把那个 bug 写成了断言）。
    const base = makeMsg({ state: 'streaming', toolTrace: [] })
    const wrapper = mount(EventBadges, {
      props: { msg: base },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(false)

    await wrapper.setProps({
      msg: { ...base, toolTrace: [{ type: 'thinking', label: '✨ 综合分析中...' }] },
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
        { type: 'tool', name: 'search_knowledge', compression: { original_count: 12, selected_count: 4, summary: 's' } },
      ],
    })
    const wrapper = mount(EventBadges, {
      props: { msg },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="event-badges"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="event-badge-retry"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="event-badge-critique"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="event-badge-compressed"]').exists()).toBe(true)
    // synthesis 是 burst 语义，必须由「流式中新到达」触发 → 用 setProps 补事件
    await wrapper.setProps({
      msg: {
        ...msg,
        toolTrace: [{ type: 'thinking', label: '✨ 综合分析中...' }, ...msg.toolTrace],
      },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(true)
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

  // ---- 2026-11-04 修复回归：一进会话就闪「正在组织回答」，3s 后自消 ----
  // 根因: watch(hasSynthesisEvent, {immediate:true}) 用 `!before` 判「新触发」，
  //       而首次回调 before 是 undefined ⇒ 历史消息一挂载就被当成新事件闪一次。
  it('⑧ 历史消息加载 (state=idle + 挂载即带 synthesis 块) → 不闪 burst', async () => {
    const wrapper = mount(EventBadges, {
      props: {
        msg: makeMsg({
          state: 'idle',
          toolTrace: [{ type: 'thinking', label: '✨ 综合分析中...' }],
        }),
      },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(false)
    vi.advanceTimersByTime(5000)
    await nextTick()
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(false)
  })

  it('⑨ 即使 state=streaming，挂载时已存在的 synthesis 块也不算新触发', async () => {
    const wrapper = mount(EventBadges, {
      props: {
        msg: makeMsg({
          state: 'streaming',
          toolTrace: [{ type: 'thinking', label: '✨ 综合分析中...' }],
        }),
      },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(false)
  })

  it('⑩ burst 期间消息结束 (state→idle) → 立刻收起，不挂在已完成回答上', async () => {
    const base = makeMsg({ state: 'streaming', toolTrace: [] })
    const wrapper = mount(EventBadges, { props: { msg: base } })
    await wrapper.setProps({
      msg: { ...base, toolTrace: [{ type: 'thinking', label: '✨ 综合分析中...' }] },
    })
    await nextTick()
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(true)

    const done = { ...base, state: 'idle' as const, toolTrace: [{ type: 'thinking', label: '✨ 综合分析中...' }] }
    await wrapper.setProps({ msg: done })
    await nextTick()
    expect(wrapper.find('[data-testid="event-badge-synthesis"]').exists()).toBe(false)
  })
})
