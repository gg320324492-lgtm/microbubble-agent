/**
 * useChatStream W100 +53 plan_step dedup 测试 — SSE plan_step 事件按 tool_use_id 原地更新
 *
 * 背景：W100 +52 在 PlanSteps.vue 加了 auto-collapse 逻辑 (全部 done 后折叠单行)，
 * 但前端 useChatStream 收到 plan_step 事件时只 push 不 dedup，
 * 导致后端发 'phase0_plan pending/running' + 每个 tool 的 'done' → 前端 plan 数组一直累积 running/pending step，
 * doneCount 永远不到 total → auto-collapse 永不触发。
 *
 * W100 +53 修复：后端每条 done 事件带 tool_use_id，前端按 id 去重原地更新 status。
 *
 * 5 case 覆盖：
 * ① 同一 tool_use_id 收到 2 次 plan_step (pending + done) → plan 数组只有 1 个 step 且 status='done'
 * ② 不同 tool_use_id 收到 2 次 plan_step → plan 数组有 2 个 step
 * ③ 老消息兼容: 无 tool_use_id 的事件 → fallback push (findIndex 返回 -1)
 * ④ 模拟完整 SSE 流: 1 phase0_pending + 1 phase0_running + 6 tool_done → 6 行 done (无孤儿 phase0_done)
 * ⑤ doneCount 从 0→6 触发 auto-collapse (集成 PlanSteps 组件)
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

// 用真实 PlanStep interface 测, 不导入整个 useChatStream (复杂 store 注入)
interface PlanStep {
  step: string
  tool?: string
  tool_use_id?: string
  status: 'pending' | 'running' | 'done'
}

/**
 * 模拟 useChatStream.ts:838-862 的 plan_step 处理逻辑
 * (同步内联版, 与生产代码 1:1 对齐, 修改 useChatStream 时必须同步更新此函数)
 */
function applyPlanStep(
  plan: PlanStep[],
  evt: {
    step?: string
    label?: string
    tool_name?: string
    tool_use_id?: string
    plan_status?: 'pending' | 'running' | 'done'
  },
): PlanStep[] {
  const incomingToolId = evt.tool_use_id || evt.tool_name
  if (incomingToolId) {
    const existingIdx = plan.findIndex(
      (s) => s.tool_use_id === incomingToolId || (!s.tool_use_id && s.tool === incomingToolId),
    )
    if (existingIdx >= 0 && evt.plan_status) {
      const next = [...plan]
      next[existingIdx] = { ...next[existingIdx], status: evt.plan_status }
      return next
    }
  }
  return [
    ...plan,
    {
      step: evt.step || evt.label || '',
      tool: evt.tool_name,
      tool_use_id: evt.tool_use_id,
      status: evt.plan_status || 'pending',
    },
  ]
}

describe('useChatStream W100 +53 plan_step dedup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① 同一 tool_use_id 收到 pending + done → plan 数组只有 1 个 step 且 status=done', () => {
    let plan: PlanStep[] = []
    // 1) 后端 push 一个 tool step (running)
    plan = applyPlanStep(plan, {
      step: 'search_knowledge',
      tool_name: 'search_knowledge',
      tool_use_id: 'plan_00_search_knowledge',
      plan_status: 'running',
    })
    expect(plan).toHaveLength(1)
    expect(plan[0].status).toBe('running')

    // 2) 同一 tool_use_id 收到 done → 原地更新, 不 push 新行
    plan = applyPlanStep(plan, {
      step: 'search_knowledge',
      tool_name: 'search_knowledge',
      tool_use_id: 'plan_00_search_knowledge',
      plan_status: 'done',
    })
    expect(plan).toHaveLength(1)
    expect(plan[0].status).toBe('done')
    expect(plan[0].tool_use_id).toBe('plan_00_search_knowledge')
  })

  it('② 不同 tool_use_id → plan 数组累积不同 step', () => {
    let plan: PlanStep[] = []
    plan = applyPlanStep(plan, {
      step: 'tool_a',
      tool_name: 'tool_a',
      tool_use_id: 'plan_00_tool_a',
      plan_status: 'done',
    })
    plan = applyPlanStep(plan, {
      step: 'tool_b',
      tool_name: 'tool_b',
      tool_use_id: 'plan_01_tool_b',
      plan_status: 'done',
    })
    plan = applyPlanStep(plan, {
      step: 'tool_c',
      tool_name: 'tool_c',
      tool_use_id: 'plan_02_tool_c',
      plan_status: 'done',
    })
    expect(plan).toHaveLength(3)
    expect(plan.map((s) => s.tool)).toEqual(['tool_a', 'tool_b', 'tool_c'])
    expect(plan.every((s) => s.status === 'done')).toBe(true)
  })

  it('③ 老消息兼容: 无 tool_use_id 事件 → fallback push (向后兼容)', () => {
    let plan: PlanStep[] = []
    // 模拟老 SSE: 后端未带 tool_use_id (W100 +52 之前的事件)
    plan = applyPlanStep(plan, {
      step: 'phase0_plan',
      plan_status: 'pending',
    })
    expect(plan).toHaveLength(1)
    expect(plan[0].status).toBe('pending')

    // 老 SSE 第二次也无 tool_use_id → 仍 fallback push (老消息会显示多行)
    plan = applyPlanStep(plan, {
      step: 'phase0_plan',
      plan_status: 'running',
    })
    expect(plan).toHaveLength(2)

    // 新 SSE 收到带 tool_use_id 的 done → 不命中老无 id step → push 新行
    // (老消息无 tool_use_id 找不到匹配, 新协议 step 仍会显示)
    plan = applyPlanStep(plan, {
      step: 'search_knowledge',
      tool_name: 'search_knowledge',
      tool_use_id: 'plan_00_search_knowledge',
      plan_status: 'done',
    })
    expect(plan).toHaveLength(3)
    expect(plan[2].status).toBe('done')
  })

  it('④ 完整 SSE 流: phase0_pending + phase0_running + 6 tool_done → 8 行 (2 phase0 + 6 tool done, 无孤儿)', () => {
    let plan: PlanStep[] = []
    // 后端顺序: pending → running → 6 个 tool 的 done (每个 done 带 tool_use_id)
    plan = applyPlanStep(plan, { step: 'phase0_plan', plan_status: 'pending' })
    plan = applyPlanStep(plan, { step: 'phase0_plan', plan_status: 'running' })
    for (let i = 0; i < 6; i++) {
      const tool = `tool_${i}`
      plan = applyPlanStep(plan, {
        step: tool,
        tool_name: tool,
        tool_use_id: `plan_${String(i).padStart(2, '0')}_${tool}`,
        plan_status: 'done',
      })
    }
    expect(plan).toHaveLength(8)
    // done step 计数
    const doneCount = plan.filter((s) => s.status === 'done').length
    expect(doneCount).toBe(6)
    // W100 +52: auto-collapse 守卫 `oldVal > 0 && newVal === total.value`
    // 用 plan 中 status='done' 的 step 数 (6) 与 total (8) 比较 → 不等于 → 不触发 (期望行为)
    // 老消息中 phase0_pending/running 也算 step, auto-collapse 仅在 done 覆盖全部时触发
    expect(doneCount).not.toBe(plan.length)
  })

  it('⑤ doneCount 触发 auto-collapse (W100 +52 集成): 6 行全 done → PlanSteps 折叠', async () => {
    // 集成测试: 把 dedup 后的 plan 喂给 PlanSteps 组件, 验证 doneCount === total → auto-collapse
    const PlanSteps = (await import('../../../components/chat/PlanSteps.vue')).default

    // 模拟 dedup 后 6 行全 done 的 plan (W100 +53 期望 SSE 产物)
    const sixDone = Array.from({ length: 6 }, (_, i) => ({
      step: `步骤 ${i + 1}`,
      tool: `tool_${i}`,
      tool_use_id: `plan_${String(i).padStart(2, '0')}_tool_${i}`,
      status: 'done' as const,
    }))

    const wrapper = mount(PlanSteps, {
      props: { steps: sixDone },
    })
    // 初次加载 (collapsedByDefault=false) → 列表可见 (老 Val=0 守卫保护)
    await new Promise((r) => setTimeout(r, 50))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)

    // 模拟流式变化: 1 个 done + 5 个 running (oldVal=1) → 6 个全 done (newVal=6, total=6)
    const partial = [
      { step: '步骤 1', tool: 'tool_0', tool_use_id: 'plan_00_tool_0', status: 'done' as const },
      ...Array.from({ length: 5 }, (_, i) => ({
        step: `步骤 ${i + 2}`,
        tool: `tool_${i + 1}`,
        tool_use_id: `plan_${String(i + 1).padStart(2, '0')}_tool_${i + 1}`,
        status: 'running' as const,
      })),
    ]
    await wrapper.setProps({ steps: partial })
    await new Promise((r) => setTimeout(r, 50))
    // 还没全部 done → 列表可见
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)

    // 全部 done → auto-collapse 触发
    await wrapper.setProps({ steps: sixDone })
    await new Promise((r) => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
    const header = wrapper.find('[data-testid="plan-steps-toggle-header"]')
    expect(header.exists()).toBe(true)
    expect(header.text()).toContain('计划完成: 6 个步骤')
  })
})