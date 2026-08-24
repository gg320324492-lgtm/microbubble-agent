// Workflow Schema — 科研工作流契约。


export type StepType = 'literature' | 'experiment' | 'analysis' | 'modeling' | 'writing' | 'review'
export const STEP_TYPES: readonly StepType[] = Object.freeze(['literature', 'experiment', 'analysis', 'modeling', 'writing', 'review'])

export type WorkflowStatus = 'draft' | 'running' | 'paused' | 'completed' | 'failed'
export const WORKFLOW_STATUSES: readonly WorkflowStatus[] = Object.freeze(['draft', 'running', 'paused', 'completed', 'failed'])

export interface WorkflowStep {
  id: string
  type: StepType
  agent: string
  condition?: string
  nextSteps: string[]
}

export interface ScientificWorkflow {
  id: string
  name: string
  steps: WorkflowStep[]
  trigger: string
  status: WorkflowStatus
}

// ============ Validators ============

const VALID_STEP_TYPES: ReadonlySet<StepType> = new Set(STEP_TYPES)
const VALID_WORKFLOW_STATUSES: ReadonlySet<WorkflowStatus> = new Set(WORKFLOW_STATUSES)

function isObject(v: unknown): v is Record<string, unknown> { return typeof v === 'object' && v !== null && !Array.isArray(v) }

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization', 'providerId', 'modelId']

function findForbidden(value: unknown): string | null {
  if (typeof value === 'string') { for (const bad of FORBIDDEN) if (value.includes(bad)) return bad; return null }
  if (Array.isArray(value)) { for (const v of value) { const r = findForbidden(v); if (r) return r } return null }
  if (value && typeof value === 'object') { for (const v of Object.values(value as Record<string, unknown>)) { const r = findForbidden(v); if (r) return r } }
  return null
}

function assertNoSecret(value: unknown, ctx: string): void {
  const hit = findForbidden(value)
  if (hit) throw new Error(`workflow schema leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-J2 strict)`)
}

export function isValidStepType(s: unknown): s is StepType { return typeof s === 'string' && VALID_STEP_TYPES.has(s as StepType) }
export function isValidWorkflowStatus(s: unknown): s is WorkflowStatus { return typeof s === 'string' && VALID_WORKFLOW_STATUSES.has(s as WorkflowStatus) }

export function isValidWorkflowStep(s: unknown): s is WorkflowStep {
  if (!isObject(s)) return false
  if (typeof s.id !== 'string' || s.id.length === 0) return false
  if (!isValidStepType(s.type)) return false
  if (typeof s.agent !== 'string') return false
  if (s.condition !== undefined && typeof s.condition !== 'string') return false
  if (!Array.isArray(s.nextSteps)) return false
  assertNoSecret(s, 'WorkflowStep')
  return true
}

export function isValidScientificWorkflow(w: unknown): w is ScientificWorkflow {
  if (!isObject(w)) return false
  if (typeof w.id !== 'string' || w.id.length === 0) return false
  if (typeof w.name !== 'string') return false
  if (!Array.isArray(w.steps)) return false
  if (typeof w.trigger !== 'string') return false
  if (!isValidWorkflowStatus(w.status)) return false
  if (!w.steps.every(s => isValidWorkflowStep(s))) return false
  assertNoSecret(w, 'ScientificWorkflow')
  return true
}

export const __testHelpers = { STEP_TYPES, WORKFLOW_STATUSES, VALID_STEP_TYPES, VALID_WORKFLOW_STATUSES, FORBIDDEN, findForbidden }
