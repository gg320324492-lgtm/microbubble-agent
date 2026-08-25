// AgentHistoryRepository — Phase 8-M1-B

import type { SQLiteDatabase, SqlParams } from '../database'

export interface AgentHistoryEntry {
  id?: number
  agent: string
  action: string
  input: string | null
  output: string | null
  timestamp: number
}

export interface AgentHistoryRepository {
  insert(entry: Omit<AgentHistoryEntry, 'id'>): AgentHistoryEntry
  findById(id: number): AgentHistoryEntry | undefined
  list(agent?: string, limit?: number): AgentHistoryEntry[]
  update(id: number, patch: Partial<Omit<AgentHistoryEntry, 'id'>>): AgentHistoryEntry | undefined
  delete(id: number): boolean
  deleteOlderThan(timestamp: number): number
  count(agent?: string): number
}

class AgentHistoryRepositoryImpl implements AgentHistoryRepository {
  constructor(private readonly db: SQLiteDatabase) {}

  insert(input: Omit<AgentHistoryEntry, 'id'>): AgentHistoryEntry {
    const result = this.db.execute(
      `INSERT INTO agent_history (agent, action, input, output, timestamp)
       VALUES (?, ?, ?, ?, ?)`,
      [input.agent, input.action, input.input, input.output, input.timestamp]
    )
    return { ...input, id: Number(result.lastInsertRowid) }
  }

  findById(id: number): AgentHistoryEntry | undefined {
    const row = this.db.queryOne<Record<string, unknown>>('SELECT * FROM agent_history WHERE id = ?', [id])
    return row ? this.mapRow(row) : undefined
  }

  list(agent?: string, limit: number = 500): AgentHistoryEntry[] {
    if (agent) {
      const params: SqlParams = [agent, limit]
      return this.db.query<Record<string, unknown>>(
        'SELECT * FROM agent_history WHERE agent = ? ORDER BY timestamp DESC LIMIT ?', params
      ).map((r) => this.mapRow(r))
    }
    const params: SqlParams = [limit]
    return this.db.query<Record<string, unknown>>(
      'SELECT * FROM agent_history ORDER BY timestamp DESC LIMIT ?', params
    ).map((r) => this.mapRow(r))
  }

  update(id: number, patch: Partial<Omit<AgentHistoryEntry, 'id'>>): AgentHistoryEntry | undefined {
    const fields: string[] = []
    const values: SqlParams = []
    if (patch.agent !== undefined) { fields.push('agent = ?'); values.push(patch.agent) }
    if (patch.action !== undefined) { fields.push('action = ?'); values.push(patch.action) }
    if (patch.input !== undefined) { fields.push('input = ?'); values.push(patch.input) }
    if (patch.output !== undefined) { fields.push('output = ?'); values.push(patch.output) }
    if (patch.timestamp !== undefined) { fields.push('timestamp = ?'); values.push(patch.timestamp) }
    if (fields.length === 0) return this.findById(id)
    values.push(id)
    this.db.execute(`UPDATE agent_history SET ${fields.join(', ')} WHERE id = ?`, values)
    return this.findById(id)
  }

  delete(id: number): boolean {
    const result = this.db.execute('DELETE FROM agent_history WHERE id = ?', [id])
    return result.changes > 0
  }

  deleteOlderThan(timestamp: number): number {
    const result = this.db.execute('DELETE FROM agent_history WHERE timestamp < ?', [timestamp])
    return result.changes
  }

  count(agent?: string): number {
    if (agent) {
      const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM agent_history WHERE agent = ?', [agent])
      return Number(row?.c ?? 0)
    }
    const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM agent_history')
    return Number(row?.c ?? 0)
  }

  private mapRow(row: Record<string, unknown>): AgentHistoryEntry {
    return {
      id: row['id'] == null ? undefined : Number(row['id']),
      agent: String(row['agent']),
      action: String(row['action']),
      input: row['input'] == null ? null : String(row['input']),
      output: row['output'] == null ? null : String(row['output']),
      timestamp: Number(row['timestamp'])
    }
  }
}

export function createAgentHistoryRepository(db: SQLiteDatabase): AgentHistoryRepository {
  return new AgentHistoryRepositoryImpl(db)
}