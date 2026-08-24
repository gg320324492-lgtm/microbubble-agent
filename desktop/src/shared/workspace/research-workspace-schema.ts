// Research Workspace Schema — 统一科研工作区契约。

// ============ Enums ============

export type ModuleStatus = 'ready' | 'running' | 'paused' | 'completed' | 'failed' | 'disabled'
export const MODULE_STATUSES: readonly ModuleStatus[] = Object.freeze([
  'ready', 'running', 'paused', 'completed', 'failed', 'disabled'
])

export type ActivityKind = 'agent' | 'experiment' | 'manuscript' | 'device' | 'twin' | 'knowledge' | 'system'
export const ACTIVITY_KINDS: readonly ActivityKind[] = Object.freeze([
  'agent', 'experiment', 'manuscript', 'device', 'twin', 'knowledge', 'system'
])

// ============ Core types ============

export interface WorkspaceModule {
  id: string
  name: string
  category: string
  status: ModuleStatus
  description: string
  enabled: boolean
}

export interface ProjectOverview {
  projectId: string
  title: string
  domain: string
  description: string
  status: string
  createdAt: number
  updatedAt: number
  memberCount: number
  taskCount: number
}

export interface ResearchProgress {
  totalTasks: number
  completedTasks: number
  totalExperiments: number
  completedExperiments: number
  totalManuscripts: number
  publishedManuscripts: number
  totalKnowledge: number
  indexedKnowledge: number
  percent: number
}

export interface WorkspaceActivity {
  id: string
  kind: ActivityKind
  title: string
  description: string
  timestamp: number
  actor: string
}

export interface WorkspaceSummary {
  projectId: string
  totalModules: number
  activeModules: number
  recentActivities: number
  healthScore: number
  generatedAt: number
}

export interface ResearchWorkspace {
  id: string
  projectId: string
  title: string
  overview: ProjectOverview
  modules: WorkspaceModule[]
  progress: ResearchProgress
  activities: WorkspaceActivity[]
  summary: WorkspaceSummary
  createdAt: number
  updatedAt: number
}

// ============ Validators ============

const VALID_MODULE_STATUSES: ReadonlySet<ModuleStatus> = new Set(MODULE_STATUSES)
const VALID_ACTIVITY_KINDS: ReadonlySet<ActivityKind> = new Set(ACTIVITY_KINDS)

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization', 'providerId', 'modelId']

function findForbidden(value: unknown): string | null {
  if (typeof value === 'string') {
    for (const bad of FORBIDDEN) if (value.includes(bad)) return bad
    return null
  }
  if (Array.isArray(value)) {
    for (const v of value) { const r = findForbidden(v); if (r) return r }
    return null
  }
  if (value && typeof value === 'object') {
    for (const v of Object.values(value as Record<string, unknown>)) {
      const r = findForbidden(v); if (r) return r
    }
  }
  return null
}

function assertNoSecret(value: unknown, ctx: string): void {
  const hit = findForbidden(value)
  if (hit) throw new Error(`workspace schema leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-L0 strict)`)
}

function isValidTimestamp(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

function isValidNonNegInt(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0
}

export function isValidModuleStatus(s: unknown): s is ModuleStatus {
  return typeof s === 'string' && VALID_MODULE_STATUSES.has(s as ModuleStatus)
}

export function isValidActivityKind(k: unknown): k is ActivityKind {
  return typeof k === 'string' && VALID_ACTIVITY_KINDS.has(k as ActivityKind)
}

export function isValidWorkspaceModule(m: unknown): m is WorkspaceModule {
  if (!isObject(m)) return false
  if (typeof m.id !== 'string' || m.id.length === 0) return false
  if (typeof m.name !== 'string') return false
  if (typeof m.category !== 'string') return false
  if (!isValidModuleStatus(m.status)) return false
  if (typeof m.description !== 'string') return false
  if (typeof m.enabled !== 'boolean') return false
  assertNoSecret(m, 'WorkspaceModule')
  return true
}

export function isValidProjectOverview(o: unknown): o is ProjectOverview {
  if (!isObject(o)) return false
  if (typeof o.projectId !== 'string' || o.projectId.length === 0) return false
  if (typeof o.title !== 'string') return false
  if (typeof o.domain !== 'string') return false
  if (typeof o.description !== 'string') return false
  if (typeof o.status !== 'string') return false
  if (!isValidTimestamp(o.createdAt)) return false
  if (!isValidTimestamp(o.updatedAt)) return false
  if (!isValidNonNegInt(o.memberCount)) return false
  if (!isValidNonNegInt(o.taskCount)) return false
  assertNoSecret(o, 'ProjectOverview')
  return true
}

export function isValidResearchProgress(p: unknown): p is ResearchProgress {
  if (!isObject(p)) return false
  if (!isValidNonNegInt(p.totalTasks)) return false
  if (!isValidNonNegInt(p.completedTasks)) return false
  if (!isValidNonNegInt(p.totalExperiments)) return false
  if (!isValidNonNegInt(p.completedExperiments)) return false
  if (!isValidNonNegInt(p.totalManuscripts)) return false
  if (!isValidNonNegInt(p.publishedManuscripts)) return false
  if (!isValidNonNegInt(p.totalKnowledge)) return false
  if (!isValidNonNegInt(p.indexedKnowledge)) return false
  if (!isValidNonNegInt(p.percent)) return false
  assertNoSecret(p, 'ResearchProgress')
  return true
}

export function isValidWorkspaceActivity(a: unknown): a is WorkspaceActivity {
  if (!isObject(a)) return false
  if (typeof a.id !== 'string' || a.id.length === 0) return false
  if (!isValidActivityKind(a.kind)) return false
  if (typeof a.title !== 'string') return false
  if (typeof a.description !== 'string') return false
  if (!isValidTimestamp(a.timestamp)) return false
  if (typeof a.actor !== 'string') return false
  assertNoSecret(a, 'WorkspaceActivity')
  return true
}

export function isValidWorkspaceSummary(s: unknown): s is WorkspaceSummary {
  if (!isObject(s)) return false
  if (typeof s.projectId !== 'string') return false
  if (!isValidNonNegInt(s.totalModules)) return false
  if (!isValidNonNegInt(s.activeModules)) return false
  if (!isValidNonNegInt(s.recentActivities)) return false
  if (!isValidNonNegInt(s.healthScore)) return false
  if (!isValidTimestamp(s.generatedAt)) return false
  assertNoSecret(s, 'WorkspaceSummary')
  return true
}

export function isValidResearchWorkspace(w: unknown): w is ResearchWorkspace {
  if (!isObject(w)) return false
  if (typeof w.id !== 'string' || w.id.length === 0) return false
  if (typeof w.projectId !== 'string') return false
  if (typeof w.title !== 'string') return false
  if (!isValidProjectOverview(w.overview)) return false
  if (!Array.isArray(w.modules)) return false
  if (!w.modules.every((m) => isValidWorkspaceModule(m))) return false
  if (!isValidResearchProgress(w.progress)) return false
  if (!Array.isArray(w.activities)) return false
  if (!w.activities.every((a) => isValidWorkspaceActivity(a))) return false
  if (!isValidWorkspaceSummary(w.summary)) return false
  if (!isValidTimestamp(w.createdAt)) return false
  if (!isValidTimestamp(w.updatedAt)) return false
  assertNoSecret(w, 'ResearchWorkspace')
  return true
}

export const __testHelpers = {
  MODULE_STATUSES, ACTIVITY_KINDS,
  VALID_MODULE_STATUSES, VALID_ACTIVITY_KINDS,
  FORBIDDEN, findForbidden
}