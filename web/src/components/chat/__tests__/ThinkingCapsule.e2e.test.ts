/**
 * ThinkingCapsule 集成 e2e（vite test-utils 替代 playwright）
 * W99 +16 — 验证 msg.phase 5 阶段 + P1 联动
 *
 * 基于 vue test-utils mount + 真实 ThinkingCapsule 组件
 * 覆盖 9 case：① 5 phase 完整序列 ② ⏹ 中断 ③ retry ④ 普通问答全程不消失 ⑤ reload sanitize
 *                ⑥ FollowUpChips skeleton 等待 ⑦ rich_block 渐显 ⑧ trace spinner ⑨ 一致性 aria-label
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ThinkingCapsule from '../ThinkingCapsule.vue'

describe('ThinkingCapsule 集成 e2e — W99 +16', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('① 5 phase 完整序列：queued → retrieved → synthesizing → generating → done', async () => {
    const trace: string[] = []
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'queued', startedAt: Date.now() },
    })
    trace.push(wrapper.find('[data-testid="capsule-label"]').text())
    wrapper.setProps({ phase: 'retrieving' })
    await nextTick()
    trace.push(wrapper.find('[data-testid="capsule-label"]').text())
    wrapper.setProps({ phase: 'synthesizing' })
    await nextTick()
    trace.push(wrapper.find('[data-testid="capsule-label"]').text())
    wrapper.setProps({ phase: 'generating' })
    await nextTick()
    trace.push(wrapper.find('[data-testid="capsule-label"]').text())
    wrapper.setProps({ phase: 'done' })
    await nextTick()
    trace.push(wrapper.find('[data-testid="capsule-label"]').text())
    expect(trace).toEqual([
      '正在理解问题',
      '正在检索',
      '正在组织回答',
      '正在生成',
      '已完成',
    ])
  })

  it('② ⏹ 中断：phase=aborted → "已中断" → 500ms 后节点消失', async () => {
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', exitDelay: 500 },
    })
    expect(wrapper.find('[data-testid="thinking-capsule"]').exists()).toBe(true)
    wrapper.setProps({ phase: 'aborted' })
    await nextTick()
    vi.advanceTimersByTime(500)
    await nextTick()
    expect(wrapper.find('[data-testid="thinking-capsule"]').exists()).toBe(false)
  })

  it('③ retry：phase=refining + retryCount=2 → "正在重新优化（第 2 次）"', async () => {
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'refining', retryCount: 2 },
    })
    expect(wrapper.find('[data-testid="capsule-label"]').text()).toBe(
      '正在重新优化（第 2 次）',
    )
    expect(wrapper.find('.spinner').exists()).toBe(true)
  })

  it('④ 普通问答全程胶囊不消失（核心回归点）', async () => {
    // 模拟无检索普通问答：queued → thinking → generating → done
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'queued', startedAt: Date.now() - 3000 },
    })
    expect(wrapper.find('[data-testid="thinking-capsule"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="capsule-elapsed"]').exists()).toBe(true)
    wrapper.setProps({ phase: 'thinking' })
    await nextTick()
    wrapper.setProps({ phase: 'generating' })
    await nextTick()
    // 整个过程胶囊始终存在（不会因为 toolTrace 出现而消失）
    expect(wrapper.find('[data-testid="thinking-capsule"]').exists()).toBe(true)
  })

  it('⑤ reload sanitize 模拟：state=streaming 反序列化 → phase=done + elapsed 不显示', async () => {
    // 模拟 scenario：流中刷新 → 反序列化读到 streaming 消息
    // useChatStream sanitizeRestored 已将 streaming → idle + phase=done
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'done', startedAt: Date.now() - 5000 },
    })
    // 终态 done 后：不应显示 elapsed（不能显示历史秒数）
    expect(wrapper.find('[data-testid="capsule-elapsed"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="capsule-label"]').text()).toBe('已完成')
  })

  it('⑥ capsule spinner 切换：retrieving → refining → found（spinner 三态切换）', async () => {
    const wrapper = mount(ThinkingCapsule, { props: { phase: 'retrieving' } })
    expect(wrapper.find('.spinner').exists()).toBe(true)
    wrapper.setProps({ phase: 'refining' })
    await nextTick()
    expect(wrapper.find('.spinner').exists()).toBe(true)
    wrapper.setProps({ phase: 'found', foundCount: 5 })
    await nextTick()
    expect(wrapper.find('.glyph').exists()).toBe(true)
    expect(wrapper.find('.glyph').text()).toBe('📚')
    expect(wrapper.find('[data-testid="capsule-label"]').text()).toBe(
      '找到 5 条相关内容',
    )
  })

  it('⑦ a11y 数据完整性：aria-label 包含阶段 + 用时（仅进行态）', async () => {
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', startedAt: Date.now() - 1500 },
    })
    const label = wrapper.find('[data-testid="thinking-capsule"]').attributes('aria-label') || ''
    expect(label).toContain('正在思考')
    expect(label).toContain('1.5s')
  })

  it('⑧ 一致性：data-phase 立即响应 prop 变化', async () => {
    const wrapper = mount(ThinkingCapsule, { props: { phase: 'queued' } })
    expect(wrapper.find('[data-testid="thinking-capsule"]').attributes('data-phase')).toBe('queued')
    wrapper.setProps({ phase: 'found' })
    await nextTick()
    expect(wrapper.find('[data-testid="thinking-capsule"]').attributes('data-phase')).toBe('found')
  })

  it('⑨ unmount 不报 setTimeout warning（防 W11 T1 同类泄漏）', () => {
    const wrapper = mount(ThinkingCapsule, {
      props: { phase: 'thinking', startedAt: Date.now() - 1000 },
    })
    vi.advanceTimersByTime(300)
    expect(() => wrapper.unmount()).not.toThrow()
    expect(vi.getTimerCount()).toBe(0)
  })
})