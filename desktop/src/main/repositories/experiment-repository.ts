// ExperimentRepository — Phase 8-M1-B

import type { SQLiteDatabase, SqlParams } from '../database'

export interface Experiment {
  id: string
  projectId: string
  name: string
  parameters: string | null
  status: string | null
  createdAt: number
}

export interface ExperimentRepository {
  create(exp: Omit<Experiment, 'createdAt'>): Experiment
  findById(id: string): Experiment | undefined
  list(): Experiment[]
  listByProject(projectId: string): Experiment[]
  update(id: string, patch: Partial<Omit<Experiment, 'id' | 'projectId' | 'createdAt'>>): Experiment | undefined
  delete(id: string): boolean
  count(): number
}

class ExperimentRepositoryImpl implements ExperimentRepository {
  constructor(private readonly db: SQLiteDatabase) {}

  create(input: Omit<Experiment, 'createdAt'>): Experiment {
    const now = Date.now()
    this.db.execute(
      `INSERT INTO experiments (id, project_id, name, parameters, status, created_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [input.id, input.projectId, input.name, input.parameters, input.status, now]
    )
    return { ...input, createdAt: now }
  }

  findById(id: string): Experiment | undefined {
    const row = this.db.queryOne<Record<string, unknown>>('SELECT * FROM experiments WHERE id = ?', [id])
    return row ? this.mapRow(row) : undefined
  }

  list(): Experiment[] {
    return this.db.query<Record<string, unknown>>('SELECT * FROM experiments ORDER BY created_at DESC').map((r) => this.mapRow(r))
  }

  listByProject(projectId: string): Experiment[] {
    return this.db.query<Record<string, unknown>>(
      'SELECT * FROM experiments WHERE project_id = ? ORDER BY created_at DESC', [projectId]
    ).map((r) => this.mapRow(r))
  }

  update(id: string, patch: Partial<Omit<Experiment, 'id' | 'projectId' | 'createdAt'>>): Experiment | undefined {
    const fields: string[] = []
    const values: SqlParams = []
    if (patch.name !== undefined) { fields.push('name = ?'); values.push(patch.name) }
    if (patch.parameters !== undefined) { fields.push('parameters = ?'); values.push(patch.parameters) }
    if (patch.status !== undefined) { fields.push('status = ?'); values.push(patch.status) }
    if (fields.length === 0) return this.findById(id)
    values.push(id)
    this.db.execute(`UPDATE experiments SET ${fields.join(', ')} WHERE id = ?`, values)
    return this.findById(id)
  }

  delete(id: string): boolean {
    const result = this.db.execute('DELETE FROM experiments WHERE id = ?', [id])
    return result.changes > 0
  }

  count(): number {
    const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM experiments')
    return Number(row?.c ?? 0)
  }

  private mapRow(row: Record<string, unknown>): Experiment {
    return {
      id: String(row['id']),
      projectId: String(row['project_id']),
      name: String(row['name']),
      parameters: row['parameters'] == null ? null : String(row['parameters']),
      status: row['status'] == null ? null : String(row['status']),
      createdAt: Number(row['created_at'])
    }
  }
}

export function createExperimentRepository(db: SQLiteDatabase): ExperimentRepository {
  return new ExperimentRepositoryImpl(db)
}