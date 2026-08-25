// ProjectRepository — Phase 8-M1-B
// CRUD 仅, 不含业务逻辑. 主进程内部使用 + 跨 IPC 暴露.

import type { SQLiteDatabase, SqlParams } from '../database'

export interface Project {
  id: string
  name: string
  field: string | null
  goal: string | null
  status: string | null
  createdAt: number
  updatedAt: number
}

export interface ProjectRepository {
  create(project: Omit<Project, 'createdAt' | 'updatedAt'>): Project
  findById(id: string): Project | undefined
  list(): Project[]
  update(id: string, patch: Partial<Omit<Project, 'id' | 'createdAt'>>): Project | undefined
  delete(id: string): boolean
  count(): number
}

class ProjectRepositoryImpl implements ProjectRepository {
  constructor(private readonly db: SQLiteDatabase) {}

  create(input: Omit<Project, 'createdAt' | 'updatedAt'>): Project {
    const now = Date.now()
    this.db.execute(
      `INSERT INTO projects (id, name, field, goal, status, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [input.id, input.name, input.field, input.goal, input.status, now, now]
    )
    return { ...input, createdAt: now, updatedAt: now }
  }

  findById(id: string): Project | undefined {
    const row = this.db.queryOne<Record<string, unknown>>('SELECT * FROM projects WHERE id = ?', [id])
    if (!row) return undefined
    return this.mapRow(row)
  }

  list(): Project[] {
    return this.db.query<Record<string, unknown>>('SELECT * FROM projects ORDER BY updated_at DESC').map((r) => this.mapRow(r))
  }

  update(id: string, patch: Partial<Omit<Project, 'id' | 'createdAt'>>): Project | undefined {
    const existing = this.findById(id)
    if (!existing) return undefined
    const fields: string[] = []
    const values: SqlParams = []
    if (patch.name !== undefined) { fields.push('name = ?'); values.push(patch.name) }
    if (patch.field !== undefined) { fields.push('field = ?'); values.push(patch.field) }
    if (patch.goal !== undefined) { fields.push('goal = ?'); values.push(patch.goal) }
    if (patch.status !== undefined) { fields.push('status = ?'); values.push(patch.status) }
    fields.push('updated_at = ?')
    values.push(Date.now())
    values.push(id)
    if (fields.length > 1) {
      this.db.execute(`UPDATE projects SET ${fields.join(', ')} WHERE id = ?`, values)
    }
    return this.findById(id)
  }

  delete(id: string): boolean {
    const result = this.db.execute('DELETE FROM projects WHERE id = ?', [id])
    return result.changes > 0
  }

  count(): number {
    const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM projects')
    return Number(row?.c ?? 0)
  }

  private mapRow(row: Record<string, unknown>): Project {
    return {
      id: String(row['id']),
      name: String(row['name']),
      field: row['field'] == null ? null : String(row['field']),
      goal: row['goal'] == null ? null : String(row['goal']),
      status: row['status'] == null ? null : String(row['status']),
      createdAt: Number(row['created_at']),
      updatedAt: Number(row['updated_at'])
    }
  }
}

export function createProjectRepository(db: SQLiteDatabase): ProjectRepository {
  return new ProjectRepositoryImpl(db)
}