/**
 * useChatStream W100 +53/+54 plan_step dedup + 老消息兼容测试
 *
 * 背景：W100 +52 在 PlanSteps.vue 加了 auto-collapse 逻辑 (全部 done 后折叠单行)，
 * 但前端 useChatStream 收到 plan_step 事件时只 push 不 dedup，
 * 导致后端发 'phase0_plan pending/running' + 每个 tool 的 'done' → 前端 plan 数组一直累积 running/pending step，
 * doneCount 永远不到 total → auto-collapse 永不触发。
 *
 * W100 +53 修复：后端每条 done 事件带 tool_use_id，前端按 id 去重原地更新 status。
 *
 * W100 +54 老消息兼容: 老 SSE plan_step 没有 tool_use_id (W100 +53 之前的会话),
 *   - case 2) 用 tool 字段匹配老 step
 *   - case 3) 找不到匹配时取第一个老 running step 标记 done
 *   - case 4) 收到第一条 text_delta 时强制把所有老 plan_step 标记 done (synthesis 阶段开始 = 计划阶段结束)
 *
 * 6 case 覆盖:
 * ① 同一 tool_use_id 收到 2 次 plan_step (pending + done) → plan 数组只有 1 个 step 且 status='done'
 * ② 不同 tool_use_id 收到 2 次 plan_step → plan 数组有 2 个 step
 * ③ 老消息兼容 (无 tool_use_id, status='running') + 新 done event (tool_use_id 不匹配 tool) → 按 step index fallback
 * ④ 收到第一条 text_delta → 所有老 plan_step (无 tool_use_id, 非 done) 标记 done
 * ⑤ 模拟完整 SSE 流 (老消息场景): 1 phase0_pending + 1 phase0_running + 6 tool_done + 第一条 text_delta → 全部 done
 * ⑥ doneCount 从 0→6 触发 auto-collapse (集成 PlanSteps 组件)
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
 * 模拟 useChatStream.ts:835-905 的 plan_step 处理逻辑 (W100 +54)
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
  const incomingToolName = evt.tool_name || evt.tool_use_id
  let existingIdx = -1
  // 1) tool_use_id 精确匹配
  if (evt.tool_use_id) {
    existingIdx = plan.findIndex((s) => s.tool_use_id === evt.tool_use_id)
  }
  // 2) 老 step 无 tool_use_id, 按 tool 字段匹配
  if (existingIdx < 0 && incomingToolName) {
    existingIdx = plan.findIndex((s) => !s.tool_use_id && s.tool === incomingToolName)
  }
  // 3) W100 +54 最稳 fallback: 老 step 都是 running, 新 done 事件取第一个老 running step
  if (
    existingIdx < 0 &&
    evt.plan_status === 'done' &&
    plan.some((s) => !s.tool_use_id)
  ) {
    const firstRunningIdx = plan.findIndex(
      (s) => !s.tool_use_id && s.status === 'running',
    )
    if (firstRunningIdx >= 0) existingIdx = firstRunningIdx
  }
  if (existingIdx >= 0 && evt.plan_status) {
    const next = [...plan]
    next[existingIdx] = { ...next[existingIdx], status: evt.plan_status }
    return next
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

/**
 * W100 +54 老消息兼容: 收到第一条 text_delta 时, 强制把老 plan_step (无 tool_use_id, 非 done) 标记 done
 */
function applyTextDeltaCompat(plan: PlanStep[]): PlanStep[] {
  if (!plan || plan.length === 0) return plan
  let changed = false
  const next = plan.map((s) => {
    if (!s.tool_use_id && s.status !== 'done') {
      changed = true
      return { ...s, status: 'done' as const }
    }
    return s
  })
  return changed ? next : plan
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

  it('③ W100 +54 老消息兼容: 无 tool_use_id 老 step + 新 done event (tool 也不匹配) → fallback 取第一个老 running step 标记 done', () => {
    let plan: PlanStep[] = []
    // 模拟老 SSE (W100 +53 之前): phase0_plan 没 tool_use_id
    plan = applyPlanStep(plan, { step: 'phase0_plan', plan_status: 'pending' })
    plan = applyPlanStep(plan, { step: 'phase0_plan', plan_status: 'running' })
    expect(plan).toHaveLength(2)
    expect(plan[1].status).toBe('running')
    // 老 step 都是通用名 'phase0_plan', 没有 tool 字段.
    // 后端 +53 后开始发 done 事件, tool_name='search_knowledge', 老 step 没 tool='search_knowledge'
    // → 1) tool_use_id 不命中; 2) tool 字段不命中; 3) fallback 3 命中: 取第一个老 running step 标记 done
    plan = applyPlanStep(plan, {
      step: 'search_knowledge',
      tool_name: 'search_knowledge',
      tool_use_id: 'plan_00_search_knowledge',
      plan_status: 'done',
    })
    expect(plan).toHaveLength(2) // 没 push 新行
    expect(plan[1].status).toBe('done') // 老 step 标记 done (fallback 3 取第一个 running)
  })

  it('④ W100 +54 老消息兼容: 收到第一条 text_delta → 所有老 plan_step (无 tool_use_id, 非 done) 标记 done', () => {
    let plan: PlanStep[] = []
    // 老 SSE: phase0_plan pending + phase0_plan running (无 tool_use_id)
    plan = applyPlanStep(plan, { step: 'phase0_plan', plan_status: 'pending' })
    plan = applyPlanStep(plan, { step: 'phase0_plan', plan_status: 'running' })
    expect(plan).toHaveLength(2)
    // 新 SSE 收一条 tool done (有 tool_use_id) — 老 step 无 id 无 tool 匹配 → fallback 3 → 第一个 running 标记 done
    plan = applyPlanStep(plan, {
      step: 'search_knowledge',
      tool_name: 'search_knowledge',
      tool_use_id: 'plan_00_search_knowledge',
      plan_status: 'done',
    })
    expect(plan[1].status).toBe('done') // fallback 3 → 第一个 running 标记 done
    expect(plan[0].status).toBe('pending') // 老 pending 没动
    expect(plan.length).toBe(2) // 没 push 新行
    // W100 +54 text_delta 兜底: 第一条 text_delta → 所有老 step 强制 done
    plan = applyTextDeltaCompat(plan)
    expect(plan.every((s) => !s.tool_use_id ? s.status === 'done' : true)).toBe(true)
    expect(plan.filter((s) => s.status === 'done').length).toBe(2) // 全部 done
  })

  it('⑤ 完整 SSE 流 (老消息场景): phase0_pending + phase0_running + 6 tool_done + text_delta → 全部 done', () => {
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
    // 第一次 tool_done: fallback 3 → 老 running 标记 done (不 push 新行) → 2 老 step + 5 新 tool = 7
    // 之后 5 次 tool_done: tool_use_id 都唯一, push 新行 → 7 + 5 = 7
    expect(plan).toHaveLength(7)
    // done 数: 1 老 running (fallback 3) + 5 新 tool done + 老 pending 没动 = 6 done, 1 pending
    const doneBeforeText = plan.filter((s) => s.status === 'done').length
    expect(doneBeforeText).toBe(6) // 5 new + 1 老 running (fallback 3)
    expect(plan[0].status).toBe('pending') // 老 pending 没动
    // W100 +54 text_delta 兜底: synthesis 阶段开始 → 老 pending 也变 done
    plan = applyTextDeltaCompat(plan)
    expect(plan.every((s) => s.status === 'done')).toBe(true)
    expect(plan.length).toBe(7) // 数组长度不变 (没 push 新行, 只 mutate 老行)
    // 全 done → auto-collapse 触发
    const doneCount = plan.filter((s) => s.status === 'done').length
    expect(doneCount).toBe(plan.length)
  })

  it('⑥ doneCount 触发 auto-collapse (W100 +52 集成): 6 行全 done → PlanSteps 折叠', async () => {
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