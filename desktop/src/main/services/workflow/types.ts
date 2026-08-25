// Workflow Types — Phase 9-B
// 工作流编排共享契约: 模板 / 步骤 / 步骤处理器引用 / 运行 / 事件

export type WorkflowCategory = 'data-import' | 'analysis' | 'manuscript' | 'device' | 'mixed'

export type StepHandlerKind =
  | 'data:sample.list'
  | 'data:import.commit'
  | 'analysis:run.kinetic'
  | 'analysis:run.statistics'
  | 'manuscript:write'
  | 'device:command'
  | 'agent:tool.invoke'
  | 'delay'
  | 'human:approval'

export interface StepHandlerRef {
  kind: StepHandlerKind
  args: Record<string, unknown>
}

export interface WorkflowStep {
  id: string
  name: string
  handler: StepHandlerRef
  dependsOn: string[]
  requiresApproval: boolean
  timeoutMs: number
  /** 允许失败时继续 (默认 false: 任一失败终止 run) */
  continueOnError: boolean
}

export interface WorkflowTemplate {
  id: string
  name: string
  description: string
  category: WorkflowCategory
  steps: WorkflowStep[]
  createdBy: string | null
  builtIn: boolean
  /** schema 版本 (运行前校验; 旧模板不能在新 schema 跑) */
  schemaVersion: number
  createdAt: number
}

export type StepState = 'pending' | 'awaiting-approval' | 'running' | 'completed' | 'failed' | 'skipped'
export type RunStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'

export interface RunStepState {
  stepId: string
  state: StepState
  startedAt: number | null
  finishedAt: number | null
  result: unknown
  error: string | null
}

export interface WorkflowRun {
  id: string
  templateId: string
  templateName: string
  status: RunStatus
  currentStepId: string | null
  startedAt: number
  finishedAt: number | null
  startedBy: string | null
  parameters: Record<string, unknown>
  steps: RunStepState[]
  results: Record<string, unknown>
  auditTrail: RunEvent[]
}

export type RunEventType =
  | 'started'
  | 'step-started'
  | 'step-completed'
  | 'step-failed'
  | 'awaiting-approval'
  | 'approved'
  | 'cancelled'
  | 'completed'

export interface RunEvent {
  runId: string
  stepId: string | null
  type: RunEventType
  at: number
  message: string
  payload?: unknown
}

export interface WorkflowService {
  listTemplates(): WorkflowTemplate[]
  startRun(input: { templateId: string; parameters: Record<string, unknown>; startedBy?: string }): Promise<WorkflowRun>
  getRun(runId: string): WorkflowRun | null
  listRuns(limit?: number): WorkflowRun[]
  cancelRun(runId: string): boolean
  approveStep(runId: string, stepId: string, approvedBy: string): boolean
  /** 注册内置模板 (启动时调用) */
  registerBuiltInTemplates(templates: WorkflowTemplate[]): void
}
