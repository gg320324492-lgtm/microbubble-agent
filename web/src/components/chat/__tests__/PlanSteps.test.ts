/**
 * PlanSteps 组件单测 — W100 +22 / W100 +49c
 * W100 +49c RICHTEXT-UNFOLD 沿用:
 *   - 默认 (collapsedByDefault 不传 / false) = 列表直接渲染, 无 toggle 按钮
 *   - collapsedByDefault=true = 折叠模式, 保留 toggle
 *
 * 8 case 覆盖：默认渲染 / 折叠模式 / 折叠模式 summary / 点击展开 / keyboard
 * Enter+Space / 三态视觉 / 全部 done auto-collapse (仅折叠模式生效) / 边界
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import PlanSteps from '../PlanSteps.vue'

const pendingSample = [
  { step: '查询知识库', tool: 'search_knowledge', status: 'pending' as const },
  { step: '提取公式', tool: 'extract_formulas', status: 'pending' as const },
  { step: '生成回答', status: 'pending' as const },
]

const mixedSample = [
  { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
  { step: '提取公式', tool: 'extract_formulas', status: 'running' as const },
  { step: '生成回答', status: 'pending' as const },
]

const allDoneSample = [
  { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
  { step: '生成回答', status: 'done' as const },
]

describe('PlanSteps — W100 +49c RICHTEXT-UNFOLD 默认展开', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① 默认 (collapsedByDefault 不传) = 列表直接渲染，无 toggle 按钮', () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: pendingSample },
    })
    expect(wrapper.find('[data-testid="plan-steps"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="plan-steps-toggle-header"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="plan-steps-summary-static"]').text()).toBe(
      '计划中: 3 个步骤',
    )
  })

  it('② collapsedByDefault=true 折叠模式：header toggle 存在，列表不可见', () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: pendingSample, collapsedByDefault: true },
    })
    expect(wrapper.find('[data-testid="plan-steps-toggle-header"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="plan-steps-summary"]').text()).toBe('计划中: 3 个步骤')
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
    expect(wrapper.attributes('data-collapsed-by-default')).toBe('true')
  })

  it('③ 折叠模式下点击 header 展开，aria-expanded=true，列表出现，每个 step 有 num/name', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: pendingSample, collapsedByDefault: true },
    })
    const btn = wrapper.find('[role="button"]')
    expect(btn.attributes('aria-expanded')).toBe('false')
    await btn.trigger('click')
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('true')
    const list = wrapper.find('[data-testid="plan-steps-list"]')
    expect(list.exists()).toBe(true)
    expect(
      wrapper
        .findAll('[data-testid^="plan-step-"]')
        .filter((n) => /^\d+$/.test(n.attributes('data-testid')?.replace('plan-step-', '') || ''))
        .length,
    ).toBeGreaterThanOrEqual(3)
    expect(wrapper.find('[data-testid="plan-step-0-name"]').text()).toBe('查询知识库')
    expect(wrapper.find('[data-testid="plan-step-0-tool"]').text()).toBe('search_knowledge')
  })

  it('④ keyboard Enter 和 Space 都触发展开（折叠模式 a11y 必需）', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: pendingSample, collapsedByDefault: true },
    })
    const btn = wrapper.find('[role="button"]')
    await btn.trigger('keydown', { key: 'Enter' })
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('true')
    await btn.trigger('click')
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('false')
    await btn.trigger('keydown', { key: ' ' })
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('true')
  })

  it('⑤ 折叠模式三态视觉 class：done/running/pending 各有 data-status 与 class', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: mixedSample, collapsedByDefault: true },
    })
    await wrapper.find('[role="button"]').trigger('click')
    await nextTick()
    const step0 = wrapper.find('[data-testid="plan-step-0"]')
    expect(step0.attributes('data-status')).toBe('done')
    expect(step0.classes()).toContain('plan-step-done')
    const step1 = wrapper.find('[data-testid="plan-step-1"]')
    expect(step1.attributes('data-status')).toBe('running')
    expect(step1.classes()).toContain('plan-step-running')
    const step2 = wrapper.find('[data-testid="plan-step-2"]')
    expect(step2.attributes('data-status')).toBe('pending')
    expect(step2.classes()).toContain('plan-step-pending')
    expect(wrapper.find('[data-testid="plan-steps-summary"]').text()).toBe('计划中: 1/3 步骤')
  })

  it('⑥ 折叠模式全部 done 时摘要改为 "计划完成: N 个步骤" 且自动折叠', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: allDoneSample, collapsedByDefault: true },
    })
    expect(wrapper.find('[data-testid="plan-steps-summary"]').text()).toBe('计划完成: 2 个步骤')
    await wrapper.find('[role="button"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    await wrapper.setProps({
      steps: [
        { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
        { step: '提取公式', tool: 'extract_formulas', status: 'done' as const },
        { step: '生成回答', status: 'done' as const },
      ],
    })
    await new Promise((r) => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
  })

  it('⑦ 默认模式 + 全部 done 时不会自动隐藏（auto-collapse 仅折叠模式生效）', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: mixedSample },
    })
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    await wrapper.setProps({
      steps: [
        { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
        { step: '生成回答', status: 'done' as const },
      ],
    })
    await new Promise((r) => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
  })

  it('⑧ 边界：空 steps 数组 → 组件不渲染', () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: [] },
    })
    expect(wrapper.find('[data-testid="plan-steps"]').exists()).toBe(false)
  })
})
