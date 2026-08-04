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

describe('PlanSteps — W100 +57 blank card fix', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① steps 仅含 placeholder → 卡片 v-if false (data-testid="plan-steps" 不存在)', () => {
    const wrapper = mount(PlanSteps, {
      props: {
        steps: [{ step: '__plan_summary__', status: 'pending' as const }],
      },
    })

    expect(wrapper.find('[data-testid="plan-steps"]').exists()).toBe(false)
  })

  it('② steps 混合 placeholder + 真实 tool_step → 卡片渲染, visibleSteps 仅含 5 个真实 step', () => {
    const wrapper = mount(PlanSteps, {
      props: {
        steps: [
          { step: '__plan_summary__', status: 'pending' as const },
          { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
          { step: '提取公式', tool: 'extract_formulas', status: 'running' as const },
          { step: '查询历史会议', tool: 'list_meetings', status: 'pending' as const },
          { step: '生成回答', status: 'pending' as const },
          { step: '__llm_thinking__', status: 'pending' as const },
          { step: '总结反馈', status: 'pending' as const },
        ],
      },
    })

    expect(wrapper.find('[data-testid="plan-steps"]').exists()).toBe(true)
    // 5 个真实 step（去掉 2 个 placeholder）
    const steps = wrapper.findAll('[data-testid^="plan-step-"]:not([data-testid$="-name"]):not([data-testid$="-tool"]):not([data-testid$="-status"])')
    expect(steps.length).toBe(5)
  })

  it('③ steps 为空数组 → 卡片不渲染', () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: [] },
    })

    expect(wrapper.find('[data-testid="plan-steps"]').exists()).toBe(false)
  })
})
