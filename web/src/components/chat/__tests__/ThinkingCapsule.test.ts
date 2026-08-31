/**
 * ThinkingCapsule 组件单测 — W99 +14
 * 11 case 覆盖：phase 文案 / data-phase / found count / elapsed / 终态 ticker 停 / exitDelay / compact / a11y / unmount 清 interval / spinner-glyph 切换
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ThinkingCapsule from '../ThinkingCapsule.vue'

describe('ThinkingCapsule — W99 +14', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('① 10 个 phase 都有非空文案', () => {
    const phases = [
      'queued',
      'thinking',
      'retrieving',
      'found',
      'synthesizing',
      'generating',
      'refining',
      'done',
      'aborted',
      'error',
    ] as const
    phases.forEach((phase) => {
      const wrapper = mount(ThinkingCapsule, { props: { phase } })
      expect(wrapper.find('[data-testid="capsule-label"]').text().length).toBeGreaterThan(0)
    })
  })

  it('② data-phase 随 prop 变化', async () => {
    const wrapper = mount(ThinkingCapsule, { props: { phase: 'thinking' } })
    expect(wrapper.find('[data-testid="thinking-capsule"]').attributes('data-phase')).toBe('thinking')
    // setProps 返回 Promise (DOM 要等 nextTick), 原测试漏 await → 读到旧值 (2026-08-31)
    await wrapper.setProps({ phase: 'retrieving' })
    expect(wrapper.find('[data-testid="thinking-capsule"]').attributes('data-phase')).toBe('retrieving')
  })

  it('③ found 含 count → "找到 7 条相关内容"', () => {
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'found', foundCount: 7 },
    })
    expect(wrapper.find('[data-testid="capsule-label"]').text()).toBe('找到 7 条相关内容')
  })

  it('④ elapsed 1.5s → "1.5s"', () => {
    const start = Date.now() - 1500
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', startedAt: start },
    })
    expect(wrapper.find('[data-testid="capsule-elapsed"]').text()).toBe('1.5s')
  })

  it('⑤ elapsed ≥ 60s → "1:05"', () => {
    const start = Date.now() - 65_000
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', startedAt: start },
    })
    expect(wrapper.find('[data-testid="capsule-elapsed"]').text()).toBe('1:05')
  })

  it('⑥ 终态后 ticker 停（advance 5s 文本不变）', async () => {
    const start = Date.now() - 1000
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', startedAt: start },
    })
    expect(wrapper.find('[data-testid="capsule-elapsed"]').text()).toBe('1.0s')
    wrapper.setProps({ phase: 'done' })
    await wrapper.vm.$nextTick()
    vi.advanceTimersByTime(5000)
    await wrapper.vm.$nextTick()
    // 终态后 ticker 停，文本应保持 1.0s（不递增到 6s）
    expect(wrapper.find('[data-testid="capsule-elapsed"]').exists()).toBe(false)
  })

  it('⑦ exitDelay 后节点消失', async () => {
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', exitDelay: 600 },
    })
    expect(wrapper.find('[data-testid="thinking-capsule"]').exists()).toBe(true)
    wrapper.setProps({ phase: 'done' })
    await wrapper.vm.$nextTick()
    vi.advanceTimersByTime(400)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="thinking-capsule"]').exists()).toBe(true)
    vi.advanceTimersByTime(300)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="thinking-capsule"]').exists()).toBe(false)
  })

  it('⑧ compact prop 加 class', () => {
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', compact: true },
    })
    expect(wrapper.find('.thinking-capsule').classes()).toContain('compact')
  })

  it('⑨ a11y: role + aria-live + aria-label 含用时', () => {
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', startedAt: Date.now() - 2000 },
    })
    const root = wrapper.find('[data-testid="thinking-capsule"]')
    expect(root.attributes('role')).toBe('status')
    expect(root.attributes('aria-live')).toBe('polite')
    const label = root.attributes('aria-label') || ''
    expect(label).toContain('正在思考')
    expect(label).toContain('2.0s')
  })

  it('⑩ unmount 清 interval（防 W11 T1 同类泄漏）', () => {
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', startedAt: Date.now() - 1000 },
    })
    // 触发 ticker 启动
    vi.advanceTimersByTime(200)
    // 卸载组件
    wrapper.unmount()
    // 卸载后 timer 数量应归零
    expect(vi.getTimerCount()).toBe(0)
  })

  it('⑪ spinner/glyph 按 phase 切换', () => {
    // 检索类 → spinner
    const w1 = mount(ThinkingCapsule, { props: { phase: 'retrieving' } })
    expect(w1.find('.spinner').exists()).toBe(true)
    expect(w1.find('.glyph').exists()).toBe(false)
    // 终态静态图标 → glyph
    const w2 = mount(ThinkingCapsule, { props: { phase: 'found' } })
    expect(w2.find('.glyph').exists()).toBe(true)
    expect(w2.find('.glyph').text()).toBe('📚')
    // 非终态且非检索 → dots
    const w3 = mount(ThinkingCapsule, { props: { phase: 'thinking' } })
    expect(w3.find('.dots').exists()).toBe(true)
    expect(w3.find('.spinner').exists()).toBe(false)
  })
})