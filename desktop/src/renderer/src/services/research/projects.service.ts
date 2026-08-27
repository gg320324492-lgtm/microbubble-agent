// Projects Service — 真实项目数据 adapter.
//
// [类 20.191] 2026-08-27: 接入真实本地 SQLite 数据源.
// 数据源: projects / experiments / samples / desktop_knowledge 4 张表.
// 调 window.api.database.query (preload 暴露, 主进程审计通过).

import type { ResearchProject } from '../stores/research/project.store'

interface ProjectRow {
  id: string
  name: string
  field: string | null
  goal: string | null
  status: string | null
  created_at: number
  updated_at: number
}

interface ExperimentRow { count: number }
interface SampleRow { count: number }
interface KnowledgeRow { count: number }

function mapStatus(local: string | null): ResearchProject['status'] {
  switch (local) {
    case 'completed': return 'completed'
    case 'paused':
    case 'cancelled':
    case 'archived': return 'paused'
    case 'active':
    case 'in_progress': return 'active'
    default: return 'planning'
  }
}

function mapProgress(status: ResearchProject['status'], updatedAt: number, createdAt: number): number {
  // 简化: 根据 status 给个 0..1 的粗略 progress.
  // 真实进度应该从 experiments 完成的 stage 算, 但本地 projects 表没有 stage 字段.
  // 留 TODO: 接入 ELN 后用 stage 计算真实 progress.
  if (status === 'completed') return 1
  if (status === 'paused') return 0.5
  if (status === 'active') {
    // 用 updated - created 计算"项目时长内已用时间比例", 上限 0.9
    const span = Math.max(1, updatedAt - createdAt)
    const age = Date.now() / 1000 - createdAt
    return Math.min(0.9, Math.max(0.1, age / (span * 4)))
  }
  return 0.05
}

interface ProjectsAdapter {
  listProjects(): Promise<ResearchProject[]>
  getProject(id: string): Promise<ResearchProject | null>
}

class SqliteProjectsAdapter implements ProjectsAdapter {
  async listProjects(): Promise<ResearchProject[]> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用 (preload 未暴露)')
    const { rows: projectRows } = await api.database.query<ProjectRow>({
      sql: 'SELECT id, name, field, goal, status, created_at, updated_at FROM projects ORDER BY updated_at DESC'
    })
    const { rows: [expCounts] } = await api.database.query<ExperimentRow>({ sql: 'SELECT COUNT(*) AS count FROM experiments' })
    const { rows: [sampleCounts] } = await api.database.query<SampleRow>({ sql: 'SELECT COUNT(*) AS count FROM samples' })
    // [类 20.200] 2026-08-28: desktop_knowledge 表没有 deleted_at 列 (schema 确认),
    //   老 query 报 "no such column: deleted_at", 计数永远 0, project.stats.documents 永远 0.
    //   删 WHERE deleted_at IS NULL (PG web schema 残留, desktop schema 是 deleted_at_epoch).
    const { rows: [knowledgeCounts] } = await api.database.query<KnowledgeRow>({
      sql: 'SELECT COUNT(*) AS count FROM desktop_knowledge'
    })
    return projectRows.map((p) => this.mapRow(p, expCounts?.count ?? 0, sampleCounts?.count ?? 0, knowledgeCounts?.count ?? 0))
  }
  async getProject(id: string): Promise<ResearchProject | null> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows } = await api.database.query<ProjectRow>({
      sql: 'SELECT id, name, field, goal, status, created_at, updated_at FROM projects WHERE id = ?',
      params: [id]
    })
    if (rows.length === 0) return null
    const [{ count: experimentCount = 0 } = { count: 0 }] = await api.database.query<{ count: number }>({ sql: 'SELECT COUNT(*) AS count FROM experiments' })
    const [{ count: sampleCount = 0 } = { count: 0 }] = await api.database.query<{ count: number }>({ sql: 'SELECT COUNT(*) AS count FROM samples' })
    const [{ count: knowledgeCount = 0 } = { count: 0 }] = await api.database.query<{ count: number }>({ sql: 'SELECT COUNT(*) AS count FROM desktop_knowledge' })
    return this.mapRow(rows[0], experimentCount, sampleCount, knowledgeCount)
  }
  private mapRow(p: ProjectRow, experimentCount: number, sampleCount: number, knowledgeCount: number): ResearchProject {
    const status = mapStatus(p.status)
    return {
      id: p.id,
      name: p.name,
      description: p.goal ?? '',
      domain: p.field ?? '',
      progress: mapProgress(status, p.updated_at, p.created_at),
      status,
      stats: {
        // 简化: 全部项目共享全局计数. 留 TODO: 改用 WHERE project_id = ? 关联计数
        experiments: experimentCount,
        datasets: sampleCount,
        documents: knowledgeCount,
        manuscriptStatus: '撰写中' // TODO: 接入 manuscript 真实状态
      }
    }
  }
}

const realAdapter: ProjectsAdapter = new SqliteProjectsAdapter()

// 当前默认即真 adapter. 不再需要 NotWiredError, 真正零成本接入本地 SQLite.
let currentAdapter: ProjectsAdapter = realAdapter

export const projectsService = {
  setAdapter(a: ProjectsAdapter) { currentAdapter = a },
  isWired(): boolean { return true }, // 永远 wired (本地 SQLite 始终可用)
  listProjects: () => currentAdapter.listProjects(),
  getProject: (id: string) => currentAdapter.getProject(id),
}
