/**
 * PlanSteps W100 +60 行号修正测试 — placeholder 在中间被过滤时显示原始 step 编号
 *
 * 真根因 (W100 +55d 隐藏 placeholder 后的跳号 bug):
 *   visibleSteps computed 过滤掉 __ 开头的 placeholder step,
 *   但 v-for 用 visibleSteps 数组 index 算 pad (i+1).
 *   若 placeholder 在中间 (e.g. steps=[A, __plan_summary__, B, C]),
 *   过滤后 visibleSteps=[A, B, C], index=0,1,2 → 行号 "01","02","03",
 *   但用户期望原始 step 编号 "01","03","04" (B 是原第 3 步).
 *
 * W100 +60 修复:
 *   visibleSteps 同时记录原 props.steps 数组 index (originalIndex),
 *   template 用 stepNum(s) (基于 originalIndex) 替代 pad(i) (基于 visibleSteps index).
 *
 * 3 case 覆盖：
 * ① placeholder 在最前 → 行号 "02","03","04" (跳过 placeholder 占的 01)
 * ② placeholder 在中间 → 行号 "01","03","04" (B 是原第 3 步)
 * ③ placeholder 在最后 → 行号 "01","02","03" (前 3 个 real step)
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PlanSteps from '../PlanSteps.vue'

describe('PlanSteps — W100 +60 行号修正 (placeholder 中间过滤跳号)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① placeholder 在最前 → 行号从 02 起, 跳过 placeholder 占的 01', () => {
    const wrapper = mount(PlanSteps, {
      props: {
        steps: [
          { step: '__plan_summary__', status: 'pending' as const },
          { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
          { step: '提取公式', tool: 'extract_formulas', status: 'running' as const },
          { step: '生成回答', status: 'pending' as const },
        ],
      },
    })
    // 可见 step 3 个, 但行号基于原始 index (1,2,3 → "02","03","04")
    const steps = wrapper.findAll('[data-testid^="plan-step-"]:not([data-testid$="-name"]):not([data-testid$="-tool"]):not([data-testid$="-status"])')
    expect(steps.length).toBe(3)
    expect(wrapper.find('[data-testid="plan-step-0-num"], .plan-step-num').exists()).toBe(true)
    // 提取所有 .plan-step-num span 文本
    const nums = wrapper.findAll('.plan-step-num').map((n) => n.text())
    expect(nums).toEqual(['02', '03', '04'])
  })

  it('② placeholder 在中间 → 行号保留原始位置 (B 是原第 3 步 → "03")', () => {
    const wrapper = mount(PlanSteps, {
      props: {
        steps: [
          { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },        // 原 index 0 → "01"
          { step: '__plan_summary__', status: 'pending' as const },                          // 占位, 原 index 1 (过滤)
          { step: '提取公式', tool: 'extract_formulas', status: 'running' as const },       // 原 index 2 → "03"
          { step: '__llm_thinking__', status: 'pending' as const },                          // 占位, 原 index 3 (过滤)
          { step: '生成回答', status: 'pending' as const },                                  // 原 index 4 → "05"
        ],
      },
    })
    const steps = wrapper.findAll('[data-testid^="plan-step-"]:not([data-testid$="-name"]):not([data-testid$="-tool"]):not([data-testid$="-status"])')
    expect(steps.length).toBe(3)
    const nums = wrapper.findAll('.plan-step-num').map((n) => n.text())
    // 关键: 修复前是 "01","02","03" (visibleSteps index); 修复后是 "01","03","05" (原始 index)
    expect(nums).toEqual(['01', '03', '05'])
  })

  it('③ placeholder 在最后 → 行号连续 01,02,03 (前 3 个 real step)', () => {
    const wrapper = mount(PlanSteps, {
      props: {
        steps: [
          { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
          { step: '提取公式', tool: 'extract_formulas', status: 'running' as const },
          { step: '生成回答', status: 'pending' as const },
          { step: '__plan_summary__', status: 'pending' as const },
        ],
      },
    })
    const nums = wrapper.findAll('.plan-step-num').map((n) => n.text())
    expect(nums).toEqual(['01', '02', '03'])
  })
})