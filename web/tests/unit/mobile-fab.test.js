import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import MobileFab from '@/components/mobile/MobileFab.vue'

const LongPressStub = {
  // 2026-08-31: 补 class="long-press-wrapper" — 本文件 L32/L38 用 wrapper.get('.long-press-wrapper')
  // 查询, 而 stub 根节点此前无该 class, get() 必抛 (既有测试自身笔误, 非实现 bug)
  template: '<div class="long-press-wrapper" @longpress="$emit(\'longpress\')"><slot /></div>',
  emits: ['longpress'],
}

describe('MobileFab', () => {
  const actions = [
    { name: 'one', label: '第一个动作', icon: '📁', handler: vi.fn() },
    { name: 'two', label: '第二个动作', icon: '🔍', handler: vi.fn() },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('navigator', { vibrate: vi.fn() })
  })

  afterEach(() => vi.unstubAllGlobals())

  it('renders the trigger and action definitions', () => {
    const wrapper = mount(MobileFab, { props: { actions }, global: { stubs: { LongPressWrapper: LongPressStub } } })
    expect(wrapper.get('button.mobile-fab-trigger').attributes('aria-label')).toBe('快速操作')
    expect(wrapper.text()).toContain('第一个动作')
    expect(wrapper.text()).toContain('第二个动作')
  })

  it('expands after a long press', async () => {
    const wrapper = mount(MobileFab, { props: { actions }, global: { stubs: { LongPressWrapper: LongPressStub } } })
    await wrapper.get('.long-press-wrapper').trigger('longpress')
    expect(wrapper.get('.mobile-fab-trigger').attributes('aria-expanded')).toBe('true')
    expect(wrapper.findAll('.mobile-fab-action').every((node) => node.isVisible())).toBe(true)
  })

  it('toggles closed when the trigger is clicked again', async () => {
    const wrapper = mount(MobileFab, { props: { actions }, global: { stubs: { LongPressWrapper: LongPressStub } } })
    const trigger = wrapper.get('.mobile-fab-trigger')
    await trigger.trigger('click')
    expect(trigger.attributes('aria-expanded')).toBe('true')
    await trigger.trigger('click')
    expect(trigger.attributes('aria-expanded')).toBe('false')
  })

  it('provides haptic feedback while changing state', async () => {
    const vibrate = navigator.vibrate
    const wrapper = mount(MobileFab, { props: { actions }, global: { stubs: { LongPressWrapper: LongPressStub } } })
    await wrapper.get('.mobile-fab-trigger').trigger('click')
    expect(vibrate).toHaveBeenCalledWith(10)
  })
})
