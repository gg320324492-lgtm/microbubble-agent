/**
 * PlanSteps 组件单测 — W100 +22
 * 6 case 覆盖：默认折叠 + 摘要文案 / 点击展开 / a11y (aria-expanded) / keyboard Enter+Space /
 * 全部 done 后自动折叠 / 三态视觉 class
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

describe('PlanSteps — W100 +22', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① 默认折叠，显示摘要 "计划中: 3 个步骤"，列表不可见', () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: pendingSample },
    })
    expect(wrapper.find('[data-testid="plan-steps"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="plan-steps-summary"]').text()).toBe('计划中: 3 个步骤')
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
  })

  it('② 点击 header 展开，aria-expanded=true，列表出现，每个 step 有 num/name', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: pendingSample },
    })
    const btn = wrapper.find('[role="button"]')
    expect(btn.attributes('aria-expanded')).toBe('false')
    await btn.trigger('click')
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('true')
    const list = wrapper.find('[data-testid="plan-steps-list"]')
    expect(list.exists()).toBe(true)
    // 3 steps
    expect(wrapper.findAll('[data-testid^="plan-step-"]').filter((n) => /^\d+$/.test(n.attributes('data-testid')?.replace('plan-step-', '') || '')).length).toBeGreaterThanOrEqual(3)
    // 第一个 step 名是 "查询知识库"
    expect(wrapper.find('[data-testid="plan-step-0-name"]').text()).toBe('查询知识库')
    expect(wrapper.find('[data-testid="plan-step-0-tool"]').text()).toBe('search_knowledge')
  })

  it('③ keyboard Enter 和 Space 都触发展开（a11y 必需）', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: pendingSample },
    })
    const btn = wrapper.find('[role="button"]')
    await btn.trigger('keydown', { key: 'Enter' })
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('true')
    // 收回
    await btn.trigger('click')
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('false')
    // Space 再展开
    await btn.trigger('keydown', { key: ' ' })
    await nextTick()
    expect(btn.attributes('aria-expanded')).toBe('true')
  })

  it('④ 三态视觉 class：done/running/pending 各有 data-status 与 class', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: mixedSample },
    })
    await wrapper.find('[role="button"]').trigger('click')
    await nextTick()
    // done 步骤
    const step0 = wrapper.find('[data-testid="plan-step-0"]')
    expect(step0.attributes('data-status')).toBe('done')
    expect(step0.classes()).toContain('plan-step-done')
    // running 步骤
    const step1 = wrapper.find('[data-testid="plan-step-1"]')
    expect(step1.attributes('data-status')).toBe('running')
    expect(step1.classes()).toContain('plan-step-running')
    // pending 步骤
    const step2 = wrapper.find('[data-testid="plan-step-2"]')
    expect(step2.attributes('data-status')).toBe('pending')
    expect(step2.classes()).toContain('plan-step-pending')
    // summary 应是 "计划中: 1/3 步骤"
    expect(wrapper.find('[data-testid="plan-steps-summary"]').text()).toBe('计划中: 1/3 步骤')
  })

  it('⑤ 全部 done 时摘要改为 "计划完成: N 个步骤" 且自动折叠', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: allDoneSample },
    })
    // 初始：全部 done → 摘要为 "计划完成"
    expect(wrapper.find('[data-testid="plan-steps-summary"]').text()).toBe('计划完成: 2 个步骤')
    // 用户展开
    await wrapper.find('[role="button"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    // props 变化：从 mixed → allDone，触发 watcher
    await wrapper.setProps({
      steps: [
        { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
        { step: '提取公式', tool: 'extract_formulas', status: 'done' as const },
        { step: '生成回答', status: 'done' as const },
      ],
    })
    // 自动折叠 (Vue Transition keep element during leave, 150ms + buffer)
    await new Promise((r) => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
  })

  it('⑥ 边界：空 steps 数组 → 组件不渲染', () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: [] },
    })
    expect(wrapper.find('[data-testid="plan-steps"]').exists()).toBe(false)
  })
})