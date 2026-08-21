// Agent Plan Model (Phase 5-D: Planning Renderer Foundation).
//
// 纯 TypeScript, 0 依赖. 不修改 Phase 3-B0 frozen schema / Chat API / SSE.
// 仅消费 SSE event 'plan_step' (Phase 3-B0 frozen StreamEventType union).
//
// Phase 5-D 范围:
//   - PlanStep 类型 (id / title / status / order / tool 留口 / 起止时间)
//   - 状态: pending / running / completed / failed (Phase 5-D frozen)
//   - 工厂 + 推导 (running plan step -> AgentState.planning)
//
// 不在范围:
//   - 真实 plan 生成 (Agent backend)
//   - Tool execution
//   - Permission / Approval 自动拒绝
//   - 改 SSE schema

import type { AgentState } from './agent-state'

// ============ PlanStep 类型 ============

export type PlanStepStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface PlanStep {
  /** 唯一 id (SSE event.step.id 或后端描述) */
  id: string
  /** 显示标题 */
  title: string
  /** 状态 (Phase 5-D frozen) */
  status: PlanStepStatus
  /** 顺序 (Phase 5-D 简化: 数组索引) */
  order: number
  /** Phase 5-D 留口: SSE event.step.tool (后端 emit, 后续接) */
  tool?: string
  /** 起止时间 (Phase 5-D 简化: ISO 字符串, 留口) */
  started_at?: string | null
  finished_at?: string | null
  /** Phase 5-D 留口: 错误详情 */
  error?: string | null
}

// ============ PlanStep 工厂 (Phase 5-D API) ============

export function pendingStep(id: string, title: string, order: number, tool?: string): PlanStep {
  return {
    id, title, status: 'pending', order,
    tool,
    started_at: null, finished_at: null,
    error: null
  }
}

export function runningStep(prev: PlanStep, started_at?: string): PlanStep {
  return {
    ...prev,
    status: 'running',
    started_at: started_at ?? new Date().toISOString(),
    finished_at: null
  }
}

export function completedStep(prev: PlanStep, finished_at?: string): PlanStep {
  return {
    ...prev,
    status: 'completed',
    finished_at: finished_at ?? new Date().toISOString()
  }
}

export function failedStep(prev: PlanStep, error: string, finished_at?: string): PlanStep {
  return {
    ...prev,
    status: 'failed',
    error,
    finished_at: finished_at ?? new Date().toISOString()
  }
}

// ============ Parser (Phase 5-D: SSE event payload -> PlanStep) ============

export interface ParsePlanStepInput {
  /** 后端 event.step.id (Phase 5-D main 推断) */
  id: string
  /** 后端 event.step.title 或 description */
  title?: string
  /** 后端 event.step.tool (Phase 5-D 留口) */
  tool?: string
  /** 后端 event.step.status (Phase 5-D: 'pending' / 'running' / 'done' / 'failed' 等) */
  status?: string
}

/**
 * 解析后端 SSE event 'plan_step' 到 PlanStep.
 *
 * 后端 schema (Phase 3-B0 frozen):
 *   { step: { id, title, tool, status: pending|running|done|failed } }
 *
 * Status 映射:
 *   'pending'   -> 'pending'
 *   'running'   -> 'running'
 *   'done' / 'completed' -> 'completed'
 *   'failed' / 'error'   -> 'failed'
 *   其它 / undefined -> 'pending' (Phase 5-D: 默认等待)
 *
 * 缺 id 时返回 null (Phase 5-D: 跳过非法 entry).
 */
export function parsePlanStepEvent(input: ParsePlanStepInput, order: number): PlanStep | null {
  if (!input.id || typeof input.id !== 'string' || input.id.length === 0) return null
  const s = input.status
  let status: PlanStepStatus = 'pending'
  if (s === 'running') status = 'running'
  else if (s === 'done' || s === 'completed') status = 'completed'
  else if (s === 'failed' || s === 'error') status = 'failed'
  return {
    id: input.id,
    title: input.title ?? input.id,
    status,
    order,
    tool: input.tool,
    started_at: status === 'running' ? new Date().toISOString() : null,
    finished_at: status === 'completed' || status === 'failed' ? new Date().toISOString() : null,
    error: status === 'failed' ? s ?? null : null
  }
}

// ============ PlanStep 摘要 (Phase 5-D: 与 AgentState 联动) ============

export interface PlanStepSummary {
  total: number
  pending: number
  running: number
  completed: number
  failed: number
  /** 当前正在 running 的 step (Phase 5-D: 单步假设) */
  activeStep: PlanStep | null
}

/**
 * PlanStep 列表推导 AgentState (Phase 5-D).
 * 用于: chat store agentStateHint 联动 (running plan step -> 'planning').
 */
export function summarizePlanSteps(steps: ReadonlyArray<PlanStep>): PlanStepSummary {
  const summary: PlanStepSummary = {
    total: steps.length,
    pending: 0,
    running: 0,
    completed: 0,
    failed: 0,
    activeStep: null
  }
  for (const s of steps) {
    if (s.status === 'pending') summary.pending++
    else if (s.status === 'running') {
      summary.running++
      if (!summary.activeStep) summary.activeStep = s
    } else if (s.status === 'completed') summary.completed++
    else if (s.status === 'failed') summary.failed++
  }
  return summary
}

/**
 * PlanStep 列表 -> AgentState 推导 (Phase 5-D).
 * 规则:
 *   - 任何 step status='failed' -> 'failed'
 *   - 任何 step status='running' 或 pending 中有非空 -> 'planning'
 *   - 全部 completed -> 'completed'
 *   - 空 -> 不影响 (返回 null, 调用方用现有 deriveAgentState)
 */
export function planStepsToAgentState(steps: ReadonlyArray<PlanStep>): AgentState | null {
  if (steps.length === 0) return null
  if (steps.some((s) => s.status === 'failed')) return 'failed'
  if (steps.some((s) => s.status === 'running' || s.status === 'pending')) return 'planning'
  if (steps.every((s) => s.status === 'completed')) return 'completed'
  return null
}

// ============ PlanStep 列表推导 (Phase 5-D 同 store.changes) ============

/**
 * Append 一个 PlanStep 到 list, 按 id dedup (existing 替换).
 * 不修改入参 (纯函数).
 */
export function appendPlanStep(steps: ReadonlyArray<PlanStep>, next: PlanStep): PlanStep[] {
  const idx = steps.findIndex((s) => s.id === next.id)
  if (idx >= 0) {
    const result = [...steps]
    result[idx] = next
    return result
  }
  return [...steps, next]
}
