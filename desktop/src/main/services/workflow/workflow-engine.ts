// Workflow Engine — Phase 9-B
// 状态机: 拓扑排序 → 顺序执行 → 失败重试 / 审批暂停 / 继续.

import type { DatabaseService } from '../database.service'
import { getStepHandler, type StepHandlerContext, type StepHandlerResult } from './step-handlers'
import type {
  RunEvent,
  RunEventType,
  RunStepState,
  StepState,
  WorkflowRun,
  WorkflowService,
  WorkflowStep,
  WorkflowTemplate
} from './types'
import { BUILTIN_TEMPLATES, getTemplate, listTemplates, registerBuiltInTemplates as register } from './workflow-registry'

const DEFAULT_TIMEOUT_MS = 60000
const MAX_RUN_HISTORY = 100

class WorkflowServiceImpl implements WorkflowService {
  private runs = new Map<string, WorkflowRun>()
  private runHistory: string[] = []
  private currentCtx: StepHandlerContext

  constructor(getService: () => DatabaseService | null) {
    this.currentCtx = { db: getService }
    register(BUILTIN_TEMPLATES)
  }

  listTemplates(): WorkflowTemplate[] { return listTemplates() }

  startRun(input: { templateId: string; parameters: Record<string, unknown>; startedBy?: string }): Promise<WorkflowRun> {
    const tpl = getTemplate(input.templateId)
    if (!tpl) throw new Error(`未知工作流模板 '${input.templateId}'`)
    if (hasCycle(tpl.steps)) throw new Error(`模板 '${input.templateId}' 步骤依赖存在环`)
    const order = topologicalSort(tpl.steps)
    const now = Date.now()
    const run: WorkflowRun = {
      id: `run-${now}-${Math.random().toString(36).slice(2, 6)}`,
      templateId: tpl.id,
      templateName: tpl.name,
      status: 'running',
      currentStepId: order[0] ?? null,
      startedAt: now,
      finishedAt: null,
      startedBy: input.startedBy ?? null,
      parameters: input.parameters,
      steps: order.map((stepId) => ({
        stepId: stepId ?? '', state: 'pending' as StepState,
        startedAt: null, finishedAt: null, result: null, error: null
      })),
      results: {},
      auditTrail: []
    }
    this.runs.set(run.id, run)
    this.runHistory.push(run.id)
    if (this.runHistory.length > MAX_RUN_HISTORY) {
      const old = this.runHistory.shift()
      if (old) this.runs.delete(old)
    }
    this.emit(run.id, null, 'started', `运行 ${tpl.name} 已启动`)
    void this.executeRun(run, order, tpl)
    return Promise.resolve(run)
  }

  private async executeRun(run: WorkflowRun, order: string[], tpl: WorkflowTemplate): Promise<void> {
    for (const stepId of order) {
      const step = tpl.steps.find((s) => s.id === stepId)
      if (!step) continue
      const stepState = run.steps.find((s) => s.stepId === stepId)
      if (!stepState) continue
      const depStates = step.dependsOn.map((d) => run.steps.find((s) => s.stepId === d)?.state)
      if (depStates.some((s) => s === 'failed')) {
        stepState.state = 'skipped'
        this.emit(run.id, stepId, 'step-failed', '依赖步骤失败, 跳过')
        continue
      }
      if (step.requiresApproval) {
        stepState.state = 'awaiting-approval'
        this.emit(run.id, stepId, 'awaiting-approval', `等待审批: ${step.name}`)
        return
      }
      await this.runOneStep(run, step, stepState)
      if (stepState.state === 'failed' && !step.continueOnError) {
        run.status = 'failed'
        run.finishedAt = Date.now()
        run.currentStepId = null
        this.emit(run.id, null, 'step-failed', `运行失败于步骤 ${step.name}`)
        return
      }
    }
    run.status = 'completed'
    run.finishedAt = Date.now()
    run.currentStepId = null
    this.emit(run.id, null, 'completed', '运行完成')
  }

  private async runOneStep(run: WorkflowRun, step: WorkflowStep, stepState: RunStepState): Promise<void> {
    stepState.state = 'running'
    stepState.startedAt = Date.now()
    this.emit(run.id, step.id, 'step-started', `开始 ${step.name}`)
    const handler = getStepHandler(step.handler.kind)
    if (!handler) {
      stepState.state = 'failed'
      stepState.error = `未知 handler '${step.handler.kind}'`
      stepState.finishedAt = Date.now()
      this.emit(run.id, step.id, 'step-failed', stepState.error)
      return
    }
    try {
      const timeoutMs = step.timeoutMs || DEFAULT_TIMEOUT_MS
      const args = this.interpolateArgs(step.handler.args, run.parameters, run.results)
      const result = await Promise.race([
        handler(args, this.currentCtx),
        new Promise<StepHandlerResult>((_, reject) => setTimeout(() => reject(new Error(`步骤超时 (>${timeoutMs}ms)`)), timeoutMs))
      ])
      if (result.ok) {
        stepState.state = 'completed'
        stepState.result = result.data
        stepState.finishedAt = Date.now()
        run.results[step.id] = result.data
        this.emit(run.id, step.id, 'step-completed', `${step.name} 完成`)
      } else if (result.error !== 'HUMAN_APPROVAL_PENDING') {
        stepState.state = 'failed'
        stepState.error = result.error
        stepState.finishedAt = Date.now()
        this.emit(run.id, step.id, 'step-failed', result.error)
      }
    } catch (err) {
      stepState.state = 'failed'
      stepState.error = err instanceof Error ? err.message : String(err)
      stepState.finishedAt = Date.now()
      this.emit(run.id, step.id, 'step-failed', stepState.error)
    }
  }

  private interpolateArgs(args: Record<string, unknown>, params: Record<string, unknown>, results: Record<string, unknown>): Record<string, unknown> {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(args)) {
      if (typeof v === 'string' && v.startsWith('${')) {
        const path = v.slice(2, -1)
        out[k] = resolvePath(path, params, results) ?? v
      } else {
        out[k] = v
      }
    }
    return out
  }

  getRun(runId: string): WorkflowRun | null {
    return this.runs.get(runId) ?? null
  }

  listRuns(limit: number = 50): WorkflowRun[] {
    const ids = [...this.runHistory].reverse().slice(0, limit)
    return ids.map((id) => this.runs.get(id)).filter((r): r is WorkflowRun => !!r)
  }

  cancelRun(runId: string): boolean {
    const run = this.runs.get(runId)
    if (!run || run.status !== 'running') return false
    run.status = 'cancelled'
    run.finishedAt = Date.now()
    this.emit(runId, null, 'cancelled', '运行被取消')
    return true
  }

  approveStep(runId: string, stepId: string, approvedBy: string): boolean {
    const run = this.runs.get(runId)
    if (!run) return false
    const tpl = getTemplate(run.templateId)
    if (!tpl) return false
    const stepState = run.steps.find((s) => s.stepId === stepId)
    if (!stepState || stepState.state !== 'awaiting-approval') return false
    this.emit(runId, stepId, 'approved', `审批通过: ${approvedBy}`)
    const order = topologicalSort(tpl.steps)
    const idx = order.indexOf(stepId)
    void this.executeRun(run, order.slice(idx + 1), tpl)
    return true
  }

  registerBuiltInTemplates(templates: WorkflowTemplate[]): void { register(templates) }

  private emit(runId: string, stepId: string | null, type: RunEventType, message: string): void {
    const run = this.runs.get(runId)
    if (!run) return
    const event: RunEvent = { runId, stepId, type, at: Date.now(), message }
    run.auditTrail.push(event)
  }
}

function resolvePath(path: string, params: Record<string, unknown>, results: Record<string, unknown>): unknown {
  if (path.startsWith('params.')) return params[path.slice(7)]
  if (path.startsWith('results.')) {
    const rest = path.slice(8)
    const parts = rest.split('.')
    let cur: unknown = results[parts[0]!]
    for (let i = 1; i < parts.length; i++) {
      if (cur && typeof cur === 'object') cur = (cur as Record<string, unknown>)[parts[i]!]
      else return undefined
    }
    return cur
  }
  return params[path]
}

function topologicalSort(steps: WorkflowStep[]): string[] {
  const map = new Map<string, WorkflowStep>(steps.map((s) => [s.id, s]))
  const visited = new Set<string>()
  const result: string[] = []
  function dfs(id: string, stack: Set<string>): void {
    if (visited.has(id)) return
    if (stack.has(id)) throw new Error(`循环依赖: ${id}`)
    stack.add(id)
    const step = map.get(id)
    if (step) for (const d of step.dependsOn) dfs(d, stack)
    stack.delete(id)
    visited.add(id)
    result.push(id)
  }
  for (const s of steps) dfs(s.id, new Set())
  return result
}

function hasCycle(steps: WorkflowStep[]): boolean {
  try { topologicalSort(steps); return false } catch { return true }
}

let serviceInstance: WorkflowService | null = null

export function bootstrapWorkflowService(getService: () => DatabaseService | null): WorkflowService {
  if (serviceInstance) return serviceInstance
  serviceInstance = new WorkflowServiceImpl(getService)
  return serviceInstance
}

export function getWorkflowService(): WorkflowService | null {
  return serviceInstance
}

export function resetWorkflowService(): void {
  serviceInstance = null
}
