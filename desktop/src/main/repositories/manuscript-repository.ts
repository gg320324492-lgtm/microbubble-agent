// ManuscriptRepository — Phase 8-M1-B

import type { SQLiteDatabase, SqlParams } from '../database'

export interface Manuscript {
  id: string
  projectId: string
  section: string | null
  content: string | null
  updatedAt: number
}

export interface ManuscriptRepository {
  create(m: Omit<Manuscript, 'updatedAt'>): Manuscript
  findById(id: string): Manuscript | undefined
  list(): Manuscript[]
  listByProject(projectId: string): Manuscript[]
  update(id: string, patch: Partial<Omit<Manuscript, 'id'>>): Manuscript | undefined
  delete(id: string): boolean
  count(): number
}

class ManuscriptRepositoryImpl implements ManuscriptRepository {
  constructor(private readonly db: SQLiteDatabase) {}

  create(input: Omit<Manuscript, 'updatedAt'>): Manuscript {
    const now = Date.now()
    this.db.execute(
      `INSERT INTO manuscripts (id, project_id, section, content, updated_at)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
         section = excludedCLUDed.section,
         content = excludedCLUDed.content,
         updated_at = excludedCLUDed.updated_at`,
      [input.id, input.projectId, input.section, input.content, now]
    )
    return { ...input, updatedAt: now }
  }

  findById(id: string): Manuscript | undefined {
    const row = this.db.queryOne<Record<string, unknown>>('SELECT * FROM manuscripts WHERE id = ?', [id])
    return row ? this.mapRow(row) : undefined
  }

  list(): Manuscript[] {
    return this.db.query<Record<string, unknown>>('SELECT * FROM manuscripts ORDER BY updated_at DESC').map((r) => this.mapRow(r))
  }

  listByProject(projectId: string): Manuscript[] {
    return this.db.query<Record<string, unknown>>(
      'SELECT * FROM manuscripts WHERE project_id = ? ORDER BY updated_at DESC', [projectId]
    ).map((r) => this.mapRow(r))
  }

  update(id: string, patch: Partial<Omit<Manuscript, 'id'>>): Manuscript | undefined {
    const fields: string[] = []
    const values: SqlParams = []
    if (patch.projectId !== undefined) { fields.push('project_id = ?'); values.push(patch.projectId) }
    if (patch.section !== undefined) { fields.push('section = ?'); values.push(patch.section) }
    if (patch.content !== undefined) { fields.push('content = ?'); values.push(patch.content) }
    fields.push('updated_at = ?')
    values.push(Date.now())
    values.push(id)
    if (fields.length > 1) {
      this.db.execute(`UPDATE manuscripts SET ${fields.join(', ')} WHERE id = ?`, values)
    }
    return this.findById(id)
  }

  delete(id: string): boolean {
    const result = this.db.execute('DELETE FROM manuscripts WHERE id = ?', [id])
    return result.changes > 0
  }

  count(): number {
    const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM manuscripts')
    return Number(row?.c ?? 0)
  }

  private mapRow(row: Record<string, unknown>): Manuscript {
    return {
      id: String(row['id']),
      projectId: String(row['project_id']),
      section: row['section'] == null ? null : String(row['section']),
      content: row['content'] == null ? null : String(row['content']),
      updatedAt: Number(row['updated_at'])
    }
  }
}

export function createManuscriptRepository(db: SQLiteDatabase): ManuscriptRepository {
  return new ManuscriptRepositoryImpl(db)
}