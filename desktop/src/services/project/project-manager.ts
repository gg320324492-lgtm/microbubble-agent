// Project Manager — 科研项目管理器（确定性 + 防御性拷贝）。
import type {
  ResearchProject, ResearchMilestone, ProjectTask,
  ProjectStatus, TaskStatus, MilestoneStatus
} from '../../shared/project/project-schema'

export class ProjectManager {
  private projects: Map<string, ResearchProject> = new Map()
  private nextId = 0

  createProject(input: { title: string; description: string; domain: string; members?: string[] }): ResearchProject {
    this.nextId++
    const now = Date.now()
    const id = `proj-${this.nextId}-${now}`
    const project: ResearchProject = {
      id, title: input.title, description: input.description, domain: input.domain,
      status: 'planning', createdAt: now, updatedAt: now,
      milestones: [], tasks: [], members: input.members ?? []
    }
    this.projects.set(id, this.cloneProject(project))
    return this.cloneProject(project)
  }

  getProject(id: string): ResearchProject | null {
    const p = this.projects.get(id)
    return p ? this.cloneProject(p) : null
  }

  updateProject(id: string, patch: Partial<{ title: string; description: string; status: ProjectStatus; domain: string }>): ResearchProject | null {
    const p = this.projects.get(id)
    if (!p) return null
    const updated: ResearchProject = {
      ...p, ...patch, updatedAt: Date.now()
    }
    this.projects.set(id, this.cloneProject(updated))
    return this.cloneProject(updated)
  }

  listProjects(): ResearchProject[] {
    const result: ResearchProject[] = []
    const ids = Array.from(this.projects.keys()).sort()
    for (const id of ids) result.push(this.cloneProject(this.projects.get(id)!))
    return result
  }

  addMilestone(projectId: string, input: { title: string; description: string; deadline: number; deliverables?: string[] }): ResearchMilestone | null {
    const p = this.projects.get(projectId)
    if (!p) return null
    this.nextId++
    const id = `mile-${this.nextId}`
    const milestone: ResearchMilestone = {
      id, projectId, title: input.title, description: input.description,
      status: 'pending', deadline: input.deadline, deliverables: input.deliverables ?? []
    }
    p.milestones.push(milestone)
    p.updatedAt = Date.now()
    this.projects.set(projectId, this.cloneProject(p))
    return this.cloneMilestone(milestone)
  }

  addTask(input: { milestoneId: string; agentRole: string; title: string; input: string; dependencies?: string[] }): ProjectTask | null {
    for (const [id, p] of this.projects) {
      if (p.milestones.some(m => m.id === input.milestoneId)) {
        this.nextId++
        const taskId = `task-${this.nextId}`
        const task: ProjectTask = {
          id: taskId, milestoneId: input.milestoneId, agentRole: input.agentRole,
          title: input.title, input: input.input, output: '', status: 'pending',
          dependencies: input.dependencies ?? []
        }
        p.tasks.push(task)
        p.updatedAt = Date.now()
        this.projects.set(id, this.cloneProject(p))
        return this.cloneTask(task)
      }
    }
    return null
  }

  updateTaskStatus(taskId: string, status: TaskStatus, output?: string): boolean {
    for (const [id, p] of this.projects) {
      const t = p.tasks.find(t => t.id === taskId)
      if (t) {
        t.status = status
        if (output !== undefined) t.output = output
        p.updatedAt = Date.now()
        this.projects.set(id, this.cloneProject(p))
        return true
      }
    }
    return false
  }

  getProgress(projectId: string): { total: number; completed: number; percent: number } {
    const p = this.projects.get(projectId)
    if (!p) return { total: 0, completed: 0, percent: 0 }
    const total = p.tasks.length
    const completed = p.tasks.filter(t => t.status === 'completed').length
    return { total, completed, percent: total > 0 ? Math.round((completed / total) * 100) : 0 }
  }

  size(): number { return this.projects.size }
  clear(): void { this.projects.clear(); this.nextId = 0 }
  snapshot(): ResearchProject[] { return this.listProjects() }

  private cloneProject(p: ResearchProject): ResearchProject {
    return {
      id: p.id, title: p.title, description: p.description, domain: p.domain, status: p.status,
      createdAt: p.createdAt, updatedAt: p.updatedAt,
      milestones: p.milestones.map(m => this.cloneMilestone(m)),
      tasks: p.tasks.map(t => this.cloneTask(t)),
      members: [...p.members]
    }
  }
  private cloneMilestone(m: ResearchMilestone): ResearchMilestone {
    return { id: m.id, projectId: m.projectId, title: m.title, description: m.description, status: m.status, deadline: m.deadline, deliverables: [...m.deliverables] }
  }
  private cloneTask(t: ProjectTask): ProjectTask {
    return { id: t.id, milestoneId: t.milestoneId, agentRole: t.agentRole, title: t.title, input: t.input, output: t.output, status: t.status, dependencies: [...t.dependencies] }
  }
}
