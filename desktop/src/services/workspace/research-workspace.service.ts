// Research Workspace Service — 统一工作区服务。

import type {
  ResearchWorkspace, WorkspaceModule, ProjectOverview, ResearchProgress,
  WorkspaceActivity, WorkspaceSummary, ModuleStatus
} from '../../shared/workspace/research-workspace-schema'

export interface ModuleDefinition {
  id: string
  name: string
  category: string
  description: string
}

export const DEFAULT_MODULES: readonly ModuleDefinition[] = Object.freeze([
  Object.freeze({ id: 'agent', name: '科研智能体', category: 'AI', description: '统一科研智能体' }),
  Object.freeze({ id: 'knowledge', name: '知识库', category: 'Data', description: 'RAG + 实体图谱检索' }),
  Object.freeze({ id: 'multi-agent', name: '多智能体协作', category: 'AI', description: '6 个专业智能体协同' }),
  Object.freeze({ id: 'experiment', name: '实验闭环', category: 'Lab', description: '实验生命周期管理' }),
  Object.freeze({ id: 'twin', name: '数字孪生', category: 'Model', description: '线性/多项式/动力学预测' }),
  Object.freeze({ id: 'device', name: '设备集成', category: 'IoT', description: '实时设备数据流' }),
  Object.freeze({ id: 'control', name: '控制中心', category: 'Ops', description: '统一实验控制中心' }),
  Object.freeze({ id: 'manuscript', name: '论文生成', category: 'Output', description: 'AI 论文生成' })
] as ModuleDefinition[])

export interface WorkspaceLoadInput {
  projectId: string
  title: string
  domain: string
  description?: string
  status?: string
  members?: number
  tasks?: { total: number; completed: number }
  experiments?: { total: number; completed: number }
  manuscripts?: { total: number; published: number }
  knowledge?: { total: number; indexed: number }
  moduleStatuses?: Record<string, ModuleStatus>
  activities?: Omit<WorkspaceActivity, 'id' | 'timestamp'>[]
}

export class ResearchWorkspaceService {
  private workspaces: Map<string, ResearchWorkspace> = new Map()
  private activitiesRetention: number

  constructor(activitiesRetention = 50) {
    this.activitiesRetention = activitiesRetention
  }

  loadWorkspace(input: WorkspaceLoadInput): ResearchWorkspace {
    const now = Date.now()
    const id = `ws-${now}-${Math.floor(Math.random() * 1e6)}`
    const tasks = input.tasks ?? { total: 0, completed: 0 }
    const experiments = input.experiments ?? { total: 0, completed: 0 }
    const manuscripts = input.manuscripts ?? { total: 0, published: 0 }
    const knowledge = input.knowledge ?? { total: 0, indexed: 0 }

    const modules: WorkspaceModule[] = DEFAULT_MODULES.map((m) => ({
      id: m.id,
      name: m.name,
      category: m.category,
      status: input.moduleStatuses?.[m.id] ?? 'ready',
      description: m.description,
      enabled: input.moduleStatuses?.[m.id] !== 'disabled'
    }))

    const totalDone = tasks.completed + experiments.completed + manuscripts.published
    const total = tasks.total + experiments.total + manuscripts.total
    const percent = total > 0 ? Math.round((totalDone / total) * 100) : 0

    const progress: ResearchProgress = {
      totalTasks: tasks.total,
      completedTasks: tasks.completed,
      totalExperiments: experiments.total,
      completedExperiments: experiments.completed,
      totalManuscripts: manuscripts.total,
      publishedManuscripts: manuscripts.published,
      totalKnowledge: knowledge.total,
      indexedKnowledge: knowledge.indexed,
      percent
    }

    const activities: WorkspaceActivity[] = (input.activities ?? []).map((a, i) => ({
      ...a,
      id: `act-${id}-${i}`,
      timestamp: now - i * 1000
    }))

    const activeModules = modules.filter((m) => m.enabled && (m.status === 'ready' || m.status === 'running')).length
    const summary: WorkspaceSummary = {
      projectId: input.projectId,
      totalModules: modules.length,
      activeModules,
      recentActivities: activities.length,
      healthScore: percent,
      generatedAt: now
    }

    const overview: ProjectOverview = {
      projectId: input.projectId,
      title: input.title,
      domain: input.domain,
      description: input.description ?? '',
      status: input.status ?? 'active',
      createdAt: now,
      updatedAt: now,
      memberCount: input.members ?? 0,
      taskCount: tasks.total
    }

    const ws: ResearchWorkspace = {
      id,
      projectId: input.projectId,
      title: input.title,
      overview,
      modules,
      progress,
      activities,
      summary,
      createdAt: now,
      updatedAt: now
    }
    this.workspaces.set(id, ws)
    return this.cloneWorkspace(ws)
  }

  getWorkspace(id: string): ResearchWorkspace | null {
    const w = this.workspaces.get(id)
    return w ? this.cloneWorkspace(w) : null
  }

  getProjectSummary(projectId: string): WorkspaceSummary | null {
    for (const w of this.workspaces.values()) {
      if (w.projectId === projectId) return { ...w.summary, projectId: w.projectId }
    }
    return null
  }

  getModuleStatus(workspaceId: string, moduleId: string): WorkspaceModule | null {
    const w = this.workspaces.get(workspaceId)
    if (!w) return null
    const m = w.modules.find((m) => m.id === moduleId)
    return m ? { ...m } : null
  }

  getRecentActivities(workspaceId: string, limit = 10): WorkspaceActivity[] {
    const w = this.workspaces.get(workspaceId)
    if (!w) return []
    const sorted = [...w.activities].sort((a, b) => b.timestamp - a.timestamp)
    return sorted.slice(0, limit)
  }

  appendActivity(workspaceId: string, activity: Omit<WorkspaceActivity, 'id' | 'timestamp'>): ResearchWorkspace | null {
    const w = this.workspaces.get(workspaceId)
    if (!w) return null
    const entry: WorkspaceActivity = {
      ...activity,
      id: `act-${Date.now()}-${Math.floor(Math.random() * 1e6)}`,
      timestamp: Date.now()
    }
    w.activities.push(entry)
    if (w.activities.length > this.activitiesRetention) {
      w.activities.splice(0, w.activities.length - this.activitiesRetention)
    }
    w.updatedAt = Date.now()
    w.summary.recentActivities = w.activities.length
    return this.cloneWorkspace(w)
  }

  size(): number { return this.workspaces.size }
  clear(): void { this.workspaces.clear() }

  private cloneWorkspace(w: ResearchWorkspace): ResearchWorkspace {
    return {
      ...w,
      overview: { ...w.overview },
      modules: w.modules.map((m) => ({ ...m })),
      progress: { ...w.progress },
      activities: w.activities.map((a) => ({ ...a })),
      summary: { ...w.summary }
    }
  }
}