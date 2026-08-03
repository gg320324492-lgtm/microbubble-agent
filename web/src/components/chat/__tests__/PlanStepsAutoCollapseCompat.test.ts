/**
 * PlanSteps W100 +54 老消息兼容 auto-collapse 测试
 *
 * 背景: W100 +53 修复后, 新 SSE plan_step 事件带 tool_use_id → 前端按 id 去重, doneCount = total.
 * 但 W100 +53 之前的会话 (老 session) 持久化的 plan_step 没有 tool_use_id 字段,
 * 后端不会再发 done 事件. W100 +54 兼容性修复:
 *   1) useChatStream plan_step case: 3 层 fallback (tool_use_id / tool / 第一个老 running)
 *   2) useChatStream text_delta case: 第一条 text_delta 时强制所有老 plan_step (无 tool_use_id) 标记 done
 *
 * 用户场景: 老 session 列表打开 → 看到 phase0_plan 一直 ⟳ (running) → 期望自动折叠
 *
 * 3 case 覆盖:
 * ① 老 step 初次加载 (无 tool_use_id, status=running) → 列表可见 (老 Val=0 守卫保护)
 * ② 老 step (mixed pending/running) + SSE 流 done event → fallback 3 命中第一个老 running → text_delta compat → 全部 done → auto-collapse
 * ③ 老 step 初次加载 (全 running) + text_delta compat 直接变 done → oldVal=0 守卫保护不折叠 (历史消息设计意图: 保持展开)
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import PlanSteps from '../PlanSteps.vue'

/**
 * W100 +54 兼容逻辑: 模拟 useChatStream text_delta case 中的老 plan_step 兜底
 * (与 useChatStream.ts text_delta case 1:1 对齐)
 */
function applyTextDeltaCompat<T extends { tool_use_id?: string; status: string }>(
  plan: T[],
): T[] {
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

describe('PlanSteps — W100 +54 老消息兼容 auto-collapse', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① 老 step 初次加载 (无 tool_use_id, status=running) → 列表可见 (老 Val=0 守卫保护)', async () => {
    // 模拟历史消息: 老 SSE 持久化的 plan_step 没 tool_use_id, status 保持 'running'
    const oldSessionSteps = [
      { step: 'phase0_plan', status: 'running' as const },
      { step: 'phase0_plan', status: 'running' as const },
      { step: 'phase0_plan', status: 'running' as const },
    ]
    const wrapper = mount(PlanSteps, {
      props: { steps: oldSessionSteps },
    })
    await new Promise((r) => setTimeout(r, 50))
    // 初次加载: 列表可见 (doneCount=0 < total=3, 不折叠; oldVal>0 守卫也没触发)
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="plan-steps-toggle-header"]').exists()).toBe(false)
  })

  it('② 老 step (mixed pending/running) + SSE done event → fallback 3 → text_delta compat → auto-collapse', async () => {
    // 模拟老 SSE 历史消息初次加载, 然后新 SSE done event 进入 (有 tool_use_id)
    const oldSessionSteps = [
      { step: 'phase0_plan', status: 'pending' as const },
      { step: 'phase0_plan', status: 'running' as const },
    ]
    const wrapper = mount(PlanSteps, {
      props: { steps: oldSessionSteps },
    })
    await new Promise((r) => setTimeout(r, 50))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)

    // 新 SSE 收一条 tool done (有 tool_use_id) — 老 step 无 id 无 tool 匹配 → fallback 3
    // fallback 3: 第一个老 running step 标记 done (不 push 新行)
    const partialDone = [
      { step: 'phase0_plan', status: 'pending' as const, tool_use_id: undefined },
      { step: 'phase0_plan', status: 'done' as const, tool_use_id: undefined },
    ]
    await wrapper.setProps({ steps: partialDone })
    await new Promise((r) => setTimeout(r, 50))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    expect(partialDone.length).toBe(2) // 数组长度不变 (fallback 3 命中老 step, 不 push 新行)

    // W100 +54 text_delta compat: 第一条 text_delta → 老 pending 也变 done
    // 此时 doneCount 从 1 → 2 (oldVal=1, newVal=2, total=2) → auto-collapse 触发
    const fullyDone = applyTextDeltaCompat(partialDone)
    expect(fullyDone.every((s) => s.status === 'done')).toBe(true)
    await wrapper.setProps({ steps: fullyDone })
    await new Promise((r) => setTimeout(r, 250))
    // doneCount=2 = total=2, oldVal=1 → auto-collapse 触发
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
    const header = wrapper.find('[data-testid="plan-steps-toggle-header"]')
    expect(header.exists()).toBe(true)
    expect(header.text()).toContain('计划完成: 2 个步骤')
  })

  it('③ 老 step 初次加载 (全 running) + text_delta compat 直接变 done → oldVal=0 守卫保护不折叠', async () => {
    // 模拟历史消息初次加载后, text_delta compat 一次性全标 done (0→3 跳变)
    const oldSessionSteps = [
      { step: 'phase0_plan', status: 'running' as const },
      { step: 'phase0_plan', status: 'running' as const },
      { step: 'phase0_plan', status: 'running' as const },
    ]
    const wrapper = mount(PlanSteps, {
      props: { steps: oldSessionSteps },
    })
    await new Promise((r) => setTimeout(r, 50))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)

    // W100 +54 模拟 useChatStream text_delta compat: 全部老 step 标记 done (跳变)
    const fixedSteps = applyTextDeltaCompat(oldSessionSteps)
    expect(fixedSteps.every((s) => s.status === 'done')).toBe(true)

    // 更新 props → watcher 触发 → oldVal=0 (上一次是 0 done, 现在是 3 done, total=3)
    // W100 +52 auto-collapse 守卫 `oldVal > 0 && newVal === total.value`
    // oldVal=0 → 跳过 auto-collapse, 列表保持可见 (历史消息设计意图)
    await wrapper.setProps({ steps: fixedSteps })
    await new Promise((r) => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
  })
})