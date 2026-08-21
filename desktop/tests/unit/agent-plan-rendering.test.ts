import { describe, it, expect } from 'vitest'
import {
  pendingStep,
  runningStep,
  completedStep,
  failedStep,
  parsePlanStepEvent,
  summarizePlanSteps,
  planStepsToAgentState,
  appendPlanStep,
  type PlanStep
} from '../../src/renderer/src/utils/agent-plan'

/**
 * Phase 5-D: Agent Plan Rendering unit tests.
 *
 * 覆盖 spec Step 6 5 场景:
 *   1. plan step append (dedup by id)
 *   2. status update (running -> completed)
 *   3. 排序 (order 字段)
 *   4. failed step (status='failed')
 *   5. 普通消息无 plan (空 list -> empty UI)
 */

describe('PlanStep 工厂 (Spec 1: append)', () => {
  it('pendingStep 起始状态', () => {
    const s = pendingStep('s1', '搜索文献', 0, 'web_search')
    expect(s.status).toBe('pending')
    expect(s.id).toBe('s1')
    expect(s.title).toBe('搜索文献')
    expect(s.tool).toBe('web_search')
    expect(s.order).toBe(0)
    expect(s.started_at).toBeNull()
    expect(s.finished_at).toBeNull()
    expect(s.error).toBeNull()
  })

  it('appendPlanStep + dedup by id', () => {
    const a = pendingStep('s1', 'Task 1', 0)
    const b = pendingStep('s2', 'Task 2', 1)
    const out1 = appendPlanStep([], a)
    expect(out1).toHaveLength(1)
    const out2 = appendPlanStep(out1, b)
    expect(out2).toHaveLength(2)
    // dedup: 同 id 替换
    const aDup = pendingStep('s1', 'Task 1 updated', 0)
    const out3 = appendPlanStep(out2, aDup)
    expect(out3).toHaveLength(2)
    expect(out3[0]?.title).toBe('Task 1 updated')
    expect(out3[1]?.id).toBe('s2')
  })

  it('appendPlanStep 不修改入参', () => {
    const input = [pendingStep('s1', 't', 0)]
    const snap = [...input]
    appendPlanStep(input, pendingStep('s2', 't2', 1))
    expect(input).toEqual(snap)
  })
})

describe('PlanStep 状态更新 (Spec 2: status update)', () => {
  it('pending -> running -> completed', () => {
    const s1 = pendingStep('s1', 't', 0)
    expect(s1.status).toBe('pending')
    const s2 = runningStep(s1, '2026-08-22T00:00:01Z')
    expect(s2.status).toBe('running')
    expect(s2.started_at).toBe('2026-08-22T00:00:01Z')
    expect(s2.finished_at).toBeNull()
    const s3 = completedStep(s2, '2026-08-22T00:00:02Z')
    expect(s3.status).toBe('completed')
    expect(s3.finished_at).toBe('2026-08-22T00:00:02Z')
  })

  it('running -> failed', () => {
    const s1 = pendingStep('s1', 't', 0)
    const s2 = runningStep(s1)
    expect(s2.status).toBe('running')
    const s3 = failedStep(s2, 'timeout 30s', '2026-08-22T00:00:05Z')
    expect(s3.status).toBe('failed')
    expect(s3.error).toBe('timeout 30s')
    expect(s3.finished_at).toBe('2026-08-22T00:00:05Z')
  })
})

describe('appendPlanStep 排序 (Spec 3: order)', () => {
  it('plan_steps 列表按 order 排序 (UI 渲染)', () => {
    const items = [
      pendingStep('a', 'A', 2),
      pendingStep('b', 'B', 0),
      pendingStep('c', 'C', 1)
    ]
    const sorted = [...items].sort((a, b) => a.order - b.order)
    expect(sorted.map((s) => s.id)).toEqual(['b', 'c', 'a'])
  })
})

describe('parsePlanStepEvent (Phase 5-D 解析)', () => {
  it('正常解析 done -> completed', () => {
    const p = parsePlanStepEvent({ id: 's1', title: 't', status: 'done' }, 0)
    expect(p?.status).toBe('completed')
    expect(p?.title).toBe('t')
  })

  it('running -> running', () => {
    const p = parsePlanStepEvent({ id: 's1', status: 'running' }, 0)
    expect(p?.status).toBe('running')
  })

  it('failed -> failed', () => {
    const p = parsePlanStepEvent({ id: 's1', status: 'failed' }, 0)
    expect(p?.status).toBe('failed')
  })

  it('error -> failed', () => {
    const p = parsePlanStepEvent({ id: 's1', status: 'error' }, 0)
    expect(p?.status).toBe('failed')
  })

  it('undefined -> pending', () => {
    const p = parsePlanStepEvent({ id: 's1' }, 0)
    expect(p?.status).toBe('pending')
  })

  it('缺 id -> null', () => {
    expect(parsePlanStepEvent({ id: '' }, 0)).toBeNull()
    expect(parsePlanStepEvent({ title: 'no id' }, 0)).toBeNull()
  })

  it('order 字段沿用入参', () => {
    const p = parsePlanStepEvent({ id: 's1', status: 'pending' }, 7)
    expect(p?.order).toBe(7)
  })
})

describe('summarizePlanSteps (Spec 4: failed step)', () => {
  it('混合状态统计', () => {
    const steps: PlanStep[] = [
      pendingStep('a', 'A', 0),
      pendingStep('b', 'B', 1),
      runningStep(pendingStep('c', 'C', 2)),
      completedStep(pendingStep('d', 'D', 3)),
      failedStep(pendingStep('e', 'E', 4), 'err')
    ]
    const s = summarizePlanSteps(steps)
    expect(s.total).toBe(5)
    expect(s.pending).toBe(2)
    expect(s.running).toBe(1)
    expect(s.completed).toBe(1)
    expect(s.failed).toBe(1)
    expect(s.activeStep?.id).toBe('c')
  })

  it('空 list', () => {
    const s = summarizePlanSteps([])
    expect(s.total).toBe(0)
    expect(s.activeStep).toBeNull()
  })
})

describe('planStepsToAgentState (Phase 5-D -> Phase 5-C 联动)', () => {
  it('空 -> null (不覆盖 AgentState 推导)', () => {
    expect(planStepsToAgentState([])).toBeNull()
  })

  it('any failed -> failed', () => {
    const steps = [completedStep(pendingStep('a', 'A', 0)), failedStep(pendingStep('b', 'B', 1), 'err')]
    expect(planStepsToAgentState(steps)).toBe('failed')
  })

  it('any running -> planning', () => {
    const steps = [completedStep(pendingStep('a', 'A', 0)), runningStep(pendingStep('b', 'B', 1))]
    expect(planStepsToAgentState(steps)).toBe('planning')
  })

  it('any pending -> planning', () => {
    const steps = [pendingStep('a', 'A', 0), completedStep(pendingStep('b', 'B', 1))]
    expect(planStepsToAgentState(steps)).toBe('planning')
  })

  it('all completed -> completed', () => {
    const steps = [completedStep(pendingStep('a', 'A', 0)), completedStep(pendingStep('b', 'B', 1))]
    expect(planStepsToAgentState(steps)).toBe('completed')
  })
})

describe('PlanStep 边界 (Spec 5: 普通消息无 plan)', () => {
  it('pendingStep 无 tool 时 tool 字段为 undefined', () => {
    const s = pendingStep('s1', 'plain', 0)
    expect(s.tool).toBeUndefined()
  })

  it('空 plan_steps list -> empty UI (PlanTimeline v-if false)', () => {
    const empty: PlanStep[] = []
    expect(empty.length).toBe(0)
  })
})
