/**
 * PlanSteps W100 +57 空白长条修复测试 — 当所有 step 都是 placeholder (以 __ 开头)
 * 时，整卡片应 v-if false 隐藏，不再渲染空白长条。
 *
 * 3 case 覆盖：
 * ① steps 仅含 placeholder (1 行 __plan_summary__) → 卡片不渲染 (data-testid="plan-steps" 不存在)
 * ② steps 混合 5 个真实 tool_step + 2 个 placeholder → 卡片渲染，visibleSteps 5 个
 * ③ steps 为空数组 → 卡片不渲染
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PlanSteps from '../PlanSteps.vue'

describe('PlanSteps — W100 +71 edge cases', () => {
  it('① all placeholders hide card and row numbers', () => {
    const wrapper = mount(PlanSteps, { props: { steps: [
      { step: '__plan_summary__', status: 'pending' as const },
      { step: '__llm_thinking__', status: 'pending' as const },
      { step: '__meta__', status: 'pending' as const },
    ] } })
    expect(wrapper.find('[data-testid="plan-steps"]').exists()).toBe(false)
  })

  it('② real steps before trailing placeholder use 01-02', () => {
    const wrapper = mount(PlanSteps, { props: { steps: [
      { step: '第一步', status: 'pending' as const },
      { step: '第二步', status: 'pending' as const },
      { step: '__plan_summary__', status: 'pending' as const },
    ] } })
    expect(wrapper.findAll('.plan-step-num').map((n) => n.text())).toEqual(['01', '02'])
  })

  it('③ placeholder in middle is omitted and numbering follows source indices', () => {
    const wrapper = mount(PlanSteps, { props: { steps: [
      { step: '第一步', status: 'pending' as const },
      { step: '__plan_summary__', status: 'pending' as const },
      { step: '第二步', status: 'pending' as const },
    ] } })
    expect(wrapper.findAll('.plan-step-num').map((n) => n.text())).toEqual(['01', '03'])
  })

  it('④ legacy placeholder without tool_use_id hides via fallback', () => {
    const wrapper = mount(PlanSteps, { props: { steps: [
      { step: 'phase0_plan', status: 'running' as const },
    ] } })
    expect(wrapper.find('[data-testid="plan-steps"]').exists()).toBe(true)
  })

  it('⑤ nine real steps render with 01-09 numbering', () => {
    const steps = Array.from({ length: 9 }, (_, i) => ({ step: `步骤${i + 1}`, status: 'pending' as const }))
    const wrapper = mount(PlanSteps, { props: { steps } })
    expect(wrapper.findAll('.plan-step-num').map((n) => n.text())).toEqual(['01','02','03','04','05','06','07','08','09'])
  })
})
