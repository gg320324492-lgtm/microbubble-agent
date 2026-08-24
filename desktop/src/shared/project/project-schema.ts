// Project Schema — 科研项目契约。
export type ProjectStatus = 'planning' | 'active' | 'paused' | 'completed' | 'archived'
export const PROJECT_STATUSES: readonly ProjectStatus[] = Object.freeze(['planning', 'active', 'paused', 'completed', 'archived'])
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'blocked'
export const TASK_STATUSES: readonly TaskStatus[] = Object.freeze(['pending', 'running', 'completed', 'failed', 'blocked'])
export type MilestoneStatus = 'pending' | 'in-progress' | 'completed' | 'blocked'
export const MILESTONE_STATUSES: readonly MilestoneStatus[] = Object.freeze(['pending', 'in-progress', 'completed', 'blocked'])

export interface ResearchProject {
  id: string
  title: string
  description: string
  domain: string
  status: ProjectStatus
  createdAt: number
  updatedAt: number
  milestones: ResearchMilestone[]
  tasks: ProjectTask[]
  members: string[]
}

export interface ResearchMilestone {
  id: string
  projectId: string
  title: string
  description: string
  status: MilestoneStatus
  deadline: number
  deliverables: string[]
}

export interface ProjectTask {
  id: string
  milestoneId: string
  agentRole: string
  title: string
  input: string
  output: string
  status: TaskStatus
  dependencies: string[]
}

// ============ Validators ============

const VALID_PROJECT_STATUSES: ReadonlySet<ProjectStatus> = new Set(PROJECT_STATUSES)
const VALID_TASK_STATUSES: ReadonlySet<TaskStatus> = new Set(TASK_STATUSES)
const VALID_MILESTONE_STATUSES: ReadonlySet<MilestoneStatus> = new Set(MILESTONE_STATUSES)

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
  if (hit) throw new Error(`project schema leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-J2 strict)`)
}

function isValidTimestamp(v: unknown): v is number { return typeof v === 'number' && Number.isFinite(v) }

export function isValidProjectStatus(s: unknown): s is ProjectStatus { return typeof s === 'string' && VALID_PROJECT_STATUSES.has(s as ProjectStatus) }
export function isValidTaskStatus(s: unknown): s is TaskStatus { return typeof s === 'string' && VALID_TASK_STATUSES.has(s as TaskStatus) }
export function isValidMilestoneStatus(s: unknown): s is MilestoneStatus { return typeof s === 'string' && VALID_MILESTONE_STATUSES.has(s as MilestoneStatus) }

export function isValidResearchProject(p: unknown): p is ResearchProject {
  if (!isObject(p)) return false
  if (typeof p.id !== 'string' || p.id.length === 0) return false
  if (typeof p.title !== 'string' || p.title.length === 0) return false
  if (typeof p.description !== 'string') return false
  if (typeof p.domain !== 'string') return false
  if (!isValidProjectStatus(p.status)) return false
  if (!isValidTimestamp(p.createdAt)) return false
  if (!isValidTimestamp(p.updatedAt)) return false
  if (!Array.isArray(p.milestones)) return false
  if (!Array.isArray(p.tasks)) return false
  if (!Array.isArray(p.members)) return false
  if (!p.milestones.every(m => isValidResearchMilestone(m))) return false
  if (!p.tasks.every(t => isValidProjectTask(t))) return false
  assertNoSecret(p, 'ResearchProject')
  return true
}

export function isValidResearchMilestone(m: unknown): m is ResearchMilestone {
  if (!isObject(m)) return false
  if (typeof m.id !== 'string' || m.id.length === 0) return false
  if (typeof m.projectId !== 'string') return false
  if (typeof m.title !== 'string') return false
  if (typeof m.description !== 'string') return false
  if (!isValidMilestoneStatus(m.status)) return false
  if (!isValidTimestamp(m.deadline)) return false
  if (!Array.isArray(m.deliverables)) return false
  assertNoSecret(m, 'ResearchMilestone')
  return true
}

export function isValidProjectTask(t: unknown): t is ProjectTask {
  if (!isObject(t)) return false
  if (typeof t.id !== 'string' || t.id.length === 0) return false
  if (typeof t.milestoneId !== 'string') return false
  if (typeof t.agentRole !== 'string') return false
  if (typeof t.title !== 'string') return false
  if (typeof t.input !== 'string') return false
  if (typeof t.output !== 'string') return false
  if (!isValidTaskStatus(t.status)) return false
  if (!Array.isArray(t.dependencies)) return false
  assertNoSecret(t, 'ProjectTask')
  return true
}

export const __testHelpers = { PROJECT_STATUSES, TASK_STATUSES, MILESTONE_STATUSES, FORBIDDEN, findForbidden }
