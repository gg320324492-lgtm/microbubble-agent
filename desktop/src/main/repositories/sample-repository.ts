// SampleRepository — Phase 8-M1-C
// 实验样本级数据. 一个 experiment 包含多个 sample, 每个 sample 含若干 measurement.

import type { SQLiteDatabase, SqlParams } from '../database'

export interface Sample {
  id: string
  experimentId: string
  batch: string | null
  replicate: number | null
  conditionLabel: string | null
  sampledAt: number
  operator: string | null
  notes: string | null
  metadata: Record<string, unknown> | null
}

export interface SampleRepository {
  create(sample: Omit<Sample, 'sampledAt'> & { sampledAt?: number }): Sample
  findById(id: string): Sample | undefined
  listByExperiment(experimentId: string): Sample[]
  update(id: string, patch: Partial<Omit<Sample, 'id' | 'experimentId'>>): Sample | undefined
  delete(id: string): boolean
  countByExperiment(experimentId: string): number
}

class SampleRepositoryImpl implements SampleRepository {
  constructor(private readonly db: SQLiteDatabase) {}

  create(input: Omit<Sample, 'sampledAt'> & { sampledAt?: number }): Sample {
    const sampledAt = input.sampledAt ?? Date.now()
    const metadataJson = input.metadata ? JSON.stringify(input.metadata) : null
    this.db.execute(
      `INSERT INTO samples (id, experiment_id, batch, replicate, condition_label, sampled_at, operator, notes, metadata)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [input.id, input.experimentId, input.batch, input.replicate, input.conditionLabel, sampledAt, input.operator, input.notes, metadataJson]
    )
    return { ...input, sampledAt, metadata: input.metadata ?? null }
  }

  findById(id: string): Sample | undefined {
    const row = this.db.queryOne<Record<string, unknown>>('SELECT * FROM samples WHERE id = ?', [id])
    return row ? this.mapRow(row) : undefined
  }

  listByExperiment(experimentId: string): Sample[] {
    return this.db.query<Record<string, unknown>>(
      'SELECT * FROM samples WHERE experiment_id = ? ORDER BY sampled_at DESC', [experimentId]
    ).map((r) => this.mapRow(r))
  }

  update(id: string, patch: Partial<Omit<Sample, 'id' | 'experimentId'>>): Sample | undefined {
    const fields: string[] = []
    const params: SqlParams = []
    if (patch.batch !== undefined) { fields.push('batch = ?'); params.push(patch.batch) }
    if (patch.replicate !== undefined) { fields.push('replicate = ?'); params.push(patch.replicate) }
    if (patch.conditionLabel !== undefined) { fields.push('condition_label = ?'); params.push(patch.conditionLabel) }
    if (patch.sampledAt !== undefined) { fields.push('sampled_at = ?'); params.push(patch.sampledAt) }
    if (patch.operator !== undefined) { fields.push('operator = ?'); params.push(patch.operator) }
    if (patch.notes !== undefined) { fields.push('notes = ?'); params.push(patch.notes) }
    if (patch.metadata !== undefined) {
      fields.push('metadata = ?')
      params.push(patch.metadata ? JSON.stringify(patch.metadata) : null)
    }
    if (fields.length === 0) return this.findById(id)
    params.push(id)
    this.db.execute(`UPDATE samples SET ${fields.join(', ')} WHERE id = ?`, params)
    return this.findById(id)
  }

  delete(id: string): boolean {
    const result = this.db.execute('DELETE FROM samples WHERE id = ?', [id])
    return result.changes > 0
  }

  countByExperiment(experimentId: string): number {
    const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM samples WHERE experiment_id = ?', [experimentId])
    return Number(row?.c ?? 0)
  }

  private mapRow(row: Record<string, unknown>): Sample {
    const metadataRaw = row['metadata']
    let metadata: Record<string, unknown> | null = null
    if (metadataRaw && typeof metadataRaw === 'string') {
      try { metadata = JSON.parse(metadataRaw) as Record<string, unknown> } catch { metadata = null }
    }
    return {
      id: String(row['id']),
      experimentId: String(row['experiment_id']),
      batch: row['batch'] == null ? null : String(row['batch']),
      replicate: row['replicate'] == null ? null : Number(row['replicate']),
      conditionLabel: row['condition_label'] == null ? null : String(row['condition_label']),
      sampledAt: Number(row['sampled_at']),
      operator: row['operator'] == null ? null : String(row['operator']),
      notes: row['notes'] == null ? null : String(row['notes']),
      metadata
    }
  }
}

export function createSampleRepository(db: SQLiteDatabase): SampleRepository {
  return new SampleRepositoryImpl(db)
}